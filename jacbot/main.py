"""Jacbot Executive Assistant — entry point. Run with: python -m jacbot.main"""

import logging

from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, ConversationHandler, filters,
)

from jacbot import config, db, scheduler
from jacbot.handlers.core import (
    cmd_start, cmd_hello, cmd_today, cmd_done, cmd_kill, cmd_silent, cmd_stats,
    ADD_TASKS, ADD_WHY, cmd_add, add_receive_tasks, add_receive_why, add_cancel,
    JOURNAL_TEXT, cmd_journal, journal_receive_text, journal_cancel,
)
from jacbot.handlers.checkin import handle_checkin_callback
from jacbot.handlers.reports import cmd_report

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    scheduler.setup(app)
    logger.info("Scheduler running")


def main() -> None:
    db.init_db()

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Simple commands
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("hello",  cmd_hello))
    app.add_handler(CommandHandler("today",  cmd_today))
    app.add_handler(CommandHandler("done",   cmd_done))
    app.add_handler(CommandHandler("kill",   cmd_kill))
    app.add_handler(CommandHandler("silent", cmd_silent))
    app.add_handler(CommandHandler("stats",  cmd_stats))
    app.add_handler(CommandHandler("report", cmd_report))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_checkin_callback, pattern=r"^ci_"))

    # /add conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", cmd_add)],
        states={
            ADD_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_receive_tasks)],
            ADD_WHY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_receive_why)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    ))

    # /journal conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("journal", cmd_journal)],
        states={
            JOURNAL_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, journal_receive_text)],
        },
        fallbacks=[CommandHandler("cancel", journal_cancel)],
    ))

    logger.info("Jacbot starting…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
