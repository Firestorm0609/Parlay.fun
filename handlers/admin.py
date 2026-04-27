from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_bot_stats


async def bot_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show live bot usage stats — total users, online now, active today."""
    stats = await get_bot_stats(online_minutes=5)

    total   = stats["total"]
    online  = stats["online"]
    today   = stats["today"]
    minutes = stats["online_minutes"]

    # Build a simple bar for visual flair
    def dot_bar(n, cap=20):
        filled = min(n, cap)
        return "🟢" * filled + "⚪" * (cap - filled)

    online_bar = dot_bar(online)

    text = (
        f"🌐 *Parlay.fun — Live Bot Stats*\n\n"
        f"👥 *Total Users:*   `{total:,}`\n"
        f"🟢 *Online Now:*    `{online:,}` _(active last {minutes} min)_\n"
        f"📅 *Active Today:*  `{today:,}`\n\n"
        f"{online_bar}\n\n"
        f"_Stats refresh every time you open this screen._"
    )

    kb = [
        [
            InlineKeyboardButton("🔄 Refresh",    callback_data="menu_botstats"),
            InlineKeyboardButton("🏠 Main Menu",  callback_data="menu_main"),
        ]
    ]
    markup = InlineKeyboardMarkup(kb)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=markup)
