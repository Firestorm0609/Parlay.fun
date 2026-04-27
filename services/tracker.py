"""
Auto-settlement engine.

Improvements:
- Returns rich settlement records (parlay + sels + result) so the notify job
  can DM users with full context
- Caches completed events for 1h, in-progress events for 5min
- Handles 'push' selections (treated as won leg → odds 1.0 contribution)
"""
import time
import logging
from typing import List, Dict

from services.espn_api import fetch_event_summary
from services.analytics import _check_selection
from database.db import (
    get_pending_parlays, get_selections, update_selection_result,
    settle_parlay, get_parlay,
)

log = logging.getLogger(__name__)

_event_cache: Dict[str, Dict] = {}  # key -> {data, expires_at}
_COMPLETED_TTL = 3600
_LIVE_TTL = 300


async def _resolve_event(sport: str, event_id: str) -> Dict:
    key = f"{sport}:{event_id}"
    now = time.time()
    cached = _event_cache.get(key)
    if cached and cached["expires_at"] > now:
        return cached["data"]
    data = await fetch_event_summary(sport, event_id)
    ttl = _COMPLETED_TTL if data.get("completed") else _LIVE_TTL
    _event_cache[key] = {"data": data, "expires_at": now + ttl}
    return data


async def settle_pending() -> List[Dict]:
    """
    Walk every pending parlay, pull its events, mark selections, and settle
    parlays that are now fully decided.
    Returns list of settlement records.
    """
    parlays = get_pending_parlays()
    settled: List[Dict] = []

    for p in parlays:
        sels = get_selections(p["id"])
        results = []
        for s in sels:
            if s["result"] != "pending":
                results.append(s["result"])
                continue
            ev = await _resolve_event(p["sport"], s["event_id"])
            r = _check_selection(s, ev)
            if r != "pending":
                update_selection_result(s["id"], r)
            results.append(r)

        # Resolve parlay status:
        # any 'lost' → lost; any 'pending' → pending; else won
        if "lost" in results:
            settle_parlay(p["id"], "lost", 0)
            settled.append({"parlay": get_parlay(p["id"]),
                            "selections": get_selections(p["id"]),
                            "status": "lost", "payout": 0.0})
        elif "pending" in results:
            continue  # not all legs in yet
        else:
            # All wins/pushes: pushes contribute odds 1.0
            payout = float(p["stake"] or 0) * float(p["total_odds"] or 0)
            adj_odds = 1.0
            for s in get_selections(p["id"]):
                adj_odds *= (s["odds"] if s["result"] == "won" else 1.0)
            adj_payout = float(p["stake"] or 0) * adj_odds
            final_payout = round(min(payout, adj_payout) if adj_odds < float(p["total_odds"] or 1)
                                 else payout, 2)
            settle_parlay(p["id"], "won", final_payout)
            settled.append({"parlay": get_parlay(p["id"]),
                            "selections": get_selections(p["id"]),
                            "status": "won", "payout": final_payout})

    if settled:
        log.info("Settled %d parlays", len(settled))
    return settled
