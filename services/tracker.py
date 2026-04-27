import logging
from datetime import datetime
from typing import List, Dict
from sqlalchemy import select

from database.db import async_session, Parlay, Selection, User
from services.espn_api import get_fixture_result

logger = logging.getLogger(__name__)


async def save_parlay(user_id: int, parlay: dict, stake: float = 0) -> int:
    async with async_session() as s:
        # ensure user
        u = await s.scalar(select(User).where(User.tg_id == user_id))
        if not u:
            u = User(tg_id=user_id)
            s.add(u)
            await s.flush()

        p = Parlay(
            user_id=u.id,
            risk=parlay["risk"],
            total_odds=parlay["total_odds"],
            stake=stake or 0,
            status="pending",
            created_at=datetime.utcnow(),
        )
        s.add(p)
        await s.flush()

        for leg in parlay["legs"]:
            sel = Selection(
                parlay_id=p.id,
                fixture_id=leg["fixture_id"],
                home=leg["home"],
                away=leg["away"],
                league=leg.get("league", ""),
                market=leg["market"],
                pick=leg["pick"],
                label=leg["label"],
                odds=leg["odds"],
                confidence=leg["confidence"],
                kickoff=leg.get("kickoff"),
                result=None,
            )
            s.add(sel)

        await s.commit()
        return p.id


async def settle_pending() -> List[Dict]:
    """Settle any pending parlays whose fixtures have finished.

    Returns a list of dicts describing parlays that *just* moved to a
    terminal state, so the caller can notify users.
    """
    notifications: List[Dict] = []

    async with async_session() as s:
        pending = (await s.execute(
            select(Parlay).where(Parlay.status == "pending")
        )).scalars().all()

        # Cache fixture results within this run so multiple parlays sharing
        # a fixture don't trigger duplicate HTTP calls.
        result_cache: Dict[str, Dict] = {}

        for p in pending:
            sels = (await s.execute(
                select(Selection).where(Selection.parlay_id == p.id)
            )).scalars().all()

            all_done = True
            won = True
            any_void_only = True  # track if every settled leg is void
            for sel in sels:
                if sel.result is not None:
                    if sel.result == "lost":
                        won = False
                        any_void_only = False
                    elif sel.result == "won":
                        any_void_only = False
                    continue

                if sel.fixture_id in result_cache:
                    res = result_cache[sel.fixture_id]
                else:
                    try:
                        res = await get_fixture_result(sel.fixture_id)
                    except Exception:
                        logger.exception("result fetch failed for %s", sel.fixture_id)
                        res = None
                    result_cache[sel.fixture_id] = res

                if not res:
                    all_done = False
                    continue

                outcome = _check_selection(sel, res)
                sel.result = outcome
                if outcome == "lost":
                    won = False
                    any_void_only = False
                elif outcome == "won":
                    any_void_only = False

            if not all_done:
                continue

            # Decide final status. If literally every leg voided, flag void
            # rather than falsely marking as won.
            if any_void_only:
                p.status = "void"
            else:
                p.status = "won" if won else "lost"
            p.settled_at = datetime.utcnow()

            # Build notification payload
            user = await s.get(User, p.user_id)
            if user:
                notifications.append({
                    "tg_id": user.tg_id,
                    "notify": bool(user.notify),
                    "parlay_id": p.id,
                    "status": p.status,
                    "total_odds": p.total_odds,
                    "actual_odds": p.actual_odds,
                    "stake": p.stake or 0,
                })

        await s.commit()

    return notifications


def _check_selection(sel, result: dict) -> str:
    hs, as_ = result.get("home_score"), result.get("away_score")
    if hs is None or as_ is None:
        return "void"

    m, pick = sel.market, sel.pick
    if m == "1X2":
        if pick == "home":
            return "won" if hs > as_ else "lost"
        if pick == "away":
            return "won" if as_ > hs else "lost"
        if pick == "draw":
            return "won" if hs == as_ else "lost"
    if m == "OU":
        total = hs + as_
        if pick == "over_2_5":
            return "won" if total > 2.5 else "lost"
        if pick == "under_2_5":
            return "won" if total < 2.5 else "lost"
    if m == "BTTS":
        both = hs > 0 and as_ > 0
        if pick == "yes":
            return "won" if both else "lost"
        if pick == "no":
            return "won" if not both else "lost"
    if m == "DC":
        if pick == "1X":
            return "won" if hs >= as_ else "lost"
        if pick == "X2":
            return "won" if as_ >= hs else "lost"
    return "void"
