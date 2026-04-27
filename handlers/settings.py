from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import update_user_pref, get_user, upsert_user
from utils.helpers import parse_stake_input


async def settings_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username, user.first_name)
    u = get_user(user.id) or {}
    text = (
        "⚙️ *Settings*\n\n"
        f"Risk:          *{u.get('risk_mode', 'balanced')}*\n"
        f"Unit size:    *{u.get('unit_size', 10)}u*\n"
        f"Sport:         *{u.get('preferred_sport', 'soccer')}*\n"
        f"Notifications: *{'on' if u.get('notifications', 1) else 'off'}*\n\n"
        "_Change preferences:_"
    )
    kb = [
        [InlineKeyboardButton("🟢 Safe",     callback_data="pref:risk_mode:safe"),
         InlineKeyboardButton("🟡 Balanced", callback_data="pref:risk_mode:balanced"),
         InlineKeyboardButton("🔴 Risky",    callback_data="pref:risk_mode:risky"),
         InlineKeyboardButton("☠️ Lottery",  callback_data="pref:risk_mode:lottery")],
        [InlineKeyboardButton("⚽", callback_data="pref:preferred_sport:soccer"),
         InlineKeyboardButton("🏀", callback_data="pref:preferred_sport:basketball"),
         InlineKeyboardButton("🏈", callback_data="pref:preferred_sport:football"),
         InlineKeyboardButton("⚾", callback_data="pref:preferred_sport:baseball"),
         InlineKeyboardButton("🏒", callback_data="pref:preferred_sport:hockey")],
        [InlineKeyboardButton("🔔 Toggle Notifs", callback_data="pref:notifications:toggle")],
        [InlineKeyboardButton("💵 Set Unit",      callback_data="pref:unit_size:prompt")],
    ]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def prefs_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, field, value = q.data.split(":", 2)
    user_id = update.effective_user.id

    if field == "notifications" and value == "toggle":
        u = get_user(user_id) or {}
        new = 0 if u.get("notifications", 1) else 1
        update_user_pref(user_id, "notifications", new)
        await q.edit_message_text(f"🔔 Notifications: {'on' if new else 'off'}")
        return

    if field == "unit_size" and value == "prompt":
        ctx.user_data["awaiting_units"] = True
        await q.edit_message_text(
            "💵 Send your unit size (number) — e.g. `25` or `/units 25`.",
            parse_mode="Markdown",
        )
        return

    if field == "unit_size":
        try:
            update_user_pref(user_id, "unit_size", float(value))
            await q.edit_message_text(f"💵 Unit size: {value}")
        except ValueError:
            pass
        return

    update_user_pref(user_id, field, value)
    await q.edit_message_text(f"✅ {field} → *{value}*", parse_mode="Markdown")


async def units_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Accept either:
      - /units 25      (command form)
      - 25             (free text, only when awaiting_units flag is set)
    """
    text = (update.message.text or "").strip()
    is_command = text.startswith("/units")

    if not is_command and not ctx.user_data.get("awaiting_units"):
        return

    raw = text.replace("/units", "").strip()
    val = parse_stake_input(raw)
    if val is None:
        if is_command:
            await update.message.reply_text("Send a number, e.g. `/units 25`.")
        else:
            await update.message.reply_text("Send a number, e.g. `25`.")
        return

    update_user_pref(update.effective_user.id, "unit_size", val)
    ctx.user_data.pop("awaiting_units", None)
    await update.message.reply_text(f"✅ Unit size set to *{val:g}u*", parse_mode="Markdown")
