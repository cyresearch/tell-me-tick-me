English | [中文](README.zh.md) | [日本語](README.ja.md)

# tell-me-tick-me

Tell me what to do, and tick me off when it's done.

An **AI-native desktop todo** that lives in a little floating window: your tasks are **plain markdown**, checking one off archives it into today's daily note, and the window **snaps to the edge of your screen** like the classic QQ messenger, sliding out when your mouse touches the edge and tucking itself away when you leave. Inside lives **Amy**, an AI secretary (her name comes from the Chinese pun "A秘", short for AI secretary). Tell her what is on your plate and she helps you **break tasks down, put them in order, and make the hard calls when deadlines collide**.

## 🌱 Why I built this

As a PhD student, my daily schedule has a lot of freedom and depends heavily on self-management. What I do each day is driven by paper progress, experiment status, project deadlines, and whatever new task just landed. **A fixed, standardized daily list has never worked for me.**

So I wanted a tool that helps me sort out "what should I do today": organize the projects in flight, separate **today, this week, this month, and long-term**, review what is already done, and be a little less "whatever comes to mind first". It should not just tell me what is unfinished. It should help me see **what deserves my attention right now**, which tasks look urgent but can wait, which ones deserve real investment, and which ones are fine at "good enough".

## 🧠 When there is too much, talk it through with AI

Several deadlines landing in the same week happens to everyone. When tasks suddenly pile up, **it is easy to panic**: you do not know what to start with, where to begin, and because you want to do everything well, you end up starting nothing.

That is when I talk to Amy directly: what is on my list, where I am stuck, what has prerequisites, how to split my energy when time is short. She does more than reorder a list. She helps with the practical judgment calls: **which tasks are fine at 60 percent, which need 80, and which deserve everything you have got**. The goal is to make **clear-headed, realistic choices** when tasks are dense and energy is limited, instead of marking everything "important".

## ✨ How it differs from a normal todo app

There are plenty of mature todo apps. This project is not trying to be another add-check-delete list. The difference is that **AI is not a bolt-on feature here, it is the core of the workflow**, and that shows up in concrete design decisions:

- **Your todos are one plain markdown file** (todo.md): the AI reads it directly, your data stays yours, and your life never gets squeezed into forms
- **Amy sees your project context and daily archives**: she breaks down tasks and sets priorities based on real progress, not guesses
- **Amy only suggests, you always confirm**: add, move, and remove cards each wait for your click. She has no power to edit your todos directly
- **Amy keeps her own memory file**: over time she builds an understanding of how you work and what you are aiming for

## 👋 This might be for you

If you are like me, your head keeps producing ideas and you start several projects at once, but following through is the hard part: somewhere along the way you drift from the original goal, forget where a project stands, and lose your grip on the overall picture. If that sounds familiar, this project might fit you too.

Most of the time, **the problem is not a lack of ideas, and it is not a lack of effort**. It is that:

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

In other words, **this is not a demo that gets finished and left on GitHub**. It is a personal working system that keeps being tested and iterated through long-term daily use.

It serves my real needs first, and I hope it grows into a tool that helps more people **organize their thinking, keep their projects continuous, and actually push their ideas forward**. ✨

## 🗺 Roadmap

Done:

- [x] todo.md check-off and archive, undo, backups, collapsible sections, in-window editing
- [x] Floating window: four-edge snapping, free resizing, dual grips, position memory, never-lost safeguards
- [x] Amy: three LLM channels, private memory, add/move/remove suggestion cards, first-run wizard

- [x] **Morning briefing, bedtime reminder and check-up**: timers wake Amy so she reaches out first; stay silent past bedtime and she pings until you answer
- [x] **Discord DM duty daemon**: plan with Amy on the go, same memory as the desktop, green presence dot
- [x] Optional Gmail (read+draft) and read-only Calendar connectors

Planned:

- [ ] A real phone-call wake-up (needs a phone line)
- [ ] E-ink and spare-device display mode

## License

MIT
