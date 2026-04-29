import aiohttp
import asyncio
from config import ESPN_BASE, LEAGUES

_TIMEOUT = aiohttp.ClientTimeout(total=15)


class ESPNClient:
    def __init__(self):
        self.session = None

    async def _get_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=_TIMEOUT)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_scoreboard(self, league: str, date: str = None):
        """Fetch fixtures + odds from ESPN. league is like 'soccer/eng.1'"""
        url = ESPN_BASE.format(path=league)
        params = {"dates": date} if date else {}
        session = await self._get_session()
        try:
            async with session.get(url, params=params) as r:
                if r.status != 200:
                    return None
                return await r.json()
        except Exception:
            return None

    async def fetch_all_leagues(self, date: str = None, leagues=None):
        leagues = leagues or list(LEAGUES.keys())
        tasks = [self.fetch_scoreboard(lg, date) for lg in leagues]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return dict(zip(leagues, results))

    @staticmethod
    def parse_events(raw, league_code):
        """Extract normalized fixture data with odds. Supports multiple sports."""
        if not raw or "events" not in raw:
            return []

        fixtures = []
        sport = league_code.split("/")[0] if "/" in league_code else "soccer"

        for event in raw["events"]:
            try:
                comp = event["competitions"][0]
                competitors = comp["competitors"]

                if sport == "soccer":
                    home = next((c for c in competitors if c["homeAway"] == "home"), None)
                    away = next((c for c in competitors if c["homeAway"] == "away"), None)
                    if not home or not away:
                        continue
                    home_form = home.get("form", "")
                    away_form = away.get("form", "")
                    draw_odds = comp.get("odds", [{}])[0].get("drawOdds")
                else:
                    # NBA, NFL, MLB, NHL - no draw, no form
                    home = competitors[0] if competitors[0]["homeAway"] == "home" else competitors[1]
                    away = competitors[1] if competitors[1]["homeAway"] == "away" else competitors[0]
                    if not home or not away:
                        continue
                    home_form = ""
                    away_form = ""
                    draw_odds = None

                fixture = {
                    "id": event["id"],
                    "league": league_code,
                    "sport": sport,
                    "date": event["date"],
                    "status": event["status"]["type"]["state"],
                    "home_team": home["team"]["displayName"],
                    "away_team": away["team"]["displayName"],
                    "home_score": int(home.get("score", 0) or 0),
                    "away_score": int(away.get("score", 0) or 0),
                    "home_form": home_form,
                    "away_form": away_form,
                    "venue": comp.get("venue", {}).get("fullName", ""),
                    "odds": None,
                }

                if comp.get("odds"):
                    o = comp["odds"][0]
                    fixture["odds"] = {
                        "details":    o.get("details", ""),
                        "over_under": o.get("overUnder"),
                        "spread":     o.get("spread"),
                        "home_ml":    o.get("homeTeamOdds", {}).get("moneyLine"),
                        "away_ml":    o.get("awayTeamOdds", {}).get("moneyLine"),
                        "draw_odds":  o.get("drawOdds", {}).get("moneyLine") if draw_odds else None,
                        "provider":   o.get("provider", {}).get("name", "DraftKings"),
                    }
                fixtures.append(fixture)
            except Exception as e:
                continue
        return fixtures

