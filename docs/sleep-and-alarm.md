# Sleep care and the smart alarm: setup guide

This optional suite lets Amy take part in your sleep: a goodnight note in the evening, a check-up past midnight, real Apple Watch sleep data in the morning briefing, and an iPhone wake-up alarm set automatically from **when you actually fell asleep**.

You need: an Apple Watch (sleep tracking), a configured Discord bot (see the Discord part of the README), and iPhone Shortcuts. No third-party apps; your data only passes through your own Discord server.

## The big picture

```
23:30  night_call      Amy says goodnight and asks for any reply
00:30  night_escalate  no reply at all -> a ping burst; one sleep_log line per night
04:30  Shortcut A      the phone posts tonight's sleep samples to the sleep channel
04:45  alarm_plan      onset + sleep target + bus timetable -> posts "ALARM hh:mm AM"
04:55  Shortcut B      reads the ALARM line and creates the iPhone alarm
12:00  Shortcut (main) the full night's data lands in the channel
12:10  sleep_report    parses, logs, DMs you last night's numbers
```

## 1. The sleep data channel

1. Create a text channel named **`amy-sleep`** in your Discord server (the scripts find it by name; override with the `AMY_SLEEP_CHANNEL` env var)
2. Channel settings → Integrations → Webhooks → New, and **copy the webhook URL**

## 2. Shortcut: sleep export (4 actions)

1. **Find Health Samples**: type = Sleep, filter "Start Date is in the last 1 day", sort by start date, oldest first
2. **Repeat with Each**: inside the loop, one **Text** action joining three variables with plain commas:
   `Repeat Item · Start Date` , `Repeat Item · End Date` , `Repeat Item · Value`
   ⚠️ Set both dates to the **Custom** format **`HH:mm`** (time only; the date is inferred from when the message was posted, so a night of dozens of segments always fits in one message)
3. **Combine Text** with newlines
4. **Get Contents of URL**: POST to the webhook URL, form body `content` = the combined text
   ⚠️ Do not use a "File" form field: iOS silently drops variables there and Discord replies "Cannot send an empty message"

Automation: run daily around noon (e.g. 12:00) — this is the main export.
Then **duplicate** the shortcut and schedule the copy at **04:30** — the early export for the alarm (no content changes needed).

## 3. The bus timetable config

```bash
cp config/bus_schedule.example.json config/bus_schedule.json
# fill in your real departures, prep minutes, and sleep target window
```

The algorithm picks the first bus whose wake-up time gives at least the minimum target sleep; if a service gap would push you past the hard cap it falls back one bus; with no fresh data (watch not worn, or still awake) it uses `no_data_fallback_alarm`.

## 4. Shortcut: set the alarm (6 actions)

1. **Get Contents of URL**: GET `https://discord.com/api/v10/channels/<your sleep channel id>/messages?limit=1`
   with one header — key `Authorization`, value `Bot <your bot token>` (note the space after `Bot`)
2. **Get Item from List** → First Item
3. **Get Dictionary Value** → key `content`
4. **Match Text** → regex **`(?<=ALARM )\d{1,2}:\d{2} [AP]M`** (the AM marker keeps iOS from parsing 10:53 as 10:53 PM; if there is no ALARM line the match is empty and nothing gets set)
5. **Get Item from Matches** → First Item
6. **Create Alarm** → time = the first item, label it something like "Amy ⏰"

Automation: daily at **04:55**.

## 5. Timers (on the Mac side)

Schedule four routines with launchd or cron (times are examples):

| When | Script |
|---|---|
| 23:30 | `routines/night_call.py` |
| 00:30 | `routines/night_escalate.py` |
| 04:45 | `routines/alarm_plan.py` |
| 12:10 | `routines/sleep_report.py` |

They use the same environment variables as the Discord daemon (`AMY_DISCORD_TOKEN`, `AMY_DISCORD_USER`, and so on).

## 6. Skipping a morning: just tell Amy

Any night you do not want an alarm (a rest day, or you want to wake naturally), **tell Amy in plain words**: "no alarm tomorrow morning". She emits a skip instruction that the planner honors — one-shot, that single morning only. Changed your mind? Say "actually, set the alarm" and it is cancelled.

## Known edges

- Health-sample filters have day granularity, so the early export carries older segments; the scripts group by night and drop phantom future times, so this is handled
- A night without the watch: the briefing says so honestly and the alarm falls back to the default
- If your timetable is weekday-only, mind the weekend differences yourself
