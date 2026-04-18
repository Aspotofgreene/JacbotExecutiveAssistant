"""Inline button handlers for task check-in responses."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from jacbot import config, db

logger = logging.getLogger(__name__)


async def handle_checkin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user and update.effective_user.id != config.TELEGRAM_ALLOWED_USER_ID:
        await query.answer("Not authorized.", show_alert=True)
        return
    await query.answer()

    parts = query.data.split("_", 2)
    if len(parts) != 3:
        return
    _, action, task_id_str = parts
    try:
        task_id = int(task_id_str)
    except ValueError:
        return

    task = db.get_task_by_id(task_id)
    if not task:
        await query.edit_message_text("Task not found.")
        return
    if task["status"] == "done":
        await query.edit_message_text(f"✅ *{task['text']}* is already done!", parse_mode="Markdown")
        return

    if action == "done":
        db.mark_task_done(task["id"])
        db.log_checkin(task["id"], "done")
        from datetime import date
        all_tasks = db.get_tasks_for_date(date.today())
        done_count = sum(1 for t in all_tasks if t["status"] == "done")
        total = len(all_tasks)
        msg = f"✅ *{task['text']}* — done!\n\n"
        msg += "All tasks complete! 🔥" if done_count == total else f"_{total - done_count} left today._"
        await query.edit_message_text(msg, parse_mode="Markdown")

    elif action == "prog":
        count = db.log_checkin(task["id"], "in_progress")
        if count >= 2:
            db.suppress_checkins(task["id"])
            msg = f"⏳ *{task['text']}*\n\nGot it — I'll leave you alone on this until 7pm. 💪"
        else:
            msg = f"⏳ *{task['text']}* — still in progress. I'll check back later."
        await query.edit_message_text(msg, parse_mode="Markdown")

    elif action == "block":
        db.log_checkin(task["id"], "blocked")
        await query.edit_message_text(
            f"🚫 *{task['text']}* — blocked.\n\nWhat's in the way? (Reply with a short note.)",
            parse_mode="Markdown")

    elif action == "snooze":
        db.log_checkin(task["id"], "snooze")
        from jacbot.scheduler import get_scheduler, task_checkin
        sched = get_scheduler()
        if sched:
            sched.add_job(task_checkin, "date",
                          run_date=datetime.now() + timedelta(minutes=30),
                          args=[context.application, task["id"]],
                          name=f"snooze_{task['id']}", replace_existing=True)
        await query.edit_message_text(
            f"💤 *{task['text']}* — snoozed 30 minutes.", parse_mode="Markdown")

    elif action == "resched":
        db.log_checkin(task["id"], "reschedule")
        await query.edit_message_text(
            f"🔁 *{task['text']}* — moving it.\n\nWhy is it being rescheduled? (Short note.)",
            parse_mode="Markdown")

    elif action == "kill":
        db.kill_task(task["id"], "Removed via /today")
        await query.edit_message_text(
            f"💀 *{task['text']}* — removed.", parse_mode="Markdown")
