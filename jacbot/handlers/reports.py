"""
/report command — on-demand weekly snapshot.
Weekly/monthly/yearly reports are also triggered by the scheduler.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from jacbot import ai, db

logger = logging.getLogger(__name__)


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On-demand weekly report."""
    await update.message.reply_text("Generating your weekly report… ⏳")

    today = date.today()
    # Last 7 days
    week_start = today - timedelta(days=6)

    tasks = db.get_tasks_in_range(week_start, today)
    journal_entries = db.get_journal_entries_in_range(week_start, today)

    settings = db.get_settings()
    theme = settings["theme_this_week"] if settings else None

    report = ai.generate_weekly_report(tasks, journal_entries, week_start, today, theme)
    db.save_report("week", week_start, today, report)

    # Split if too long for Telegram (4096 char limit)
    if len(report) <= 4000:
        await update.message.reply_text(report, parse_mode="Markdown")
    else:
        # Send in chunks
        for chunk in _split(report, 4000):
            await update.message.reply_text(chunk, parse_mode="Markdown")

    await update.message.reply_text(
        "Any theme for next week? Reply with one sentence, or skip.",
        parse_mode="Markdown",
    )


async def send_weekly_report(app) -> None:
    """Called by scheduler on Sunday at configured time."""
    user = db.get_user()
    if not user or not user["telegram_id"]:
        return

    today = date.today()
    week_start = today - timedelta(days=6)
    tasks = db.get_tasks_in_range(week_start, today)
    journal_entries = db.get_journal_entries_in_range(week_start, today)
    settings = db.get_settings()
    theme = settings["theme_this_week"] if settings else None

    report = ai.generate_weekly_report(tasks, journal_entries, week_start, today, theme)
    db.save_report("week", week_start, today, report)

    try:
        for chunk in _split(report, 4000):
            await app.bot.send_message(
                chat_id=user["telegram_id"], text=chunk, parse_mode="Markdown"
            )
        await app.bot.send_message(
            chat_id=user["telegram_id"],
            text="Any theme for next week? Reply with one sentence, or /skip.",
        )
    except Exception as e:
        logger.error("Weekly report send failed: %s", e)


async def send_monthly_report(app) -> None:
    """Called by scheduler on first day of each month."""
    user = db.get_user()
    if not user or not user["telegram_id"]:
        return

    today = date.today()
    # Previous month
    if today.month == 1:
        month_start = date(today.year - 1, 12, 1)
        month_end = date(today.year - 1, 12, 31)
    else:
        month_start = date(today.year, today.month - 1, 1)
        # Last day of previous month = day before first of this month
        month_end = date(today.year, today.month, 1) - timedelta(days=1)

    tasks = db.get_tasks_in_range(month_start, month_end)
    journal_entries = db.get_journal_entries_in_range(month_start, month_end)

    report = ai.generate_monthly_report(tasks, journal_entries, month_start, month_end)
    db.save_report("month", month_start, month_end, report)

    try:
        for chunk in _split(report, 4000):
            await app.bot.send_message(
                chat_id=user["telegram_id"], text=chunk, parse_mode="Markdown"
            )
    except Exception as e:
        logger.error("Monthly report send failed: %s", e)


async def send_yearly_report(app) -> None:
    """Called by scheduler on Jan 1."""
    user = db.get_user()
    if not user or not user["telegram_id"]:
        return

    last_year = date.today().year - 1
    year_start = date(last_year, 1, 1)
    year_end = date(last_year, 12, 31)

    tasks = db.get_tasks_in_range(year_start, year_end)
    journal_entries = db.get_journal_entries_in_range(year_start, year_end)

    report = ai.generate_yearly_report(tasks, journal_entries, last_year)
    db.save_report("year", year_start, year_end, report)

    try:
        for chunk in _split(report, 4000):
            await app.bot.send_message(
                chat_id=user["telegram_id"], text=chunk, parse_mode="Markdown"
            )
    except Exception as e:
        logger.error("Yearly report send failed: %s", e)


def _split(text: str, size: int) -> list[str]:
    """Split text into chunks of at most `size` characters at paragraph boundaries."""
    if len(text) <= size:
        return [text]
    chunks = []
    while text:
        if len(text) <= size:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, size)
        if split_at == -1:
            split_at = size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks
