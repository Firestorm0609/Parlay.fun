from itertools import combinations
from datetime import datetime
from services.espn_api import ESPNClient
from services.analytics import evaluate_market
from config import RISK_LEVELS, LEAGUES


class ParlayEngine:
    def __init__(self):
        self.client = ESPNClient()

    async def gather_selections(self, date: str = None, markets=None):
        markets = markets or ["1X2", "OU", "BTTS", "ML"]
        raw = await self.client.fetch_all_leagues(date)
        all_selections = []

        for league_code, data in raw.items():
            if isinstance(data, Exception) or not data:
                continue
            fixtures = ESPNClient.parse_events(data, league_code)
            for fx in fixtures:
                if fx["status"] != "pre":
                    continue
                # Only use BTTS/1X2 for soccer
                if fx.get("sport") == "soccer":
                    mkt_list = ["1X2", "OU", "BTTS"]
                else:
                    mkt_list = ["OU", "ML"]  # NBA/NFL/MLB/NHL: Over/Under + Money Line
                for m in mkt_list:
                    all_selections.extend(evaluate_market(fx, m))
        return all_selections

    def build_parlay(self, selections, target_odds, risk="balanced", tolerance=0.15):
        """Find a combination of selections close to target_odds."""
        cfg = RISK_LEVELS[risk]

        # Dynamic tolerance: tighter for low targets, looser for high targets
        if target_odds >= 10:
            tolerance = 0.30  # Allow 30% deviation for high-odds parlays
        elif target_odds >= 5:
            tolerance = 0.20

        # Filter by criteria
        pool = [
            s for s in selections
            if s["probability"] >= cfg["min_prob"]
            and s["odds"] <= cfg["max_odds_per_leg"]
            and s["confidence"] >= 40
        ]
        # Sort by confidence
        pool.sort(key=lambda x: x["confidence"], reverse=True)
        # Dynamic pool size: more selections for higher targets
        pool_limit = min(80 if target_odds >= 10 else 40, len(pool))
        pool = pool[:pool_limit]

        # Avoid same fixture twice
        best = None
        best_diff = float("inf")
        max_legs = cfg["max_legs"]

        target_min = target_odds * (1 - tolerance)
        target_max = target_odds * (1 + tolerance)

        for n in range(1, max_legs + 1):
            for combo in combinations(pool, n):
                fids = [s["fixture"]["id"] for s in combo]
                if len(set(fids)) != len(fids):
                    continue
                total = 1.0
                for s in combo:
                    total *= s["odds"]
                if target_min <= total <= target_max:
                    # score: prefer higher avg confidence + closer to target
                    avg_conf = sum(s["confidence"] for s in combo) / len(combo)
                    diff = abs(total - target_odds) / target_odds - (avg_conf / 1000)
                    if diff < best_diff:
                        best_diff = diff
                        best = {
                            "selections": list(combo),
                            "total_odds": round(total, 2),
                            "avg_confidence": round(avg_conf, 1),
                            "combined_probability": _combined_prob(combo),
                        }
            if best and n >= 2:
                # good enough, stop early to save CPU
                break
        return best

    async def close(self):
        await self.client.close()


def _combined_prob(combo):
    p = 1.0
    for s in combo:
        p *= s["probability"]
    return round(p, 4)
