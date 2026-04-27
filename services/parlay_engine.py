"""
Parlay generator.

Upgrades:
- gather_selections() honours user-chosen market filters
- generate_parlay() supports "Any" market (no filter), graceful fallback when fewer events match
- Lottery mode mixes scored picks with random long-shots
"""
import random
from typing import List, Dict, Optional

from services.espn_api import fetch_scoreboard, parse_event
from services.analytics import build_market_options, score_selection


# Default markets per risk band when the user picks "Any"
RISK_PROFILES = {
    "safe":     {"picks": 3, "min_odds": 1.30, "max_odds": 1.85,
                 "markets": ["ML", "Spread", "DC"]},
    "balanced": {"picks": 4, "min_odds": 1.50, "max_odds": 2.50,
                 "markets": ["ML", "Total", "Spread", "DC"]},
    "risky":    {"picks": 5, "min_odds": 1.80, "max_odds": 4.00,
                 "markets": ["ML", "Total", "BTTS", "Spread"]},
    "lottery":  {"picks": 6, "min_odds": 2.50, "max_odds": 8.00,
                 "markets": ["ML", "Total", "BTTS", "CorrectScore"]},
}

# Map of UI filter → analytics market list
MARKET_FILTER_MAP = {
    "any":          None,                       # use risk-profile default
    "win":          ["ML"],
    "draw":         ["ML"],                     # we'll filter to Draw picks below
    "goals":        ["Total"],
    "btts":         ["BTTS"],
    "dc":           ["DC"],
    "spread":       ["Spread"],
    "correctscore": ["CorrectScore"],
}


async def gather_selections(sport: str,
                            risk: str,
                            markets: Optional[List[str]] = None,
                            market_filter: Optional[str] = None) -> List[Dict]:
    """
    Returns a flat list of scored selection dicts.
    `market_filter` is the UI string (any/win/draw/goals/btts/dc/spread/correctscore).
    `markets` is an explicit list of analytics market codes (overrides filter).
    """
    profile = RISK_PROFILES.get(risk, RISK_PROFILES["balanced"])
    events = await fetch_scoreboard(sport)
    parsed = [parse_event(e) for e in events if e]
    upcoming = [e for e in parsed if e.get("status") in ("pre", "in")]

    if markets is None:
        if market_filter and market_filter in MARKET_FILTER_MAP:
            mapped = MARKET_FILTER_MAP[market_filter]
            markets = mapped if mapped else profile["markets"]
        else:
            markets = profile["markets"]

    selections: List[Dict] = []
    for ev in upcoming:
        opts = build_market_options(ev, sport, markets)

        # Special-case "Draw only"
        if market_filter == "draw":
            opts = [o for o in opts if o["pick"] == "Draw"]
        # Special-case "Win or Draw" (== DC 1X / X2)
        if market_filter == "win_or_draw":
            opts = [o for o in opts if o["market"] == "DC" and o["pick"].startswith(("1X", "X2"))]

        for o in opts:
            if profile["min_odds"] <= o["odds"] <= profile["max_odds"]:
                o["score"] = score_selection(o, profile)
                selections.append(o)

    return selections


def generate_parlay(selections: List[Dict], risk: str) -> List[Dict]:
    profile = RISK_PROFILES.get(risk, RISK_PROFILES["balanced"])
    n = profile["picks"]
    if not selections:
        return []

    selections = list(selections)
    selections.sort(key=lambda s: s["score"], reverse=True)

    seen_events = set()
    chosen: List[Dict] = []
    for s in selections:
        if s["event_id"] in seen_events:
            continue
        seen_events.add(s["event_id"])
        chosen.append(s)
        if len(chosen) >= n:
            break

    # Lottery / risky → swap last leg with a random long-shot
    if risk in ("risky", "lottery") and len(selections) > n:
        pool = [s for s in selections
                if s["event_id"] not in {c["event_id"] for c in chosen[:-1]}]
        pool.sort(key=lambda s: s["odds"], reverse=True)  # bias long shots
        head = pool[: max(3, n)]
        if head:
            random.shuffle(head)
            chosen[-1] = head[0]

    return chosen
