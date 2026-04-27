import logging
import os
from datetime import time as dtime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from dotenv import load_dotenv

from database.db import (
    init_db, get_user, get_unnotified_settled_parlays, mark_parlay_notified,
)
from handlers.start import start, help_command, quick_callback
from handlers.parlay import (
    parlay_command, sport_callback, market_callback, riskmode_callback,
    refresh_callback, track_callback, stake_callback,
    oddsinput_handler, refresh_oddsinput_handler, stake_input_handler,
    history_command,
)
from handlers.settings import (
    settings_command, prefs_callback, units_input_handler,
)
from handlers.analytics import stats_command, leaderboard_command
from handlers.challenges import challenge_command, accept_challenge
from handlers.admin import broadcast_command, stats_admin

from services.tracker import settle_pending
from utils.helpers import format_settlement_message

load_dotenv()
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("parlay")
logging.getLogger("httpx").setLevel(logging.WARNING)


# ─── Periodic jobs ─────────────────────────────────────────────
async def auto_settle_job(ctx: ContextTypes.DEFAULT_TYPE):
    """Settle pending parlays from ESPN scores; DM users their results."""
    try:
        settled = await settle_pending()
    except Exception:
        log.exception("settle_pending crashed")
        return

    if not settled:
        return
    log.info("Auto-settle: %d parlays settled", len(settled))

    # Notify users (only those with notifications enabled)
    pending_notify = get_unnotified_settled_parlays()
    by_id = {r["parlay"]["id"]: r for r in settled}
    for p in pending_notify:
        rec = by_id.get(p["id"])
        if not rec:
            # Already known but maybe missed cache; rebuild minimally
            rec = {"parlay": p, "selections": [], "status": p["status"],
                   "payout": p["actual_payout"]}
        user = get_user(p["user_id"]) or {}
        if not user.get("notifications", 1):
            mark_parlay_notified(p["id"])
            continue
        try:
            text = format_settlement_message(rec)
            await ctx.bot.send_message(p["user_id"], text, parse_mode="Markdown")
        except Exception as e:
            log.warning("Couldn't DM user %s: %s", p["user_id"], e)
        finally:
            mark_parlay_notified(p["id"])


async def post_init(app: Application):
    init_db()
    log.info("Database initialized")
    # Schedule the auto-settle job (hourly)
    interval = int(os.getenv("SETTLE_INTERVAL_SECONDS", "3600"))
    app.job_queue.run_repeating(auto_settle_job, interval=interval, first=20)
    log.info("Auto-settle job scheduled every %ds", interval)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN missing in environment / .env")

    app = (Application.builder()
           .token(token)
           .post_init(post_init)
           .build())

    # ── Commands ────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("parlay", parlay_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("challenge", challenge_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("admin", stats_admin))
    # legacy odds/units commands
    app.add_handler(CommandHandler("odds", oddsinput_handler))
    app.add_handler(CommandHandler("units", units_input_handler))

    # ── Callback queries ────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(quick_callback,    pattern=r"^quick:"))
    app.add_handler(CallbackQueryHandler(sport_callback,    pattern=r"^sport:"))
    app.add_handler(CallbackQueryHandler(market_callback,   pattern=r"^market:"))
    app.add_handler(CallbackQueryHandler(riskmode_callback, pattern=r"^risk:"))
    app.add_handler(CallbackQueryHandler(refresh_callback,  pattern=r"^refresh:"))
    app.add_handler(CallbackQueryHandler(track_callback,    pattern=r"^track:"))
    app.add_handler(CallbackQueryHandler(stake_callback,    pattern=r"^stake:"))
    app.add_handler(CallbackQueryHandler(prefs_callback,    pattern=r"^pref:"))
    app.add_handler(CallbackQueryHandler(accept_challenge,  pattern=r"^chal:"))

    # ── Free-text handlers ──────────────────────────────────────
    # Order matters: stake/units handlers check their own awaiting_* flags first.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, stake_input_handler), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, units_input_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, refresh_oddsinput_handler), group=2)

    log.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
