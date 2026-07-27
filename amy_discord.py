#!/usr/bin/env python3
"""Amy 的 Discord 值班员: 专属频道或私聊 DM 收发消息, 手机上随时找她。

配置(环境变量, 没配就不上岗):
  AMY_DISCORD_TOKEN    Discord bot 的 token(建一个叫 Amy 的新 bot, 和其他 bot 分开)
  AMY_DISCORD_CHANNEL  频道模式: Amy 专属频道的 ID
  AMY_DISCORD_USER     DM 模式: 你自己的用户 ID(bot 会自动开一条私聊线;
                       需要你和 bot 至少同在一个服务器)
  两者给一个即可; 都给则优先频道。

轮询模式(每 5 秒), 不需要公网; 消息进出都走与桌面同一份聊天历史,
手机聊的桌面能看到, 桌面聊的手机也有记录。DM 里说话不需要 @。
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
USER = os.environ.get("AMY_DISCORD_USER")
STATE_F = pathlib.Path(__file__).resolve().parent / "runtime/discord_state.json"


def resolve_channel(tok, channel=None, user=None):
    """频道 ID 直接用; 只给用户 ID 则向 Discord 开一条 DM 线并返回它的频道 ID。"""
    if channel:
        return channel
    if not user:
        return None
    r = subprocess.run(
        ["curl", "-s", "--max-time", "15", "-X", "POST",
         "-H", f"Authorization: Bot {tok}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"recipient_id": str(user)}),
         "https://discord.com/api/v10/users/@me/channels"],
        capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout).get("id")
    except json.JSONDecodeError:
        return None


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
    if not TOK or not (CHANNEL or USER):
        print("AMY_DISCORD_TOKEN + (AMY_DISCORD_CHANNEL 或 AMY_DISCORD_USER) 没配, "
              "Discord 值班不启动")
        return
    channel = resolve_channel(TOK, CHANNEL, USER)
    if not channel:
        print("DM 频道解析失败: 确认 bot 和你同在一个服务器、你的隐私设置允许成员私信")
        return
    st = state()
    print(f"Amy Discord 值班中 · {'DM' if not CHANNEL else 'channel'}={channel}", flush=True)
    while True:
        try:
            after = f"?after={st['last_id']}" if st.get("last_id") else "?limit=1"
            msgs = api(f"/channels/{channel}/messages{after}")
            if isinstance(msgs, list) and msgs:
                for m in sorted(msgs, key=lambda x: int(x["id"])):
                    st["last_id"] = m["id"]
                    save_state(st)
                    if m.get("author", {}).get("bot"):
                        continue                      # 自己(或其它 bot)的消息不接
                    if USER and m.get("author", {}).get("id") != str(USER):
                        continue                      # 只听主人本人
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
                    send(TOK, channel, reply)
        except Exception as e:
            print("loop error:", e, flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
