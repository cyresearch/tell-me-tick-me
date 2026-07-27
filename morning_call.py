#!/usr/bin/env python3
"""每日早安: 定时器替 Amy 按下开关, 她主动开启用户的一天。

由 launchd/cron 在早上调用(见 README 的定时设置)。Amy 结合 todo、
今日日历(若开了连接器)和她的记忆, 主动发一条今日开场; 写进聊天历史后,
悬浮窗的未读红点会亮; 配了 Discord 的话同时推到手机。
"""
import datetime
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import secretary
import server as srv


def _last_night_note():
    """昨夜的睡眠情况: 手表真实数据(sleep_sync) + 睡前提醒的回音记录。"""
    log = pathlib.Path(__file__).resolve().parent / "runtime/sleep_log.jsonl"
    try:
        rows = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    except Exception:
        return ""
    ynight = f"{datetime.date.today() - datetime.timedelta(days=1)}"
    row = next((r for r in rows if r.get("night") == ynight), None)
    if not row:
        return ""
    bits = []
    w = row.get("watch")
    if w:
        h, m = divmod(w["asleep_min"], 60)
        bits.append(f"手表实测: {w['bed']} 入睡, {w['wake']} 醒, 实睡 {h}h{m:02d}m, "
                    f"深睡 {w['deep_min']}m, 夜醒 {w['awake_min']}m")
    if row.get("responded"):
        bits.append(f"睡前提醒后 {row.get('responded_at', '?')[11:16]} 有回音")
    elif row.get("escalated"):
        bits.append("睡前提醒一直没回音, 00:30 查岗了")
    return "; ".join(bits)


def main():
    try:                                    # 手表睡眠数据: 快捷指令 10:00 发, 这里 10:30 收
        import sleep_sync
        sleep_sync.sync()
    except Exception as e:
        print(f"(sleep_sync 跳过: {e})")
    srv.ensure_todo()
    todo_text, _ = srv.read_todo()
    done = [f"- {d['time']} 【{d['section']}】{d['text']}" for d in srv.parse_done_today()]
    weekday = "一二三四五六日"[datetime.datetime.now().weekday()]
    prompt = (f"(系统定时任务: 每日早安)现在是早上, 请你主动向她开启今天:\n"
              f"1. 简短问候(今天周{weekday})\n"
              f"2. 若日历连接器可用, 看一眼今天和明天的日程, 有安排就提醒\n"
              f"3. 结合 todo 给出今天最值得推进的 1-3 件事(有临近 deadline 的优先)\n"
              f"4. 最后问她今天打算怎么安排\n"
              f"整体简短温暖, 像秘书的晨间简报, 不要长篇大论。")
    night = _last_night_note()
    if night:
        prompt += f"\n【昨夜睡眠记录】{night}\n如果显示熬夜了, 温柔关心一句, 别说教。"
    reply, _ = secretary.chat(prompt, todo_text, done,
                              history_user_text="(每日早安定时器)")
    print(reply)

    # 配了 Discord 就同步推一份到手机(频道或 DM 均可)
    tok = os.environ.get("AMY_DISCORD_TOKEN")
    ch = os.environ.get("AMY_DISCORD_CHANNEL")
    user = os.environ.get("AMY_DISCORD_USER")
    if tok and (ch or user):
        import amy_discord
        channel = amy_discord.resolve_channel(tok, ch, user)
        if channel:
            amy_discord.send(tok, channel, reply)


if __name__ == "__main__":
    main()
