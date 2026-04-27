from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
from database.db import SessionLocal, Parlay, User
from services.espn_api import ESPNClient


class ParlayTracker:
    def __init__(self):
        self.client = ESPNClient()

    async def save_parlay(self, user_id, target_odds, parlay, stake=0,
                          challenge_type=None, challenge_stage=None):
        async with SessionLocal() as s:
            sels = [{
                "fixture_id": x["fixture"]["id"],
                "league": x["fixture"]["league"],
                "home": x["fixture"]["home_team"],
                "away": x["fixture"]["away_team"],
                "date": x["fixture"]["date"],
                "market": x["market"],
                "selection": x["selection"],
                "label": x["label"],
                "odds": x["odds"],
                "probability": x["probability"],
                "confidence": x["confidence"],
                "result": "pending",
            } for x in parlay["selections"]]

            p = Parlay(
                user_id=user_id,
                target_odds=target_odds,
                total_odds=parlay["total_odds"],
                stake=stake,
                selections=sels,
                challenge_type=challenge_type,
                challenge_stage=challenge_stage,
            )
            s.add(p)
            await s.commit()
            await s.refresh(p)
            return p.id

    async def settle_pending(self):
        """Check pending parlays, update fixture results, settle."""
        async with SessionLocal() as s:
            res = await s.execute(select(Parlay).where(Parlay.status == "pending"))
            pending = res.scalars().all()

            for parlay in pending:
                all_done = True
                any_lost = False
                updated = []
                for sel in parlay.selections:
                    if sel["result"] != "pending":
                        updated.append(sel)
                        continue
                    result = await self._check_selection(sel)
                    sel["result"] = result
                    if result == "pending":
                        all_done = False
                    elif result == "lost":
                        any_lost = True
                    updated.append(sel)
                parlay.selections = updated
                flag_modified(parlay, "selections")
                if any_lost:
                    parlay.status = "lost"
                    parlay.settled_at = datetime.utcnow()
                elif all_done:
                    parlay.status = "won"
                    parlay.settled_at = datetime.utcnow()
            await s.commit()

    async def _check_selection(self, sel):
        date = sel["date"][:10].replace("-", "")
        data = await self.client.fetch_scoreboard(sel["league"], date)
        if not data:
            return "pending"
        fixtures = ESPNClient.parse_events(data, sel["league"])
        fx = next((f for f in fixtures if f["id"] == sel["fixture_id"]), None)
        if not fx or fx["status"] != "post":
            return "pending"

        h, a = fx["home_score"], fx["away_score"]
        market, selection = sel["market"], sel["selection"]

        if market == "1X2":
            if selection == "Home Win":
                return "won" if h > a else "lost"
            if selection == "Away Win":
                return "won" if a > h else "lost"
            if selection == "Draw":
                return "won" if h == a else "lost"
        if market == "DC":
            if selection == "1X":
                return "won" if h >= a else "lost"
            if selection == "X2":
                return "won" if a >= h else "lost"
        if market == "OU":
            line = float(selection.split()[1])
            total = h + a
            if selection.startswith("Over"):
                return "won" if total > line else "lost"
            else:
                return "won" if total < line else "lost"
        if market == "BTTS":
            both = h > 0 and a > 0
            if selection == "Yes":
                return "won" if both else "lost"
            else:
                return "won" if not both else "lost"
        return "pending"

    async def user_stats(self, user_id):
        async with SessionLocal() as s:
            res = await s.execute(select(Parlay).where(Parlay.user_id == user_id))
            parlays = res.scalars().all()
            total = len(parlays)
            won = sum(1 for p in parlays if p.status == "won")
            lost = sum(1 for p in parlays if p.status == "lost")
            pending = sum(1 for p in parlays if p.status == "pending")
            staked = sum(p.stake for p in parlays if p.status != "pending")
            returns = sum(p.stake * p.total_odds for p in parlays if p.status == "won")
            profit = returns - staked
            roi = (profit / staked * 100) if staked > 0 else 0
            return {
                "total": total, "won": won, "lost": lost, "pending": pending,
                "win_rate": (won / (won + lost) * 100) if (won + lost) else 0,
                "profit": profit, "roi": roi, "staked": staked,
            }
