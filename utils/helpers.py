from datetime import datetime


def format_parlay(parlay, target_odds):
    lines = [
        f"🎯 *Parlay (Target: {target_odds})*",
        f"💰 Total Odds: *{parlay['total_odds']}*",
        f"📊 Avg Confidence: {parlay['avg_confidence']}%",
        f"📈 Combined Prob: {parlay['combined_probability']*100:.1f}%",
        "",
        "*Selections:*",
    ]
    for i, s in enumerate(parlay["selections"], 1):
        fx = s["fixture"]
        dt = datetime.fromisoformat(fx["date"].replace("Z", "+00:00"))
        lines.append(
            f"{i}. *{fx['home_team']} vs {fx['away_team']}*\n"
            f"   📅 {dt.strftime('%b %d %H:%M')} | 🏆 {fx['league']}\n"
            f"   ✅ {s['label']} @ *{s['odds']}*\n"
            f"   🎯 Conf: {s['confidence']:.0f}% | Prob: {s['probability']*100:.0f}%"
        )
    return "\n".join(lines)


def format_stats(stats):
    return (
        f"📊 *Your Performance*\n\n"
        f"Total Parlays: {stats['total']}\n"
        f"✅ Won: {stats['won']}\n"
        f"❌ Lost: {stats['lost']}\n"
        f"⏳ Pending: {stats['pending']}\n"
        f"🎯 Win Rate: {stats['win_rate']:.1f}%\n"
        f"💰 Profit: {stats['profit']:.2f}\n"
        f"📈 ROI: {stats['roi']:.2f}%\n"
        f"💵 Total Staked: {stats['staked']:.2f}"
    )
