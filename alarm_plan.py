#!/usr/bin/env python3
"""智能闹钟计算员: 按实际入睡时间 + 巴士时刻表, 算出今早该几点被叫醒。

三段接力的中段(凌晨定时跑, 如 04:45):
  04:30 手机快捷指令把"过去 6 小时"的睡眠样本发到睡眠频道(早导出)
  04:45 本脚本: 取早导出(只认 2 小时内的新消息)→ 找入睡时刻 →
        在 [入睡+目标睡眠] 窗口里挑赶得上的巴士 → 闹钟 = 发车 - 准备时长
        → 把 "ALARM HH:MM" 发回频道(不发 DM, 避免半夜推送吵醒人)
  04:55 手机快捷指令读频道最新 ALARM 行, 创建当天闹钟

策略(config/bus_schedule.json 可调):
  - 目标睡眠 [min_h, max_h]; 挑第一班"醒来时刻 ≥ 入睡+min_h"的巴士
  - 若因班次断档导致睡眠 > hard_max_h, 退回前一班(宁可少睡一点不睡过站)
  - 兜底: 没有新数据(没戴表/还没睡)→ no_data_fallback_alarm
"""
import datetime
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import amy_discord
import sleep_sync

ROOT = pathlib.Path(__file__).resolve().parent
CONF_F = ROOT / "config/bus_schedule.json"
PLAN_F = ROOT / "runtime/alarm_plan.json"

ASLEEP = sleep_sync.ASLEEP
AWAKE = sleep_sync.AWAKE


def _is_asleep(stage):
    st = stage.lower()
    return any(k in st for k in ASLEEP) and not any(k in st for k in AWAKE)


def compute(onset, conf, today):
    """入睡时刻 → (闹钟 datetime, 赶哪班巴士, 预计实睡小时)。onset=None 走兜底。"""
    prep = datetime.timedelta(minutes=conf["prep_minutes"])
    buses = [datetime.datetime.combine(today, datetime.time(*map(int, b.split(":"))))
             for b in conf["weekday_departures"]]
    if onset is None:
        alarm = datetime.datetime.combine(
            today, datetime.time(*map(int, conf["no_data_fallback_alarm"].split(":"))))
        bus = next((b for b in buses if b >= alarm + prep), buses[-1])
        return alarm, bus, None
    lo = onset + datetime.timedelta(hours=conf["sleep_target_min_h"])
    hard = onset + datetime.timedelta(hours=conf["sleep_hard_max_h"])
    pick = None
    for i, bus in enumerate(buses):
        wake = bus - prep
        if wake >= lo:
            if wake > hard and i > 0:     # 班次断档睡过头: 退回前一班
                pick = i - 1
            else:
                pick = i
            break
    if pick is None:                       # 全部班次都太早(入睡太晚): 取末班
        pick = len(buses) - 1
    alarm = buses[pick] - prep
    slept = (alarm - onset).total_seconds() / 3600
    return alarm, buses[pick], round(slept, 2)


def main():
    conf = json.loads(CONF_F.read_text())
    today = datetime.date.today()
    onset = None
    channel = sleep_sync._find_channel()
    if channel:
        segs = sleep_sync._fetch_latest_payload(channel, max_age_h=2)  # 只认早导出
        nights = {}
        for s, e, st in segs:
            nights.setdefault(sleep_sync._night_of(s), []).append((s, st))
        if nights:
            latest = max(nights)
            if latest >= today - datetime.timedelta(days=1):   # 必须是今夜, 旧夜不算
                # 短格式无日期, 昨晨片段会被错标成"今晨未来时刻"; 未来的开始时刻=幻影, 丢弃
                now = datetime.datetime.now()
                asleep = sorted(s.replace(tzinfo=None) if s.tzinfo else s
                                for s, st in nights[latest] if _is_asleep(st))
                asleep = [s for s in asleep if s <= now]
                if asleep:
                    onset = asleep[0]
    alarm, bus, slept = compute(onset, conf, today)
    line = (f"ALARM {alarm:%H:%M} (赶 {bus:%H:%M} 的巴士"
            + (f", 入睡 {onset:%H:%M}, 预计实睡 {slept}h)" if onset else ", 无新睡眠数据走兜底)"))
    print(line)
    PLAN_F.parent.mkdir(parents=True, exist_ok=True)
    PLAN_F.write_text(json.dumps({
        "date": f"{today}", "alarm": f"{alarm:%H:%M}", "bus": f"{bus:%H:%M}",
        "onset": f"{onset:%H:%M}" if onset else None, "slept_h": slept},
        ensure_ascii=False))
    tok = os.environ.get("AMY_DISCORD_TOKEN")
    if tok and channel:
        amy_discord.send(tok, channel, line)   # 发睡眠频道(静音), 不 DM 不吵醒


if __name__ == "__main__":
    main()
