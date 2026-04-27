from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import create_challenge


async def challenge_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Usage: `/challenge @username <stake>`\nExample: `/challenge @bob 50`",
            parse_mode="Markdown",
        )
        return
    target = ctx.args[0].lstrip("@")
    try:
        stake = float(ctx.args[1])
        if stake <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Stake must be a positive number.")
        return

    challenger = update.effective_user
    msg = (
        "⚔️ *Parlay Duel!*\n"
        f"@{challenger.username or challenger.first_name} challenges @{target} "
        f"to a parlay duel for *{stake:g}u*.\n\n"
        "Both players build a parlay — whoever cashes wins the pot."
    )
    kb = [[
        InlineKeyboardButton("✅ Accept",
                             callback_data=f"chal:accept:{challenger.id}:{stake}"),
        InlineKeyboardButton("❌ Decline",
                             callback_data=f"chal:decline:{challenger.id}"),
    ]]
    await update.message.reply_text(msg, parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))


async def accept_challenge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    action = parts[1]

    if action == "decline":
        await q.edit_message_text("❌ Challenge declined.")
        return

    if action != "accept" or len(parts) < 4:
        return
    try:
        challenger_id = int(parts[2])
        stake = float(parts[3])
    except ValueError:
        return

    opponent = update.effective_user
    if opponent.id == challenger_id:
        await q.answer("You can't accept your own challenge.", show_alert=True)
        return

    cid = create_challenge(challenger_id, opponent.id, "soccer", stake)
    await q.edit_message_text(
        f"✅ *Challenge #{cid} accepted!*\n"
        "Both players run /parlay — best result wins the pot.",
        parse_mode="Markdown",
    )
