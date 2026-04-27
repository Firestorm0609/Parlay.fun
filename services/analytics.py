"""
Probability + market-builder + result-checker logic.

Major upgrades vs original:
- Deterministic odds-per-event (seeded by event_id) so refreshes are stable
- DC (Double Chance) market generation
- Robust result checking with team-name normalisation
- Spread/Total parsing fixed
- ML draw handling
"""
import math
import random
from typing import List, Dict


# ---------- Probability helpers ----------
def implied_prob(odds: float) -> float:
    return 1.0 / odds if odds and odds > 0 else 0.0


def fair_odds_from_prob(p: float, vig: float = 0.05) -> float:
    """Convert probability → odds, applying a small bookmaker margin."""
    p = max(0.02, min(0.98, p))
    return round(1.0 / (p * (1 + vig)), 2)


def estimate_team_strength(team_name: str) -> float:
    """Deterministic pseudo-strength from team name (0.40–0.99)."""
    h = sum(ord(c) for c in (team_name or ""))
    return 0.40 + ((h * 13) % 60) / 100.0


def home_advantage(sport: str) -> float:
    return {
        "soccer": 0.08, "basketball": 0.05, "football": 0.07,
        "baseball": 0.04, "hockey": 0.05,
    }.get(sport, 0.05)


def _seeded_rng(event_id, market):
    """Per-event deterministic RNG so a refresh shows stable odds."""
    seed = abs(hash(f"{event_id}:{market}")) % (2**31)
    return random.Random(seed)


# ---------- Market builder ----------
def build_market_options(event: Dict, sport: str, markets: List[str]) -> List[Dict]:
    """Generate plausible (event, market, pick, odds) options."""
    opts: List[Dict] = []
    home, away = event["home"], event["away"]
    s_home = estimate_team_strength(home) + home_advantage(sport)
    s_away = estimate_team_strength(away)

    # Soccer needs a draw probability
    if sport == "soccer":
        gap = abs(s_home - s_away)
        p_draw = max(0.18, 0.32 - gap * 0.3)
        remaining = 1 - p_draw
        denom = s_home + s_away
        p_home = remaining * (s_home / denom)
        p_away = remaining * (s_away / denom)
    else:
        denom = s_home + s_away
        p_home = s_home / denom
        p_away = s_away / denom
        p_draw = 0.0

    rng = _seeded_rng(event["id"], "core")

    if "ML" in markets or "Win" in markets:
        opts.append(_mk(event, "ML", f"{home} to win", fair_odds_from_prob(p_home)))
        opts.append(_mk(event, "ML", f"{away} to win", fair_odds_from_prob(p_away)))
        if sport == "soccer" and ("Draw" in markets or "ML" in markets):
            opts.append(_mk(event, "ML", "Draw", fair_odds_from_prob(p_draw)))

    if "DC" in markets and sport == "soccer":
        opts.append(_mk(event, "DC", f"1X ({home} or Draw)",
                        fair_odds_from_prob(p_home + p_draw)))
        opts.append(_mk(event, "DC", f"X2 ({away} or Draw)",
                        fair_odds_from_prob(p_away + p_draw)))
        opts.append(_mk(event, "DC", f"12 ({home} or {away})",
                        fair_odds_from_prob(p_home + p_away)))

    if "Spread" in markets:
        line = round((s_home - s_away) * 5, 1)
        line = round(line * 2) / 2
        if line == 0:
            line = 0.5
        opts.append(_mk(event, "Spread",
                        f"{home} {-abs(line):+.1f}",
                        round(rng.uniform(1.80, 1.95), 2)))
        opts.append(_mk(event, "Spread",
                        f"{away} {abs(line):+.1f}",
                        round(rng.uniform(1.80, 1.95), 2)))

    if "Total" in markets or "Goals" in markets:
        ou_line = _ou_line(sport)
        opts.append(_mk(event, "Total", f"Over {ou_line}",
                        round(rng.uniform(1.80, 2.00), 2)))
        opts.append(_mk(event, "Total", f"Under {ou_line}",
                        round(rng.uniform(1.80, 2.00), 2)))

    if "BTTS" in markets and sport == "soccer":
        p_btts = min(0.78, 0.45 + (s_home + s_away - 1) * 0.4)
        opts.append(_mk(event, "BTTS", "Yes", fair_odds_from_prob(p_btts)))
        opts.append(_mk(event, "BTTS", "No", fair_odds_from_prob(1 - p_btts)))

    if "CorrectScore" in markets and sport == "soccer":
        rng2 = _seeded_rng(event["id"], "cs")
        for sc in ["1-0", "2-1", "2-0", "1-1", "0-0", "0-1"]:
            opts.append(_mk(event, "CorrectScore", sc, round(rng2.uniform(5.5, 14.0), 2)))

    return opts


def _ou_line(sport: str) -> float:
    return {
        "soccer": 2.5, "basketball": 220.5, "football": 45.5,
        "baseball": 8.5, "hockey": 6.5,
    }.get(sport, 2.5)


def _mk(event, market, pick, odds):
    return {
        "event_id": event["id"],
        "event_name": f"{event['away']} @ {event['home']}",
        "home": event["home"],
        "away": event["away"],
        "market": market,
        "pick": pick,
        "odds": round(odds, 2),
    }


# ---------- Scoring ----------
def score_selection(opt: Dict, profile: Dict) -> float:
    o = opt["odds"]
    mid = (profile["min_odds"] + profile["max_odds"]) / 2
    span = max(profile["max_odds"] - profile["min_odds"], 0.01)
    closeness = 1 - abs(o - mid) / span
    market_bias = {
        "ML": 1.10, "Total": 1.05, "DC": 1.08, "Spread": 1.00,
        "BTTS": 0.95, "CorrectScore": 0.85,
    }.get(opt["market"], 1.0)
    rng = _seeded_rng(opt["event_id"], opt["pick"])
    return round(closeness * market_bias + rng.uniform(0, 0.12), 4)


def compute_total_odds(selections: List[Dict]) -> float:
    total = 1.0
    for s in selections:
        total *= s.get("odds", 1.0)
    return round(total, 2)


# ---------- Result checking ----------
def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _check_selection(sel: Dict, event_summary: Dict) -> str:
    """Decide W/L/pending for a selection given an event summary."""
    if not event_summary or not event_summary.get("completed"):
        return "pending"
    try:
        h = float(event_summary.get("home_score") or 0)
        a = float(event_summary.get("away_score") or 0)
    except (TypeError, ValueError):
        return "pending"

    market = sel["market"]
    pick = sel["pick"]
    home = event_summary.get("home") or ""
    away = event_summary.get("away") or ""

    # ---- Moneyline ----
    if market == "ML":
        if pick == "Draw":
            return "won" if h == a else "lost"
        if "to win" in pick.lower():
            team = pick.lower().replace(" to win", "").strip()
            if h > a and _norm(home) == team:
                return "won"
            if a > h and _norm(away) == team:
                return "won"
            return "lost"
        return "pending"

    # ---- Double Chance ----
    if market == "DC":
        winner = "home" if h > a else "away" if a > h else "draw"
        code = pick.split()[0]  # 1X / X2 / 12
        if code == "1X":
            return "won" if winner in ("home", "draw") else "lost"
        if code == "X2":
            return "won" if winner in ("away", "draw") else "lost"
        if code == "12":
            return "won" if winner in ("home", "away") else "lost"
        return "pending"

    # ---- Totals ----
    if market == "Total":
        try:
            line = float(pick.split()[-1])
        except (ValueError, IndexError):
            return "pending"
        total_pts = h + a
        if pick.startswith("Over"):
            if total_pts == line:
                return "push"
            return "won" if total_pts > line else "lost"
        if pick.startswith("Under"):
            if total_pts == line:
                return "push"
            return "won" if total_pts < line else "lost"
        return "pending"

    # ---- BTTS ----
    if market == "BTTS":
        btts = h > 0 and a > 0
        return "won" if (pick == "Yes") == btts else "lost"

    # ---- Spread ----
    if market == "Spread":
        try:
            sign_line = float(pick.split()[-1])
        except (ValueError, IndexError):
            return "pending"
        is_home_pick = _norm(pick).startswith(_norm(home))
        margin = (h - a) if is_home_pick else (a - h)
        adjusted = margin + sign_line
        if adjusted == 0:
            return "push"
        return "won" if adjusted > 0 else "lost"

    # ---- Correct Score ----
    if market == "CorrectScore":
        return "won" if f"{int(h)}-{int(a)}" == pick else "lost"

    return "pending"
