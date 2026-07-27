#!/usr/bin/env python3
"""睡前查岗: night_call 提醒后一直没回音, 就连环 ping; 结果记进睡眠日志。

睡眠日志 runtime/sleep_log.jsonl 每晚一行, 早安简报会顺手带上昨夜情况。
"""
import datetime
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import amy_discord
import secretary

ROOT = pathlib.Path(__file__).resolve().parent
STATE = ROOT / "runtime/night_state.json"
LOG = ROOT / "runtime/sleep_log.jsonl"

BURST = ["还没睡吗? 👀",
         "再不睡的话, 明早的简报我可就要念叨啦 😤 今天就收到这里吧~",
         "好——数到三就去睡: 三、二、一。晚安 🌙"]


def main():
    tok = os.environ.get("AMY_DISCORD_TOKEN")
    user = os.environ.get("AMY_DISCORD_USER")
    try:
        st = json.loads(STATE.read_text())
    except Exception:
        print("无今晚状态, 不查岗")
        return
    if time.time() - st.get("ts", 0) > 3 * 3600:
        print("状态过期, 不查岗")
        return
    channel, ping = st.get("channel"), st.get("ping_id")
    if not (tok and channel and ping):
        print("Discord 信息不全, 不查岗")
        return
    msgs = amy_discord.api(f"/channels/{channel}/messages?after={ping}&limit=50")
    hers = [m for m in (msgs if isinstance(msgs, list) else [])
            if m.get("author", {}).get("id") == str(user)]
    entry = {"night": st["night"], "reminded": True}
    if hers:
        entry.update(responded=True,
                     responded_at=min(m["timestamp"] for m in hers))
        print("她回音了, 不打扰")
    else:
        for line in BURST:
            amy_discord.send(tok, channel, line)
            time.sleep(20)
        entry.update(responded=False, escalated=True)
        stamp = f"{datetime.datetime.now():%Y-%m-%d %H:%M}"
        secretary._append_history({"t": stamp, "role": "secretary",
                                   "text": "\n".join(BURST) + "\n(睡前查岗连环 ping)"})
        print("查岗 ping 已发")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
