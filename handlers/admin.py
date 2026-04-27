import os
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

from database.db import all_users, get_conn

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def broadcast_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    msg = " ".join(ctx.args) if ctx.args else None
    if not msg:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    sent, failed = 0, 0
    for u in all_users():
        try:
            await ctx.bot.send_message(u["user_id"], f"📢 {msg}")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # avoid Telegram rate-limit

    await update.message.reply_text(f"✅ Sent to {sent} users ({failed} failed).")


async def stats_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    with get_conn() as c:
        users    = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        parlays  = c.execute("SELECT COUNT(*) AS n FROM parlays").fetchone()["n"]
        won      = c.execute("SELECT COUNT(*) AS n FROM parlays WHERE status='won'").fetchone()["n"]
        lost     = c.execute("SELECT COUNT(*) AS n FROM parlays WHERE status='lost'").fetchone()["n"]
        pending  = c.execute("SELECT COUNT(*) AS n FROM parlays WHERE status='pending'").fetchone()["n"]
        volume   = c.execute("SELECT COALESCE(SUM(stake),0) AS v FROM parlays").fetchone()["v"] or 0
    await update.message.reply_text(
        f"👤 Users: *{users}*\n"
        f"🎯 Parlays: *{parlays}* (won {won} / lost {lost} / pending {pending})\n"
        f"💵 Total volume: *{volume:.2f}u*",
        parse_mode="Markdown",
    )
