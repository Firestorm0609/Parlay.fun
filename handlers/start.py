from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_or_create_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username)

    text = (
        f"👋 Welcome, *{user.first_name}*!\n\n"
        "I'm your *Advanced Parlay & Odds Selector*.\n"
        "I generate intelligent parlays based on real data, odds analysis, "
        "and your risk preferences.\n\n"
        "Choose an option below:"
    )
    kb = [
        [InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay")],
        [InlineKeyboardButton("🏆 Challenges", callback_data="menu_challenges")],
        [InlineKeyboardButton("📊 My Stats", callback_data="menu_stats")],
        [InlineKeyboardButton("💰 Bankroll", callback_data="menu_bankroll")],
        [InlineKeyboardButton("⚙️ Settings (Risk)", callback_data="menu_settings")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ]
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*Commands:*\n"
        "/start — main menu\n"
        "/parlay <odds> — build parlay (e.g. `/parlay 5.0`)\n"
        "/challenge — start a rollover/longshot\n"
        "/stats — your performance\n"
        "/risk <safe|balanced|aggressive>\n"
        "/bankroll <amount>\n\n"
        "*Markets supported:* 1X2, Double Chance, Over/Under, BTTS\n"
        "*Risk profiles:* Safe, Balanced, Aggressive\n"
        "*Data:* ESPN API + DraftKings odds"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
