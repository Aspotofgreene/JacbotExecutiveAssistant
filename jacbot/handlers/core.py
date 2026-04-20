from __future__ import annotations
import logging
from datetime import date, datetime, time, timedelta
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from jacbot import db

logger = logging.getLogger(__name__)
ADD_TASKS = 0
ADD_WHY = 1
JOURNAL_TEXT = 10

def _today() -> date:
    return date.today()

def _format_task_line(task, index: int) -> str:
    icon = {"pending": "⬜", "done": "✅", "missed": "❌", "carried": "🔁", "killed": "💀"}.get(task["status"], "⬜")
    label = f"{icon} {index}. {task['text']}"
    if task["carried_from_id"]:
        label += " _(carried)_"
    return label

def _build_today_message(tasks) -> str:
    if not tasks:
        return "No tasks yet for today.\n\nUse /add to enter your priorities (aim for at least 3)."
    carried = [t for t in tasks if t["carried_from_id"]]
    fresh = [t for t in tasks if not t["carried_from_id"]]
    lines = [f"*Your priorities for {_today().strftime('%A, %b %d')}*\n"]
    if carried:
        lines.append("*Carried over:*")
        for i, t in enumerate(carried, 1):
            lines.append(_format_task_line(t, i))
        lines.append("")
    if fresh:
        if carried:
            lines.append("*Today's priorities:*")
        for i, t in enumerate(fresh, len(carried) + 1):
            lines.append(_format_task_line(t, i))
    done = sum(1 for t in tasks if t["status"] == "done")
    total = len(tasks)
    lines.append(f"\n_{done}/{total} complete_")
    return "\n".join(lines)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.set_telegram_id(user.id)
    await update.message.reply_text(
        f"Hey {user.first_name}! I'm Jacbot, your personal executive assistant.\n\n"
        "Every morning I'll ask for your *top priorities* for the day — aim for at least 3. "
        "I'll check in through the day, keep you accountable, and at the end of "
        "each week give you an honest summary of what you shipped.\n\n"
        "/today — see today's tasks\n"
        "/add — enter your priorities\n"
        "/done N — mark task N complete\n"
        "/report — generate a weekly summary (anytime)\n"
        "/journal — add a journal entry\n"
        "/silent — no nudges today\n"
        "/stats — streak & completion rate\n"
        "/kill N — abandon task N\n\n"
        "Let's go. What are you working on today? /add",
        parse_mode="Markdown",
    )

async def cmd_hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Jacbot is alive and watching. Let's get things done.")

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    tasks = db.get_tasks_for_date(_today())

    # Send the task list
    await update.message.reply_text(_build_today_message(tasks), parse_mode="Markdown")

    # Show buttons for pending tasks, and for carried tasks (after evening rollover)
    actionable = [t for t in tasks if t["status"] in ("pending", "carried")]
    for t in actionable:
        tid = t["id"]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Done",        callback_data=f"ci_done_{tid}"),
             InlineKeyboardButton("⏳ In progress", callback_data=f"ci_prog_{tid}")],
            [InlineKeyboardButton("🚫 Blocked",     callback_data=f"ci_block_{tid}"),
             InlineKeyboardButton("💤 Snooze 30m",  callback_data=f"ci_snooze_{tid}")],
            [InlineKeyboardButton("🔁 Reschedule",  callback_data=f"ci_resched_{tid}"),
             InlineKeyboardButton("💀 Kill",        callback_data=f"ci_kill_{tid}")],
        ])
        await update.message.reply_text(
            f"*{t['text']}*", parse_mode="Markdown", reply_markup=keyboard
        )

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    all_tasks = db.get_tasks_for_date(_today())
    fresh = [t for t in all_tasks if not t["carried_from_id"]]
    carried = [t for t in all_tasks if t["carried_from_id"]]

    msg = ""
    if fresh:
        msg += "*Already set today:*\n"
        for i, t in enumerate(fresh, 1):
            msg += f"{i}. {t['text']}\n"
        msg += "\nWhat else do you want to add?\n\n"
    else:
        msg += "What are your *priorities for today*? Aim for at least 3.\n\n"

    if carried:
        msg += f"_{len(carried)} carried task(s) from yesterday — tracked separately._\n\n"

    msg += "Send as a numbered list:\n1. Draft proposal for client X\n2. Fix login bug\n\nOr /cancel to bail."
    await update.message.reply_text(msg, parse_mode="Markdown")
    return ADD_TASKS

async def add_receive_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import re
    lines = [l.strip() for l in update.message.text.strip().splitlines() if l.strip()]
    cleaned = []
    for line in lines:
        # Strip any leading number prefix (1. 2) 10. etc) or bullet (- *)
        line = re.sub(r"^\d+[.)]\s*", "", line).lstrip("-* ").strip()
        if line:
            cleaned.append(line)
    if len(cleaned) < 1:
        await update.message.reply_text("Send at least 1 task, or /cancel.")
        return ADD_TASKS

    context.user_data["pending_tasks"] = cleaned
    n = len(cleaned)
    await update.message.reply_text(
        f"Got it — {n} task{'s' if n > 1 else ''}. Want to add a quick *why* for each?\n\n"
        "Send one reason per line, or type *skip* to lock them in now.",
        parse_mode="Markdown"
    )
    return ADD_WHY

async def add_receive_why(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    tasks = context.user_data.get("pending_tasks", [])
    n = len(tasks)
    whys: list[str | None] = [None] * n
    if raw.lower() != "skip":
        why_lines = [l.strip() for l in raw.splitlines() if l.strip()]
        for i in range(min(n, len(why_lines))):
            whys[i] = why_lines[i] or None

    # AI evaluation — runs before saving so we can show feedback
    await update.message.reply_text("Analysing your tasks… ⚡", parse_mode="Markdown")
    from jacbot import ai
    evaluations = ai.evaluate_tasks(tasks, whys)

    # Build feedback message
    feedback_lines = ["Here's my take on your tasks:\n"]
    final_tasks = []
    has_suggestions = False
    for ev in evaluations:
        suggestion = ev.get("suggestion", ev["original"])
        issues = ev.get("issues", [])
        feedback = ev.get("feedback", "")
        effort = ev.get("effort_min", 60)
        final_tasks.append(suggestion)

        line = f"*{ev['original']}*"
        if suggestion != ev["original"]:
            has_suggestions = True
            line += f"\n  → _{suggestion}_"
        if issues:
            line += f"\n  ⚠️ {', '.join(issues)}"
        line += f"\n  {feedback} (~{effort}min)"
        feedback_lines.append(line)

    feedback_msg = "\n\n".join(feedback_lines)
    if has_suggestions:
        feedback_msg += "\n\n_I've used the suggested versions. Reply 'keep mine' to use your originals._"

    await update.message.reply_text(feedback_msg, parse_mode="Markdown")

    # Append new tasks after any that are already set today
    fresh_existing = [t for t in db.get_tasks_for_date(_today()) if not t["carried_from_id"]]
    next_pos = len(fresh_existing) + 1
    task_ids = []
    for i, (task_text, why) in enumerate(zip(final_tasks, whys), next_pos):
        task_id = db.add_task(_today(), i, task_text, why)
        task_ids.append(task_id)

    # Categorize and update tasks
    categories = ai.categorize_tasks(final_tasks)
    for task_id, category in zip(task_ids, categories):
        db.set_task_category(task_id, category)

    # Check for repeat-offender carried tasks
    carried_tasks = [t for t in db.get_tasks_for_date(_today()) if t["carried_from_id"]]
    repeat_warnings = []
    for t in carried_tasks:
        days_carried = db.count_days_carried(t["id"])
        if days_carried >= 3:
            repeat_warnings.append(
                f"⚠️ *{t['text']}* has been carried {days_carried} days. "
                "Break it down, do it today, or /kill it."
            )

    # Schedule check-ins
    from jacbot.scheduler import schedule_checkins_for_today
    schedule_checkins_for_today(context.application)

    all_tasks = db.get_tasks_for_date(_today())
    fresh_count = sum(1 for t in all_tasks if not t["carried_from_id"])
    final_msg = "Locked in! Here's your day:\n\n" + _build_today_message(all_tasks) + "\n\nGo get it. 💪"
    if fresh_count < 3:
        needed = 3 - fresh_count
        final_msg += f"\n\n_You're {needed} goal{'s' if needed > 1 else ''} short of your minimum 3. Use /add to keep going — I'll remind you at 8am if you're still under._"
    await update.message.reply_text(final_msg, parse_mode="Markdown")

    if repeat_warnings:
        await update.message.reply_text("\n\n".join(repeat_warnings), parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END

async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Use /add when you're ready.")
    return ConversationHandler.END

async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /done N")
        return
    tasks = db.get_tasks_for_date(_today())
    ordered = [t for t in tasks if t["carried_from_id"]] + [t for t in tasks if not t["carried_from_id"]]
    pos = int(args[0])
    if pos < 1 or pos > len(ordered):
        await update.message.reply_text(f"No task {pos}. Use /today to see task numbers.")
        return
    task = ordered[pos - 1]
    if task["status"] == "done":
        await update.message.reply_text(f"Task {pos} is already done.")
        return
    db.mark_task_done(task["id"])
    all_tasks = db.get_tasks_for_date(_today())
    done_count = sum(1 for t in all_tasks if t["status"] == "done")
    total = len(all_tasks)
    msg = f"✅ *{task['text']}* — done!\n\n"
    msg += "That's all of them! Great day. 🔥" if done_count == total else f"_{total - done_count} task{'s' if total - done_count > 1 else ''} left._"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /kill N [reason]")
        return
    tasks = db.get_tasks_for_date(_today())
    ordered = [t for t in tasks if t["carried_from_id"]] + [t for t in tasks if not t["carried_from_id"]]
    pos = int(args[0])
    reason = " ".join(args[1:]) if len(args) > 1 else "No reason given"
    if pos < 1 or pos > len(ordered):
        await update.message.reply_text(f"No task {pos}. Use /today to see task numbers.")
        return
    task = ordered[pos - 1]
    db.kill_task(task["id"], reason)
    await update.message.reply_text(f"💀 *{task['text']}* killed.\nReason: _{reason}_\n\nLogged for your weekly summary.", parse_mode="Markdown")

async def cmd_silent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tonight = datetime.combine(date.today() + timedelta(days=1), time.min)
    db.set_silent_until(tonight)
    await update.message.reply_text("Silent mode on. No nudges until tomorrow. 🤫")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with db.get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tasks WHERE carried_from_id IS NULL").fetchone()[0]
        done = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done' AND carried_from_id IS NULL").fetchone()[0]
        rows = conn.execute("""SELECT date, SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done_count, COUNT(*) AS total FROM tasks WHERE carried_from_id IS NULL GROUP BY date ORDER BY date DESC""").fetchall()
    streak = 0
    for row in rows:
        if row["date"] == date.today().isoformat():
            continue
        if row["done_count"] == row["total"] and row["total"] > 0:
            streak += 1
        else:
            break
    rate = f"{round(done / total * 100)}%" if total else "n/a"
    await update.message.reply_text(f"📊 *Your stats*\n\nCompletion rate: *{rate}* ({done}/{total} tasks)\nStreak: *{streak} day{'s' if streak != 1 else ''}* with all tasks done", parse_mode="Markdown")

async def cmd_journal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("📓 What's on your mind? Write anything — ideas, blockers, wins, reflections.\n\n/cancel to exit.")
    return JOURNAL_TEXT

async def journal_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Nothing to save. Try again or /cancel.")
        return JOURNAL_TEXT
    entry_id = db.add_journal_entry(text)
    await update.message.reply_text(f"Saved 📓 _(Entry #{entry_id})_\n\nIt'll appear in your weekly summary.", parse_mode="Markdown")
    return ConversationHandler.END

async def journal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Journal cancelled.")
    return ConversationHandler.END
