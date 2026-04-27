import math
from typing import List, Dict


TEAM_STRENGTH_DEFAULT = 0.5


def _team_strength(team: str) -> float:
    h = sum(ord(c) for c in team) % 100
    return 0.35 + (h / 100) * 0.5


def _poisson_pmf(lmbda: float, k: int) -> float:
    return math.exp(-lmbda) * (lmbda ** k) / math.factorial(k)


def _match_probs(home_str: float, away_str: float) -> Dict[str, float]:
    home_xg = 1.1 + home_str * 1.4
    away_xg = 0.8 + away_str * 1.2

    p_home = p_draw = p_away = 0.0
    for i in range(0, 6):
        for j in range(0, 6):
            p = _poisson_pmf(home_xg, i) * _poisson_pmf(away_xg, j)
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p

    total = p_home + p_draw + p_away
    return {
        "home": p_home / total,
        "draw": p_draw / total,
        "away": p_away / total,
        "home_xg": home_xg,
        "away_xg": away_xg,
    }


def _odds_from_prob(p: float, vig: float = 0.05) -> float:
    if p <= 0:
        return 99.0
    fair = 1 / p
    return round(fair * (1 - vig), 2)


def _confidence(prob: float, odds: float, edge_bias: float = 0.0) -> int:
    base = prob * 100
    edge = (prob * odds - 1) * 30
    score = base + edge + edge_bias
    return max(0, min(100, int(score)))


def analyse_fixture(fx: Dict) -> List[Dict]:
    home_str = _team_strength(fx["home"])
    away_str = _team_strength(fx["away"])
    probs = _match_probs(home_str, away_str)

    selections = []

    home_odds = _odds_from_prob(probs["home"])
    draw_odds = _odds_from_prob(probs["draw"])
    away_odds = _odds_from_prob(probs["away"])

    if probs["home"] >= 0.45:
        selections.append({
            "market": "1X2",
            "pick": "home",
            "label": f"{fx['home']} to win",
            "odds": home_odds,
            "prob": round(probs["home"], 3),
            "confidence": _confidence(probs["home"], home_odds, 5),
        })
    if probs["away"] >= 0.45:
        selections.append({
            "market": "1X2",
            "pick": "away",
            "label": f"{fx['away']} to win",
            "odds": away_odds,
            "prob": round(probs["away"], 3),
            "confidence": _confidence(probs["away"], away_odds, 5),
        })
    if probs["draw"] >= 0.32:
        selections.append({
            "market": "1X2",
            "pick": "draw",
            "label": "Draw",
            "odds": draw_odds,
            "prob": round(probs["draw"], 3),
            "confidence": _confidence(probs["draw"], draw_odds, 0),
        })

    p_1x = probs["home"] + probs["draw"]
    p_x2 = probs["away"] + probs["draw"]
    if p_1x >= 0.62:
        odds = _odds_from_prob(p_1x)
        selections.append({
            "market": "DC",
            "pick": "1X",
            "label": f"{fx['home']} or Draw",
            "odds": odds,
            "prob": round(p_1x, 3),
            "confidence": _confidence(p_1x, odds, 4),
        })
    if p_x2 >= 0.62:
        odds = _odds_from_prob(p_x2)
        selections.append({
            "market": "DC",
            "pick": "X2",
            "label": f"{fx['away']} or Draw",
            "odds": odds,
            "prob": round(p_x2, 3),
            "confidence": _confidence(p_x2, odds, 4),
        })

    expected_goals = probs["home_xg"] + probs["away_xg"]
    over_prob = 1 - sum(_poisson_pmf(expected_goals, k) for k in range(0, 3))
    over_prob = max(0.05, min(0.95, over_prob))
    under_prob = 1 - over_prob
    if over_prob >= 0.55:
        odds = _odds_from_prob(over_prob)
        selections.append({
            "market": "OU",
            "pick": "over_2_5",
            "label": "Over 2.5 goals",
            "odds": odds,
            "prob": round(over_prob, 3),
            "confidence": _confidence(over_prob, odds, 3),
        })
    if under_prob >= 0.55:
        odds = _odds_from_prob(under_prob)
        selections.append({
            "market": "OU",
            "pick": "under_2_5",
            "label": "Under 2.5 goals",
            "odds": odds,
            "prob": round(under_prob, 3),
            "confidence": _confidence(under_prob, odds, 3),
        })

    p_home_scores = 1 - _poisson_pmf(probs["home_xg"], 0)
    p_away_scores = 1 - _poisson_pmf(probs["away_xg"], 0)
    btts_yes = p_home_scores * p_away_scores
    attack_factor = (home_str + away_str) / 2
    btts_yes = 0.6 * btts_yes + 0.4 * (0.55 + (attack_factor - 0.5) * 0.20)
    btts_yes = max(0.25, min(0.85, btts_yes))
    btts_no = 1 - btts_yes

    if btts_yes >= 0.6:
        yes_odds = _odds_from_prob(btts_yes)
        selections.append({
            "market": "BTTS",
            "pick": "yes",
            "label": "Both teams to score: Yes",
            "odds": yes_odds,
            "prob": round(btts_yes, 3),
            "confidence": _confidence(btts_yes, yes_odds, 0),
        })
    if btts_no >= 0.6:
        no_odds = _odds_from_prob(btts_no)
        selections.append({
            "market": "BTTS",
            "pick": "no",
            "label": "Both teams to score: No",
            "odds": no_odds,
            "prob": round(btts_no, 3),
            "confidence": _confidence(btts_no, no_odds, 0),
        })

    return selections
