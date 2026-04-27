from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import CHALLENGES
from handlers.parlay import build_and_send


async def challenges_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🥇 2.0 Rollover", callback_data="chal_rollover_2_1")],
        [InlineKeyboardButton("🥈 1.5 Rollover", callback_data="chal_rollover_1_5_1")],
        [InlineKeyboardButton("🚀 Long Shot (20.0)", callback_data="chal_longshot_1")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu_main")],
    ]
    text = (
        "🏆 *Betting Challenges*\n\n"
        "• *2.0 Rollover* — 10 stages of x2 compounding\n"
        "• *1.5 Rollover* — 15 stages of safer x1.5 growth\n"
        "• *Long Shot* — high-risk, high-reward (~20.0)\n\n"
        "💡 _Profit protection automatically reserves 30% after each win._"
    )
    msg = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await msg.reply_text(text, parse_mode="Markdown",
                             reply_markup=InlineKeyboardMarkup(kb))


async def challenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    # chal_<type>_<stage>
    chal_type = "_".join(parts[1:-1])
    stage = int(parts[-1])

    if chal_type == "rollover_2":
        target = 2.0
        name = "2.0 Rollover"
    elif chal_type == "rollover_1_5":
        target = 1.5
        name = "1.5 Rollover"
    elif chal_type == "longshot":
        target = 20.0
        name = "Long Shot"
    else:
        await q.edit_message_text("Unknown challenge.")
        return

    await build_and_send(update, context, target, challenge=name, stage=stage)
