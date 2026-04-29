"""
AI-driven parlay suggestion engine.
Analyzes user's historical performance and provides confidence-scored recommendations.
"""
from datetime import datetime, timedelta
from sqlalchemy import select, func, case
from database.db import SessionLocal, Parlay, User
from config import RISK_LEVELS
import logging

logger = logging.getLogger(__name__)


class AISuggester:
    """Provides AI-driven parlay suggestions based on historical performance."""

    def __init__(self):
        self.min_parlays_for_suggestion = 5

    async def get_user_stats(self, user_id: int) -> dict:
        """Get comprehensive user statistics for AI analysis."""
        async with SessionLocal() as s:
            # Get all settled parlays for the user
            result = await s.execute(
                select(Parlay).where(
                    Parlay.user_id == user_id,
                    Parlay.status.in_(["won", "lost"]),
                    Parlay.settled_at.isnot(None)
                )
            )
            parlays = result.scalars().all()

            if len(parlays) < self.min_parlays_for_suggestion:
                return {
                    "has_enough_data": False,
                    "total_parlays": len(parlays),
                    "needed": self.min_parlays_for_suggestion
                }

            # Calculate statistics
            total = len(parlays)
            won = sum(1 for p in parlays if p.status == "won")
            lost = total - won
            win_rate = won / total if total > 0 else 0

            # Calculate average odds
            avg_odds = sum(p.total_odds for p in parlays) / total if total > 0 else 0

            # Calculate profit
            total_profit = sum(
                (p.total_odds - 1) * p.stake if p.status == "won" else -p.stake
                for p in parlays
            )

            # Performance by odds range
            odds_ranges = {
                "low": {"min": 1.0, "max": 3.0, "count": 0, "wins": 0},
                "medium": {"min": 3.0, "max": 10.0, "count": 0, "wins": 0},
                "high": {"min": 10.0, "max": float('inf'), "count": 0, "wins": 0}
            }

            for p in parlays:
                for range_name, range_data in odds_ranges.items():
                    if range_data["min"] <= p.total_odds < range_data["max"]:
                        range_data["count"] += 1
                        if p.status == "won":
                            range_data["wins"] += 1
                        break

            # Calculate win rates per range
            for range_data in odds_ranges.values():
                range_data["win_rate"] = (
                    range_data["wins"] / range_data["count"]
                    if range_data["count"] > 0 else 0
                )

            return {
                "has_enough_data": True,
                "total_parlays": total,
                "won": won,
                "lost": lost,
                "win_rate": win_rate,
                "avg_odds": avg_odds,
                "total_profit": total_profit,
                "odds_ranges": odds_ranges,
                "recent_parlays": parlays[-10:] if len(parlays) >= 10 else parlays
            }

    async def suggest_parlay(self, user_id: int, risk_level: str = "balanced") -> dict:
        """
        Generate AI-driven parlay suggestion.
        Returns suggestion with confidence score and reasoning.
        """
        stats = await self.get_user_stats(user_id)

        if not stats["has_enough_data"]:
            return {
                "has_suggestion": False,
                "message": (
                    f"📊 *Not enough data yet!*\n\n"
                    f"You need at least {stats['needed']} settled parlays for AI suggestions.\n"
                    f"Current: {stats['total_parlays']} parlays tracked.\n\n"
                    f"Keep betting and tracking to unlock AI-powered suggestions!"
                )
            }

        risk_config = RISK_LEVELS.get(risk_level, RISK_LEVELS["balanced"])
        min_prob = risk_config["min_prob"]
        max_odds = risk_config["max_odds_per_leg"]
        max_legs = risk_config["max_legs"]

        # Determine best odds range based on historical performance
        best_range = None
        best_win_rate = 0

        for range_name, range_data in stats["odds_ranges"].items():
            if range_data["count"] >= 3 and range_data["win_rate"] > best_win_rate:
                best_win_rate = range_data["win_rate"]
                best_range = range_name

        # Calculate confidence score (0-100)
        confidence_factors = {
            "win_rate": stats["win_rate"] * 40,  # Up to 40 points
            "sample_size": min(stats["total_parlays"] / 20, 1.0) * 30,  # Up to 30 points
            "profit": min(max(stats["total_profit"] / 100, 0), 1.0) * 20,  # Up to 20 points
            "consistency": (1 - abs(stats["win_rate"] - 0.5) * 2) * 10  # Up to 10 points
        }

        confidence_score = sum(confidence_factors.values())
        confidence_score = min(max(confidence_score, 0), 100)

        # Generate suggestion
        if best_range == "low":
            suggested_odds = 2.5
            suggestion_reason = "Low-risk bets have been your sweet spot"
        elif best_range == "medium":
            suggested_odds = 5.0
            suggestion_reason = "Medium-risk parlays show strong performance"
        elif best_range == "high":
            suggested_odds = 10.0
            suggestion_reason = "You've been crushing high-odds parlays!"
        else:
            suggested_odds = 4.0
            suggestion_reason = "Balanced approach based on your history"

        # Adjust based on risk level
        target_odds = suggested_odds * (1 + (max_legs - 3) * 0.5)
        target_odds = min(target_odds, max_odds * max_legs)

        return {
            "has_suggestion": True,
            "confidence_score": round(confidence_score, 1),
            "target_odds": round(target_odds, 2),
            "suggested_legs": min(max_legs, 3 if confidence_score < 50 else max_legs),
            "reason": suggestion_reason,
            "stats": stats,
            "confidence_factors": confidence_factors,
            "risk_level": risk_level
        }

    async def format_suggestion_message(self, suggestion: dict) -> str:
        """Format the suggestion into a readable message."""
        if not suggestion["has_suggestion"]:
            return suggestion["message"]

        confidence = suggestion["confidence_score"]
        confidence_emoji = (
            "🟢" if confidence >= 70
            else "🟡" if confidence >= 40
            else "🔴"
        )

        stats = suggestion["stats"]

        msg = (
            f"🤖 *AI Parlay Suggestion*\n\n"
            f"{confidence_emoji} *Confidence Score: {confidence}%*\n\n"
            f"🎯 *Recommended Target Odds: ×{suggestion['target_odds']}*\n"
            f"📊 *Suggested Legs: {suggestion['suggested_legs']}*\n"
            f"⚙️ *Risk Level: {suggestion['risk_level'].title()}*\n\n"
            f"💡 *Why this suggestion?*\n"
            f"{suggestion['reason']}\n\n"
            f"📈 *Your Performance:*\n"
            f"• Total Parlays: {stats['total_parlays']}\n"
            f"• Win Rate: {stats['win_rate']*100:.1f}%\n"
            f"• Avg Odds: ×{stats['avg_odds']:.2f}\n"
            f"• Total Profit: ${stats['total_profit']:.2f}\n\n"
            f"Use /parlay to build this suggested parlay!"
        )

        return msg


# Singleton instance
ai_suggester = AISuggester()
