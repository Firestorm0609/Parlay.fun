"""
ESPN public scoreboard / summary client.

Upgrades vs original:
- Retries with exponential backoff
- Returns normalized event summaries for the tracker
- Soccer covers multiple major leagues (EPL, La Liga, Serie A, UCL, MLS)
- Optional log warnings on persistent failures
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import httpx

log = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# A sport may map to multiple ESPN league paths; we merge their scoreboards.
SPORT_PATHS = {
    "soccer": [
        "soccer/eng.1",      # Premier League
        "soccer/esp.1",      # La Liga
        "soccer/ita.1",      # Serie A
        "soccer/ger.1",      # Bundesliga
        "soccer/fra.1",      # Ligue 1
        "soccer/uefa.champions",
        "soccer/usa.1",      # MLS
    ],
    "basketball": ["basketball/nba"],
    "football":   ["football/nfl"],
    "baseball":   ["baseball/mlb"],
    "hockey":     ["hockey/nhl"],
}


async def _get_json(url: str, params: Dict[str, Any] = None, retries: int = 3) -> Dict[str, Any]:
    delay = 0.7
    last_err = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as cli:
                r = await cli.get(url, params=params or {})
                r.raise_for_status()
                return r.json()
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
    log.warning("ESPN GET failed (%s) %s params=%s", last_err, url, params)
    return {}


async def fetch_scoreboard(sport: str, days_ahead: int = 2) -> List[Dict]:
    paths = SPORT_PATHS.get(sport, [])
    if not paths:
        return []
    d1 = datetime.utcnow().strftime("%Y%m%d")
    d2 = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y%m%d")
    params = {"dates": f"{d1}-{d2}"} if days_ahead else {}

    tasks = [_get_json(f"{ESPN_BASE}/{p}/scoreboard", params) for p in paths]
    results = await asyncio.gather(*tasks)
    events: List[Dict] = []
    for j in results:
        for ev in j.get("events", []) or []:
            events.append(ev)
    return events


async def fetch_event_summary_raw(sport: str, event_id: str) -> Dict:
    """ESPN summary payload (raw)."""
    paths = SPORT_PATHS.get(sport, [])
    for p in paths:
        url = f"{ESPN_BASE}/{p}/summary"
        data = await _get_json(url, {"event": event_id}, retries=2)
        if data and (data.get("header") or data.get("boxscore")):
            return data
    return {}


async def fetch_event_summary(sport: str, event_id: str) -> Dict:
    """Normalized summary used by the settlement engine."""
    data = await fetch_event_summary_raw(sport, event_id)
    if not data:
        return {}
    header = data.get("header") or {}
    competitions = header.get("competitions") or [{}]
    comp = competitions[0]
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status = (header.get("status") or {}).get("type") or {}
    return {
        "id": event_id,
        "home": (home.get("team") or {}).get("displayName"),
        "away": (away.get("team") or {}).get("displayName"),
        "home_score": home.get("score"),
        "away_score": away.get("score"),
        "completed": status.get("completed", False),
        "state": status.get("state", "pre"),
    }


def parse_event(ev: Dict) -> Dict:
    """Reduce ESPN scoreboard event → clean dict."""
    comp = (ev.get("competitions") or [{}])[0]
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status = (ev.get("status") or {}).get("type") or {}
    return {
        "id": ev.get("id"),
        "name": ev.get("name") or ev.get("shortName") or "Unknown",
        "date": ev.get("date"),
        "status": status.get("state", "pre"),
        "home": (home.get("team") or {}).get("displayName") or "Home",
        "away": (away.get("team") or {}).get("displayName") or "Away",
        "home_score": home.get("score"),
        "away_score": away.get("score"),
        "completed": status.get("completed", False),
    }
