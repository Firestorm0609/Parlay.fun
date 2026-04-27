from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import upsert_user
from handlers.parlay import parlay_command
from handlers.analytics import stats_command, leaderboard_command
from handlers.settings import settings_command


WELCOME = """
🎰 *Welcome to ParlayBot* 🎰

Smart sports parlays from real-time ESPN data:

⚽🏀🏈⚾🏒  5 sports
📊  4 risk tiers
🎚️  8 market filters
📌  Track / auto-settle
🏆  Leaderboard & 1v1 challenges

*Commands*
/parlay – Build a parlay
/stats  – Your performance
/history – Recent parlays
/leaderboard – Top players
/challenge – Challenge a user
/settings – Preferences
/help – Full guide
"""


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username, user.first_name)
    kb = [
        [InlineKeyboardButton("🎯 Build Parlay", callback_data="quick:parlay")],
        [InlineKeyboardButton("📊 My Stats", callback_data="quick:stats"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="quick:lb")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="quick:settings")],
    ]
    await update.message.reply_text(
        WELCOME, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "*ParlayBot Help*\n\n"
        "1. /parlay → choose sport → choose market → choose risk\n"
        "2. Bot pulls live games and crafts a parlay\n"
        "3. Tap *📌 Track* and pick a stake to log it\n"
        "4. The bot auto-settles when results come in and DMs you\n\n"
        "*Risk levels*\n"
        "🟢 Safe — 3 high-prob picks\n"
        "🟡 Balanced — 4 mixed picks\n"
        "🔴 Risky — 5 picks incl. underdogs\n"
        "☠️ Lottery — 6 moonshots\n\n"
        "*Markets*\n"
        "🏆 Win | 🤝 Draw | ⚽ Goals (O/U) | 🥅 BTTS\n"
        "🛡️ Win or Draw (DC) | 📏 Spread | 🎯 Correct Score\n\n"
        "Tip: tweak default unit-size in /settings."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def quick_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Route the start-screen shortcut buttons to their command handlers."""
    q = update.callback_query
    await q.answer()
    action = q.data.split(":", 1)[1]

    fake = _FakeUpdate(update)
    if action == "parlay":
        await parlay_command(fake, ctx)
    elif action == "stats":
        await stats_command(fake, ctx)
    elif action == "lb":
        await leaderboard_command(fake, ctx)
    elif action == "settings":
        await settings_command(fake, ctx)


class _FakeUpdate:
    """Minimal shim so command handlers can run from a callback query."""
    def __init__(self, real_update: Update):
        self._u = real_update
        self.effective_user = real_update.effective_user
        self.effective_chat = real_update.effective_chat
        self.message = real_update.callback_query.message  # has reply_text
        self.callback_query = None
