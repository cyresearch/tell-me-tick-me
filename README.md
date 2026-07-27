English | [中文](README.zh.md) | [日本語](README.ja.md)

# tell-me-tick-me

Tell me what to do, and tick me off when it's done.

An **AI-native desktop todo app** with an AI secretary living inside: **Amy** (her name comes from the Chinese pun "A秘", short for AI secretary).

The todo window **snaps to the edge of your screen** like the classic QQ messenger, sliding out when your mouse touches it and tucking away when you leave, so it **takes no screen space**. Talk to Amy regularly about what is coming up and she helps you **break tasks down, put them in order, and make the hard calls when deadlines collide**; she keeps her own **long-term memory**, so she understands your long-term plans and how each project is going. Grant her web search, mail access or calendar permissions and she gets even better at understanding and supporting your work and life. Every task you tick off is archived into today's daily note automatically, ready for reviewing your progress.

Also recommended: hook Amy into **Discord** (or any chat app you like), so your phone can reach her anytime. Every morning Amy messages you to **remind you of the day's todos**, in the evening she **reviews the day and says goodnight**, and when you go silent late at night she **tells you to go to bed**; with an **Apple Watch** connected, she even creates your phone's wake-up alarm **automatically**, from **when you actually fell asleep** and your transit timetable.

## 🌱 Why I built this

As a PhD student, my daily schedule has a lot of freedom and depends heavily on self-management. What I do each day is driven by paper progress, experiment status, project deadlines, and whatever new task just landed. **A fixed, standardized daily list has never worked for me.**

So I wanted a tool that helps me sort out "what should I do today": organize the projects in flight, separate **today, this week, this month, and long-term**, review what is already done, and be a little less "whatever comes to mind first". Listing what is unfinished is the easy part. It should help me see **what deserves my attention right now**, which tasks look urgent but can wait, which ones deserve real investment, and which ones are fine at "good enough".

## 🧠 When there is too much, talk it through with AI

Several deadlines landing in the same week happens to everyone. When tasks suddenly pile up, **it is easy to panic**: you do not know what to start with, where to begin, and because you want to do everything well, you end up starting nothing.

That is when I talk to Amy directly: what is on my list, where I am stuck, what has prerequisites, how to split my energy when time is short. She does more than reorder a list. She helps with the practical judgment calls: **which tasks are fine at 60 percent, which need 80, and which deserve everything you have got**. The goal is to make **clear-headed, realistic choices** when tasks are dense and energy is limited, instead of marking everything "important".

## ✨ How it differs from a normal todo app

There are plenty of mature todo apps. What sets this one apart: **AI is the core of the workflow**, and that shows up in concrete design decisions:

- **Your todos are one plain markdown file** (todo.md): the AI reads it directly, your data stays yours, and your life never gets squeezed into forms
- **Amy sees your project context and daily archives**: she breaks down tasks and sets priorities based on real progress, not guesses
- **Amy only suggests, you always confirm** (a click on the desktop, or a "confirm" reply in DM): add, move and remove all wait for your OK. She has no power to edit your todos directly
- **Amy keeps her own memory file**: over time she builds an understanding of how you work and what you are aiming for

## 👋 This might be for you

If you are like me, your head keeps producing ideas and you start several projects at once, but following through is the hard part: somewhere along the way you drift from the original goal, forget where a project stands, and lose your grip on the overall picture. If that sounds familiar, this project might fit you too.

Most of the time, **there is no shortage of ideas or effort**. What gets in the way:

- too many things are in flight at once;
- new ideas keep arriving;
- the next step of a project is fuzzy;
- tasks get half-done with no clear record of progress;
- attention drifts to whatever is newest, and you gradually lose track;
- coming back after a while, it is hard to pick up the thread quickly.

I want this tool to record more than "what to do today". It should **preserve the context of your work**: which project a task belongs to, why it exists, where it stands, what comes next, and how it relates to other tasks.

That way, **even when something interrupts you, getting back on track is much easier**.

## 🧪 Born from a workflow I have actually used for over half a year

Before turning this into a standalone project, I had already been **using AI to manage my schedule, sort out tasks, track progress, and talk through work strategy for more than half a year**.

Over that time, the AI and I would:

- organize the day's and the week's tasks;
- weigh priorities across projects;
- figure out why a task was stuck;
- split vague goals into executable next steps;
- keep records of what each project had completed;
- talk through trade-offs when deadlines collided;
- review progress regularly, so no project quietly went missing in a busy stretch.

This way of working clearly improved my efficiency. More importantly, it **reduced the burden of repeatedly wondering "what should I actually be doing right now"**, and made it much easier to re-enter a project after an interruption.

Until now, though, all of that lived only inside my personal workspace. The task files, project records, AI conversations, and working rules grew around my own environment. It was never something other people could just install and use.

What I am doing now is **distilling that workflow into a self-contained open-source tool**, shaped by real interaction habits rather than imagined features.

## 🚀 Getting started

Requirements: macOS (the floating window is Mac-native; the web part runs anywhere), Python 3.10+, and optionally the Xcode command line tools to build the floating shell.

```bash
git clone https://github.com/cyresearch/tell-me-tick-me
cd tell-me-tick-me
./run.sh
# open http://127.0.0.1:8765 in your browser
```

The first run generates a sample todo (`data/todo.md`), so **you can start ticking right away**. For the floating window:

```bash
./shell/build.sh      # compile once
./shell/TellMeTickMe  # docks to the right edge, slides out on hover
```

## 🔌 Bring your own LLM (putting Amy to work)

The first time you open the chat panel you will see a setup wizard. **Pick one of three channels**:

| Channel | Who it is for | Notes |
|---|---|---|
| **Claude Code** | Claude subscribers | Uses your own subscription, first-party and compliant. **The fullest experience**: Amy can search directories you designate and maintain her own memory |
| **Anthropic API** | API key holders | Your key **stays on your machine** in `config/llm.json`, never passes through a third party |
| **Ollama** | Zero-cost, fully offline | Local models, **your data never leaves your computer** |

**Everything except Amy works without an LLM**: checking off, archiving, editing, and the snap-to-edge window need no AI at all. This project does **no subscription-piggybacking third-party tricks**. All three channels are front doors.

💡 **Tip: pair it with voice input.** Use system dictation or any voice input method and just **talk** to Amy about your week. For planning conversations, speaking beats typing.

## 📱 Amy in your pocket: Discord DM (optional)

Give Amy a Discord bot and she moves into your phone:

- **Direct messages**: one-on-one DM, no channel to create, no @-mentions; she only answers you (filtered by user id)
- **The same Amy as on the desktop**: one memory, one history across both; when she suggests todo changes, **replying "confirm" applies them on the spot**, no computer needed
- **She reaches out first**: the daily briefing lands on the desktop and in DM at the same time, and the goodnight note and the late-night check-up use this line too
- **A green presence dot**: the daemon keeps a gateway heartbeat, so her avatar shows online

Two settings are all it takes: a bot token and your user id (env vars `AMY_DISCORD_TOKEN` / `AMY_DISCORD_USER`); the daemon is `engine/amy_discord.py`. The sleep data in the next section also travels through a Discord channel, so this is its prerequisite.

## ⏰ A smart wake-up alarm from sleep tracking: your alarm should not be decided before you have even fallen asleep

The plan is usually to sleep at 23:30 and set a 7:30 alarm for a full eight hours. But you lie awake, fall asleep an hour later than planned, and the fixed alarm fires anyway, quietly cutting into your sleep. Pushing it later means missing the bus, the metro, the train, or your must-leave time when driving, so you end up juggling sleep length, wake-up time and departure time in your head.

This project also includes a smart alarm that **knows when you actually fell asleep last night, and when you have to leave this morning**.

Tell Me, Tick Me reads the sleep your Apple Watch actually recorded, combines it with your target sleep length, your timetable (bus, metro, train, or your must-leave time when driving; you can send Amy your usual departures in advance) and how long you need to get ready, then computes a wake-up time that protects your rest without missing your ride, and creates the iPhone alarm automatically. **The later you fall asleep, the later the departure it aims for.**

The sleep suite also includes:

- **A goodnight note at 23:30**, acknowledging what you finished today; stay silent and Amy **checks on you at 00:30**
- **Measured sleep in the morning briefing** (when you fell asleep, real sleep time, deep sleep)
- **Skipping takes one sentence**: tell Amy "no alarm tomorrow" and that single morning is exempt

Sleep in peace. Amy does the math. Setup guide: [docs/sleep-and-alarm.md](docs/sleep-and-alarm.md) (needs an Apple Watch and a Discord bot; entirely optional).

## 🧩 Goes well with: making Amy know you from day one

The better Amy knows you, the better her advice. I also built [chatgpt-memory-extraction](https://github.com/cyresearch/chatgpt-memory-extraction): it turns years of your exported ChatGPT conversations into a **structured personal memory archive** (timelines, people, topics). Point Amy's persona file at the archive directory, and with the Claude Code channel she can search it on demand. **Your history, your ongoing work, the people around you: she knows it from day one**, and you never have to introduce yourself from scratch again.

## ⚙️ Configuration (environment variables, all with defaults)

| Variable | Default | Meaning |
|---|---|---|
| `DESK_TODO_FILE` | `data/todo.md` | The todo file (point it at your own markdown) |
| `DESK_DAILY_DIR` | `data/daily` | Daily archive directory |
| `DESK_PORT` | `8765` | Port |
| `DESK_BIND` | `127.0.0.1` | Set `0.0.0.0` for LAN access (mind shared networks) |
| `TMTM_CLAUDE_MODEL` | `opus` | Model for the Claude Code channel |

Amy's persona lives in `config/secretary.example.md`. Copy it to `config/secretary.md` and fill in your own situation following the comments. It, Amy's memory, and your LLM config are all **kept out of git**.

## 🛡 How it protects your todo.md

- **Hand edits always win**: the file is re-read before every operation, disk is the source of truth
- **Writes are surgical, line-block level only**: everything else stays byte-identical
- **Automatic backup** to `runtime/backups/` before the first write of each day
- **Every operation is undoable**, and every AI suggestion waits for a human click
- If an item cannot be found (the file was just edited elsewhere), it refuses and asks you to refresh. **It never guesses and deletes**

## 🔄 A project that evolves through real use

This project will not be built from an imagined feature checklist. **I keep using it every day for my own study, research, and project management**, and I maintain and improve it based on what real use teaches me:

- which features genuinely reduce cognitive load;
- which reminders just create new pressure;
- when the AI should step in proactively;
- which decisions AI can assist with, and which must stay with the user;
- how to record context so that re-entering a project actually gets easier;
- how to balance "more systematic" against "not building a system too heavy to use".

In other words, this is a **personal working system, tested and iterated through long-term daily use**, and it keeps evolving after it lands on GitHub.

It serves my real needs first, and I hope it grows into a tool that helps more people **organize their thinking, keep their projects continuous, and actually push their ideas forward**. ✨

## 🗺 Roadmap

Done:

- [x] todo.md check-off and archive, undo, backups, collapsible sections, in-window editing
- [x] Floating window: four-edge snapping, free resizing, dual grips, position memory, never-lost safeguards
- [x] Amy: three LLM channels, private memory, add/move/remove suggestion cards, first-run wizard

- [x] **Morning briefing, bedtime reminder and check-up**: timers wake Amy so she reaches out first; stay silent past bedtime and she pings until you answer
- [x] **Discord DM duty daemon**: plan with Amy on the go, same memory as the desktop, green presence dot
- [x] Optional Gmail (read+draft) and read-only Calendar connectors
- [x] **The full sleep suite**: goodnight note and check-up, watch data flowing back, an alarm set from actual sleep onset, one-sentence exemptions

Planned:

- [ ] A real phone-call wake-up (needs a phone line)
- [ ] E-ink and spare-device display mode

## License

MIT
