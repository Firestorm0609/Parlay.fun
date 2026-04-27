import logging
from sqlalchemy import select, func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import async_session, User, Parlay

logger = logging.getLogger(__name__)


async def challenges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    active_count = 0
    async with async_session() as s:
        u = await s.scalar(select(User).where(User.tg_id == uid))
        if u:
            active_count = await s.scalar(
                select(func.count(Parlay.id)).where(
                    Parlay.user_id == u.id,
                    Parlay.status == "pending",
                )
            ) or 0

    text = (
        "🎖 *Daily Challenges*\n\n"
        f"⏳ Active parlays: *{active_count}*\n\n"
        "1. Build a parlay today (+10 XP)\n"
        "2. Hit a 5+ odds parlay (+50 XP)\n"
        "3. Track 3 parlays in a row (+25 XP)\n\n"
        "_(XP system coming soon — for now just bragging rights.)_"
    )
    keyboard = [[InlineKeyboardButton("Refresh", callback_data="challenge:refresh")]]
    target = update.effective_message
    if target is None and update.callback_query is not None:
        target = update.callback_query.message
    await target.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "challenge:refresh":
        await challenges(update, context)
