from telegram import Update
from telegram.ext import ContextTypes

from database.db import user_stats, leaderboard


async def stats_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = user_stats(update.effective_user.id)
    if not s or s.get("total", 0) == 0:
        await update.message.reply_text("📊 No parlays yet. Run /parlay to start.")
        return

    total   = s.get("total", 0) or 0
    wins    = s.get("wins", 0) or 0
    losses  = s.get("losses", 0) or 0
    pending = s.get("pending", 0) or 0
    staked  = s.get("total_staked", 0) or 0
    won     = s.get("total_won", 0) or 0
    biggest = s.get("biggest_odds", 0) or 0
    profit  = won - staked
    settled = wins + losses
    wr      = (wins / settled * 100) if settled else 0
    roi     = (profit / staked * 100) if staked else 0

    streak_n = s.get("streak", 0) or 0
    streak_t = s.get("streak_type")
    streak_line = ""
    if streak_n:
        emoji = "🔥" if streak_t == "won" else "🥶"
        streak_line = f"{emoji} Current streak: *{streak_n} {streak_t}*\n"

    text = (
        "📊 *Your Stats*\n\n"
        f"🎯 Total parlays:   *{total}*\n"
        f"✅ Wins:               *{wins}*\n"
        f"❌ Losses:            *{losses}*\n"
        f"⏳ Pending:           *{pending}*\n"
        f"📈 Win rate:           *{wr:.1f}%*\n"
        f"💵 Staked:            *{staked:.2f}u*\n"
        f"🏆 Won:                *{won:.2f}u*\n"
        f"💰 Profit:              *{profit:+.2f}u*\n"
        f"⚡ ROI:                 *{roi:+.1f}%*\n"
        f"🚀 Biggest odds:   *{biggest:.2f}*\n"
        f"{streak_line}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def leaderboard_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = leaderboard(10)
    if not rows:
        await update.message.reply_text("Leaderboard empty — be the first to /parlay!")
        return
    lines = ["🏆 *Top Parlay Players*\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        name = r["username"] or r["first_name"] or f"User{r['user_id']}"
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(
            f"{prefix} *{name}* — {r['parlays']} parlays | "
            f"{r['wins']} W | profit *{r['profit']:+.2f}u*"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
