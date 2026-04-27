from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
from database.db import SessionLocal, User

RISK_LABELS = {
    "safe":       "🟢 Safe",
    "balanced":   "🟡 Balanced",
    "aggressive": "🔴 Aggressive",
}

RISK_DESCRIPTIONS = {
    "safe":       "Lower odds per leg · higher probability · fewer legs",
    "balanced":   "Best mix of value and safety — recommended for most",
    "aggressive": "Higher odds · more legs · bigger risk & reward",
}


async def risk_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == user_id))
        user = res.scalar_one_or_none()
        current = user.risk_level if user else "balanced"

    current_label = RISK_LABELS.get(current, current.title())
    text = (
        "⚙️ *Risk Profile*\n\n"
        f"Current setting: *{current_label}*\n\n"
        f"🟢 *Safe* — {RISK_DESCRIPTIONS['safe']}\n"
        f"🟡 *Balanced* — {RISK_DESCRIPTIONS['balanced']}\n"
        f"🔴 *Aggressive* — {RISK_DESCRIPTIONS['aggressive']}\n"
    )
    kb = [
        [
            InlineKeyboardButton("🟢 Safe",       callback_data="risk_set_safe"),
            InlineKeyboardButton("🟡 Balanced",   callback_data="risk_set_balanced"),
            InlineKeyboardButton("🔴 Aggressive", callback_data="risk_set_aggressive"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def risk_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    new_risk = q.data[len("risk_set_"):]
    await q.answer(f"✅ Risk set to {new_risk.title()}!")

    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if user:
            user.risk_level = new_risk
            await s.commit()

    label = RISK_LABELS.get(new_risk, new_risk.title())
    desc = RISK_DESCRIPTIONS.get(new_risk, "")
    text = (
        f"✅ Risk profile set to *{label}*\n\n"
        f"_{desc}_"
    )
    kb = [
        [
            InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay"),
            InlineKeyboardButton("⚙️ Change",       callback_data="menu_settings"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    await q.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

