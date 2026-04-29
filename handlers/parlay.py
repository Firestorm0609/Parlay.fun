from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from sqlalchemy import select
from services.parlay_engine import ParlayEngine
from services.tracker import ParlayTracker
from database.db import SessionLocal, User
from utils.helpers import format_parlay

ODDS_OPTIONS = [2.0, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 20.0]

CHALLENGE_PREFIX_MAP = {
    "2.0 Rollover": "rollover_2",
    "1.5 Rollover": "rollover_1_5",
    "Long Shot":    "longshot",
}
CHALLENGE_MAX_STAGES = {
    "2.0 Rollover": 10,
    "1.5 Rollover": 15,
    "Long Shot":    1,
}


async def parlay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Show active sport/market filters
    filter_text = ""
    try:
        async with SessionLocal() as s:
            res = await s.execute(
                select(User).where(User.tg_id == update.effective_user.id))
            user = res.scalar_one_or_none()
        if user:
            from handlers.sports import get_user_sports, get_user_markets, SPORT_CATEGORIES
            sports = get_user_sports(user)
            markets = get_user_markets(user)
            sport_list = ", ".join(SPORT_CATEGORIES[s] for s in sorted(sports) if s in SPORT_CATEGORIES)
            # Count total enabled markets
            total_markets = sum(len(markets.get(s, [])) for s in sports)
            filter_text = (
                f"\n\n🔧 *Active Filters*\n"
                f"Sports: {sport_list}\n"
                f"Bet types: {total_markets} enabled\n"
                f"[Configure → Sports Settings]"
            )
    except Exception:
        pass

    text = (
        "🎯 *Build a Parlay*\n\n"
        "Select your *target odds* or enter a custom value.\n"
        "_Higher odds = more legs + more risk._"
        f"{filter_text}"
    )
    buttons = []
    row = []
    for i, odds in enumerate(ODDS_OPTIONS):
        row.append(InlineKeyboardButton(
            f"×{odds:.1f}", callback_data=f"parlay_odds_{odds}"))
        if len(row) == 3 or i == len(ODDS_OPTIONS) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton("✏️ Custom Odds", callback_data="parlay_custom")])
    buttons.append([
        InlineKeyboardButton("⚽ Sports", callback_data="menu_sports"),
        InlineKeyboardButton("🏠 Menu", callback_data="menu_main"),
    ])

    markup = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def parlay_custom_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                challenge=None, stage=None):
    """Prompt user to type custom odds. Works for both parlay and challenge flows."""
    context.user_data["awaiting_odds"] = {
        "active":    True,
        "challenge": challenge,
        "stage":     stage,
    }
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="menu_parlay" if not challenge else "menu_challenges")]]
    text = (
        "✏️ *Custom Target Odds*\n\n"
        "Send me your target odds as a number.\n"
        "_Example: 4.5 or 12 or 33.0_"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def parlay_custom_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await parlay_custom_prompt(update, context)


async def parlay_odds_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("🔍 Building your parlay...")
    target = float(q.data[len("parlay_odds_"):])
    await build_and_send(update, context, target)


async def handle_custom_odds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MessageHandler — fires on any text when awaiting_odds is active."""
    state = context.user_data.get("awaiting_odds", {})
    if not state.get("active"):
        return

    raw = update.message.text.strip()
    try:
        target = float(raw)
        if target < 1.1 or target > 1000:
            raise ValueError
    except ValueError:
        cancel_cb = "menu_challenges" if state.get("challenge") else "menu_parlay"
        kb = [[InlineKeyboardButton("❌ Cancel", callback_data=cancel_cb)]]
        await update.message.reply_text(
            "❌ Please send a valid number between *1.1* and *1000*.\n_e.g. 4.5_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    context.user_data["awaiting_odds"] = {}
    challenge = state.get("challenge")
    stage = state.get("stage")
    await build_and_send(update, context, target, challenge=challenge, stage=stage)


async def build_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         target_odds: float, challenge=None, stage=None):
    msg = update.message or update.callback_query.message
    status = await msg.reply_text("🔍 Scanning fixtures & odds...")

    async with SessionLocal() as s:
        result = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = result.scalar_one_or_none()
        risk = user.risk_level if user else "balanced"
        user_pk = user.id if user else None

    engine = ParlayEngine()
    try:
        # Get user's preferred sports and market prefs
        user_sports = None
        user_markets = None
        if user:
            from handlers.sports import get_user_sports, get_user_markets
            user_sports = get_user_sports(user)
            user_markets = get_user_markets(user)

        date = datetime.utcnow().strftime("%Y%m%d")
        selections = await engine.gather_selections(date, sports=user_sports, market_prefs=user_markets)
        if not selections:
            date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y%m%d")
            selections = await engine.gather_selections(date, sports=user_sports, market_prefs=user_markets)

        if not selections:
            kb = [
                [InlineKeyboardButton("🔁 Try Again", callback_data=f"parlay_odds_{target_odds}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]
            await status.edit_text(
                "❌ No fixtures with odds found right now. Try again later.",
                reply_markup=InlineKeyboardMarkup(kb))
            return

        parlay = engine.build_parlay(selections, target_odds, risk=risk)
        if not parlay:
            kb = [
                [InlineKeyboardButton("🎯 Pick Different Odds", callback_data="menu_parlay")],
                [InlineKeyboardButton("⚙️ Change Risk Profile", callback_data="menu_settings")],
                [InlineKeyboardButton("🏠 Main Menu",           callback_data="menu_main")],
            ]
            await status.edit_text(
                f"❌ Couldn't build a parlay near *×{target_odds}* with risk *{risk}*.\n\n"
                "Try different odds or adjust your risk profile.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb))
            return

        text = format_parlay(parlay, target_odds)
        if challenge:
            text = f"🏆 *Challenge: {challenge}* — Stage {stage}\n\n" + text

        context.user_data["last_parlay"] = {
            "target":    target_odds,
            "data":      parlay,
            "challenge": challenge,
            "stage":     stage,
            "user_pk":   user_pk,
        }

        kb = [
            [
                InlineKeyboardButton("📌 Track This",  callback_data="track_yes"),
                InlineKeyboardButton("🔁 Regenerate", callback_data=f"regen_{target_odds}"),
            ],
        ]

        if challenge:
            prefix = CHALLENGE_PREFIX_MAP.get(challenge)
            max_stage = CHALLENGE_MAX_STAGES.get(challenge, 1)
            next_stage = stage + 1
            if prefix and next_stage <= max_stage:
                kb.append([InlineKeyboardButton(
                    f"✅ Won! → Stage {next_stage}",
                    callback_data=f"chal_{prefix}_{next_stage}")])
            kb.append([InlineKeyboardButton("🏆 Challenges", callback_data="menu_challenges")])
        else:
            kb.append([
                InlineKeyboardButton("🎯 New Parlay", callback_data="menu_parlay"),
                InlineKeyboardButton("🏠 Menu",       callback_data="menu_main"),
            ])

        await status.edit_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    finally:
        await engine.close()


async def track_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = context.user_data.get("last_parlay")

    if not data:
        kb = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]]
        await q.edit_message_text(
            "⚠️ Nothing to track — please build a parlay first.",
            reply_markup=InlineKeyboardMarkup(kb))
        return
    if not data["user_pk"]:
        kb = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]]
        await q.edit_message_text(
            "⚠️ User not found. Please press /start first.",
            reply_markup=InlineKeyboardMarkup(kb))
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
        kb = [
            [
                InlineKeyboardButton("🎯 New Parlay", callback_data="menu_parlay"),
                InlineKeyboardButton("📊 My Stats",   callback_data="menu_stats"),
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ]
        await q.edit_message_text(
            q.message.text + f"\n\n✅ *Tracked!* Parlay ID #{pid}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb))
    finally:
        await tracker.client.close()


async def regen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("🔁 Regenerating...")

    target = float(q.data[len("regen_"):])
    last = context.user_data.get("last_parlay", {})
    await build_and_send(
        update, context, target,
        challenge=last.get("challenge"),
        stage=last.get("stage"),
    )

