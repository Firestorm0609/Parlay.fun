"""
Real-time odds watcher service.
Monitors ESPN API for target odds and notifies users when reached.
"""
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from services.parlay_engine import ParlayEngine
from config import LEAGUES

WATCH_INTERVAL = 120  # seconds between checks

# Store active watches: {user_id: {"target": float, "chat_id": int, "task": asyncio.Task}}
active_watches = {}


async def watch_target_odds(app, user_id: int, target_odds: float, chat_id: int):
    """
    Poll ESPN until odds reach target_odds, then notify the user.
    Runs as a background task.
    """
    engine = ParlayEngine()
    try:
        while user_id in active_watches:
            # Check if target still exists (user might have cancelled)
            if active_watches[user_id].get("target") != target_odds:
                break

            # Gather selections for today and tomorrow
            date_today = datetime.utcnow().strftime("%Y%m%d")
            selections = await engine.gather_selections(date_today)

            if not selections:
                date_tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y%m%d")
                selections = await engine.gather_selections(date_tomorrow)

            if selections:
                # Find best combined odds from available selections
                best_odds = max(s["odds"] for s in selections) if selections else 0

                if best_odds >= target_odds:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🎯 *Target Odds Reached!*\n\n"
                            f"Current best odds: *×{best_odds:.2f}*\n"
                            f"Your target was: *×{target_odds}*\n\n"
                            f"Ready to build your parlay?"
                        ),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("🎯 Build Parlay", callback_data=f"parlay_odds_{target_odds}"),
                                InlineKeyboardButton("❌ Dismiss", callback_data="menu_main"),
                            ]
                        ])
                    )
                    break  # Stop watching after notification

            await asyncio.sleep(WATCH_INTERVAL)

    except asyncio.CancelledError:
        pass  # Task was cancelled
    except Exception as e:
        print(f"Error in odds watcher for user {user_id}: {e}")
    finally:
        await engine.close()
        # Clean up
        if user_id in active_watches:
            del active_watches[user_id]


def start_watching(app, user_id: int, target_odds: float, chat_id: int):
    """Start watching odds for a user."""
    # Cancel existing watch for this user
    if user_id in active_watches:
        active_watches[user_id]["task"].cancel()

    # Create new watch task
    task = asyncio.create_task(
        watch_target_odds(app, user_id, target_odds, chat_id)
    )
    active_watches[user_id] = {
        "target": target_odds,
        "chat_id": chat_id,
        "task": task,
    }


def stop_watching(user_id: int):
    """Stop watching odds for a user."""
    if user_id in active_watches:
        active_watches[user_id]["task"].cancel()
        del active_watches[user_id]
