#!/usr/bin/env python3
"""正午睡眠报数员: 手表导出到达后(用户自定的发送时刻), 同步并把昨晚实测 DM 出去。

晨报若早于导出时刻, 当天拿不到手表数据; 这个轻量脚本在导出后运行:
sleep_sync 入库成功就发一条简短汇总(纯模板, 不动 LLM), 没有新数据保持安静。
"""
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "engine"))
import amy_discord
import sleep_sync


def main():
    entry = sleep_sync.sync()
    if not entry:
        print("没有新的睡眠数据, 不打扰")
        return
    print(sleep_sync.human(entry))
    tok = os.environ.get("AMY_DISCORD_TOKEN")
    ch = os.environ.get("AMY_DISCORD_CHANNEL")
    user = os.environ.get("AMY_DISCORD_USER")
    channel = amy_discord.resolve_channel(tok, ch, user) if tok else None
    if channel:
        h, m = divmod(entry["asleep_min"], 60)
        amy_discord.send(tok, channel,
                         f"📊 昨晚手表实测: {entry['bed']} 入睡, {entry['wake']} 醒, "
                         f"实睡 {h}h{m:02d}m(深睡 {entry['deep_min']}m, "
                         f"REM {entry['rem_min']}m, 夜醒 {entry['awake_min']}m)")


if __name__ == "__main__":
    main()
