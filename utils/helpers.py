from typing import Optional


def parse_odds(text: str) -> Optional[float]:
    try:
        v = float(text.replace(",", ".").strip())
        if v < 1.01 or v > 1000:
            return None
        return round(v, 2)
    except ValueError:
        return None


def parse_stake(text: str) -> Optional[float]:
    try:
        v = float(text.replace(",", ".").strip())
        if v < 0 or v > 100000:
            return None
        return round(v, 2)
    except ValueError:
        return None


def _market_label(code: str) -> str:
    return {
        "1X2": "Win",
        "DC": "Double Chance",
        "OU": "Goals",
        "BTTS": "BTTS",
        "ANY": "Any",
    }.get(code, code)


def format_parlay_message(parlay: dict) -> str:
    markets = parlay.get("markets") or ["ANY"]
    market_str = ", ".join(_market_label(m) for m in markets)

    lines = [
        f"🎯 *{len(parlay['legs'])}-Leg Parlay* — _{parlay['risk'].title()}_",
        f"Markets: _{market_str}_",
        f"Total Odds: *{parlay['total_odds']}*",
        "",
    ]
    for i, leg in enumerate(parlay["legs"], 1):
        lines.append(
            f"*{i}.* {leg['home']} vs {leg['away']}\n"
            f"   ↳ {leg['label']} @ {leg['odds']} ({leg['confidence']}%)"
        )
    lines.append("")
    lines.append(f"_Target: ~{parlay['target_total']}x_")
    return "\n".join(lines)


def format_tracking_confirmation(parlay_id: int, parlay: dict, stake: float) -> str:
    lines = [
        f"✅ *Tracking parlay #{parlay_id}*",
        f"Total Odds: *{parlay['total_odds']}x*",
        f"Stake: *{stake}u*",
        "",
        "*Legs:*",
    ]
    for i, leg in enumerate(parlay["legs"], 1):
        lines.append(
            f"  {i}. {leg['home']} vs {leg['away']} — {leg['label']} @ {leg['odds']}"
        )
    lines.append("")
    if stake > 0:
        potential = round((parlay["total_odds"] - 1) * stake, 2)
        lines.append(f"_Potential profit: +{potential}u_")
    lines.append("_Auto-settles after kickoff. View with /history or /stats._")
    return "\n".join(lines)
