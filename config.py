import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = "sqlite+aiosqlite:///parlay_bot.db"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"

LEAGUES = {
    # ── Soccer ──────────────────────────────────────────────
    # Top European Leagues
    "soccer/eng.1": "Premier League",
    "soccer/esp.1": "La Liga",
    "soccer/ger.1": "Bundesliga",
    "soccer/ita.1": "Serie A",
    "soccer/fra.1": "Ligue 1",
    "soccer/por.1": "Primeira Liga",
    "soccer/ned.1": "Eredivisie",
    "soccer/be.1": "Pro League",
    "soccer/tur.1": "Super Lig",
    # Cups & International
    "soccer/uefa.champions": "Champions League",
    "soccer/uefa.europa": "Europa League",
    "soccer/uefa.europa.conf": "Conference League",
    "soccer/eng.fa": "FA Cup",
    "soccer/esp.copa": "Copa del Rey",
    "soccer/fifa.ww": "World Cup",
    "soccer/uefa.nations": "Nations League",
    # Americas
    "soccer/usa.1": "MLS",
    "soccer/bra.1": "Brasileiro Serie A",
    "soccer/mex.1": "Liga MX",
    "soccer/arg.1": "Argentine Primera",
    "soccer/col.1": "Categoría Primera A",
    "soccer/chi.1": "Chilean Primera",
    # Rest of World
    "soccer/saf.1": "Premier Soccer League",
    "soccer/jpn.1": "J1 League",
    "soccer/kor.1": "K League 1",
    "soccer/aus.1": "A-League",
    "soccer/saudi.1": "Saudi Pro League",

    # ── Basketball ─────────────────────────────────────────
    "basketball/nba": "NBA",
    "basketball/wnba": "WNBA",
    "basketball/esp.1": "Liga ACB",
    "basketball/usa.ncaa": "NCAA Men's Basketball",
    "basketball/esp.acb": "Spanish ACB",

    # ── American Football ────────────────────────────────
    "football/nfl": "NFL",
    "football/usa.ncaa": "NCAA FBS",
    "football/eng.1": "NFL UK",

    # ── Baseball ──────────────────────────────────────────
    "baseball/mlb": "MLB",
    "baseball/usa.ncaa": "NCAA Baseball",
    "baseball/jpn.1": "NPB",
    "baseball/kor.1": "KBO",

    # ── Hockey ────────────────────────────────────────────
    "hockey/nhl": "NHL",
    "hockey/usa.ncaa": "NCAA Hockey",
    "hockey/rus.1": "KHL",

    # ── Other Sports ─────────────────────────────────────
    "rugby/eng.1": "Premiership Rugby",
    "rugby/fra.1": "Top 14",
    "cricket/eng.1": "County Championship",
    "cricket/ind.1": "IPL",
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
