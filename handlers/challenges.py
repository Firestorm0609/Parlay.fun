from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.parlay import build_and_send, parlay_custom_prompt

CHALLENGES = {
    "rollover_2":   {"name": "2.0 Rollover",  "target": 2.0,  "max_stages": 10},
    "rollover_1_5": {"name": "1.5 Rollover",  "target": 1.5,  "max_stages": 15},
    "longshot":     {"name": "Long Shot",      "target": None, "max_stages": 1},
}


async def challenges_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏆 *Betting Challenges*\n\n"
        "🥇 *2.0 Rollover* — 10 stages of ×2 compounding\n"
        "🥈 *1.5 Rollover* — 15 stages of safer ×1.5 growth\n"
        "🚀 *Long Shot* — Your custom high-risk, high-reward target\n\n"
        "💡 _30% profit protection kicks in automatically after each win._"
    )
    kb = [
        [InlineKeyboardButton("🥇 2.0 Rollover (×2)",    callback_data="chal_rollover_2_1")],
        [InlineKeyboardButton("🥈 1.5 Rollover (×1.5)",  callback_data="chal_rollover_1_5_1")],
        [InlineKeyboardButton("🚀 Long Shot (Custom ×)", callback_data="chal_longshot_1")],
        [InlineKeyboardButton("🏠 Main Menu",             callback_data="menu_main")],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    stage = int(parts[-1])
    chal_key = "_".join(parts[1:-1])

    challenge = CHALLENGES.get(chal_key)
    if not challenge:
        kb = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]]
        await q.edit_message_text("❌ Unknown challenge.", reply_markup=InlineKeyboardMarkup(kb))
        return

    if stage > challenge["max_stages"]:
        kb = [
            [InlineKeyboardButton("🏆 Challenges", callback_data="menu_challenges")],
            [InlineKeyboardButton("🏠 Main Menu",  callback_data="menu_main")],
        ]
        await q.edit_message_text(
            f"🎉 *Challenge Complete!*\n\n"
            f"You finished all {challenge['max_stages']} stages of *{challenge['name']}*!\n"
            "Congratulations! 🥳",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    # Long Shot has no fixed target — ask user to type their own
    if challenge["target"] is None:
        await parlay_custom_prompt(
            update, context,
            challenge=challenge["name"],
            stage=stage)
        return

    await build_and_send(
        update, context,
        target_odds=challenge["target"],
        challenge=challenge["name"],
        stage=stage,
    )

