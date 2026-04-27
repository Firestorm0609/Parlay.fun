import logging
from datetime import datetime
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"


async def get_today_fixtures() -> List[Dict]:
    today = datetime.utcnow().strftime("%Y%m%d")
    url = f"{SCOREBOARD_URL}?dates={today}"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error("espn fetch failed: %s", e)
            return []

    fixtures = []
    for ev in data.get("events", []):
        try:
            comp = ev["competitions"][0]
            home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
            away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
            fixtures.append({
                "id": ev["id"],
                "home": home["team"]["displayName"],
                "away": away["team"]["displayName"],
                "league": ev.get("league", {}).get("name") or comp.get("league", {}).get("name", ""),
                "kickoff": ev.get("date"),
                "status": comp.get("status", {}).get("type", {}).get("state"),
            })
        except (KeyError, StopIteration):
            continue
    return fixtures


async def get_fixture_result(fixture_id: str) -> Optional[Dict]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary?event={fixture_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error("espn summary fetch failed for %s: %s", fixture_id, e)
            return None

    try:
        header = data.get("header", {})
        comp = header["competitions"][0]
        status = comp.get("status", {}).get("type", {}).get("state")
        if status != "post":
            return None
        home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
        away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
        return {
            "fixture_id": fixture_id,
            "home_score": int(home.get("score", 0)),
            "away_score": int(away.get("score", 0)),
            "status": status,
        }
    except (KeyError, StopIteration, ValueError):
        return None
