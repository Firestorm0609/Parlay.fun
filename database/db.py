import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "parlay.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT,
            risk_mode TEXT DEFAULT 'balanced',
            unit_size REAL DEFAULT 10.0,
            preferred_sport TEXT DEFAULT 'soccer',
            notifications INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS parlays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sport TEXT,
            risk_mode TEXT,
            stake REAL,
            total_odds REAL,
            potential_payout REAL,
            status TEXT DEFAULT 'pending',
            actual_payout REAL DEFAULT 0,
            notified INTEGER DEFAULT 0,
            created_at TEXT,
            settled_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parlay_id INTEGER,
            event_id TEXT,
            event_name TEXT,
            market TEXT,
            pick TEXT,
            odds REAL,
            result TEXT DEFAULT 'pending',
            FOREIGN KEY(parlay_id) REFERENCES parlays(id)
        );

        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id INTEGER,
            opponent_id INTEGER,
            sport TEXT,
            stake REAL,
            status TEXT DEFAULT 'open',
            winner_id INTEGER,
            created_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_parlays_user ON parlays(user_id);
        CREATE INDEX IF NOT EXISTS idx_parlays_status ON parlays(status);
        CREATE INDEX IF NOT EXISTS idx_parlays_notified ON parlays(notified, status);
        CREATE INDEX IF NOT EXISTS idx_selections_parlay ON selections(parlay_id);
        """)
        # Defensive migrations for older DBs that lack the `notified` column
        cols = [r["name"] for r in c.execute("PRAGMA table_info(parlays)").fetchall()]
        if "notified" not in cols:
            c.execute("ALTER TABLE parlays ADD COLUMN notified INTEGER DEFAULT 0")


def upsert_user(user_id, username, first_name):
    with get_conn() as c:
        c.execute("""
            INSERT INTO users (user_id, username, first_name, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (user_id, username, first_name, datetime.utcnow().isoformat()))


def get_user(user_id):
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user_pref(user_id, field, value):
    allowed = {"risk_mode", "unit_size", "preferred_sport", "notifications"}
    if field not in allowed:
        return
    with get_conn() as c:
        c.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))


def save_parlay(user_id, sport, risk_mode, stake, total_odds, selections):
    payout = stake * total_odds
    with get_conn() as c:
        cur = c.execute("""
            INSERT INTO parlays (user_id, sport, risk_mode, stake, total_odds, potential_payout, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, sport, risk_mode, stake, total_odds, payout, datetime.utcnow().isoformat()))
        pid = cur.lastrowid
        for s in selections:
            c.execute("""
                INSERT INTO selections (parlay_id, event_id, event_name, market, pick, odds)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pid, s["event_id"], s["event_name"], s["market"], s["pick"], s["odds"]))
        return pid


def get_parlay(parlay_id):
    with get_conn() as c:
        row = c.execute("SELECT * FROM parlays WHERE id=?", (parlay_id,)).fetchone()
        return dict(row) if row else None


def get_pending_parlays():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM parlays WHERE status='pending'").fetchall()]


def get_unnotified_settled_parlays():
    with get_conn() as c:
        rows = c.execute("""
            SELECT * FROM parlays
            WHERE status IN ('won','lost') AND notified=0
        """).fetchall()
        return [dict(r) for r in rows]


def mark_parlay_notified(parlay_id):
    with get_conn() as c:
        c.execute("UPDATE parlays SET notified=1 WHERE id=?", (parlay_id,))


def get_selections(parlay_id):
    with get_conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM selections WHERE parlay_id=?", (parlay_id,)
        ).fetchall()]


def update_selection_result(sel_id, result):
    with get_conn() as c:
        c.execute("UPDATE selections SET result=? WHERE id=?", (result, sel_id))


def settle_parlay(parlay_id, status, actual_payout):
    with get_conn() as c:
        c.execute("""
            UPDATE parlays SET status=?, actual_payout=?, settled_at=?
            WHERE id=?
        """, (status, actual_payout, datetime.utcnow().isoformat(), parlay_id))


def user_recent_parlays(user_id, limit=10):
    with get_conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT * FROM parlays WHERE user_id=?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit)).fetchall()]


def user_stats(user_id):
    with get_conn() as c:
        row = c.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(stake),0) as total_staked,
                COALESCE(SUM(actual_payout),0) as total_won,
                COALESCE(MAX(total_odds),0) as biggest_odds
            FROM parlays WHERE user_id=?
        """, (user_id,)).fetchone()
        stats = dict(row) if row else {}
        # Compute current streak (consecutive same-status latest settled parlays)
        streak = 0
        streak_type = None
        rows = c.execute("""
            SELECT status FROM parlays WHERE user_id=? AND status IN ('won','lost')
            ORDER BY id DESC LIMIT 50
        """, (user_id,)).fetchall()
        for r in rows:
            if streak_type is None:
                streak_type = r["status"]
                streak = 1
            elif r["status"] == streak_type:
                streak += 1
            else:
                break
        stats["streak"] = streak
        stats["streak_type"] = streak_type
        return stats


def leaderboard(limit=10):
    with get_conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT u.username, u.first_name, u.user_id,
                COUNT(p.id) as parlays,
                SUM(CASE WHEN p.status='won' THEN 1 ELSE 0 END) as wins,
                COALESCE(SUM(p.actual_payout - p.stake),0) as profit
            FROM users u
            LEFT JOIN parlays p ON p.user_id = u.user_id
            GROUP BY u.user_id
            HAVING parlays > 0
            ORDER BY profit DESC
            LIMIT ?
        """, (limit,)).fetchall()]


def create_challenge(challenger_id, opponent_id, sport, stake):
    with get_conn() as c:
        cur = c.execute("""
            INSERT INTO challenges (challenger_id, opponent_id, sport, stake, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (challenger_id, opponent_id, sport, stake, datetime.utcnow().isoformat()))
        return cur.lastrowid


def all_users():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT user_id, notifications FROM users").fetchall()]
