#!/usr/bin/env python3
"""睡前提醒: 晚上定时让 Amy 主动来道晚安, 关照别熬太晚。

这是用户主动开启的睡眠管理(不是 AI 自作主张管教作息)。流程:
  23:30 本脚本: Amy 写一封睡前小信 → Discord DM + 桌面历史
  00:30 night_escalate.py: 她一直没回音才连环 ping 查岗
回一句(晚安也好、还要熬也好)就算有回音, 不再打扰。
"""
import datetime
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import amy_discord
import secretary
import server as srv

STATE = pathlib.Path(__file__).resolve().parent / "runtime/night_state.json"


def main():
    tok = os.environ.get("AMY_DISCORD_TOKEN")
    ch = os.environ.get("AMY_DISCORD_CHANNEL")
    user = os.environ.get("AMY_DISCORD_USER")
    srv.ensure_todo()
    todo_text, _ = srv.read_todo()
    done = [f"- {d['time']} 【{d['section']}】{d['text']}" for d in srv.parse_done_today()]
    prompt = ("(系统定时任务: 睡前提醒)夜深了, 请你主动来道晚安:\n"
              "1. 先简短肯定她今天完成的事(看【今日已完成】; 一件没有也别批评)\n"
              "2. 提醒她可以收尾准备睡了, 语气是关心和陪伴, 绝不说教\n"
              "3. 请她回一句: 准备睡就道个晚安; 还想再熬一会儿也回一声, 你就不打扰\n"
              "4. 俏皮地预告: 要是一直没回音, 00:30 你会来连环查岗\n"
              "简短, 三五句话的睡前小信。")
    reply, _ = secretary.chat(prompt, todo_text, done,
                              history_user_text="(睡前提醒定时器)")
    print(reply)

    channel = amy_discord.resolve_channel(tok, ch, user) if tok else None
    ping_id = None
    if channel:
        amy_discord.send(tok, channel, reply)
        msgs = amy_discord.api(f"/channels/{channel}/messages?limit=1")
        if isinstance(msgs, list) and msgs:
            ping_id = msgs[0]["id"]          # 查岗脚本以这条为基准找她的回音
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({
        "night": f"{datetime.date.today()}",
        "ts": datetime.datetime.now().timestamp(),
        "channel": channel, "ping_id": ping_id}))


if __name__ == "__main__":
    main()
