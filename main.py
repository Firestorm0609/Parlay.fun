import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from config import BOT_TOKEN
from database.db import init_db, touch_user
from handlers.start import start, help_handler
from handlers.parlay import (
    parlay_menu, parlay_odds_callback, parlay_custom_callback,
    handle_custom_odds, track_callback, regen_callback,
)
from handlers.analytics import (
    stats_handler, bankroll_handler, bankroll_set_callback,
    bankroll_custom_prompt, handle_custom_balance,
    currency_menu, currency_set_callback, smart_bet_handler,
    leaderboard_handler,
)
from handlers.challenges import challenges_menu, challenge_callback
from handlers.settings import risk_menu, risk_set_callback
from handlers.admin import bot_stats_handler
from services.odds_watcher import active_watches

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)


# ─── Presence middleware ───────────────────────────────────────────────

async def presence_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update last_seen on every interaction so online-count stays accurate."""
    if update.effective_user:
        await touch_user(update.effective_user.id)


# ─── Menu router ──────────────────────────────────────────────────────

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "menu_main":
        await start(update, context)
    elif data == "menu_parlay":
        await parlay_menu(update, context)
    elif data == "menu_challenges":
        await challenges_menu(update, context)
    elif data == "menu_stats":
        await stats_handler(update, context)
    elif data == "menu_bankroll":
        await bankroll_handler(update, context)
    elif data == "menu_settings":
        await risk_menu(update, context)
    elif data == "menu_help":
        await help_handler(update, context)
    elif data == "menu_botstats":
        await bot_stats_handler(update, context)
    elif data == "menu_leaderboard":
        await leaderboard_handler(update, context)


# ─── Text input router ────────────────────────────────────────────────

async def text_input_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route typed messages to the active input handler (balance or odds)."""
    if await handle_custom_balance(update, context):
        return
    await handle_custom_odds(update, context)


# ─── Startup ──────────────────────────────────────────────────────────

async def post_init(app):
    await init_db()
    logging.info("DB initialized")
    # Store active_watches reference in bot_data for cleanup
    app.bot_data["active_watches"] = active_watches


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing in config")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # ── Presence tracking — runs before every handler ──────────────────────
    app.add_handler(
        MessageHandler(filters.ALL, presence_middleware), group=-1)
    app.add_handler(
        CallbackQueryHandler(presence_middleware, pattern=r".*"), group=-1)

    # ── Commands ────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("botstats", bot_stats_handler))
    app.add_handler(CommandHandler("smart-bet", smart_bet_handler))
    app.add_handler(CommandHandler("leaderboard", leaderboard_handler))

    # ── Menu routing ────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(menu_router,            pattern=r"^menu_"))

    # ── Parlay ──────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(parlay_odds_callback,   pattern=r"^parlay_odds_"))
    app.add_handler(CallbackQueryHandler(parlay_custom_callback, pattern=r"^parlay_custom$"))
    app.add_handler(CallbackQueryHandler(track_callback,         pattern=r"^track_"))
    app.add_handler(CallbackQueryHandler(regen_callback,         pattern=r"^regen_"))

    # ── Challenges ──────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(challenge_callback,     pattern=r"^chal_"))

    # ── Settings ────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(risk_set_callback,      pattern=r"^risk_set_"))

    # ── Bankroll & currency ─────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(bankroll_set_callback,  pattern=r"^bankroll_set_"))
    app.add_handler(CallbackQueryHandler(bankroll_custom_prompt, pattern=r"^bankroll_custom$"))
    app.add_handler(CallbackQueryHandler(currency_menu,          pattern=r"^bankroll_currency$"))
    app.add_handler(CallbackQueryHandler(currency_set_callback,  pattern=r"^currency_set_"))

    # ── Text input (custom odds / custom balance) ───────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_router))

    logging.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
