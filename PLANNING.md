# Jacbot Executive Assistant — Planning Document

## Overview

A personal accountability agent delivered via Telegram. Every day starts
with 3 locked-in priorities. The agent watches, nudges, and analyzes.
At the end of each week (and month and year) it tells you the honest story
of how you actually spent your time vs. how you intended to.

---

## Locked Decisions

| Question | Decision |
|---|---|
| Delivery channel | Telegram bot |
| User scope | Single-user (just me) |
| Silent mode | Per-day toggle via `/silent` |
| Timezone | Local, hardcoded |
| Journal privacy | Encrypted at rest (SQLCipher) |

---

## Core Workflows

### Morning Flow (7am window)
7am → Bot: "What are your 3 for today?"
→ User sends 3 tasks (numbered list or 3 messages)
→ AI evaluates each:
• Vague? ("Work on project" → "Which part? What's the deliverable?")
• Too big? (>3hr estimate → suggest breaking down)
• Missing action verb? ("Email draft" → "Draft email to X about Y")
• Optional: suggest better phrasing
→ Bot shows proposed rewrites inline
→ User taps: ✅ Accept all | ✏️ Edit | 🔄 Keep mine
→ Tasks locked. AI estimates effort + picks check-in times.


**Optional "why" field:** One sentence per task. Skippable, but improves
AI feedback quality and powers weekly summaries. ("Ship signup flow" → why: "Blocking beta launch")

**7am enforcement:** If fewer than 3 tasks entered by 7am, hourly nudges
fire until 3 tasks are submitted. Carried-over tasks do not count toward the 3-task minimum.

---

### Midday Flow (AI-timed check-ins)

Bot: "Task 1: [text] — is it done yet?"
→ User taps:
✅ Done
⏳ In progress
🚫 Blocked → follow-up: "What's blocking?"
🔁 Reschedule → follow-up: "Why moving it?"
💤 Snooze 30min


**AI adaptation rules:**
- Task receives 2x "In progress" → bot stops pinging that task until 7pm
- "Blocked" or "Reschedule" responses + notes feed into weekly analysis (patterns live here)
- Check-in times are AI-selected per task based on estimated effort and historical patterns (not uniform)

---

### Evening Flow (8pm)

8pm → For each unfinished task:
Missed (log it) | Carry (→ tomorrow) | Kill (abandon, log reason)
→ One reflection question (varies nightly):
"What drained you today?"
"One win?"
"Energy level tomorrow: 1–5?"
→ Carried tasks queued for next morning


Reflection is kept to under 30 seconds. One question only.

---

### Weekly Flow (Sunday 6pm)
Agent aggregates: tasks, check-in responses, reflection answers, journal notes
→ AI categorizes all tasks into themes (Deep Work / Admin / Health /
Relationships / Side Project / etc.) — no manual tagging
→ Produces full weekly report:
• Completion rate
• Dominant work categories
• What kept getting carried (pattern signal)
• Journal themes
• One improvement suggestion
→ 2-minute interactive planning moment:
Bot: "Any theme for next week?"
Your answer stored, referenced in Monday's task feedback


**Monthly report:** Trends by category, productivity patterns by day/time, which goals got dropped.

**Yearly report:** Narrative summary — the story of your year.

---

## Accountability Mechanics (the teeth)

- **Streaks:** "3 tasks by 7am" streak + "all 3 done by 8pm" streak
- **Repeat-offender detection:** Task carries 3+ days → bot interrupts: "This has carried 3 days. Break it down, do it now, or kill it."
- **Kill switch:** Explicit abandon is always available. Reason is logged. Shows up in weekly report.
- **Silent mode:** `/silent` suppresses all nudges until midnight. No questions asked.

---

## Deferred Features (revisit after 4 weeks of use)

- **Habit tracker:** Habits (binary/recurring) live differently than daily priorities. Add as a second module once the core loop is proven.
- **Calendar integration:** Read Google Calendar to inform check-in timing.
- **Voice journal:** Telegram already supports voice notes. Whisper transcription is an easy add-on later.

---

## Telegram Commands

| Command | Action |
|---|---|
| `/today` | Show today's 3 tasks + current status |
| `/add` | Enter or replace today's 3 tasks |
| `/done N` | Mark task N done |
| `/journal` | Start a journal entry |
| `/silent` | Silent mode for today |
| `/report` | On-demand weekly snapshot |
| `/kill N` | Explicitly abandon task N (prompts for reason) |
| `/stats` | Streak + completion rate |

---

## Data Model

```sql
-- Core identity (one row)
users (id, name, timezone, morning_nudge_time, evening_review_time, created_at)

-- Daily priorities
tasks (
  id, date, position (1-3), text, why,
  status (pending/done/missed/carried/killed),
  carried_from_task_id,
  ai_category, ai_effort_min,
  created_at, completed_at, killed_reason
)

-- Check-in events
checkins (
  id, task_id, sent_at,
  response (done/in_progress/blocked/snooze/reschedule),
  note, responded_at
)

-- Journal (encrypted)
journal_entries (id, created_at, text_encrypted, ai_tags, mood)

-- Evening reflections
reflections (id, date, prompt, response)

-- Generated reports
reports (id, period (week/month/year), start_date, end_date, markdown_content, generated_at)

-- App settings
settings (silent_until, morning_time, evening_time, theme_this_week, last_updated)

Tech Stack
Layer	Choice	Reason
Language	Python 3.12	Best data/AI ecosystem
Bot library	python-telegram-bot (async)	Mature, well-documented
Database	SQLite + SQLCipher (journal table)	Single-user, zero ops, encrypted where needed
Scheduler	APScheduler (persistent jobstore)	In-process, survives restarts
LLM - fast	Claude Haiku 4.5	Categorization, routing, check-in timing
LLM - deep	Claude Sonnet 4.6	Weekly/monthly/yearly reports, task evaluation
Prompt caching	Anthropic SDK cache_control	User context as a cached system prompt
Secrets	python-dotenv + .env	Telegram token, Anthropic key, journal encryption key
Hosting	Fly.io or Hetzner (~$5/mo)	Persistent volume for SQLite
Build Order
Step	What	Why first
1	Telegram bot skeleton + SQLite + /hello + deployed	Proves the plumbing works
2	Morning flow (no AI): enter 3 tasks, stored, listed	Core data loop
3	Scheduler: 7am nudge, 8pm rollover job	Accountability backbone
4	Check-in flow: buttons + heuristic timing	Daily interaction loop
5	AI v1: task evaluation on entry + auto-categorization	First LLM value
6	AI check-in timing: replace heuristic with LLM suggestion	Smarter nudges
7	Journal module (encrypted)	Capture thinking
8	Silent mode command	Quality of life
9	Evening reflection + kill switch	Completing the daily loop
10	Weekly report	First real "wow" moment — polish this
11	Monthly + yearly reports	Long-term value
12	Repeat-offender detection + streaks	Accountability teeth

