import hashlib
import time
from typing import List, Dict, Optional

from services.espn_api import get_today_fixtures
from services.analytics import analyse_fixture


RISK_PROFILES = {
    "safe": {"min_conf": 75, "max_odds": 1.8, "target_total": 2.5},
    "balanced": {"min_conf": 60, "max_odds": 3.0, "target_total": 5.0},
    "risky": {"min_conf": 45, "max_odds": 6.0, "target_total": 15.0},
}


# Friendly labels for UI buttons
MARKET_LABELS = {
    "1X2": "Win",
    "DC": "Win or Draw",
    "OU": "Goals",
    "BTTS": "BTTS",
    "ANY": "Any",
}


async def gather_selections(markets: Optional[List[str]] = None) -> List[Dict]:
    fixtures = await get_today_fixtures()
    if not fixtures:
        return []

    selections = []
    for fx in fixtures:
        analysis = analyse_fixture(fx)
        for sel in analysis:
            if markets and sel["market"] not in markets:
                continue
            selections.append({
                "fixture_id": fx["id"],
                "home": fx["home"],
                "away": fx["away"],
                "league": fx["league"],
                "kickoff": fx["kickoff"],
                **sel,
            })
    return selections


async def build_parlay(
    legs: int,
    risk: str,
    markets: Optional[List[str]] = None,
) -> Dict:
    """Build a parlay.

    Args:
        legs: number of selections (2..6)
        risk: "safe" | "balanced" | "risky"
        markets: optional list of market codes to restrict to, e.g. ["1X2", "DC"].
                 None or empty means no restriction.
    """
    profile = RISK_PROFILES.get(risk, RISK_PROFILES["balanced"])

    # Treat empty list / "ANY" sentinel as no filter
    if markets and "ANY" in markets:
        markets = None

    selections = await gather_selections(markets=markets)

    selections = [
        s for s in selections
        if s["confidence"] >= profile["min_conf"]
        and s["odds"] <= profile["max_odds"]
    ]
    selections.sort(key=lambda x: x["confidence"], reverse=True)

    used_fixtures = set()
    chosen = []
    for sel in selections:
        if sel["fixture_id"] in used_fixtures:
            continue
        chosen.append(sel)
        used_fixtures.add(sel["fixture_id"])
        if len(chosen) == legs:
            break

    if len(chosen) < legs:
        return {}

    total_odds = 1.0
    for c in chosen:
        total_odds *= c["odds"]

    cache_id = hashlib.md5(
        f"{time.time()}:{legs}:{risk}:{markets}".encode()
    ).hexdigest()[:10]

    return {
        "cache_id": cache_id,
        "legs": chosen,
        "total_odds": round(total_odds, 2),
        "risk": risk,
        "markets": markets or ["ANY"],
        "target_total": profile["target_total"],
    }
