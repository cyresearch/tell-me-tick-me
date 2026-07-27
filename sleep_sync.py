#!/usr/bin/env python3
"""Apple Watch 睡眠数据同步: 从 Discord 的睡眠数据频道取最新导出, 解析进睡眠日志。

数据来源: iPhone 快捷指令每天定时把昨晚的睡眠样本(逗号分隔三列:
开始 ISO 时间, 结束 ISO 时间, 阶段)经 webhook 发到专用频道(默认名 amy-sleep),
正文或 txt 附件皆可。本脚本由晨报调用(也可手动跑), 解析后按夜合并进
runtime/sleep_log.jsonl 的 watch 字段。

夜的归属: 片段开始时间在 15:00 前算前一晚(凌晨 1 点入睡属于昨夜)。
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import amy_discord

ROOT = pathlib.Path(__file__).resolve().parent
LOG = ROOT / "runtime/sleep_log.jsonl"
CH_CACHE = ROOT / "runtime/sleep_channel.json"
CHANNEL_NAME = os.environ.get("AMY_SLEEP_CHANNEL", "amy-sleep")

ASLEEP = ("core", "deep", "rem", "asleep", "核心", "深", "快速眼动")
AWAKE = ("awake", "清醒")


def _find_channel():
    try:
        cached = json.loads(CH_CACHE.read_text())
        if cached.get("name") == CHANNEL_NAME:
            return cached["id"]
    except Exception:
        pass
    guilds = amy_discord.api("/users/@me/guilds") or []
    for g in guilds:
        for c in amy_discord.api(f"/guilds/{g['id']}/channels") or []:
            if c.get("name") == CHANNEL_NAME:
                CH_CACHE.parent.mkdir(parents=True, exist_ok=True)
                CH_CACHE.write_text(json.dumps({"name": CHANNEL_NAME, "id": c["id"]}))
                return c["id"]
    return None


def _parse_lines(text, anchor=None):
    """'开始,结束,阶段' 行 → [(start_dt, end_dt, stage), ...]

    两种时间格式都认:
      完整 ISO: 2026-07-18T03:02:48+09:00
      短时刻:   03:02(需 anchor=消息发送日; ≥15:00 算前一天, 跨午夜自动处理)
    """
    def _dt(raw):
        raw = raw.strip()
        try:
            return datetime.datetime.fromisoformat(raw)
        except ValueError:
            pass
        if anchor:
            t = datetime.datetime.strptime(raw, "%H:%M").time()
            day = anchor - datetime.timedelta(days=1) if t.hour >= 15 else anchor
            return datetime.datetime.combine(day, t)
        raise ValueError(raw)

    out = []
    for ln in text.splitlines():
        parts = ln.strip().split(",")
        if len(parts) < 3:
            continue
        try:
            s, e = _dt(parts[0]), _dt(parts[1])
        except ValueError:
            continue
        out.append((s, e, ",".join(parts[2:]).strip()))
    return out


def _fetch_latest_payload(channel):
    """频道里最新一条能解析出睡眠行的消息(正文或 txt 附件)。"""
    msgs = amy_discord.api(f"/channels/{channel}/messages?limit=10") or []
    now = datetime.datetime.now(datetime.timezone.utc)
    for m in msgs:                                   # Discord 返回新→旧
        try:                                          # 短格式行靠消息发送日定日期
            ts = datetime.datetime.fromisoformat(m["timestamp"])
            if (now - ts).total_seconds() > 20 * 3600:
                continue                              # 保鲜期: 旧消息(如几天没戴表)不当新账记
            anchor = ts.astimezone().date()
        except Exception:
            anchor = None
        if m.get("attachments"):
            url = m["attachments"][0]["url"]
            r = subprocess.run(["curl", "-s", "-L", url], capture_output=True, timeout=60)
            segs = _parse_lines(r.stdout.decode("utf-8-sig", "replace"), anchor)
        else:
            segs = _parse_lines(m.get("content", ""), anchor)
        if len(segs) >= 3:
            return segs
    return []


def _night_of(dt):
    d = dt.date()
    return d - datetime.timedelta(days=1) if dt.hour < 15 else d


def summarize(segs):
    """按夜聚合, 返回最新一晚的统计 dict。"""
    nights = {}
    for s, e, stage in segs:
        nights.setdefault(_night_of(s), []).append((s, e, stage))
    night = max(nights)
    rows = sorted(nights[night])
    low = [r for r in rows if not any(k in r[2].lower() for k in ("in bed", "inbed", "在床"))]
    rows_eff = low or rows
    mins = lambda pred: round(sum((e - s).total_seconds() / 60
                                  for s, e, st in rows_eff if pred(st.lower())))
    asleep = mins(lambda st: any(k in st for k in ASLEEP) and not any(k in st for k in AWAKE))
    return {
        "night": f"{night}",
        "bed": f"{rows_eff[0][0]:%H:%M}",
        "wake": f"{rows_eff[-1][1]:%H:%M}",
        "asleep_min": asleep,
        "deep_min": mins(lambda st: "deep" in st or "深" in st),
        "rem_min": mins(lambda st: "rem" in st or "快速眼动" in st),
        "awake_min": mins(lambda st: any(k in st for k in AWAKE)),
        "segments": len(rows),
    }


def upsert(entry):
    """按 night 合并进 sleep_log.jsonl 的 watch 字段。"""
    lines = []
    if LOG.exists():
        lines = [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]
    for row in lines:
        if row.get("night") == entry["night"]:
            row["watch"] = entry
            break
    else:
        lines.append({"night": entry["night"], "watch": entry})
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n")


def human(entry):
    h, m = divmod(entry["asleep_min"], 60)
    return (f"{entry['night']} 晚(手表): {entry['bed']} 入睡, {entry['wake']} 醒, "
            f"实睡 {h}h{m:02d}m, 深睡 {entry['deep_min']}m, REM {entry['rem_min']}m, "
            f"夜醒 {entry['awake_min']}m")


def sync():
    """取→解析→入库。返回最新一晚的统计(没有新数据返回 None)。"""
    if not amy_discord.TOK:
        return None
    channel = _find_channel()
    if not channel:
        return None
    segs = _fetch_latest_payload(channel)
    if not segs:
        return None
    entry = summarize(segs)
    upsert(entry)
    return entry


if __name__ == "__main__":
    e = sync()
    print(human(e) if e else "没有可解析的睡眠数据")
