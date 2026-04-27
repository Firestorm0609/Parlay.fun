from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from sqlalchemy import select
from services.parlay_engine import ParlayEngine
from services.tracker import ParlayTracker
from database.db import SessionLocal, User
from utils.helpers import format_parlay


async def parlay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/parlay <target_odds>`\nExample: `/parlay 5.0`",
            parse_mode="Markdown")
        return
    try:
        target = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid odds. Try `/parlay 3.5`")
        return
    await build_and_send(update, context, target)


async def build_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         target_odds: float, challenge=None, stage=None):
    msg = update.message or update.callback_query.message
    status = await msg.reply_text("🔍 Scanning fixtures & odds...")

    async with SessionLocal() as s:
        result = await s.execute(select(User).where(User.tg_id == update.effective_user.id))
        user = result.scalar_one_or_none()
        risk = user.risk_level if user else "balanced"
        user_pk = user.id if user else None

    engine = ParlayEngine()
    try:
        date = datetime.utcnow().strftime("%Y%m%d")
        selections = await engine.gather_selections(date)
        if not selections:
            # try tomorrow
            from datetime import timedelta
            date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y%m%d")
            selections = await engine.gather_selections(date)

        if not selections:
            await status.edit_text("❌ No fixtures with odds found right now. Try later.")
            return

        parlay = engine.build_parlay(selections, target_odds, risk=risk)
        if not parlay:
            await status.edit_text(
                f"❌ Couldn't build a parlay near *{target_odds}* with current risk *{risk}*.\n"
                "Try different odds, change risk via /risk, or come back later.",
                parse_mode="Markdown")
            return

        text = format_parlay(parlay, target_odds)
        if challenge:
            text = f"🏆 *Challenge: {challenge}* — Stage {stage}\n\n" + text

        # store parlay temporarily for tracking
        context.user_data["last_parlay"] = {
            "target": target_odds, "data": parlay,
            "challenge": challenge, "stage": stage,
            "user_pk": user_pk,
        }

        kb = [
            [InlineKeyboardButton("📌 Track This Parlay", callback_data="track_yes")],
            [InlineKeyboardButton("🔁 Regenerate", callback_data=f"regen_{target_odds}")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu_main")],
        ]
        await status.edit_text(text, parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(kb))
    finally:
        await engine.close()


async def track_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = context.user_data.get("last_parlay")
    if not data:
        await q.edit_message_text("⚠️ Nothing to track.")
        return
    if not data["user_pk"]:
        await q.edit_message_text("⚠️ User not found. /start first.")
        return

    tracker = ParlayTracker()
    try:
        pid = await tracker.save_parlay(
            user_id=data["user_pk"],
            target_odds=data["target"],
            parlay=data["data"],
            challenge_type=data["challenge"],
            challenge_stage=data["stage"],
        )
        await q.edit_message_text(
            q.message.text + f"\n\n✅ *Tracking enabled* (ID #{pid})",
            parse_mode="Markdown")
    finally:
        await tracker.client.close()


async def regen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Regenerating...")
    target = float(q.data.split("_")[1])
    await build_and_send(update, context, target)


async def set_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0] not in ("safe", "balanced", "aggressive"):
        await update.message.reply_text("Usage: `/risk safe|balanced|aggressive`",
                                        parse_mode="Markdown")
        return
    new = context.args[0]
    async with SessionLocal() as s:
        result = await s.execute(select(User).where(User.tg_id == update.effective_user.id))
        user = result.scalar_one_or_none()
        if user:
            user.risk_level = new
            await s.commit()
    await update.message.reply_text(f"✅ Risk set to *{new}*", parse_mode="Markdown")
