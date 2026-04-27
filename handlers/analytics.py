from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select
from services.tracker import ParlayTracker
from database.db import SessionLocal, User
from utils.helpers import format_stats


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
    if not user:
        await msg.reply_text("Send /start first.")
        return

    tracker = ParlayTracker()
    try:
        await tracker.settle_pending()
        stats = await tracker.user_stats(user.id)
    finally:
        await tracker.client.close()

    text = format_stats(stats)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await msg.reply_text(text, parse_mode="Markdown")


async def bankroll_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if not user:
            await msg.reply_text("Send /start first.")
            return

        if context.args:
            try:
                amt = float(context.args[0])
                user.bankroll = amt
                await s.commit()
                await msg.reply_text(f"✅ Bankroll set to *{amt:.2f}*", parse_mode="Markdown")
                return
            except ValueError:
                pass

        text = (
            f"💰 *Bankroll Dashboard*\n\n"
            f"Balance: *{user.bankroll:.2f}*\n"
            f"Protected: *{user.profit_protection:.2f}*\n"
            f"Risk: *{user.risk_level}*\n\n"
            f"Use `/bankroll <amount>` to update."
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await msg.reply_text(text, parse_mode="Markdown")
