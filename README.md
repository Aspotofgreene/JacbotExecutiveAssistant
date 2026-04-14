# Jacbot Executive Assistant

A personal accountability AI agent delivered via Telegram. Every morning you lock in your 3 most important tasks; Jacbot checks in through the day, carries unfinished work to tomorrow, and sends weekly / monthly / yearly reports on what you actually shipped.

See [`PLANNING.md`](./PLANNING.md) for the full spec.

## Features

- **Daily 3-priority discipline** — `/add` walks you through entering 3 tasks with an optional "why"
- **AI evaluation** — Claude Haiku reviews each task for clarity, scope, and phrasing; suggests rewrites; estimates effort
- **Auto-categorization** — Deep Work / Admin / Health / Relationships / Side Project / Learning / Finance / Other
- **Smart check-ins** — inline buttons (Done / In progress / Blocked / Snooze 30m / Reschedule) spread between now and 7pm; two "in progress" replies suppress further nudges
- **Morning nudge (7am)** — prompts if you haven't set 3 fresh tasks
- **Evening rollover (8pm)** — unfinished tasks carry to tomorrow + reflection prompt
- **Repeat-offender detection** — tasks carried 3+ days trigger a "break it down or /kill it" warning
- **Journal** — `/journal` for free-form entries that feed into weekly summaries
- **Reports** — `/report` for on-demand weekly; scheduler auto-sends weekly (Sunday), monthly (1st), yearly (Jan 1) using Claude Sonnet
- **Streak / stats** — `/stats` shows completion rate and consecutive clean days
- **Silent mode** — `/silent` suppresses nudges until tomorrow

## Tech

- Python 3.12+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 21.6 (async)
- APScheduler (runs inside the bot's event loop via `post_init`)
- SQLite
- Local LLMs via Ollama (OpenAI-compatible API) — light tasks on one host, heavy tasks on another

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
TELEGRAM_TOKEN=...                                  # from @BotFather

# Ollama — light tasks (task eval, categorization)
OLLAMA_MAC_URL=http://localhost:11434
OLLAMA_MAC_MODEL=qwen3:14b

# Ollama — heavy tasks (weekly/monthly/yearly reports)
OLLAMA_DESKTOP_URL=http://192.168.50.206:11434
OLLAMA_DESKTOP_MODEL=deepseek-r1:14b

# Optional overrides
TIMEZONE=America/New_York
MORNING_TIME=07:00
EVENING_TIME=20:00
REPORT_TIME=18:00                                   # Sunday weekly report time
```

Make sure both Ollama hosts have the models pulled:

```bash
ollama pull qwen3:14b          # on the light host
ollama pull deepseek-r1:14b    # on the heavy host
```

## Run

```bash
python -m jacbot.main
```

## Smoke test

Before going live, verify the app wiring without hitting Telegram or the Anthropic API:

```bash
python scripts/smoke_test.py
```

This checks imports, DB schema creation, CRUD round-trips, and handler module loading.

## Telegram commands

| Command | What it does |
|---|---|
| `/start` | Register your Telegram ID and see help |
| `/add` | Enter today's 3 priorities (AI-reviewed) |
| `/today` | Show today's task list |
| `/done N` | Mark task N complete |
| `/kill N [reason]` | Abandon task N |
| `/journal` | Add a free-form journal entry |
| `/silent` | No nudges until tomorrow |
| `/stats` | Streak & completion rate |
| `/report` | Generate an on-demand weekly report |

## Project layout

```
jacbot/
├── main.py              # entry point, handler wiring, post_init scheduler setup
├── config.py            # env vars (.env loader)
├── db.py                # SQLite schema + query helpers
├── scheduler.py         # morning nudge, evening rollover, check-ins, reports
├── ai.py                # Anthropic SDK: task eval, categorization, reports
└── handlers/
    ├── core.py          # /start /today /add /done /kill /silent /stats /journal
    ├── checkin.py       # inline-button check-in callbacks
    └── reports.py       # /report + scheduled weekly/monthly/yearly sends
scripts/
└── smoke_test.py        # offline sanity check
```
