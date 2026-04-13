"""Scheduler for Jacbot — morning nudge, evening rollover, task check-ins."""

import logging
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from jacbot import config, db

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def setup(app) -> AsyncIOScheduler:
    global _scheduler

    try:
        tz = ZoneInfo(config.TIMEZONE)
    except Exception:
        logger.warning("Invalid TIMEZONE %r, using America/New_York", config.TIMEZONE)
        tz = ZoneInfo("America/New_York")

    mh, mm = _parse_time(config.MORNING_TIME, 7, 0)
    eh, em = _parse_time(config.EVENING_TIME, 20, 0)

    _scheduler = AsyncIOScheduler(timezone=tz)

    rh, rm = _parse_time(config.REPORT_TIME, 18, 0)

    _scheduler.add_job(morning_nudge, CronTrigger(hour=mh, minute=mm, timezone=tz),
                       args=[app], name="morning_nudge", replace_existing=True)
    _scheduler.add_job(evening_rollover, CronTrigger(hour=eh, minute=em, timezone=tz),
                       args=[app], name="evening_rollover", replace_existing=True)

    # Weekly report — Sunday at configured time
    _scheduler.add_job(
        _run_weekly_report, CronTrigger(day_of_week="sun", hour=rh, minute=rm, timezone=tz),
        args=[app], name="weekly_report", replace_existing=True)

    # Monthly report — 1st of each month at 9am
    _scheduler.add_job(
        _run_monthly_report, CronTrigger(day=1, hour=9, minute=0, timezone=tz),
        args=[app], name="monthly_report", replace_existing=True)

    # Yearly report — Jan 1 at 9am
    _scheduler.add_job(
        _run_yearly_report, CronTrigger(month=1, day=1, hour=9, minute=0, timezone=tz),
        args=[app], name="yearly_report", replace_existing=True)

    _scheduler.start()
    logger.info("Scheduler started | morning=%02d:%02d | evening=%02d:%02d | tz=%s",
                mh, mm, eh, em, config.TIMEZONE)
    return _scheduler


def _parse_time(value: str, dh: int, dm: int) -> tuple[int, int]:
    try:
        h, m = map(int, value.split(":"))
        return h, m
    except Exception:
        return dh, dm


async def morning_nudge(app) -> None:
    """7am: warn if <3 fresh tasks entered."""
    today = date.today()
    all_tasks = db.get_tasks_for_date(today)
    fresh_count = sum(1 for t in all_tasks if not t["carried_from_id"])
    if fresh_count >= 3:
        return
    user = db.get_user()
    if not user or not user["telegram_id"]:
        return
    carried = [t for t in all_tasks if t["carried_from_id"]]
    note = (f"\n\nYou have {len(carried)} carried task(s) from yesterday — "
            "those don't count toward your 3.") if carried else ""
    await _send(app, user["telegram_id"],
        f"Good morning! ☀️\n\nYou have {fresh_count}/3 priorities set for today.{note}\n\n"
        "Use /add to lock in your 3 most important tasks.")
    logger.info("Morning nudge sent (fresh=%d)", fresh_count)


async def evening_rollover(app) -> None:
    """8pm: carry unfinished tasks + reflection prompt."""
    today = date.today()
    n = db.carry_over_unfinished(today, today + timedelta(days=1))
    user = db.get_user()
    if not user or not user["telegram_id"]:
        return
    if n > 0:
        msg = (f"End of day 🌙\n\n{n} task{'s' if n > 1 else ''} didn't get done — "
               f"I've moved {'them' if n > 1 else 'it'} to tomorrow.\n\n"
               "Quick reflection: *what got in the way today?*")
    else:
        msg = "All done! 🔥 Great execution today.\n\nQuick reflection: *what was your biggest win?*"
    await _send(app, user["telegram_id"], msg, parse_mode="Markdown")
    logger.info("Evening rollover done (carried=%d)", n)


async def task_checkin(app, task_id: int) -> None:
    """Send an inline-button check-in for a specific task."""
    task = db.get_task_by_id(task_id)
    if not task or task["status"] != "pending":
        return
    if db.is_silent():
        return
    user = db.get_user()
    if not user or not user["telegram_id"]:
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Done",         callback_data=f"ci_done_{task_id}"),
         InlineKeyboardButton("⏳ In progress",  callback_data=f"ci_prog_{task_id}")],
        [InlineKeyboardButton("🚫 Blocked",      callback_data=f"ci_block_{task_id}"),
         InlineKeyboardButton("💤 Snooze 30m",   callback_data=f"ci_snooze_{task_id}")],
        [InlineKeyboardButton("🔁 Reschedule",   callback_data=f"ci_resched_{task_id}")],
    ])
    await _send(app, user["telegram_id"],
        f"Check-in 📋\n\n*{task['text']}*\n\nIs it done yet?",
        parse_mode="Markdown", reply_markup=keyboard)
    logger.info("Check-in sent for task=%d", task_id)


def schedule_checkins_for_today(app) -> None:
    """Spread check-ins evenly between now and 7pm."""
    if not _scheduler:
        return
    now = datetime.now()
    cutoff = datetime.combine(date.today(), time(19, 0))
    if now >= cutoff:
        return
    tasks = [t for t in db.get_tasks_for_date(date.today()) if t["status"] == "pending"]
    if not tasks:
        return
    window = int((cutoff - now).total_seconds() / 60)
    interval = max(30, window // (len(tasks) + 1))
    for i, task in enumerate(tasks, 1):
        run_at = now + timedelta(minutes=interval * i)
        if run_at >= cutoff:
            break
        _scheduler.add_job(task_checkin, "date", run_date=run_at,
                            args=[app, task["id"]],
                            name=f"checkin_{task['id']}", replace_existing=True)
        logger.info("Scheduled check-in: task=%d at %s", task["id"], run_at.strftime("%H:%M"))


async def _run_weekly_report(app) -> None:
    from jacbot.handlers.reports import send_weekly_report
    await send_weekly_report(app)


async def _run_monthly_report(app) -> None:
    from jacbot.handlers.reports import send_monthly_report
    await send_monthly_report(app)


async def _run_yearly_report(app) -> None:
    from jacbot.handlers.reports import send_yearly_report
    await send_yearly_report(app)


async def _send(app, chat_id: int, text: str, **kwargs) -> None:
    try:
        await app.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except Exception as e:
        logger.error("Send failed to %d: %s", chat_id, e)
