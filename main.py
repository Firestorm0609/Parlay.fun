import logging
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)
from config import BOT_TOKEN
from database.db import init_db
from handlers.start import start, help_cmd
from handlers.parlay import (
    parlay_cmd, track_callback, regen_callback, set_risk
)
from handlers.challenges import challenges_menu, challenge_callback
from handlers.analytics import stats_cmd, bankroll_cmd

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "menu_main":
        await start(update, context)
    elif data == "menu_parlay":
        await q.edit_message_text(
            "Send `/parlay <odds>` (e.g. `/parlay 4.5`) to build a parlay.",
            parse_mode="Markdown")
    elif data == "menu_challenges":
        await challenges_menu(update, context)
    elif data == "menu_stats":
        await stats_cmd(update, context)
    elif data == "menu_bankroll":
        await bankroll_cmd(update, context)
    elif data == "menu_settings":
        await q.edit_message_text(
            "Use `/risk safe`, `/risk balanced`, or `/risk aggressive`",
            parse_mode="Markdown")
    elif data == "menu_help":
        await help_cmd(update, context)


async def post_init(app):
    await init_db()
    logging.info("DB initialized")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing in .env")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("parlay", parlay_cmd))
    app.add_handler(CommandHandler("risk", set_risk))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("bankroll", bankroll_cmd))
    app.add_handler(CommandHandler("challenge", challenges_menu))

    # Callbacks
    app.add_handler(CallbackQueryHandler(menu_router, pattern=r"^menu_"))
    app.add_handler(CallbackQueryHandler(track_callback, pattern=r"^track_"))
    app.add_handler(CallbackQueryHandler(regen_callback, pattern=r"^regen_"))
    app.add_handler(CallbackQueryHandler(challenge_callback, pattern=r"^chal_"))

    logging.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
