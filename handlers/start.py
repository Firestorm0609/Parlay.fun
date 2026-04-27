import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _main_menu_text(first_name: str) -> str:
    return (
        f"👋 Hey {first_name}!\n\n"
        f"Welcome to *Parlay.fun* — a smart parlay builder powered by live data.\n\n"
        f"What I can do:\n"
        f"• /parlay — build a parlay\n"
        f"• /today — fixtures today\n"
        f"• /stats — your record\n"
        f"• /history — past parlays\n"
        f"• /leaderboard — top users\n"
        f"• /challenges — daily missions\n"
        f"• /settings — preferences\n"
    )


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Build Parlay", callback_data="menu:parlay"),
            InlineKeyboardButton("📅 Today", callback_data="menu:today"),
        ],
        [
            InlineKeyboardButton("📊 My Stats", callback_data="menu:stats"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data="menu:leaderboard"),
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = _main_menu_text(user.first_name)
    keyboard = _main_menu_keyboard()

    if update.message is not None:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )
    elif update.callback_query is not None:
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=keyboard
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text, parse_mode="Markdown", reply_markup=keyboard
            )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = query.data.split(":", 1)[1]
    if target == "parlay":
        from handlers.parlay import parlay_start
        await parlay_start(update, context)
    elif target == "main":
        await start(update, context)
    else:
        await query.edit_message_text(f"Use /{target} to access this section.")
