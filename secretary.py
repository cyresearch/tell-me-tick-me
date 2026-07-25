"""Amy — tellmetickme 的 AI 秘书: 聊出待办、排轻重缓急、deadline 撞车时帮忙分诊。

大脑走 brain.py 三通道 (claude-code / api / ollama, 见 config/llm.json)。
claude-code 通道功能最全: Amy 有用户资料库的只读权限(Read/Glob/Grep)和
唯一可写的记忆文件; api/ollama 通道无工具, Amy 只看得到消息里注入的上下文。

协议: Amy 建议增/挪/删待办时输出 ◆todo / ◆todo-move / ◆todo-remove 块,
这里解析成结构化建议返回页面, 用户点确认才落盘 — AI 永远不直接动 todo。
"""
import datetime
import json
import os
import pathlib
import subprocess
import time

import brain

ROOT = pathlib.Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
STATE_F = RUNTIME / "secretary_state.json"
HOME = RUNTIME / "secretary_home"          # claude-code 会话隔离用的专属 cwd
PERSONA_F = ROOT / "config/secretary.md"
PERSONA_EXAMPLE = ROOT / "config/secretary.example.md"
MEMORY_F = ROOT / "config/secretary_memory.md"
HISTORY_F = RUNTIME / "chat_history.json"
HIST_CAP = 200

MODEL = os.environ.get("TMTM_CLAUDE_MODEL", os.environ.get("DESK_SECRETARY_MODEL", "opus"))
# 权限模型(仅 claude-code 通道): 全库只读 + 仅记忆文件可写; todo 修改走 ◆todo 确认流
_MEM_SPEC = "//" + str(MEMORY_F).lstrip("/")
TOOLS = ("Read", "Glob", "Grep", f"Write({_MEM_SPEC})", f"Edit({_MEM_SPEC})")
WEEKDAYS = "一二三四五六日"


def _state():
    try:
        return json.loads(STATE_F.read_text())
    except Exception:
        return {}


def _save_state(st):
    STATE_F.parent.mkdir(parents=True, exist_ok=True)
    STATE_F.write_text(json.dumps(st))


def _rolled_over(last_ts):
    """跨天且闲置超 4 小时 → 翻篇开新会话 (半夜聊到一半不砍断)。"""
    if not last_ts:
        return False
    gap = time.time() - last_ts
    same_day = datetime.date.fromtimestamp(last_ts) == datetime.date.today()
    return gap > 4 * 3600 and not same_day


def _persona():
    for f in (PERSONA_F, PERSONA_EXAMPLE):
        try:
            return f.read_text(encoding="utf-8")
        except Exception:
            continue
    return "你是 Amy, 一个干练简洁的中文工作秘书, 帮用户整理待办、排轻重缓急。"


def history():
    try:
        return json.loads(HISTORY_F.read_text())
    except Exception:
        return []


def _append_history(entry):
    h = history()
    h.append(entry)
    HISTORY_F.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_F.write_text(json.dumps(h[-HIST_CAP:], ensure_ascii=False, indent=1))


BLOCK_TYPES = {"◆todo": "add", "◆todo-move": "move", "◆todo-remove": "remove"}


def _after_colon(s):
    return s.split(":", 1)[-1].split("：", 1)[-1].strip()


def parse_reply(raw):
    """拆出可见回复与建议块(add / move / remove 三种), 逐行状态机。"""
    reply_lines, collected, cur = [], [], None
    for ln in raw.splitlines():
        s = ln.strip()
        if s in BLOCK_TYPES:
            cur = {"type": BLOCK_TYPES[s], "section": "", "from": "", "to": "",
                   "orig": "", "lines": []}
            collected.append(cur)
            continue
        if cur is None:
            reply_lines.append(ln)
            continue
        if not cur["lines"] and s.startswith(("分区:", "分区：")):
            cur["section"] = _after_colon(s)
        elif not cur["lines"] and s.startswith(("从:", "从：")):
            cur["from"] = _after_colon(s)
        elif not cur["lines"] and s.startswith(("到:", "到：")):
            cur["to"] = _after_colon(s)
        elif not cur["lines"] and s.startswith(("原文:", "原文：")):
            cur["orig"] = _after_colon(s)
        elif s.startswith("- ") and not cur["lines"]:
            cur["lines"].append(s)
        elif (s.startswith("- ") or ln.startswith(("  ", "\t"))) and cur["lines"]:
            cur["lines"].append(ln.rstrip())
        elif not s:
            continue                        # 块内空行容忍
        else:                               # 块后接续的普通文字, 归回复
            cur = None
            reply_lines.append(ln)
    out = []
    for c in collected:
        block = "\n".join(c["lines"])
        if c["type"] == "add" and block:
            out.append({"type": "add", "section": c["section"] or "本周", "block": block})
        elif c["type"] == "move" and c["from"] and c["to"] and c["orig"]:
            out.append({"type": "move", "from": c["from"], "to": c["to"],
                        "orig": c["orig"], "block": block})
        elif c["type"] == "remove" and (c["section"] or c["from"]) and c["orig"]:
            out.append({"type": "remove", "section": c["section"] or c["from"],
                        "orig": c["orig"]})
    return "\n".join(reply_lines).strip(), out


def _think_claude_code(full, persona):
    binpath = brain.claude_bin()
    if not binpath:
        raise RuntimeError("找不到 claude 命令 (装 Claude Code, 或在设置里换一条通道)")
    HOME.mkdir(parents=True, exist_ok=True)
    st = _state()
    if st.get("started") and _rolled_over(st.get("last_ts")):
        st["started"] = False
    cmd = [binpath, "-p", full, "--model", MODEL,
           "--append-system-prompt", persona,
           "--allowedTools", *TOOLS]
    if st.get("started"):
        cmd.append("--continue")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240, cwd=str(HOME))
        raw = r.stdout.strip()
        if not raw and st.get("started"):   # 会话丢了就重开一条
            cmd.remove("--continue")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=240, cwd=str(HOME))
            raw = r.stdout.strip()
    except subprocess.TimeoutExpired:
        # 千万别把原始异常吐给界面: 它带着整条命令和 prompt 全文
        raise RuntimeError("Amy 想得太久, 这一轮超时了(4 分钟)。她可能正在翻比较大的资料; "
                           "再发一次试试, 或把问题拆小一点。") from None
    if not raw:
        raise RuntimeError(f"Amy 没回话 (claude 退出码 {r.returncode}: {r.stderr.strip()[:200]})")
    st["started"] = True
    st["last_ts"] = time.time()
    _save_state(st)
    return raw


def chat(message, todo_text, done_lines):
    """一轮对话。返回 (回复, 建议列表) 或抛 RuntimeError。"""
    prov = brain.provider()
    if not prov:
        raise RuntimeError("UNCONFIGURED")   # 前端识别这个哨兵, 弹设置向导

    d = datetime.datetime.now()
    ctx = [f"【今天】{d:%Y-%m-%d} 周{WEEKDAYS[d.weekday()]} {d:%H:%M}",
           "【todo.md 现状】\n" + todo_text.strip()]
    if done_lines:
        ctx.append("【今日已完成】\n" + "\n".join(done_lines))
    try:                                      # Amy 自己的记忆, 每轮随身带
        mem = MEMORY_F.read_text(encoding="utf-8").strip()
        if mem:
            ctx.append("【你的记忆(secretary_memory.md)】\n" + mem)
    except FileNotFoundError:
        pass
    ctx.append("【用户说】\n" + message.strip())
    full = "\n\n".join(ctx)
    persona = _persona()

    stamp = f"{d:%Y-%m-%d %H:%M}"
    _append_history({"t": stamp, "role": "user", "text": message})   # 先记档, 失败轮次也留痕

    if prov == "claude-code":
        raw = _think_claude_code(full, persona)
    elif prov == "api":
        raw = brain.think_api(full, persona, "amy")
    elif prov == "ollama":
        raw = brain.think_ollama(full, persona, "amy")
    else:
        raise RuntimeError(f"未知通道 {prov}")
    if not raw:
        raise RuntimeError("Amy 没回话, 再试一次?")

    reply, suggestions = parse_reply(raw)
    _append_history({"t": stamp, "role": "secretary", "text": reply,
                     "suggestions": suggestions})
    return reply, suggestions
