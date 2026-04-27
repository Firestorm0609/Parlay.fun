from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func
from services.tracker import ParlayTracker
from database.db import SessionLocal, User
from utils.helpers import format_stats, currency_symbol, CURRENCY_SYMBOLS

BANKROLL_PRESETS = [50, 100, 250, 500, 1000, 2500, 5000]


# ─── Stats ────────────────────────────────────────────────────────────────────

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


# ─── Bankroll ─────────────────────────────────────────────────────────────────

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

    # Preset balance buttons — 3 per row
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


# ─── Currency ─────────────────────────────────────────────────────────────────

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

    # Build currency grid — 3 per row
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
