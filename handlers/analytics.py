from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func, case
from services.tracker import ParlayTracker
from services.ai_suggester import ai_suggester
from database.db import SessionLocal, User, Parlay
from utils.helpers import format_stats, currency_symbol, CURRENCY_SYMBOLS

BANKROLL_PRESETS = [50, 100, 250, 500, 1000, 2500, 5000]


# ─── Stats ────────────────────────────────────────────────────────────

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()

    if not user:
        kb = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]]
        await msg.reply_text(
            "⚠️ Please start the bot first.",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    tracker = ParlayTracker()
    try:
        await tracker.settle_pending()
        stats = await tracker.user_stats(user.id)
    finally:
        await tracker.client.close()

    sym = currency_symbol(getattr(user, "currency", "USD"))
    text = format_stats(stats, sym=sym)
    kb = [
        [
            InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay"),
            InlineKeyboardButton("💰 Bankroll",     callback_data="menu_bankroll"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await msg.reply_text(text, parse_mode="Markdown", reply_markup=markup)


# ─── Smart Bet (AI Suggestion) ─────────────────────────────────────

async def smart_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /smart-bet command with AI-driven parlay suggestions."""
    user_id = update.effective_user.id

    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == user_id))
        user = res.scalar_one_or_none()

    if not user:
        kb = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]]
        text = "⚠️ Please /start the bot first to use AI suggestions."
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    risk_level = getattr(user, "risk_level", "balanced")
    suggestion = await ai_suggester.suggest_parlay(user.id, risk_level)
    message = await ai_suggester.format_suggestion_message(suggestion)

    if suggestion.get("has_suggestion"):
        target_odds = suggestion.get("target_odds", 4.0)
        kb = [[InlineKeyboardButton("🎯 Build This Parlay", callback_data=f"parlay_odds_{target_odds}"),
               InlineKeyboardButton("🏠 Menu", callback_data="menu_main")]]
    else:
        kb = [[InlineKeyboardButton("🎯 Try Parlay", callback_data="menu_parlay"),
               InlineKeyboardButton("🏠 Menu", callback_data="menu_main")]]

    markup = InlineKeyboardMarkup(kb)

    if update.message:
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.callback_query.edit_message_text(message, parse_mode="Markdown", reply_markup=markup)


# ─── Bankroll ─────────────────────────────────────────────────────────

async def bankroll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()

    if not user:
        kb = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]]
        await msg.reply_text(
            "⚠️ Please start the bot first.",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    sym = currency_symbol(getattr(user, "currency", "USD"))
    cur = getattr(user, "currency", "USD")

    text = (
        f"💰 *Bankroll Dashboard*\n\n"
        f"Balance:   *{sym}{user.bankroll:,.2f}*\n"
        f"Protected: *{sym}{user.profit_protection:,.2f}*\n"
        f"Risk:      *{user.risk_level.title()}*\n"
        f"Currency:  *{cur}*\n\n"
        f"Set balance:"
    )

    preset_buttons = []
    row = []
    for i, amt in enumerate(BANKROLL_PRESETS):
        row.append(InlineKeyboardButton(
            f"{sym}{amt:,}", callback_data=f"bankroll_set_{amt}"))
        if len(row) == 3 or i == len(BANKROLL_PRESETS) - 1:
            preset_buttons.append(row)
            row = []

    preset_buttons.append([
        InlineKeyboardButton("✏️ Custom Amount",   callback_data="bankroll_custom"),
        InlineKeyboardButton("🌍 Change Currency", callback_data="bankroll_currency"),
    ])
    preset_buttons.append([
        InlineKeyboardButton("📊 My Stats",  callback_data="menu_stats"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
    ])

    markup = InlineKeyboardMarkup(preset_buttons)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await msg.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def bankroll_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    amt = float(q.data[len("bankroll_set_"):])

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if user:
            user.bankroll = amt
            await s.commit()
        sym = currency_symbol(getattr(user, "currency", "USD"))

    await q.answer(f"💰 Set to {sym}{amt:,.0f}!")
    kb = [
        [
            InlineKeyboardButton("💰 Bankroll",     callback_data="menu_bankroll"),
            InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    await q.edit_message_text(
        f"✅ Bankroll updated to *{sym}{amt:,.2f}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb))


async def bankroll_custom_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt the user to type a custom balance amount."""
    q = update.callback_query
    await q.answer()

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
    sym = currency_symbol(getattr(user, "currency", "USD"))

    context.user_data["awaiting_balance"] = True

    text = (
        f"✏️ *Custom Balance Amount*\n\n"
        f"Type any amount in {sym} to set as your bankroll.\n"
        f"_Example: 750 or 3500 or 12000_\n\n"
        f"No upper limit — enter what you actually play with."
    )
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="menu_bankroll")]]
    await q.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def handle_custom_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """MessageHandler — fires on any text when awaiting_balance is active.
    Returns True if the message was consumed, False otherwise."""
    if not context.user_data.get("awaiting_balance"):
        return False

    raw = update.message.text.strip().replace(",", "")
    try:
        amt = float(raw)
        if amt <= 0 or amt > 10_000_000:
            raise ValueError
    except ValueError:
        kb = [[InlineKeyboardButton("❌ Cancel", callback_data="menu_bankroll")]]
        await update.message.reply_text(
            "❌ Please enter a valid positive number (up to 10,000,000).\n_e.g. 750 or 5000_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb))
        return True  # consumed — keep awaiting_balance True

    context.user_data["awaiting_balance"] = False

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if user:
            user.bankroll = amt
            await s.commit()
    sym = currency_symbol(getattr(user, "currency", "USD"))

    kb = [
        [
            InlineKeyboardButton("💰 Bankroll",     callback_data="menu_bankroll"),
            InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    await update.message.reply_text(
        f"✅ Bankroll set to *{sym}{amt:,.2f}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb))
    return True  # consumed


# ─── Currency ─────────────────────────────────────────────────────────

async def currency_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
    current = getattr(user, "currency", "USD")

    text = (
        f"🌍 *Select Currency*\n\n"
        f"Current: *{current} {currency_symbol(current)}*"
    )

    buttons = []
    row = []
    for i, (code, sym) in enumerate(CURRENCY_SYMBOLS.items()):
        label = f"{sym} {code}" + (" ✓" if code == current else "")
        row.append(InlineKeyboardButton(label, callback_data=f"currency_set_{code}"))
        if len(row) == 3 or i == len(CURRENCY_SYMBOLS) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton("💰 Back to Bankroll", callback_data="menu_bankroll")])

    await q.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def currency_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    new_currency = q.data[len("currency_set_"):]

    async with SessionLocal() as s:
        res = await s.execute(
            select(User).where(User.tg_id == update.effective_user.id))
        user = res.scalar_one_or_none()
        if user:
            user.currency = new_currency
            await s.commit()

    sym = currency_symbol(new_currency)
    await q.answer(f"Currency set to {new_currency} {sym}!")

    kb = [
        [InlineKeyboardButton("💰 Bankroll",  callback_data="menu_bankroll")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    await q.edit_message_text(
        f"✅ Currency updated to *{new_currency} {sym}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb))


# ─── Leaderboard ──────────────────────────────────────────────────────

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 5 users by ROI with anonymized names."""
    async with SessionLocal() as s:
        stmt = (
            select(
                User.id,
                User.username,
                func.sum(Parlay.stake).label("stake"),
                func.sum(
                    case(
                        (Parlay.status == "won", (Parlay.total_odds - 1) * Parlay.stake),
                        else_=-Parlay.stake
                    )
                ).label("profit")
            )
            .join(Parlay, Parlay.user_id == User.id)
            .group_by(User.id)
            .having(func.sum(Parlay.stake) > 0)
            .order_by(
                (
                    func.sum(
                        case(
                            (Parlay.status == "won", (Parlay.total_odds - 1) * Parlay.stake),
                            else_=-Parlay.stake
                        )
                    ) / func.sum(Parlay.stake)
                ).desc()
            )
            .limit(5)
        )
        rows = (await s.execute(stmt)).fetchall()

    if not rows:
        text = "🏆 *Leaderboard*\n\nNo completed parlays yet. Be the first to place a tracked parlay!"
    else:
        lines = ["🏆 *Top 5 ROI Leaderboard*\n"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, row in enumerate(rows):
            # Anonymize username
            if row.username and len(row.username) > 3:
                masked = f"{row.username[:2]}••{row.username[-1]}"
            elif row.username:
                masked = f"{row.username[0]}•••"
            else:
                masked = f"User{row.id}"
            roi = (row.profit / row.stake * 100) if row.stake else 0
            lines.append(f"{medals[i]} {masked} — ROI {roi:.1f}%")

        text = "\n".join(lines)

    kb = [
        [InlineKeyboardButton("🎯 Build Parlay", callback_data="menu_parlay")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ]
    markup = InlineKeyboardMarkup(kb)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
