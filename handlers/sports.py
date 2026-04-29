"""
Sport selector handler.
Lets users choose which sports/leagues to include in parlay building,
and configure which bet types (markets) are enabled per sport.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
from database.db import SessionLocal, User
from config import LEAGUES, SPORT_MARKETS, DEFAULT_MARKET_PREFS
import json

# All available sport categories
SPORT_CATEGORIES = {
    "soccer":     "⚽ Soccer",
    "basketball": "🏀 Basketball",
    "football":   "🏈 Football",
    "baseball":   "⚾ Baseball",
    "hockey":     "🏒 Hockey",
    "rugby":      "🏉 Rugby",
    "cricket":    "🏏 Cricket",
}

# Emoji map for display
SPORT_EMOJI = {
    "soccer": "⚽", "basketball": "🏀", "football": "🏈",
    "baseball": "⚾", "hockey": "🏒", "rugby": "🏉", "cricket": "🏏",
}


def get_user_sports(user: User) -> set:
    """Get user's preferred sports as a set. 'all' means all sports."""
    if not user.preferred_sports or user.preferred_sports == "all":
        return set(SPORT_CATEGORIES.keys())
    return set(user.preferred_sports.split(","))


def get_user_markets(user: User) -> dict:
    """Get user's market preferences per sport. Missing sports use defaults."""
    if not user.market_prefs or user.market_prefs == "all":
        return dict(DEFAULT_MARKET_PREFS)
    try:
        prefs = json.loads(user.market_prefs)
        # Fill in defaults for any missing sports
        for sport in SPORT_MARKETS:
            if sport not in prefs:
                prefs[sport] = list(SPORT_MARKETS[sport].keys())
        return prefs
    except (json.JSONDecodeError, TypeError):
        return dict(DEFAULT_MARKET_PREFS)


def count_enabled_markets(market_list):
    return len(market_list)


async def sports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show sport selector menu with configure buttons."""
    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()

    if not user:
        kb = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]]
        msg = update.message or update.callback_query.message
        await msg.reply_text("⚠️ Please /start first.", reply_markup=InlineKeyboardMarkup(kb))
        return

    selected = get_user_sports(user)
    market_prefs = get_user_markets(user)

    buttons = []
    for sport, label in SPORT_CATEGORIES.items():
        checked = "✅ " if sport in selected else ""
        market_count = count_enabled_markets(market_prefs.get(sport, []))
        total_markets = len(SPORT_MARKETS.get(sport, {}))
        buttons.append([
            InlineKeyboardButton(
                f"{checked}{label}",
                callback_data=f"sport_toggle_{sport}"
            ),
            InlineKeyboardButton(
                f"⚙️ {market_count}/{total_markets} bets",
                callback_data=f"sport_config_{sport}"
            ),
        ])

    # Quick presets
    buttons.append([
        InlineKeyboardButton("🔄 All Sports", callback_data="sport_set_all"),
        InlineKeyboardButton("❌ Clear All", callback_data="sport_set_none"),
    ])
    buttons.append([
        InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    text = (
        "🏆 *Select Sports*\n\n"
        "Choose which sports to include when building parlays.\n"
        f"Currently: *{len(selected)}* sport(s) selected.\n\n"
        "Tap sport name to toggle. Tap ⚙️ to configure bet types."
    )

    markup = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=markup)


async def sport_config_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, sport: str):
    """Show bet type configuration menu for a specific sport."""
    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
    if not user:
        return

    market_prefs = get_user_markets(user)
    enabled = set(market_prefs.get(sport, []))

    sport_label = SPORT_CATEGORIES.get(sport, sport)
    sport_emoji = SPORT_EMOJI.get(sport, "🏆")
    markets = SPORT_MARKETS.get(sport, {})

    buttons = []
    for mkt_key, mkt_info in markets.items():
        checked = "✅ " if mkt_key in enabled else ""
        buttons.append([
            InlineKeyboardButton(
                f"{checked}{mkt_info['emoji']} {mkt_info['label']}",
                callback_data=f"sport_mkt_toggle_{sport}_{mkt_key}"
            )
        ])

    # Quick presets for this sport
    buttons.append([
        InlineKeyboardButton("✅ All Types", callback_data=f"sport_mkt_all_{sport}"),
        InlineKeyboardButton("❌ None", callback_data=f"sport_mkt_none_{sport}"),
    ])
    buttons.append([
        InlineKeyboardButton("◀️ Back to Sports", callback_data="menu_sports"),
    ])

    text = (
        f"{sport_emoji} *{sport_label} — Bet Types*\n\n"
        f"Select which bet types to include for {sport_label}.\n"
        f"Currently: *{len(enabled)}* of *{len(markets)}* enabled.\n\n"
        "Tap to toggle:"
    )

    markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=markup)


async def sport_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle a sport on/off."""
    q = update.callback_query
    await q.answer()

    sport = q.data[len("sport_toggle_"):]

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if not user:
            return

        selected = get_user_sports(user)
        if sport in selected:
            selected.discard(sport)
        else:
            selected.add(sport)

        user.preferred_sports = ",".join(sorted(selected)) if selected != set(SPORT_CATEGORIES.keys()) else "all"
        await s.commit()

    await sports_menu(update, context)


async def sport_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'All' or 'None' presets."""
    q = update.callback_query
    await q.answer()

    preset = q.data[len("sport_set_"):]

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if not user:
            return

        if preset == "all":
            user.preferred_sports = "all"
        else:
            user.preferred_sports = ""
        await s.commit()

    await sports_menu(update, context)


async def sport_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route to sport config menu when sport_config_ is clicked."""
    q = update.callback_query
    await q.answer()
    sport = q.data[len("sport_config_"):]
    await sport_config_menu(update, context, sport)


async def sport_mkt_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle a specific market on/off for a sport."""
    q = update.callback_query
    await q.answer()

    # Data format: sport_mkt_toggle_{sport}_{market}
    prefix = "sport_mkt_toggle_"
    remainder = q.data[len(prefix):]
    # sport name may contain underscores? No - sport keys don't.
    # Format: sport_mkt_toggle_football_SPREAD
    parts = remainder.split("_", 1)
    if len(parts) != 2:
        return
    sport, market = parts

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if not user:
            return

        market_prefs = get_user_markets(user)
        enabled = set(market_prefs.get(sport, []))

        if market in enabled:
            enabled.discard(market)
        else:
            enabled.add(market)

        market_prefs[sport] = sorted(enabled)
        user.market_prefs = json.dumps(market_prefs)
        await s.commit()

    await sport_config_menu(update, context, sport)


async def sport_mkt_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable all markets for a sport."""
    q = update.callback_query
    await q.answer()

    sport = q.data[len("sport_mkt_all_"):]

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if not user:
            return

        market_prefs = get_user_markets(user)
        market_prefs[sport] = list(SPORT_MARKETS.get(sport, {}).keys())
        user.market_prefs = json.dumps(market_prefs)
        await s.commit()

    await sport_config_menu(update, context, sport)


async def sport_mkt_none_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable all markets for a sport."""
    q = update.callback_query
    await q.answer()

    sport = q.data[len("sport_mkt_none_"):]

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if not user:
            return

        market_prefs = get_user_markets(user)
        market_prefs[sport] = []
        user.market_prefs = json.dumps(market_prefs)
        await s.commit()

    await sport_config_menu(update, context, sport)
