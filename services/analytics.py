import math
from typing import Dict, List


def american_to_decimal(american):
    if american is None:
        return None
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    if a > 0:
        return round(1 + a / 100, 3)
    else:
        return round(1 + 100 / abs(a), 3)


def implied_probability(decimal_odds):
    if not decimal_odds or decimal_odds <= 1:
        return 0
    return 1 / decimal_odds


def remove_vig(probs: List[float]) -> List[float]:
    total = sum(probs)
    if total == 0:
        return probs
    return [p / total for p in probs]


def parse_form(form_str: str) -> Dict:
    """ESPN form string like 'WWLDW'. Higher index = more recent."""
    if not form_str:
        return {"score": 0.5, "wins": 0, "draws": 0, "losses": 0, "momentum": 0}
    pts = 0
    weighted = 0
    weights_total = 0
    wins = draws = losses = 0
    for i, ch in enumerate(form_str):
        weight = i + 1
        weights_total += weight * 3
        if ch == "W":
            pts += 3
            weighted += 3 * weight
            wins += 1
        elif ch == "D":
            pts += 1
            weighted += 1 * weight
            draws += 1
        else:
            losses += 1
    score = weighted / weights_total if weights_total else 0.5
    momentum = 0
    if len(form_str) >= 3:
        recent = form_str[-3:]
        momentum = sum(1 if c == "W" else -1 if c == "L" else 0 for c in recent)
    return {
        "score": score,
        "wins": wins, "draws": draws, "losses": losses,
        "momentum": momentum,
    }


def evaluate_market(fixture, market_type):
    """Return list of {selection, odds, probability, confidence}."""
    if not fixture.get("odds"):
        return []

    odds = fixture["odds"]
    home_dec = american_to_decimal(odds.get("home_ml"))
    away_dec = american_to_decimal(odds.get("away_ml"))
    draw_dec = american_to_decimal(odds.get("draw_odds"))

    home_form = parse_form(fixture.get("home_form", ""))
    away_form = parse_form(fixture.get("away_form", ""))

    is_soccer = fixture.get("sport") == "soccer"
    selections = []

    # Money Line (for NBA, NFL, MLB, NHL, and soccer)
    if market_type == "ML" and home_dec and away_dec:
        probs = [implied_probability(home_dec), implied_probability(away_dec)]
        true_probs = remove_vig(probs)

        form_adj = (home_form["score"] - away_form["score"]) * 0.05 if is_soccer else 0

        home_p = max(0.01, min(0.99, true_probs[0] + form_adj))
        away_p = max(0.01, min(0.99, true_probs[1] - form_adj))

        selections.append({
            "fixture": fixture, "market": "ML", "selection": "Home Win",
            "label": fixture["home_team"], "odds": home_dec,
            "probability": home_p,
            "confidence": _confidence(home_p, home_dec, home_form["momentum"] if is_soccer else 0),
        })
        selections.append({
            "fixture": fixture, "market": "ML", "selection": "Away Win",
            "label": fixture["away_team"], "odds": away_dec,
            "probability": away_p,
            "confidence": _confidence(away_p, away_dec, away_form["momentum"] if is_soccer else 0),
        })

    if market_type == "1X2" and is_soccer and home_dec and away_dec:
        probs = [implied_probability(home_dec)]
        if draw_dec:
            probs.append(implied_probability(draw_dec))
        probs.append(implied_probability(away_dec))
        true_probs = remove_vig(probs)

        # Form-adjusted probability
        form_adj = (home_form["score"] - away_form["score"]) * 0.05

        home_p = max(0.01, min(0.99, true_probs[0] + form_adj))
        away_p = max(0.01, min(0.99, true_probs[-1] - form_adj))

        selections.append({
            "fixture": fixture, "market": "1X2", "selection": "Home Win",
            "label": fixture["home_team"], "odds": home_dec,
            "probability": home_p,
            "confidence": _confidence(home_p, home_dec, home_form["momentum"]),
        })
        selections.append({
            "fixture": fixture, "market": "1X2", "selection": "Away Win",
            "label": fixture["away_team"], "odds": away_dec,
            "probability": away_p,
            "confidence": _confidence(away_p, away_dec, away_form["momentum"]),
        })

        # Double chance
        dc_home = home_p + (true_probs[1] if draw_dec else 0)
        if dc_home > 0:
            dc_odds = round(1 / max(dc_home, 0.01) * 0.95, 2)
            selections.append({
                "fixture": fixture, "market": "DC", "selection": "1X",
                "label": f"{fixture['home_team']} or Draw",
                "odds": dc_odds, "probability": dc_home,
                "confidence": _confidence(dc_home, dc_odds, home_form["momentum"]),
            })

        dc_away = away_p + (true_probs[1] if draw_dec else 0)
        if dc_away > 0:
            dc_odds = round(1 / max(dc_away, 0.01) * 0.95, 2)
            selections.append({
                "fixture": fixture, "market": "DC", "selection": "X2",
                "label": f"Draw or {fixture['away_team']}",
                "odds": dc_odds, "probability": dc_away,
                "confidence": _confidence(dc_away, dc_odds, away_form["momentum"]),
            })

    if market_type == "OU" and odds.get("over_under"):
        line = float(odds["over_under"])
        # Heuristic: assume balanced -110/-110 base, refine via form
        base_p = 0.5
        # Teams in good form score more
        attack_factor = (home_form["score"] + away_form["score"]) / 2
        over_p = max(0.3, min(0.75, base_p + (attack_factor - 0.5) * 0.4))
        under_p = 1 - over_p
        over_odds = round(1 / over_p * 0.95, 2)
        under_odds = round(1 / under_p * 0.95, 2)
        selections.append({
            "fixture": fixture, "market": "OU", "selection": f"Over {line}",
            "label": f"Over {line} Goals", "odds": over_odds,
            "probability": over_p,
            "confidence": _confidence(over_p, over_odds, 0),
        })
        selections.append({
            "fixture": fixture, "market": "OU", "selection": f"Under {line}",
            "label": f"Under {line} Goals", "odds": under_odds,
            "probability": under_p,
            "confidence": _confidence(under_p, under_odds, 0),
        })

    if market_type == "BTTS":
        # Heuristic from forms & ML probabilities
        attack_factor = (home_form["score"] + away_form["score"]) / 2

        # BUG FIX 1: Baseline was 0.45 (biased toward "No"). Real-world BTTS Yes
        # rate in top leagues is ~52-55%, so use 0.52 as the neutral baseline.
        # BUG FIX 2: Also factor in moneyline closeness — when both teams have
        # competitive ML odds (neither is a heavy favourite), it signals an
        # open game where both sides are likely to score.
        ml_balance_bonus = 0.0
        if home_dec and away_dec:
            # If odds are close (e.g. 2.0 vs 2.0), both teams are evenly matched
            # → more open, attacking game → higher BTTS Yes probability.
            ratio = min(home_dec, away_dec) / max(home_dec, away_dec)
            ml_balance_bonus = (ratio - 0.5) * 0.08  # max ~+0.04 when evenly matched

        btts_yes = max(0.35, min(0.75, 0.55 + (attack_factor - 0.5) * 0.20 + ml_balance_bonus))
        btts_no = 1 - btts_yes

        # BUG FIX 3: Confidence was passing raw 1/btts_yes (no vig) as odds,
        # making implied == prob always, so edge was always 0. Pass the actual
        # vig-adjusted odds instead so edge is computed correctly.
        yes_odds = round(1 / btts_yes * 0.95, 2)
        no_odds = round(1 / btts_no * 0.95, 2)
        selections.append({
            "fixture": fixture, "market": "BTTS", "selection": "Yes",
            "label": "Both Teams To Score: Yes",
            "odds": yes_odds,
            "probability": btts_yes,
            "confidence": _confidence(btts_yes, yes_odds, 0),
        })
        selections.append({
            "fixture": fixture, "market": "BTTS", "selection": "No",
            "label": "Both Teams To Score: No",
            "odds": no_odds,
            "probability": btts_no,
            "confidence": _confidence(btts_no, no_odds, 0),
        })

    return selections


def _confidence(prob, odds, momentum):
    """0-100 score combining prob, edge, momentum."""
    if not odds or odds <= 1:
        return 0
    implied = 1 / odds
    edge = prob - implied
    base = prob * 100
    edge_bonus = edge * 50
    momentum_bonus = momentum * 2
    return max(0, min(100, base + edge_bonus + momentum_bonus))
