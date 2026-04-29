import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = "sqlite+aiosqlite:///parlay_bot.db"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

LEAGUES = {
    "eng.1": "Premier League",
    "eng.fa": "FA Cup",
    "esp.1": "La Liga",
    "ger.1": "Bundesliga",
    "ita.1": "Serie A",
    "fra.1": "Ligue 1",
    "usa.1": "MLS",
    "bra.1": "Brazilian Serie A",
    "mex.1": "Liga MX",
    "arg.1": "Argentine Primera",
    "uefa.champions": "Champions League",
}

RISK_LEVELS = {
    "safe":       {"min_prob": 0.65, "max_odds_per_leg": 1.80, "max_legs": 4},
    "balanced":   {"min_prob": 0.50, "max_odds_per_leg": 2.50, "max_legs": 6},
    "aggressive": {"min_prob": 0.30, "max_odds_per_leg": 5.00, "max_legs": 10},
}

CHALLENGES = {
    "rollover_2": {"name": "2.0 Rollover", "target_odds": 2.0, "stages": 10},
    "rollover_1_5": {"name": "1.5 Rollover", "target_odds": 1.5, "stages": 15},
    "longshot": {"name": "Long Shot", "target_odds": 20.0, "stages": 1},
}
