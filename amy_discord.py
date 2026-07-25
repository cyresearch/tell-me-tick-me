#!/usr/bin/env python3
"""Amy 的 Discord 值班员: 在专属频道收消息、回消息, 手机上随时找她。

配置(环境变量, 没配就不上岗):
  AMY_DISCORD_TOKEN    Discord bot 的 token(建一个叫 Amy 的新 bot, 和其他 bot 分开)
  AMY_DISCORD_CHANNEL  Amy 专属频道的 ID

轮询模式(每 5 秒), 不需要公网; 消息进出都走与桌面同一份聊天历史,
手机聊的桌面能看到, 桌面聊的手机也有记录。
"""
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import secretary
import server as srv

TOK = os.environ.get("AMY_DISCORD_TOKEN")
CHANNEL = os.environ.get("AMY_DISCORD_CHANNEL")
STATE_F = pathlib.Path(__file__).resolve().parent / "runtime/discord_state.json"


def api(path, extra=None):
    cmd = ["curl", "-s", "--max-time", "15",
           "-H", f"Authorization: Bot {TOK}",
           "https://discord.com/api/v10" + path]
    if extra:
        cmd = cmd[:1] + extra + cmd[1:]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def send(tok, channel, text):
    """长文本分条发(Discord 单条上限 2000)。供本模块与 morning_call 复用。"""
    for i in range(0, max(len(text), 1), 1900):
        subprocess.run(
            ["curl", "-s", "--max-time", "30",
             "-H", f"Authorization: Bot {tok}",
             "-F", "payload_json=" + json.dumps({"content": text[i:i + 1900]},
                                                ensure_ascii=False),
             f"https://discord.com/api/v10/channels/{channel}/messages"],
            capture_output=True, timeout=60)


def state():
    try:
        return json.loads(STATE_F.read_text())
    except Exception:
        return {}


def save_state(st):
    STATE_F.parent.mkdir(parents=True, exist_ok=True)
    STATE_F.write_text(json.dumps(st))


def main():
    if not (TOK and CHANNEL):
        print("AMY_DISCORD_TOKEN / AMY_DISCORD_CHANNEL 没配, Discord 值班不启动")
        return
    st = state()
    print(f"Amy Discord 值班中 · channel={CHANNEL}", flush=True)
    while True:
        try:
            after = f"?after={st['last_id']}" if st.get("last_id") else "?limit=1"
            msgs = api(f"/channels/{CHANNEL}/messages{after}")
            if isinstance(msgs, list) and msgs:
                for m in sorted(msgs, key=lambda x: int(x["id"])):
                    st["last_id"] = m["id"]
                    save_state(st)
                    if m.get("author", {}).get("bot"):
                        continue                      # 自己(或其它 bot)的消息不接
                    text = (m.get("content") or "").strip()
                    if not text:
                        continue
                    srv.ensure_todo()
                    todo_text, _ = srv.read_todo()
                    done = [f"- {d['time']} 【{d['section']}】{d['text']}"
                            for d in srv.parse_done_today()]
                    try:
                        reply, sugg = secretary.chat(text, todo_text, done)
                    except Exception as e:
                        reply, sugg = f"(出错了: {e})", []
                    if sugg:
                        reply += ("\n\n(有 " + str(len(sugg)) +
                                  " 条待办建议, 在桌面小窗里点确认)")
                    send(TOK, CHANNEL, reply)
        except Exception as e:
            print("loop error:", e, flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
