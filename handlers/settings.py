import logging
from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import async_session, User

logger = logging.getLogger(__name__)


LEGS_CYCLE = [2, 3, 4, 5, 6]
RISK_CYCLE = ["safe", "balanced", "risky"]


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with async_session() as s:
        u = await s.scalar(select(User).where(User.tg_id == uid))
        if not u:
            u = User(tg_id=uid)
            s.add(u)
            await s.commit()
            u = await s.scalar(select(User).where(User.tg_id == uid))

    text = (
        "⚙️ *Settings*\n\n"
        f"Risk: *{u.pref_risk}*\n"
        f"Default legs: *{u.pref_legs}*\n"
        f"Notifications: *{'on' if u.notify else 'off'}*\n\n"
        "Tap to cycle a setting:"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 Risk", callback_data="settings:risk")],
        [InlineKeyboardButton("📊 Default legs", callback_data="settings:legs")],
        [InlineKeyboardButton("🔔 Notify", callback_data="settings:notify")],
    ]
    target = update.effective_message
    if target is None and update.callback_query is not None:
        target = update.callback_query.message
    await target.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    field = query.data.split(":", 1)[1]
    async with async_session() as s:
        u = await s.scalar(select(User).where(User.tg_id == uid))
        if not u:
            u = User(tg_id=uid)
            s.add(u)
            await s.flush()

        if field == "risk":
            i = RISK_CYCLE.index(u.pref_risk) if u.pref_risk in RISK_CYCLE else 1
            u.pref_risk = RISK_CYCLE[(i + 1) % len(RISK_CYCLE)]
        elif field == "legs":
            i = LEGS_CYCLE.index(u.pref_legs) if u.pref_legs in LEGS_CYCLE else 1
            u.pref_legs = LEGS_CYCLE[(i + 1) % len(LEGS_CYCLE)]
        elif field == "notify":
            u.notify = not u.notify

        await s.commit()

        await query.edit_message_text(
            "✅ *Saved.*\n\n"
            f"Risk: *{u.pref_risk}*\n"
            f"Default legs: *{u.pref_legs}*\n"
            f"Notifications: *{'on' if u.notify else 'off'}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 Risk", callback_data="settings:risk")],
                [InlineKeyboardButton("📊 Default legs", callback_data="settings:legs")],
                [InlineKeyboardButton("🔔 Notify", callback_data="settings:notify")],
            ]),
        )
