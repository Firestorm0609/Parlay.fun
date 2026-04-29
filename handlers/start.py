from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_or_create_user


def _main_menu_markup():
    kb = [
        [InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay")],
        [
            InlineKeyboardButton("🏆 Challenges", callback_data="menu_challenges"),
            InlineKeyboardButton("📊 My Stats",   callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton("💰 Bankroll",    callback_data="menu_bankroll"),
            InlineKeyboardButton("⚙️ Risk Profile", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard"),
            InlineKeyboardButton("🤖 Smart Bet",   callback_data="menu_smartbet"),
        ],
        [
            InlineKeyboardButton("👥 Bot Stats", callback_data="menu_botstats"),
            InlineKeyboardButton("❓ Help",       callback_data="menu_help"),
        ],
    ]
    return InlineKeyboardMarkup(kb)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username)

    text = (
        f"👋 Welcome, *{user.first_name}*!\n\n"
        "I'm your *Advanced Parlay & Odds Selector*.\n"
        "I generate smart parlays using real fixtures, odds analysis, "
        "and your chosen risk profile.\n\n"
        "Choose an option below:"
    )
    markup = _main_menu_markup()
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ *How to Use Parlay.fun*\n\n"
        "🎯 *Build Parlay* — Choose target odds, get smart selections\n"
        "🏆 *Challenges* — Rollover & longshot multi-stage challenges\n"
        "📊 *My Stats* — Win rate, profit, ROI & history\n"
        "💰 *Bankroll* — Set and track your balance (custom amounts supported)\n"
        "⚙️ *Risk Profile* — Safe / Balanced / Aggressive\n"
        "👥 *Bot Stats* — See how many users are online & total registered\n\n"
        "*Markets:* 1X2 · Double Chance · Over/Under · BTTS\n"
        "*Data Source:* ESPN fixtures + DraftKings odds\n\n"
        "💡 _Tip: Higher target odds = more legs = more risk._\n"
        "💡 _Profit protection locks 30% of winnings automatically._"
    )
    kb = [
        [
            InlineKeyboardButton("👥 Bot Stats", callback_data="menu_botstats"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ]
    ]
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
