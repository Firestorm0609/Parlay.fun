import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.parlay_engine import build_parlay
from services.tracker import save_parlay
from utils.helpers import (
    format_parlay_message,
    format_tracking_confirmation,
    parse_odds,
    parse_stake,
)

logger = logging.getLogger(__name__)


# ----- Step 1: choose number of legs -----
async def parlay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("2-Leg", callback_data="parlay:legs:2"),
            InlineKeyboardButton("3-Leg", callback_data="parlay:legs:3"),
            InlineKeyboardButton("4-Leg", callback_data="parlay:legs:4"),
        ],
        [
            InlineKeyboardButton("5-Leg", callback_data="parlay:legs:5"),
            InlineKeyboardButton("6-Leg", callback_data="parlay:legs:6"),
        ],
    ]
    text = (
        "🎯 *Build a Parlay*\n\n"
        "Pick how many legs you want.\n"
        "Engine will analyse today's fixtures and pick the highest-confidence selections."
    )
    target = update.effective_message
    if target is None and update.callback_query is not None:
        target = update.callback_query.message
    await target.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def parlay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")

    # parlay:legs:<N>  -> ask for risk
    if data[1] == "legs":
        legs = int(data[2])
        keyboard = [
            [
                InlineKeyboardButton("Conservative", callback_data=f"parlay:risk:{legs}:safe"),
                InlineKeyboardButton("Balanced",     callback_data=f"parlay:risk:{legs}:balanced"),
                InlineKeyboardButton("Aggressive",   callback_data=f"parlay:risk:{legs}:risky"),
            ]
        ]
        await query.edit_message_text(
            f"📊 *{legs}-Leg Parlay*\n\nChoose risk profile:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # parlay:risk:<N>:<risk>  -> ask for market filter
    if data[1] == "risk":
        legs = int(data[2])
        risk = data[3]
        keyboard = [
            [
                InlineKeyboardButton("⚽ Win",        callback_data=f"parlay:mkt:{legs}:{risk}:1X2"),
                InlineKeyboardButton("🤝 Win or Draw", callback_data=f"parlay:mkt:{legs}:{risk}:DC"),
            ],
            [
                InlineKeyboardButton("🎯 Goals (O/U)", callback_data=f"parlay:mkt:{legs}:{risk}:OU"),
                InlineKeyboardButton("🥅 BTTS",        callback_data=f"parlay:mkt:{legs}:{risk}:BTTS"),
            ],
            [
                InlineKeyboardButton("✨ Any market",  callback_data=f"parlay:mkt:{legs}:{risk}:ANY"),
            ],
        ]
        await query.edit_message_text(
            f"📊 *{legs}-Leg · {risk.title()}*\n\nWhich market?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # parlay:mkt:<N>:<risk>:<market>  -> build it
    if data[1] == "mkt":
        legs = int(data[2])
        risk = data[3]
        market = data[4]

        await query.edit_message_text("⏳ Crunching numbers...")

        markets = None if market == "ANY" else [market]
        try:
            parlay = await build_parlay(legs=legs, risk=risk, markets=markets)
        except Exception as e:
            logger.exception("parlay build failed")
            await query.edit_message_text(f"❌ Couldn't build parlay: {e}")
            return

        if not parlay or not parlay.get("legs"):
            keyboard = [[
                InlineKeyboardButton("🔄 Try again", callback_data=f"parlay:risk:{legs}:{risk}"),
                InlineKeyboardButton("⬅️ Back",       callback_data="menu:main"),
            ]]
            await query.edit_message_text(
                "😕 Not enough quality fixtures matched that filter.\n"
                "Try a different market or risk profile.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        msg = format_parlay_message(parlay)
        keyboard = [
            [
                InlineKeyboardButton(
                    "📌 Track this parlay",
                    callback_data=f"track:save:{parlay['cache_id']}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Rebuild",
                    callback_data=f"parlay:mkt:{legs}:{risk}:{market}",
                ),
                InlineKeyboardButton("⬅️ Back", callback_data="menu:main"),
            ],
        ]
        context.bot_data.setdefault("parlay_cache", {})[parlay["cache_id"]] = parlay
        await query.edit_message_text(
            msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return


# ----- Tracking flow -----
async def track_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")

    # track:save:<cache_id>  -> ask for stake
    if data[1] == "save":
        cache_id = data[2]
        cache = context.bot_data.get("parlay_cache", {}).get(cache_id)
        if not cache:
            await query.edit_message_text("⚠️ Parlay expired. Build a new one with /parlay.")
            return

        # Offer quick-pick stakes + custom
        keyboard = [
            [
                InlineKeyboardButton("0u (track only)", callback_data=f"track:stake:{cache_id}:0"),
                InlineKeyboardButton("1u",  callback_data=f"track:stake:{cache_id}:1"),
                InlineKeyboardButton("2u",  callback_data=f"track:stake:{cache_id}:2"),
            ],
            [
                InlineKeyboardButton("5u",  callback_data=f"track:stake:{cache_id}:5"),
                InlineKeyboardButton("10u", callback_data=f"track:stake:{cache_id}:10"),
                InlineKeyboardButton("✏️ Custom", callback_data=f"track:custom:{cache_id}"),
            ],
        ]
        await query.edit_message_text(
            "💰 *Stake size?*\n\nPick a quick amount or enter a custom value.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # track:custom:<cache_id>  -> wait for typed stake
    if data[1] == "custom":
        cache_id = data[2]
        cache = context.bot_data.get("parlay_cache", {}).get(cache_id)
        if not cache:
            await query.edit_message_text("⚠️ Parlay expired. Build a new one with /parlay.")
            return
        context.user_data["awaiting_stake"] = cache_id
        await query.message.reply_text(
            "Send me the stake (in units). E.g. `2.5` or `0` to just track.",
            parse_mode="Markdown",
        )
        return

    # track:stake:<cache_id>:<amount>  -> persist
    if data[1] == "stake":
        cache_id = data[2]
        try:
            stake = float(data[3])
        except (ValueError, IndexError):
            stake = 0.0
        await _persist_parlay(update, context, cache_id, stake, edit=True)
        return

    # track:odds:<parlay_id>  -> log actual odds taken later
    if data[1] == "odds":
        parlay_id = int(data[2])
        context.user_data["awaiting_odds"] = parlay_id
        await query.message.reply_text(
            "Send me the actual odds you got (e.g. `5.40`)", parse_mode="Markdown"
        )
        return


async def _persist_parlay(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cache_id: str,
    stake: float,
    edit: bool,
):
    cache = context.bot_data.get("parlay_cache", {}).get(cache_id)
    if not cache:
        msg = "⚠️ Parlay expired. Build a new one with /parlay."
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.effective_message.reply_text(msg)
        return

    user_id = update.effective_user.id
    try:
        parlay_id = await save_parlay(user_id=user_id, parlay=cache, stake=stake)
    except Exception as e:
        logger.exception("save failed")
        err = f"❌ Couldn't save: {e}"
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(err)
        else:
            await update.effective_message.reply_text(err)
        return

    confirmation = format_tracking_confirmation(parlay_id, cache, stake)
    keyboard = [[
        InlineKeyboardButton(
            "🎟 Log actual odds taken",
            callback_data=f"track:odds:{parlay_id}",
        )
    ]]

    # cache_id is single-use; clean up so re-clicks don't double-save
    context.bot_data.get("parlay_cache", {}).pop(cache_id, None)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            confirmation,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.effective_message.reply_text(
            confirmation,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# ----- Free-text input router (stake & odds) -----
async def handle_odds_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Stake first (typed via Custom)
    if "awaiting_stake" in context.user_data:
        cache_id = context.user_data.pop("awaiting_stake")
        text = update.message.text.strip()
        stake = parse_stake(text)
        if stake is None:
            # put it back so they can retry
            context.user_data["awaiting_stake"] = cache_id
            await update.message.reply_text(
                "❌ Invalid stake. Send a number like `1`, `2.5` or `0`.",
                parse_mode="Markdown",
            )
            return
        await _persist_parlay(update, context, cache_id, stake, edit=False)
        return

    # Actual odds for an already-saved parlay
    if "awaiting_odds" in context.user_data:
        parlay_id = context.user_data.pop("awaiting_odds")
        text = update.message.text.strip()
        odds = parse_odds(text)
        if odds is None:
            context.user_data["awaiting_odds"] = parlay_id
            await update.message.reply_text(
                "❌ Invalid odds. Send a number like `5.40`.", parse_mode="Markdown"
            )
            return

        from sqlalchemy import update as sql_update
        from database.db import async_session, Parlay, User
        from sqlalchemy import select

        uid = update.effective_user.id
        async with async_session() as s:
            u = await s.scalar(select(User).where(User.tg_id == uid))
            if not u:
                await update.message.reply_text("❌ User not found.")
                return
            # ensure ownership
            p = await s.scalar(
                select(Parlay).where(Parlay.id == parlay_id, Parlay.user_id == u.id)
            )
            if not p:
                await update.message.reply_text("❌ Parlay not found or not yours.")
                return
            await s.execute(
                sql_update(Parlay)
                .where(Parlay.id == parlay_id)
                .values(actual_odds=odds)
            )
            await s.commit()

        await update.message.reply_text(
            f"✅ Updated parlay #{parlay_id} with odds *{odds}x*",
            parse_mode="Markdown",
        )
        return

    # Otherwise: ignore (it's a normal message)
    return
