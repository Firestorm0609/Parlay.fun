"""
Parlay flow:

  /parlay → sport → market filter → risk → generate
  Track button → prompts for stake → saves with full context
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.parlay_engine import generate_parlay, gather_selections
from services.analytics import compute_total_odds
from database.db import (
    save_parlay, get_user, upsert_user, user_recent_parlays, get_selections
)
from utils.helpers import (
    format_parlay, parse_odds_input, parse_stake_input,
    format_track_confirmation, md_escape, SPORT_EMOJI,
)

SPORTS = [
    ("⚽ Soccer", "soccer"),
    ("🏀 Basketball", "basketball"),
    ("🏈 NFL", "football"),
    ("⚾ MLB", "baseball"),
    ("🏒 NHL", "hockey"),
]

RISK_MODES = [
    ("🟢 Safe (3 picks)", "safe"),
    ("🟡 Balanced (4 picks)", "balanced"),
    ("🔴 Risky (5 picks)", "risky"),
    ("☠️ Lottery (6 picks)", "lottery"),
]

MARKET_FILTERS = [
    ("🌐 Any", "any"),
    ("🏆 Win (ML)", "win"),
    ("🤝 Draw", "draw"),
    ("⚽ Goals (O/U)", "goals"),
    ("🥅 BTTS", "btts"),
    ("🛡️ Win or Draw (DC)", "dc"),
    ("📏 Spread", "spread"),
    ("🎯 Correct Score", "correctscore"),
]


# ─── /parlay ──────────────────────────────────────────────────
async def parlay_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username, user.first_name)
    kb = [[InlineKeyboardButton(t, callback_data=f"sport:{c}")] for t, c in SPORTS]
    await update.message.reply_text(
        "🎯 *Pick a sport*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def sport_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    sport = q.data.split(":", 1)[1]
    ctx.user_data["sport"] = sport

    filters = MARKET_FILTERS if sport == "soccer" else [
        f for f in MARKET_FILTERS if f[1] in ("any", "win", "goals", "spread")
    ]
    kb = [[InlineKeyboardButton(t, callback_data=f"market:{c}")] for t, c in filters]
    em = SPORT_EMOJI.get(sport, "🎯")
    await q.edit_message_text(
        f"{em} *Sport:* `{sport.title()}`\n\n*Choose a market filter:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def market_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    market = q.data.split(":", 1)[1]
    ctx.user_data["market_filter"] = market
    sport = ctx.user_data.get("sport", "soccer")

    kb = [[InlineKeyboardButton(t, callback_data=f"risk:{c}")] for t, c in RISK_MODES]
    em = SPORT_EMOJI.get(sport, "🎯")
    label = next((t for t, c in MARKET_FILTERS if c == market), market.title())
    await q.edit_message_text(
        f"{em} *Sport:* `{sport.title()}`\n"
        f"🎚️ *Market:* `{md_escape(label)}`\n\n*Pick risk level:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def riskmode_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    risk = q.data.split(":", 1)[1]
    sport = ctx.user_data.get("sport", "soccer")
    market_filter = ctx.user_data.get("market_filter", "any")
    ctx.user_data["risk"] = risk

    await q.edit_message_text("🔄 Generating your parlay...")

    selections = await gather_selections(sport, risk, market_filter=market_filter)
    if not selections:
        await q.edit_message_text(
            "⚠️ No matching events found right now.\nTry another market, sport, or risk level."
        )
        return

    parlay = generate_parlay(selections, risk)
    if not parlay:
        await q.edit_message_text("⚠️ Couldn't build a parlay from current data.")
        return

    ctx.user_data["last_parlay"] = parlay
    user = get_user(update.effective_user.id) or {}
    unit = float(user.get("unit_size") or 10.0)

    text = format_parlay(parlay, sport, risk, unit_size=unit)
    kb = [
        [InlineKeyboardButton("🔁 Refresh", callback_data=f"refresh:{sport}:{risk}:{market_filter}")],
        [InlineKeyboardButton("📌 Track", callback_data=f"track:{sport}:{risk}")],
    ]
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def refresh_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Regenerating...")
    parts = q.data.split(":")
    sport = parts[1]
    risk = parts[2]
    market_filter = parts[3] if len(parts) > 3 else ctx.user_data.get("market_filter", "any")
    ctx.user_data["sport"] = sport
    ctx.user_data["risk"] = risk
    ctx.user_data["market_filter"] = market_filter

    selections = await gather_selections(sport, risk, market_filter=market_filter)
    if not selections:
        await q.edit_message_text("⚠️ Couldn't fetch fresh data.")
        return
    parlay = generate_parlay(selections, risk)
    if not parlay:
        await q.edit_message_text("⚠️ No valid parlay this time.")
        return
    ctx.user_data["last_parlay"] = parlay

    user = get_user(update.effective_user.id) or {}
    unit = float(user.get("unit_size") or 10.0)

    text = format_parlay(parlay, sport, risk, unit_size=unit)
    kb = [
        [InlineKeyboardButton("🔁 Refresh", callback_data=f"refresh:{sport}:{risk}:{market_filter}")],
        [InlineKeyboardButton("📌 Track", callback_data=f"track:{sport}:{risk}")],
    ]
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


# ─── Tracking flow ────────────────────────────────────────────
async def track_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """First click: ask for stake (don't save yet)."""
    q = update.callback_query
    await q.answer()
    parlay = ctx.user_data.get("last_parlay")
    if not parlay:
        await q.edit_message_text("Nothing to track. Run /parlay first.")
        return

    user = get_user(update.effective_user.id) or {}
    default_stake = float(user.get("unit_size") or 10.0)

    ctx.user_data["awaiting_stake"] = True
    ctx.user_data["pending_parlay"] = parlay

    kb = [
        [
            InlineKeyboardButton(f"{default_stake:g}u (default)",
                                 callback_data=f"stake:{default_stake}"),
            InlineKeyboardButton("5u", callback_data="stake:5"),
            InlineKeyboardButton("10u", callback_data="stake:10"),
        ],
        [
            InlineKeyboardButton("25u", callback_data="stake:25"),
            InlineKeyboardButton("50u", callback_data="stake:50"),
            InlineKeyboardButton("100u", callback_data="stake:100"),
        ],
        [InlineKeyboardButton("✖️ Cancel", callback_data="stake:cancel")],
    ]
    await q.edit_message_text(
        "💵 *Set your stake*\n\nPick a preset below or just type a number "
        "(e.g. `7.5`).",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def stake_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    val = q.data.split(":", 1)[1]
    if val == "cancel":
        ctx.user_data.pop("awaiting_stake", None)
        ctx.user_data.pop("pending_parlay", None)
        await q.edit_message_text("❌ Tracking cancelled.")
        return
    try:
        stake = float(val)
    except ValueError:
        return
    await _finalize_track(update, ctx, stake, via_callback=True)


async def stake_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Catch a free-text stake number when awaiting_stake is set."""
    if not ctx.user_data.get("awaiting_stake"):
        return
    stake = parse_stake_input(update.message.text)
    if stake is None:
        await update.message.reply_text("Send a number, e.g. `25` or `7.5`.")
        return
    await _finalize_track(update, ctx, stake, via_callback=False)


async def _finalize_track(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                          stake: float, via_callback: bool):
    parlay = ctx.user_data.get("pending_parlay") or ctx.user_data.get("last_parlay")
    if not parlay:
        msg = "Nothing to track. Run /parlay first."
        if via_callback:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    sport = ctx.user_data.get("sport", "soccer")
    risk = ctx.user_data.get("risk", "balanced")
    total_odds = compute_total_odds(parlay)
    pid = save_parlay(update.effective_user.id, sport, risk,
                      stake=stake, total_odds=total_odds, selections=parlay)

    ctx.user_data.pop("awaiting_stake", None)
    ctx.user_data.pop("pending_parlay", None)

    text = format_track_confirmation(pid, parlay, stake, total_odds)
    if via_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


# ─── /history ─────────────────────────────────────────────────
async def history_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = user_recent_parlays(update.effective_user.id, 10)
    if not rows:
        await update.message.reply_text("No parlays yet. Build one with /parlay.")
        return
    icon = {"won": "✅", "lost": "❌", "pending": "⏳"}
    lines = ["📜 *Recent parlays*\n"]
    for p in rows:
        sels = get_selections(p["id"])
        lines.append(
            f"{icon.get(p['status'], '•')} #{p['id']} — "
            f"{p['sport']} / {p['risk_mode']} — "
            f"*{p['total_odds']:.2f}* — stake {p['stake']:g}u "
            f"({len(sels)} legs)"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─── legacy /odds ─────────────────────────────────────────────
async def oddsinput_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.replace("/odds", "").strip()
    odds = parse_odds_input(txt)
    if not odds:
        await update.message.reply_text("Format: /odds 1.85 2.10 1.50")
        return
    ctx.user_data["custom_odds"] = odds
    await update.message.reply_text(f"✅ Custom odds saved: {odds}")


async def refresh_oddsinput_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Legacy free-text odds catcher (only when explicitly awaiting odds)."""
    if not ctx.user_data.get("awaiting_odds"):
        return
    odds = parse_odds_input(update.message.text or "")
    if odds:
        ctx.user_data["awaiting_odds"] = False
        ctx.user_data["custom_odds"] = odds
        await update.message.reply_text(f"Updated odds: {odds}")
