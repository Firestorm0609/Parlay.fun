import re
from typing import List, Dict, Optional


# ---------- Markdown safety ----------
_MD_SPECIALS = re.compile(r"([_\*\[\]\(\)~`>#\+\-=|{}\.!])")


def md_escape(text: str) -> str:
    """Escape Telegram MarkdownV1-ish characters that commonly break parsing."""
    if text is None:
        return ""
    return (text.replace("_", "\\_")
                .replace("*", "\\*")
                .replace("`", "\\`")
                .replace("[", "\\["))


# ---------- Parsers ----------
def parse_odds_input(text: str) -> List[float]:
    nums = re.findall(r"\d+\.?\d*", text or "")
    out = []
    for n in nums:
        try:
            v = float(n)
            if 1.01 <= v <= 1000:
                out.append(v)
        except ValueError:
            pass
    return out


def parse_stake_input(text: str) -> Optional[float]:
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    if not m:
        return None
    try:
        v = float(m.group(0))
        if 0 < v <= 1_000_000:
            return v
    except ValueError:
        return None
    return None


# ---------- Formatters ----------
RISK_EMOJI = {"safe": "🟢", "balanced": "🟡", "risky": "🔴", "lottery": "☠️"}
SPORT_EMOJI = {"soccer": "⚽", "basketball": "🏀", "football": "🏈",
               "baseball": "⚾", "hockey": "🏒"}


def format_event_line(s: Dict, idx: Optional[int] = None) -> str:
    prefix = f"{idx}. " if idx else "• "
    return (f"{prefix}*{md_escape(s['event_name'])}*\n"
            f"   {s['market']}: _{md_escape(s['pick'])}_ @ *{s['odds']}*")


def format_parlay(selections: List[Dict], sport: str, risk: str,
                  unit_size: float = 10.0) -> str:
    if not selections:
        return "⚠️ No parlay built — try a different market or sport."
    total = 1.0
    for s in selections:
        total *= s.get("odds", 1.0)
    em_s = SPORT_EMOJI.get(sport, "🎯")
    em_r = RISK_EMOJI.get(risk, "🎲")
    lines = [f"{em_r} *{risk.title()} {em_s} {sport.title()} Parlay* ({len(selections)} legs)\n"]
    for i, s in enumerate(selections, 1):
        lines.append(format_event_line(s, i))
    payout = unit_size * total
    lines.append(f"\n📈 *Total odds:* `{total:.2f}`")
    lines.append(f"💰 Stake `{unit_size:g}u` → payout `{payout:.2f}u` "
                 f"(profit `{payout - unit_size:+.2f}u`)")
    return "\n".join(lines)


def format_track_confirmation(parlay_id: int, selections: List[Dict],
                              stake: float, total_odds: float) -> str:
    lines = [f"✅ *Parlay #{parlay_id} tracked!*\n"]
    for i, s in enumerate(selections, 1):
        lines.append(f"  {i}. _{md_escape(s['event_name'])}_ — "
                     f"{s['market']}: *{md_escape(s['pick'])}* @ {s['odds']}")
    payout = stake * total_odds
    lines.append(f"\n💵 Stake: *{stake:g}u*")
    lines.append(f"📈 Total odds: *{total_odds:.2f}*")
    lines.append(f"💰 Potential payout: *{payout:.2f}u*  "
                 f"(profit *{payout - stake:+.2f}u*)")
    lines.append("\n_You'll be notified when it settles._ Use /stats anytime.")
    return "\n".join(lines)


def format_settlement_message(rec: Dict, unit_size: float = 1.0) -> str:
    p = rec["parlay"]
    sels = rec["selections"]
    icon = "🎉" if rec["status"] == "won" else "💔"
    head = "WON" if rec["status"] == "won" else "LOST"
    lines = [f"{icon} *Parlay #{p['id']} {head}*\n"]
    for i, s in enumerate(sels, 1):
        mark = {"won": "✅", "lost": "❌", "push": "↩️"}.get(s["result"], "⏳")
        lines.append(f"  {mark} {i}. _{md_escape(s['event_name'])}_ — "
                     f"{s['market']}: {md_escape(s['pick'])} @ {s['odds']}")
    stake = float(p.get("stake") or 0)
    payout = float(rec.get("payout") or 0)
    lines.append(f"\n💵 Stake: *{stake:g}u*  |  📈 Odds: *{p['total_odds']:.2f}*")
    if rec["status"] == "won":
        lines.append(f"💰 Payout: *{payout:.2f}u*  (profit *{payout - stake:+.2f}u*)")
    else:
        lines.append(f"📉 Loss: *-{stake:g}u*")
    return "\n".join(lines)
