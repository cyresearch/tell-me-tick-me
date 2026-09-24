#!/usr/bin/env python3
"""番茄钟: 「开工」计时,「收工」记录, 到点由 Discord 值班员发一条消息。

口令(与「确认/取消」同级的固定入口, 不经过 LLM, 消息以口令开头才算):
  开工 [分钟数] [任务]   默认 25 分钟。例:「开工」「开工 40」「开工 写引言」「开工 40 写引言」
  收工 [做了什么]        提前收也行; 汇报原样归档进当天 daily

设计约定(2026-09-24 与用户商定):
  - 没有可见倒计时; 到点只发一条消息, 不催第二遍, 也没有休息结束提醒
  - Amy 不主动指定任务内容; 用户想要建议时自己开口问(走正常聊天)
  - 每颗番茄自动记一行进当天 daily 的 🍅 小节; 收工汇报作缩进行跟在番茄行后面
  - 中断/提前收工照记, 不区分完整与否; 到点没收工也不算失败, 自动行照样在
  - 新「开工」时上一颗还没收尾的先按实际用时记档再开新的, 不丢记录
"""
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import server as srv

ROOT = pathlib.Path(__file__).resolve().parents[1]
FOCUS_F = ROOT / "runtime/focus.json"
FOCUS_HEADER = "## 🍅 番茄专注（tellmetickme）"
DEFAULT_MIN = 25
MAX_MIN = 180

_START_RE = re.compile(r"^(?:开工|開工|开番茄|開番茄)\s*(\d{1,3})?\s*(?:分钟|分鐘|分)?\s*(.*)$",
                       re.S)
_STOP_RE = re.compile(r"^(?:收工|收番茄)\s*[:：,，、]?\s*(.*)$", re.S)
# 英文别名(开源用户): pomo [min] [task] / pomo done [report]
_START_EN_RE = re.compile(r"^pomo(?!\w)\s*(\d{1,3})?\s*(?:min(?:ute)?s?)?\s*(.*)$",
                          re.I | re.S)
_STOP_EN_RE = re.compile(r"^pomo\s+(?:done|stop)\s*[:：,，、]?\s*(.*)$", re.I | re.S)
_FILLER = {"", "吧", "啦", "咯", "喽", "了"}


def _load():
    try:
        return json.loads(FOCUS_F.read_text())
    except Exception:
        return None


def _save(st):
    FOCUS_F.parent.mkdir(parents=True, exist_ok=True)
    FOCUS_F.write_text(json.dumps(st, ensure_ascii=False))


def _clear():
    FOCUS_F.unlink(missing_ok=True)


def _fmt(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def _append_daily(line, sub=None):
    """把一行番茄记录追加到当天 daily 的 🍅 小节末尾(时间顺序, 像一条时间线)。"""
    p = srv.daily_path_today()
    block = line + ("\n" + sub if sub else "") + "\n"
    if not p.exists():
        p.write_text(f"# {srv.now():%Y-%m-%d}\n\n{FOCUS_HEADER}\n\n{block}",
                     encoding="utf-8")
        return
    cur = p.read_text(encoding="utf-8")
    if FOCUS_HEADER not in cur:
        p.write_text(cur.rstrip("\n") + f"\n\n{FOCUS_HEADER}\n\n{block}",
                     encoding="utf-8")
        return
    head, _, tail = cur.partition(FOCUS_HEADER)
    nxt = tail.find("\n## ")
    if nxt == -1:                              # 小节在文件尾
        new = cur.rstrip("\n") + "\n" + block
    else:                                      # 插进小节与下一小节之间
        seg, rest = tail[:nxt], tail[nxt:]
        new = head + FOCUS_HEADER + seg.rstrip("\n") + "\n" + block + rest
    p.write_text(new, encoding="utf-8")


def _log_session(st, end_ts, report=None):
    mins = max(1, round((end_ts - st["start_ts"]) / 60))
    task = f" {st['task']}" if st.get("task") else ""
    line = f"- {_fmt(st['start_ts'])}–{_fmt(end_ts)}（{mins} 分）{task.strip()}".rstrip()
    sub = f"  ↳ 收工：{report}" if report else None
    _append_daily(line, sub)
    return mins


def _append_report(report):
    """到点已自动记档后才收工: 把汇报作为缩进行补在 🍅 小节末尾。"""
    _append_daily(f"  ↳ 收工：{report}".rstrip())


def check_due():
    """值班员每轮轮询调一次。到点未提醒 → 自动记档并返回要发的那一条消息。"""
    st = _load()
    if not st or st.get("notified"):
        return None
    if time.time() < st["end_ts"]:
        return None
    _log_session(st, st["end_ts"])
    st["notified"] = True
    st["logged"] = True
    _save(st)
    return f"🍅 {st['minutes']} 分钟到了, 歇会儿吧。"


# 口令常被引号/括号裹着发过来(照着说明书的「开工」原样输入), 先剥壳再匹配。
# 只剥首尾的括号引号类字符; 任务名末尾偶有半边括号被顺走, 无伤大雅。
_WRAPPERS = "「」『』【】《》〈〉（）()\"'""''<>"


def handle(text):
    """开工/收工口令(别名: 开番茄/收番茄, 英文 pomo / pomo done)。
    命中返回回复文本, 否则 None 走正常聊天。"""
    s = text.strip().strip(_WRAPPERS).strip()
    if s.startswith(("收工", "收番茄")):
        return _handle_stop(_STOP_RE.match(s).group(1).strip())
    m = _STOP_EN_RE.match(s)                   # pomo done 要在 pomo 之前判
    if m:
        return _handle_stop(m.group(1).strip())
    m = (_START_RE.match(s) if s.startswith(("开工", "開工", "开番茄", "開番茄"))
         else _START_EN_RE.match(s))
    if m:
        mins = int(m.group(1)) if m.group(1) else DEFAULT_MIN
        mins = min(max(mins, 1), MAX_MIN)
        task = m.group(2).strip()
        if task in _FILLER:
            task = ""
        return _handle_start(mins, task)
    return None


def _handle_start(mins, task):
    prev_note = ""
    prev = _load()
    if prev and not prev.get("logged"):        # 上一颗跑到一半: 先按实际用时记档
        used = _log_session(prev, min(time.time(), prev["end_ts"]))
        prev_task = f"「{prev['task']}」" if prev.get("task") else "上一颗"
        prev_note = f"({prev_task}先记了 {used} 分)"
    now_ts = time.time()
    _save({"task": task, "minutes": mins, "start_ts": now_ts,
           "end_ts": now_ts + mins * 60, "notified": False, "logged": False})
    label = f"「{task}」" if task else ""
    return f"好, {label}{mins} 分钟, 开始 🍅{prev_note}"


def _handle_stop(report):
    st = _load()
    if not st:
        return "现在没有在跑的番茄, 说「开工」就能开一颗。"
    if st.get("logged"):                       # 到点自动行已写, 只补汇报
        if report:
            _append_report(report)
        _clear()
        return "记下了, 辛苦 🍅" if report else "好, 这颗收好了 🍅"
    mins = _log_session(st, time.time(), report or None)
    _clear()
    return f"记下了, 这颗 {mins} 分 🍅"
