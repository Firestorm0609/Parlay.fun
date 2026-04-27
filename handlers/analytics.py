import logging
from sqlalchemy import select, desc
from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session, User, Parlay
from services.espn_api import get_today_fixtures

logger = logging.getLogger(__name__)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with async_session() as s:
        u = await s.scalar(select(User).where(User.tg_id == uid))
        if not u:
            await update.message.reply_text("No history yet. Build a parlay with /parlay!")
            return

        rows = (await s.execute(
            select(Parlay).where(Parlay.user_id == u.id)
        )).scalars().all()

    total = len(rows)
    won = sum(1 for r in rows if r.status == "won")
    lost = sum(1 for r in rows if r.status == "lost")
    pending = sum(1 for r in rows if r.status == "pending")
    win_rate = (won / max(1, won + lost)) * 100

    profit = 0.0
    for r in rows:
        if r.status == "won":
            odds = r.actual_odds or r.total_odds
            profit += (odds - 1) * (r.stake or 0)
        elif r.status == "lost":
            profit -= (r.stake or 0)

    text = (
        f"📊 *Your Stats*\n\n"
        f"Total parlays: *{total}*\n"
        f"✅ Won: {won}\n"
        f"❌ Lost: {lost}\n"
        f"⏳ Pending: {pending}\n"
        f"Win rate: *{win_rate:.1f}%*\n"
        f"Net profit: *{profit:+.2f}u*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with async_session() as s:
        u = await s.scalar(select(User).where(User.tg_id == uid))
        if not u:
            await update.message.reply_text("Nothing here yet.")
            return
        parlays = (await s.execute(
            select(Parlay).where(Parlay.user_id == u.id).order_by(desc(Parlay.created_at)).limit(10)
        )).scalars().all()

    if not parlays:
        await update.message.reply_text("No parlays yet.")
        return

    lines = ["🗂 *Recent Parlays*\n"]
    for p in parlays:
        icon = {"won": "✅", "lost": "❌", "pending": "⏳", "void": "⚪️"}.get(p.status, "•")
        odds = p.actual_odds or p.total_odds
        lines.append(
            f"{icon} #{p.id} — {odds}x — {p.risk} — {p.created_at.strftime('%d/%m')}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as s:
        users = (await s.execute(select(User))).scalars().all()
        rows = []
        for u in users:
            parlays = (await s.execute(
                select(Parlay).where(Parlay.user_id == u.id, Parlay.status.in_(["won", "lost"]))
            )).scalars().all()
            if not parlays:
                continue
            won = sum(1 for p in parlays if p.status == "won")
            total = len(parlays)
            wr = won / total * 100
            rows.append((u, won, total, wr))

    rows.sort(key=lambda x: (x[3], x[1]), reverse=True)
    lines = ["🏆 *Leaderboard*\n"]
    for i, (u, won, total, wr) in enumerate(rows[:10], 1):
        name = u.username or f"user{u.tg_id}"
        lines.append(f"{i}. @{name} — {won}/{total} ({wr:.0f}%)")
    if len(lines) == 1:
        lines.append("Nobody has a settled parlay yet.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fixtures = await get_today_fixtures()
    if not fixtures:
        await update.message.reply_text("No fixtures today (or ESPN is grumpy).")
        return
    lines = ["📅 *Today's Fixtures*\n"]
    for fx in fixtures[:25]:
        lines.append(f"• {fx['home']} vs {fx['away']} — _{fx.get('league','')}_")
    if len(fixtures) > 25:
        lines.append(f"\n_+{len(fixtures)-25} more_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
