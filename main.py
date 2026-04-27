import logging
import os
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from database.db import init_db
from handlers.start import start, help_cmd, button_handler
from handlers.parlay import (
    parlay_start,
    parlay_callback,
    track_callback,
    handle_odds_input,
)
from handlers.analytics import stats, history, leaderboard, today
from handlers.challenges import challenges, challenge_callback
from handlers.settings import settings_cmd, settings_callback
from handlers.admin import broadcast
from services.tracker import settle_pending

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


SETTLE_INTERVAL = int(os.getenv("SETTLE_INTERVAL", "3600"))


async def auto_settle_job(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job: settle pending parlays and notify owners."""
    try:
        results = await settle_pending()
    except Exception:
        logger.exception("settle_pending crashed")
        return

    if not results:
        return

    for item in results:
        if not item.get("notify", True):
            continue
        tg_id = item.get("tg_id")
        if not tg_id:
            continue

        status = item["status"]
        odds = item.get("actual_odds") or item.get("total_odds") or 0
        stake = item.get("stake") or 0
        if status == "won":
            profit = round((odds - 1) * stake, 2) if stake else 0
            text = (
                f"✅ *Parlay #{item['parlay_id']} WON!*\n"
                f"Odds: *{odds}x*"
            )
            if stake:
                text += f"\nStake: {stake}u → Profit: *+{profit}u*"
        elif status == "lost":
            text = (
                f"❌ *Parlay #{item['parlay_id']} lost.*\n"
                f"Odds: {odds}x"
            )
            if stake:
                text += f"\nStake: -{stake}u"
        else:
            continue

        try:
            await context.bot.send_message(
                chat_id=tg_id, text=text, parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning("notify failed for %s: %s", tg_id, e)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN env var required")

    app = Application.builder().token(token).build()

    init_db()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("parlay", parlay_start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("challenges", challenges))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^(menu|help)"))
    app.add_handler(CallbackQueryHandler(parlay_callback, pattern=r"^parlay:"))
    app.add_handler(CallbackQueryHandler(track_callback, pattern=r"^track:"))
    app.add_handler(CallbackQueryHandler(challenge_callback, pattern=r"^challenge:"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^settings:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_odds_input))

    if app.job_queue is not None:
        app.job_queue.run_repeating(
            auto_settle_job,
            interval=SETTLE_INTERVAL,
            first=60,
            name="auto_settle",
        )
    else:
        logger.warning(
            "JobQueue not available — install python-telegram-bot[job-queue]. "
            "Auto-settlement disabled."
        )

    app.run_polling()


if __name__ == "__main__":
    main()
