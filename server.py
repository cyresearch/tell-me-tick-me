#!/usr/bin/env python3
"""tellmetickme: 读写 todo.md 的本地小服务 (纯标准库, 零依赖)。

设计铁律:
- todo.md 是唯一真相源, 手动编辑永远优先 (每次操作前重读文件)
- 写回时只做"目标行块删除 + 更新日期行替换", 绝不重新序列化整个文件,
  用户的手写格式(加粗/内链/缩进/备注)一个字节都不动
- 勾掉的条目按 CLAUDE.md 规矩归档进 daily/YYYY-MM/YYYY-MM-DD.md
- 每天第一次写操作前自动备份 todo.md 到 runtime/backups/

配置(环境变量, 都有默认值):
  DESK_TODO_FILE   todo 文件路径   默认 data/todo.md (首跑自动生成示例)
  DESK_DAILY_DIR   daily 根目录    默认 data/daily
  DESK_PORT        端口           默认 8765
  DESK_BIND        绑定地址        默认 127.0.0.1 (手机局域网访问改 0.0.0.0)
"""
import datetime
import json
import os
import pathlib
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import brain
import secretary

ROOT = pathlib.Path(__file__).resolve().parent
TODO = pathlib.Path(os.environ.get("DESK_TODO_FILE", ROOT / "data/todo.md"))
DAILY = pathlib.Path(os.environ.get("DESK_DAILY_DIR", ROOT / "data/daily"))
PORT = int(os.environ.get("DESK_PORT", "8765"))
BIND = os.environ.get("DESK_BIND", "127.0.0.1")
BACKUPS = ROOT / "runtime/backups"

SAMPLE_TODO = """# 待办事项

> 更新日期：{today}
> 这个文件就是一切的真相源: 纯 markdown, 直接手改也完全没问题。

---

## 今日

- [ ] 跟 Amy 打个招呼, 告诉她你最近在忙什么
- [ ] 勾掉这一条, 看看庆祝动画

## 本周

- [ ] 把自己的待办搬进来 (直接编辑这个文件, 或在界面上双击/右键/新增)

## 本月

## 长期

- [ ] 在设置里接入你自己的 LLM, 让 Amy 上岗
"""


def ensure_todo():
    """首跑没有 todo 文件时生成一份示例, 新用户开箱即见。"""
    if not TODO.exists():
        TODO.parent.mkdir(parents=True, exist_ok=True)
        TODO.write_text(SAMPLE_TODO.format(today=f"{datetime.datetime.now():%Y-%m-%d}"),
                        encoding="utf-8")

LOCK = threading.Lock()          # 所有读改写走同一把锁, 防并发写坏文件
UNDO_STACK = []                  # [(todo_snapshot, daily_path, daily_appended_text)]


def now():
    return datetime.datetime.now()


# ---------- 解析 (只为展示; 写回不经过它) ----------

def parse(text):
    """把 todo.md 拆成分区列表。每个顶层 `- [ ]` 行连同它的缩进后续行算一个条目块。"""
    sections, cur = [], None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("## "):
            cur = {"title": ln[3:].strip(), "items": [], "notes": []}
            sections.append(cur)
            i += 1
            continue
        if cur is not None and ln.startswith("- "):
            block = [ln]
            j = i + 1
            while j < len(lines) and (lines[j].startswith(("  ", "\t")) and lines[j].strip()):
                block.append(lines[j])
                j += 1
            entry = {"text": ln, "sub": block[1:], "line": i}
            if ln.startswith("- [ ]"):
                cur["items"].append(entry)
            else:                      # 删除线/无 checkbox 的备注行
                cur["notes"].append(entry)
            i = j
            continue
        if cur is not None and ln.strip() and not ln.startswith(("#", "---")):
            cur["notes"].append({"text": ln, "sub": [], "line": i})
        i += 1
    return sections


def read_todo():
    text = TODO.read_text(encoding="utf-8")
    return text, TODO.stat().st_mtime


# ---------- 写操作 ----------

def backup_once_today():
    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / f"todo-{now():%Y%m%d}.md"
    if not dst.exists():
        shutil.copy2(TODO, dst)


def bump_update_date(lines):
    """头部 `> 更新日期：...` 行改为今天; 找不到就不动。"""
    for k, ln in enumerate(lines[:8]):
        if ln.startswith("> 更新日期"):
            lines[k] = f"> 更新日期：{now():%Y-%m-%d}"
            return


def daily_path_today():
    d = now()
    p = DAILY / f"{d:%Y-%m}" / f"{d:%Y-%m-%d}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


DONE_HEADER = "## ✅ 今日完成（tellmetickme）"
DONE_HEADER_OLD = "## ✅ 今日完成（desk-todo）"      # 更名前写下的归档, 读取时兼容


def _done_header_in(text):
    for h in (DONE_HEADER, DONE_HEADER_OLD):
        if h in text:
            return h
    return None


def parse_done_today():
    """读今天 daily 的完成小节, 供页面把已完成项划线展示一整天。"""
    p = daily_path_today()
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    hdr = _done_header_in(text)
    if hdr is None:
        return []
    seg = text.partition(hdr)[2]
    nxt = seg.find("\n## ")
    if nxt != -1:
        seg = seg[:nxt]
    out, cur = [], None
    for ln in seg.splitlines():
        if ln.startswith("- ") and "】" in ln:
            stamp, rest = "", ln[2:]
            if len(rest) > 5 and rest[:5].count(":") == 1 and rest[5:6] == " ":
                stamp, rest = rest[:5], rest[6:]
            if rest.startswith("【"):
                section, _, main = rest[1:].partition("】")
                cur = {"time": stamp, "section": section, "text": main, "sub": []}
                out.append(cur)
        elif cur is not None and ln.startswith(("  ", "\t")) and ln.strip():
            cur["sub"].append(ln.strip())
    return out


def append_daily(section_title, block_lines):
    """完成条目写进当天 daily。返回 (daily 路径, 实际追加的文本) 供 undo。"""
    p = daily_path_today()
    stamp = f"{now():%H:%M}"
    main = block_lines[0]
    for pre in ("- [ ] ", "- "):
        if main.startswith(pre):
            main = main[len(pre):]
            break
    entry = [f"- {stamp} 【{section_title}】{main}"] + [f"  {s.strip()}" for s in block_lines[1:]]
    text = "\n".join(entry) + "\n"

    if not p.exists():
        content = f"# {now():%Y-%m-%d}\n\n{DONE_HEADER}\n\n{text}"
        p.write_text(content, encoding="utf-8")
        return p, text
    cur = p.read_text(encoding="utf-8")
    hdr = _done_header_in(cur)
    if hdr:
        head, _, tail = cur.partition(hdr)
        nl = tail.find("\n\n", 1)
        if nl == -1:                       # 小节在文件尾
            new = cur.rstrip("\n") + "\n" + text
        else:
            insert_at = len(head) + len(hdr) + nl + 2
            new = cur[:insert_at] + text + cur[insert_at:]
    else:
        new = cur.rstrip("\n") + f"\n\n{DONE_HEADER}\n\n{text}"
    p.write_text(new, encoding="utf-8")
    return p, text


def locate_block(lines, section_title, main_line):
    """在指定分区里按主行全文精确匹配, 返回 (块首行号, 块尾行号+1) 或 None。"""
    in_section = False
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            in_section = ln[3:].strip() == section_title
            continue
        if in_section and ln == main_line:
            j = i + 1
            while j < len(lines) and lines[j].startswith(("  ", "\t")) and lines[j].strip():
                j += 1
            return i, j
    return None


NOT_FOUND = {"ok": False, "error": "条目没找到 (文件可能刚被编辑过), 请刷新"}


def write_back(lines, snapshot, daily_info=None):
    """统一收尾: 更新日期 → 写回 → 压 undo 栈。"""
    bump_update_date(lines)
    TODO.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dp, appended = daily_info if daily_info else (None, "")
    UNDO_STACK.append((snapshot, dp, appended))
    if len(UNDO_STACK) > 20:
        UNDO_STACK.pop(0)


def clean_block(raw, auto_checkbox=True):
    """把编辑框/新增框的多行文本整理成行块; 首行没写 '- ' 前缀就自动补 '- [ ] '。"""
    out = [l.rstrip() for l in raw.splitlines() if l.strip()]
    if out and auto_checkbox and not out[0].lstrip().startswith("- "):
        out[0] = "- [ ] " + out[0].strip()
    return out


def complete_item(section_title, main_line, client_mtime):
    """勾选完成: 定位条目块 → 删块 → 写回 → 归档 daily。"""
    with LOCK:
        text, mtime = read_todo()
        lines = text.splitlines()
        loc = locate_block(lines, section_title, main_line)
        if loc is None:
            return NOT_FOUND, 409
        block = lines[loc[0]:loc[1]]
        backup_once_today()
        del lines[loc[0]:loc[1]]
        dp, appended = append_daily(section_title, block)
        write_back(lines, text, (dp, appended))
        return {"ok": True, "archived_to": str(dp)}, 200


def replace_item(section_title, main_line, new_raw):
    """双击编辑保存: 整块替换(主行+子行), 位置不变。"""
    new_lines = clean_block(new_raw)
    if not new_lines:
        return {"ok": False, "error": "内容是空的; 想删掉这条请用右键菜单的「删除」"}, 400
    with LOCK:
        text, _ = read_todo()
        lines = text.splitlines()
        loc = locate_block(lines, section_title, main_line)
        if loc is None:
            return NOT_FOUND, 409
        backup_once_today()
        lines[loc[0]:loc[1]] = new_lines
        write_back(lines, text)
        return {"ok": True}, 200


def delete_item(section_title, main_line):
    """右键删除: 删块但不归档 daily (写错的/不要了的条目)。"""
    with LOCK:
        text, _ = read_todo()
        lines = text.splitlines()
        loc = locate_block(lines, section_title, main_line)
        if loc is None:
            return NOT_FOUND, 409
        backup_once_today()
        del lines[loc[0]:loc[1]]
        write_back(lines, text)
        return {"ok": True}, 200


def move_item(from_section, main_line, to_section, new_raw=""):
    """挪动: 锁内原子地从 A 区删块 + 插进 B 区尾部; 未给新文本则原块原样搬。"""
    with LOCK:
        text, _ = read_todo()
        lines = text.splitlines()
        loc = locate_block(lines, from_section, main_line)
        if loc is None:
            return NOT_FOUND, 409
        block = lines[loc[0]:loc[1]]
        new_lines = clean_block(new_raw) if new_raw.strip() else block
        backup_once_today()
        del lines[loc[0]:loc[1]]
        sec_start = None
        for i, ln in enumerate(lines):
            if ln.startswith("## ") and ln[3:].strip() == to_section:
                sec_start = i
                break
        if sec_start is None:
            return {"ok": False, "error": "目标分区没找到, 请刷新"}, 409
        last = sec_start
        j = sec_start + 1
        while j < len(lines) and not lines[j].startswith("## "):
            if lines[j].strip() and lines[j].strip() != "---":
                last = j
            j += 1
        lines[last + 1:last + 1] = new_lines
        write_back(lines, text)
        return {"ok": True}, 200


def rename_section(old, new):
    """改分区标题 (## 行的行级替换)。"""
    new = new.strip().lstrip("#").strip()
    if not new:
        return {"ok": False, "error": "组名是空的"}, 400
    with LOCK:
        text, _ = read_todo()
        lines = text.splitlines()
        if any(l.startswith("## ") and l[3:].strip() == new for l in lines):
            return {"ok": False, "error": "已有同名分区"}, 400
        for i, ln in enumerate(lines):
            if ln.startswith("## ") and ln[3:].strip() == old:
                backup_once_today()
                lines[i] = "## " + new
                write_back(lines, text)
                return {"ok": True}, 200
        return {"ok": False, "error": "分区没找到, 请刷新"}, 409


def add_item(section_title, raw):
    """新增: 插到该分区最后一条内容之后。"""
    new_lines = clean_block(raw)
    if not new_lines:
        return {"ok": False, "error": "内容是空的"}, 400
    with LOCK:
        text, _ = read_todo()
        lines = text.splitlines()
        sec_start = None
        for i, ln in enumerate(lines):
            if ln.startswith("## ") and ln[3:].strip() == section_title:
                sec_start = i
                break
        if sec_start is None:
            return {"ok": False, "error": "分区没找到, 请刷新"}, 409
        last = sec_start
        j = sec_start + 1
        while j < len(lines) and not lines[j].startswith("## "):
            if lines[j].strip() and lines[j].strip() != "---":
                last = j
            j += 1
        backup_once_today()
        lines[last + 1:last + 1] = new_lines
        write_back(lines, text)
        return {"ok": True}, 200


def undo_last():
    with LOCK:
        if not UNDO_STACK:
            return {"ok": False, "error": "没有可撤销的操作"}, 400
        snapshot, dp, appended = UNDO_STACK.pop()
        TODO.write_text(snapshot, encoding="utf-8")
        if dp is not None and appended:      # 完成类操作才有 daily 记录要撤
            try:
                cur = dp.read_text(encoding="utf-8")
                if appended in cur:
                    dp.write_text(cur.replace(appended, "", 1), encoding="utf-8")
            except FileNotFoundError:
                pass
        return {"ok": True}, 200


# ---------- HTTP ----------

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        print(f"{now():%H:%M:%S} {self.address_string()} {fmt % a}", flush=True)

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = (ROOT / "static/index.html").read_bytes()
            self._send(200, page, "text/html; charset=utf-8")
        elif self.path == "/api/todos":
            text, mtime = read_todo()
            self._send(200, {"mtime": mtime, "sections": parse(text),
                             "done_today": parse_done_today(),
                             "today": f"{now():%Y-%m-%d}", "undoable": bool(UNDO_STACK)})
        elif self.path == "/api/chat/history":
            self._send(200, {"messages": secretary.history()[-60:]})
        elif self.path == "/api/settings":
            conf = brain.load_conf()
            self._send(200, {"provider": brain.provider(), "model": conf.get("model", ""),
                             "ollama_url": conf.get("ollama_url", ""),
                             "has_key": bool(conf.get("api_key")), "detect": brain.detect()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        if self.path == "/api/done":
            body, code = complete_item(req.get("section", ""), req.get("text", ""),
                                       req.get("mtime"))
            self._send(code, body)
        elif self.path == "/api/replace":
            body, code = replace_item(req.get("section", ""), req.get("text", ""),
                                      req.get("new", ""))
            self._send(code, body)
        elif self.path == "/api/delete":
            body, code = delete_item(req.get("section", ""), req.get("text", ""))
            self._send(code, body)
        elif self.path == "/api/add":
            body, code = add_item(req.get("section", ""), req.get("block", ""))
            self._send(code, body)
        elif self.path == "/api/rename":
            body, code = rename_section(req.get("old", ""), req.get("new", ""))
            self._send(code, body)
        elif self.path == "/api/move":
            body, code = move_item(req.get("from", ""), req.get("text", ""),
                                   req.get("to", ""), req.get("new", ""))
            self._send(code, body)
        elif self.path == "/api/undo":
            body, code = undo_last()
            self._send(code, body)
        elif self.path == "/api/chat":
            msg = (req.get("message") or "").strip()
            if not msg:
                self._send(400, {"ok": False, "error": "消息是空的"})
                return
            try:
                text, _ = read_todo()
                done = [f"- {d['time']} 【{d['section']}】{d['text']}"
                        for d in parse_done_today()]
                reply, sugg = secretary.chat(msg, text, done)
                self._send(200, {"ok": True, "reply": reply, "suggestions": sugg})
            except Exception as e:
                if str(e) == "UNCONFIGURED":
                    self._send(200, {"ok": False, "unconfigured": True,
                                     "error": "还没接入 LLM"})
                else:
                    self._send(500, {"ok": False, "error": str(e)})
        elif self.path == "/api/settings":
            prov = (req.get("provider") or "").strip()
            if prov not in ("claude-code", "api", "ollama", ""):
                self._send(400, {"ok": False, "error": "未知通道"})
                return
            conf = brain.load_conf()
            conf["provider"] = prov
            for k in ("model", "ollama_url"):
                if req.get(k) is not None:
                    conf[k] = req[k].strip()
            if req.get("api_key"):
                conf["api_key"] = req["api_key"].strip()
            brain.save_conf(conf)
            self._send(200, {"ok": True, "provider": prov})
        else:
            self._send(404, {"error": "not found"})


if __name__ == "__main__":
    ensure_todo()
    print(f"tellmetickme · todo={TODO} · daily={DAILY} · http://{BIND}:{PORT}", flush=True)
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
