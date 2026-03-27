import hashlib
import hmac
import json
import os
import random
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = (
    os.environ.get("FC_CLOUD_DATA_DIR")
    or (os.path.join(os.environ["RENDER_DISK_PATH"], "fc-legends-cloud") if os.environ.get("RENDER_DISK_PATH") else "")
    or os.path.join(BASE_DIR, "data")
)
DB_PATH = os.environ.get("FC_CLOUD_DB_PATH") or os.path.join(DATA_DIR, "cloud_accounts.db")
BACKUP_PATH = os.path.join(DATA_DIR, "cloud_accounts_backup.json")
DEVELOPER_CODE = "Reve1@+ion"
SESSION_TTL_DAYS = 30
PBKDF2_ROUNDS = 200_000
ONLINE_DIVISION_MATCHES_PER_CYCLE = 5
ONLINE_TOURNAMENT_TARGET_WINS = 3
ONLINE_TOURNAMENT_MAX_LOSSES = 2


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def clamp(value, low, high):
    return max(low, min(high, value))


def valid_username(value):
    if not value:
        return False
    return all(ch.isalnum() or ch in ("_", "-", ".", "@", "+") for ch in value)


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


class CloudStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()
        ensure_data_dir()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_name TEXT NOT NULL,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    is_developer INTEGER NOT NULL DEFAULT 0,
                    career_snapshot TEXT,
                    fantasy_snapshot TEXT,
                    last_mode TEXT NOT NULL DEFAULT 'CAREER',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS online_divisions (
                    user_id INTEGER PRIMARY KEY,
                    division_tier INTEGER NOT NULL DEFAULT 10,
                    points INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    draws INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    goals_for INTEGER NOT NULL DEFAULT 0,
                    goals_against INTEGER NOT NULL DEFAULT 0,
                    cycle_played INTEGER NOT NULL DEFAULT 0,
                    cycle_points INTEGER NOT NULL DEFAULT 0,
                    reward_coins INTEGER NOT NULL DEFAULT 0,
                    squad_name TEXT,
                    squad_rating INTEGER NOT NULL DEFAULT 0,
                    submitted_squad TEXT,
                    recent_results TEXT NOT NULL DEFAULT '[]',
                    submitted_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS online_tournaments (
                    user_id INTEGER PRIMARY KEY,
                    round INTEGER NOT NULL DEFAULT 1,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    matches_played INTEGER NOT NULL DEFAULT 0,
                    reward_coins INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            conn.commit()
            self._restore_from_backup_if_needed(conn)

    def _write_backup(self, conn):
        users = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, display_name, username, password_hash, password_salt,
                       is_developer, career_snapshot, fantasy_snapshot, last_mode,
                       created_at, updated_at
                FROM users
                ORDER BY id
                """
            ).fetchall()
        ]
        online_divisions = [
            dict(row)
            for row in conn.execute(
                """
                SELECT user_id, division_tier, points, wins, draws, losses, goals_for, goals_against,
                       cycle_played, cycle_points, reward_coins, squad_name, squad_rating,
                       submitted_squad, recent_results, submitted_at, updated_at
                FROM online_divisions
                ORDER BY user_id
                """
            ).fetchall()
        ]
        cursor = conn.execute(
            """
            SELECT user_id, round, wins, losses, matches_played, reward_coins, updated_at
            FROM online_tournaments
            ORDER BY user_id
            """
        )
        online_tournaments = [dict(row) for row in cursor.fetchall()]
        payload = {
            "users": users,
            "online_divisions": online_divisions,
            "online_tournaments": online_tournaments,
            "backed_up_at": utc_iso(utc_now()),
        }
        tmp_path = BACKUP_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, BACKUP_PATH)

    def _restore_from_backup_if_needed(self, conn):
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count or not os.path.exists(BACKUP_PATH):
            return
        try:
            with open(BACKUP_PATH, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:
            return
        users = payload.get("users", []) if isinstance(payload, dict) else []
        online_divisions = payload.get("online_divisions", []) if isinstance(payload, dict) else []
        for row in users:
            conn.execute(
                """
                INSERT OR REPLACE INTO users (
                    id, display_name, username, password_hash, password_salt,
                    is_developer, career_snapshot, fantasy_snapshot, last_mode,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("id"),
                    row.get("display_name"),
                    row.get("username"),
                    row.get("password_hash"),
                    row.get("password_salt"),
                    row.get("is_developer", 0),
                    row.get("career_snapshot"),
                    row.get("fantasy_snapshot"),
                    row.get("last_mode", "CAREER"),
                    row.get("created_at", utc_iso(utc_now())),
                    row.get("updated_at", utc_iso(utc_now())),
                ),
            )
        for row in online_divisions:
            conn.execute(
                """
                INSERT OR REPLACE INTO online_divisions (
                    user_id, division_tier, points, wins, draws, losses, goals_for, goals_against,
                    cycle_played, cycle_points, reward_coins, squad_name, squad_rating,
                    submitted_squad, recent_results, submitted_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("user_id"),
                    row.get("division_tier", 10),
                    row.get("points", 0),
                    row.get("wins", 0),
                    row.get("draws", 0),
                    row.get("losses", 0),
                    row.get("goals_for", 0),
                    row.get("goals_against", 0),
                    row.get("cycle_played", 0),
                    row.get("cycle_points", 0),
                    row.get("reward_coins", 0),
                    row.get("squad_name"),
                    row.get("squad_rating", 0),
                    row.get("submitted_squad"),
                    row.get("recent_results", "[]"),
                    row.get("submitted_at"),
                    row.get("updated_at", utc_iso(utc_now())),
                ),
            )
        online_tournaments = payload.get("online_tournaments", []) if isinstance(payload, dict) else []
        for row in online_tournaments:
            conn.execute(
                """
                INSERT OR REPLACE INTO online_tournaments (
                    user_id, round, wins, losses, matches_played, reward_coins, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("user_id"),
                    row.get("round", 1),
                    row.get("wins", 0),
                    row.get("losses", 0),
                    row.get("matches_played", 0),
                    row.get("reward_coins", 0),
                    row.get("updated_at", utc_iso(utc_now())),
                ),
            )
        conn.commit()

    def _hash_password(self, password, salt):
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PBKDF2_ROUNDS,
        )
        return digest.hex()

    def _verify_password(self, password, salt, password_hash):
        expected = self._hash_password(password, salt)
        return hmac.compare_digest(expected, password_hash)

    def _make_session(self, user_id):
        token = secrets.token_urlsafe(32)
        created_at = utc_now()
        expires_at = created_at + timedelta(days=SESSION_TTL_DAYS)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, user_id, utc_iso(created_at), utc_iso(expires_at)),
            )
            conn.commit()
        return token

    def _snapshot_summary(self, snapshot_text):
        if not snapshot_text:
            return {
                "has_save": False,
                "team_name": None,
                "cards": 0,
                "coins": 0,
            }
        try:
            snapshot = json.loads(snapshot_text)
        except Exception:
            return {
                "has_save": True,
                "team_name": None,
                "cards": 0,
                "coins": 0,
            }
        roster = snapshot.get("fantasy_roster", [])
        return {
            "has_save": True,
            "team_name": snapshot.get("fantasy_team_name"),
            "cards": len(roster) if isinstance(roster, list) else 0,
            "coins": snapshot.get("fantasy_coins", 0),
        }

    def _serialize_user(self, row, include_snapshots=False):
        fantasy_summary = self._snapshot_summary(row["fantasy_snapshot"])
        payload = {
            "display_name": row["display_name"],
            "username": row["username"],
            "is_developer": bool(row["is_developer"]),
            "last_mode": row["last_mode"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "fantasy_summary": fantasy_summary,
        }
        if include_snapshots:
            payload["career_snapshot"] = json.loads(row["career_snapshot"]) if row["career_snapshot"] else None
            payload["fantasy_snapshot"] = json.loads(row["fantasy_snapshot"]) if row["fantasy_snapshot"] else None
        return payload

    def _ensure_online_entry(self, user_id):
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO online_divisions (user_id, updated_at)
                VALUES (?, ?)
                """,
                (user_id, timestamp),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT od.*, u.username, u.display_name
                FROM online_divisions od
                JOIN users u ON u.id = od.user_id
                WHERE od.user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return row

    def _online_recent_results(self, value):
        try:
            data = json.loads(value or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _normalize_lineup_entry(self, entry):
        if isinstance(entry, (list, tuple)):
            name = str(entry[0]) if len(entry) > 0 else "Unknown"
            rating = int(entry[2]) if len(entry) > 2 and str(entry[2]).isdigit() else None
            return name, rating
        if isinstance(entry, dict):
            name = str(entry.get("name") or entry.get("player") or "Unknown")
            rating = entry.get("rating")
            return name, int(rating) if isinstance(rating, (int, float)) else None
        return str(entry), None

    def _extract_online_squad(self, snapshot_text):
        if not snapshot_text:
            raise ValueError("Create a fantasy squad before joining online divisions.")
        try:
            snapshot = json.loads(snapshot_text)
        except Exception as exc:
            raise ValueError("Fantasy save is unreadable.") from exc
        roster = snapshot.get("fantasy_roster") or []
        lineup = snapshot.get("lineup") or []
        if not isinstance(roster, list):
            roster = []
        if not isinstance(lineup, list):
            lineup = []

        roster_lookup = {}
        for card in roster:
            if not isinstance(card, dict):
                continue
            name = str(card.get("name") or "").strip()
            if not name:
                continue
            roster_lookup.setdefault(name, []).append(card)

        squad_cards = []
        used_names = set()
        for entry in lineup:
            name, rating = self._normalize_lineup_entry(entry)
            if not name or name in used_names:
                continue
            card = None
            matches = roster_lookup.get(name, [])
            if matches:
                card = max(matches, key=lambda item: int(item.get("rating", 0)))
            if card:
                rating = int(card.get("rating", rating or 0))
            if rating is None:
                rating = 60
            squad_cards.append({"name": name, "rating": int(rating)})
            used_names.add(name)

        if len(squad_cards) < 11:
            remaining = []
            for card in roster:
                if not isinstance(card, dict):
                    continue
                name = str(card.get("name") or "").strip()
                if not name or name in used_names:
                    continue
                remaining.append({"name": name, "rating": int(card.get("rating", 60))})
            remaining.sort(key=lambda item: item["rating"], reverse=True)
            squad_cards.extend(remaining[: max(0, 11 - len(squad_cards))])

        if len(squad_cards) < 11:
            raise ValueError("You need at least 11 fantasy players to join online divisions.")

        squad_cards = squad_cards[:11]
        ratings = [card["rating"] for card in squad_cards]
        squad_rating = round(sum(ratings) / len(ratings))
        return {
            "team_name": str(snapshot.get("fantasy_team_name") or "Fantasy FC"),
            "squad_rating": squad_rating,
            "captain": max(squad_cards, key=lambda item: item["rating"])["name"],
            "lineup": squad_cards,
        }

    def _serialize_online_entry(self, row):
        squad = None
        if row["submitted_squad"]:
            try:
                squad = json.loads(row["submitted_squad"])
            except Exception:
                squad = None
        return {
            "username": row["username"],
            "display_name": row["display_name"],
            "division_tier": row["division_tier"],
            "points": row["points"],
            "wins": row["wins"],
            "draws": row["draws"],
            "losses": row["losses"],
            "goals_for": row["goals_for"],
            "goals_against": row["goals_against"],
            "goal_difference": row["goals_for"] - row["goals_against"],
            "cycle_played": row["cycle_played"],
            "cycle_points": row["cycle_points"],
            "reward_coins": row["reward_coins"],
            "submitted": bool(row["submitted_squad"]),
            "submitted_at": row["submitted_at"],
            "updated_at": row["updated_at"],
            "squad_name": row["squad_name"] or (squad or {}).get("team_name"),
            "squad_rating": row["squad_rating"],
            "captain": (squad or {}).get("captain"),
            "recent_results": self._online_recent_results(row["recent_results"]),
        }

    def _leaderboard_for_tier(self, tier, limit=12):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT od.*, u.username, u.display_name
                FROM online_divisions od
                JOIN users u ON u.id = od.user_id
                WHERE od.division_tier = ? AND od.submitted_squad IS NOT NULL
                ORDER BY od.points DESC, (od.goals_for - od.goals_against) DESC, od.goals_for DESC, od.squad_rating DESC, u.username ASC
                LIMIT ?
                """,
                (tier, limit),
            ).fetchall()
        return [self._serialize_online_entry(row) for row in rows]

    def _serialize_tournament_entry(self, row):
        if not row:
            return {}
        return {
            "user_id": row["user_id"],
            "round": row["round"],
            "wins": row["wins"],
            "losses": row["losses"],
            "matches_played": row["matches_played"],
            "reward_coins": row["reward_coins"],
            "updated_at": row["updated_at"],
        }

    def _ensure_online_tournament_entry(self, user_id):
        with self.lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM online_tournaments WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row:
                return dict(row)
            now = utc_iso(utc_now())
            conn.execute(
                """
                INSERT INTO online_tournaments (user_id, round, wins, losses, matches_played, reward_coins, updated_at)
                VALUES (?, 1, 0, 0, 0, 0, ?)
                """,
                (user_id, now),
            )
            conn.commit()
            return dict(
                conn.execute("SELECT * FROM online_tournaments WHERE user_id = ?", (user_id,)).fetchone()
            )

    def _tournament_leaderboard(
        self, round_key, limit=8
    ):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ot.*, u.username, u.display_name
                FROM online_tournaments ot
                JOIN users u ON u.id = ot.user_id
                WHERE ot.round = ?
                ORDER BY ot.wins DESC, ot.matches_played ASC, u.username ASC
                LIMIT ?
                """,
                (round_key, limit),
            ).fetchall()
        leaderboard = []
        for row in rows:
            entry = self._serialize_tournament_entry(row)
            entry.update(
                {
                    "username": row["username"],
                    "display_name": row["display_name"],
                    "score": row["wins"] * 3 - row["losses"],
                }
            )
            leaderboard.append(entry)
        return leaderboard

    def _auto_submit_online_squad(self, user_row):
        squad = self._extract_online_squad(user_row["fantasy_snapshot"])
        if not squad:
            return None
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO online_divisions (user_id, squad_name, squad_rating, submitted_squad, submitted_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET
                    squad_name = excluded.squad_name,
                    squad_rating = excluded.squad_rating,
                    submitted_squad = excluded.submitted_squad,
                    submitted_at = excluded.submitted_at,
                    updated_at = excluded.updated_at
                """,
                (
                    user_row["id"],
                    squad["team_name"],
                    squad["squad_rating"],
                    json.dumps(squad),
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
            self._write_backup(conn)
            row = conn.execute(
                """
                SELECT od.*, u.username, u.display_name
                FROM online_divisions od
                JOIN users u ON u.id = od.user_id
                WHERE od.user_id = ?
                """,
                (user_row["id"],),
            ).fetchone()
            return self._serialize_online_entry(row)

    def _append_recent_result(self, current, result):
        history = self._online_recent_results(current)
        history.insert(0, result)
        return json.dumps(history[:5])

    def _apply_online_cycle(self, stats, user_name, opponent_name):
        message = ""
        if stats["cycle_played"] < ONLINE_DIVISION_MATCHES_PER_CYCLE:
            return stats, message
        if stats["cycle_points"] >= 10 and stats["division_tier"] > 1:
            stats["division_tier"] -= 1
            stats["reward_coins"] += 250
            message = f"{user_name} earned promotion to Division {stats['division_tier']} after facing {opponent_name}."
        elif stats["cycle_points"] <= 2 and stats["division_tier"] < 10:
            stats["division_tier"] += 1
            stats["reward_coins"] += 60
            message = f"{user_name} dropped to Division {stats['division_tier']} after facing {opponent_name}."
        else:
            stats["reward_coins"] += 120
            message = f"{user_name} completed the weekly division set against {opponent_name}."
        stats["cycle_played"] = 0
        stats["cycle_points"] = 0
        return stats, message

    def _simulate_online_match(self, home_squad, away_squad):
        home_rating = int(home_squad.get("squad_rating", 70))
        away_rating = int(away_squad.get("squad_rating", 70))
        base = 1.35
        diff = (home_rating - away_rating) / 14
        home = max(0, int(round(random.gauss(base + 0.15 + diff, 0.95))))
        away = max(0, int(round(random.gauss(base - 0.05 - diff, 0.95))))
        if abs(home_rating - away_rating) > 8 and home == away:
            if home_rating > away_rating:
                home += 1
            else:
                away += 1
        return home, away

    def _generate_ai_squad(self, tier):
        base_rating = clamp(68 + (11 - tier) * 2, 60, 90)
        promo = random.choice(["Event", "Signature", "Mythic"])
        squad = {
            "team_name": f"AI Tier {tier}",
            "squad_rating": base_rating,
            "squad": [
                {"name": f"AI Player {i+1}", "rating": base_rating + random.randint(-3, 3), "position": random.choice(["ST","CM","CDM","CB","GK"])}
                for i in range(11)
            ],
            "captain": f"AI Captain",
            "promo": promo,
        }
        return squad

    def _ensure_division_submission(self, user_row):
        row = self._ensure_online_entry(user_row["id"])
        if row.get("submitted_squad"):
            return row
        auto_entry = self._auto_submit_online_squad(user_row)
        return auto_entry or row

    def _apply_tournament_result(self, entry, won, drew, opponent_name):
        reward = entry["reward_coins"]
        if won:
            reward += 30
        elif drew:
            reward += 10
        else:
            reward += 5
        wins = entry["wins"] + (1 if won else 0)
        losses = entry["losses"] + (1 if not won and not drew else 0)
        matches = entry["matches_played"] + 1
        round_key = entry["round"]
        message = ""
        if wins >= ONLINE_TOURNAMENT_TARGET_WINS:
            round_key += 1
            reward += 200
            wins = losses = matches = 0
            message = f"Advanced to round {round_key} after beating {opponent_name}."
        elif losses >= ONLINE_TOURNAMENT_MAX_LOSSES:
            round_key = max(1, round_key - 1)
            wins = losses = matches = 0
            message = f"Dropped to round {round_key} after {opponent_name}."
        return {
            "round": round_key,
            "wins": wins,
            "losses": losses,
            "matches_played": matches,
            "reward_coins": reward,
            "message": message,
        }

    def get_online_division_status(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        online_row = self._ensure_online_entry(user_row["id"])
        entry = self._serialize_online_entry(online_row)
        leaderboard = self._leaderboard_for_tier(entry["division_tier"])
        return {
            "entry": entry,
            "leaderboard": leaderboard,
        }

    def get_online_tournament_status(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        self._ensure_division_submission(user_row)
        entry = self._ensure_online_tournament_entry(user_row["id"])
        leaderboard = self._tournament_leaderboard(entry["round"])
        return {
            "entry": entry,
            "leaderboard": leaderboard,
        }

    def play_online_tournament(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        division_row = self._ensure_division_submission(user_row)
        if not division_row or not division_row.get("submitted_squad"):
            raise ValueError("Submit your fantasy squad before joining the tournament.")
        player_squad = json.loads(division_row["submitted_squad"])
        tournament_entry = self._ensure_online_tournament_entry(user_row["id"])
        with self._connect() as conn:
            opponents = conn.execute(
                """
                SELECT ot.*, od.submitted_squad, u.username, u.display_name
                FROM online_tournaments ot
                JOIN online_divisions od ON od.user_id = ot.user_id
                JOIN users u ON u.id = ot.user_id
                WHERE ot.user_id != ? AND ot.round = ? AND od.submitted_squad IS NOT NULL
                ORDER BY RANDOM()
                LIMIT 8
                """,
                (user_row["id"], tournament_entry["round"]),
            ).fetchall()
        if not opponents:
            raise ValueError("No tournament opponents available yet.")
        opponent_row = random.choice(opponents)
        opponent_squad = json.loads(opponent_row["submitted_squad"])
        user_goals, opp_goals = self._simulate_online_match(player_squad, opponent_squad)
        won = user_goals > opp_goals
        drew = user_goals == opp_goals
        opponent_entry_row = self._ensure_online_tournament_entry(opponent_row["user_id"])
        player_updated = self._apply_tournament_result(
            tournament_entry, won, drew, opponent_row["username"]
        )
        opponent_updated = self._apply_tournament_result(
            opponent_entry_row, not won and not drew, drew, user_row["username"]
        )
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE online_tournaments
                SET round = ?, wins = ?, losses = ?, matches_played = ?, reward_coins = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    player_updated["round"],
                    player_updated["wins"],
                    player_updated["losses"],
                    player_updated["matches_played"],
                    player_updated["reward_coins"],
                    timestamp,
                    user_row["id"],
                ),
            )
            conn.execute(
                """
                UPDATE online_tournaments
                SET round = ?, wins = ?, losses = ?, matches_played = ?, reward_coins = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    opponent_updated["round"],
                    opponent_updated["wins"],
                    opponent_updated["losses"],
                    opponent_updated["matches_played"],
                    opponent_updated["reward_coins"],
                    timestamp,
                    opponent_row["user_id"],
                ),
            )
            conn.commit()
            self._write_backup(conn)
        refreshed = self.get_online_tournament_status(token)
        result = "win" if won else "draw" if drew else "loss"
        return {
            "match": {
                "opponent": opponent_row["username"],
                "opponent_display": opponent_row["display_name"],
                "user_goals": user_goals,
                "opponent_goals": opp_goals,
                "result": result,
            },
            **refreshed,
        }

    def claim_online_tournament_reward(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        entry = self._ensure_online_tournament_entry(user_row["id"])
        reward = int(entry["reward_coins"] or 0)
        if reward <= 0:
            raise ValueError("No tournament rewards available.")
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE online_tournaments
                SET reward_coins = 0, updated_at = ?
                WHERE user_id = ?
                """,
                (timestamp, user_row["id"]),
            )
            conn.commit()
            self._write_backup(conn)
        refreshed = self.get_online_tournament_status(token)
        return {"reward_coins": reward, **refreshed}

    def submit_online_division(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        squad = self._extract_online_squad(user_row["fantasy_snapshot"])
        self._ensure_online_entry(user_row["id"])
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE online_divisions
                SET squad_name = ?, squad_rating = ?, submitted_squad = ?, submitted_at = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    squad["team_name"],
                    squad["squad_rating"],
                    json.dumps(squad),
                    timestamp,
                    timestamp,
                    user_row["id"],
                ),
            )
            conn.commit()
            self._write_backup(conn)
            row = conn.execute(
                """
                SELECT od.*, u.username, u.display_name
                FROM online_divisions od
                JOIN users u ON u.id = od.user_id
                WHERE od.user_id = ?
                """,
                (user_row["id"],),
            ).fetchone()
        return self._serialize_online_entry(row)

    def play_online_division(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        player_row = self._ensure_online_entry(user_row["id"])
        if not player_row["submitted_squad"]:
            raise ValueError("Submit your fantasy squad before playing online.")
        with self._connect() as conn:
            opponents = conn.execute(
                """
                SELECT od.*, u.username, u.display_name
                FROM online_divisions od
                JOIN users u ON u.id = od.user_id
                WHERE od.user_id != ?
                  AND od.division_tier = ?
                  AND od.submitted_squad IS NOT NULL
                ORDER BY RANDOM()
                LIMIT 8
                """,
                (user_row["id"], player_row["division_tier"]),
            ).fetchall()
        player_squad = json.loads(player_row["submitted_squad"])
        if not opponents:
            opponent_row = {"user_id": 0, "username": "AI Bot", "display_name": "AI Bot"}
            opponent_squad = self._generate_ai_squad(player_row["division_tier"])
            ai_match = True
        else:
            opponent_row = random.choice(opponents)
            opponent_squad = json.loads(opponent_row["submitted_squad"])
            ai_match = False
        user_goals, opp_goals = self._simulate_online_match(player_squad, opponent_squad)

        player_stats = dict(player_row)
        opponent_stats = dict(opponent_row)

        player_stats["points"] += 3 if user_goals > opp_goals else 1 if user_goals == opp_goals else 0
        player_stats["wins"] += 1 if user_goals > opp_goals else 0
        player_stats["draws"] += 1 if user_goals == opp_goals else 0
        player_stats["losses"] += 1 if user_goals < opp_goals else 0
        player_stats["goals_for"] += user_goals
        player_stats["goals_against"] += opp_goals
        player_stats["cycle_played"] += 1
        player_stats["cycle_points"] += 3 if user_goals > opp_goals else 1 if user_goals == opp_goals else 0

        opponent_stats["points"] += 3 if opp_goals > user_goals else 1 if user_goals == opp_goals else 0
        opponent_stats["wins"] += 1 if opp_goals > user_goals else 0
        opponent_stats["draws"] += 1 if user_goals == opp_goals else 0
        opponent_stats["losses"] += 1 if opp_goals < user_goals else 0
        opponent_stats["goals_for"] += opp_goals
        opponent_stats["goals_against"] += user_goals
        opponent_stats["cycle_played"] += 1
        opponent_stats["cycle_points"] += 3 if opp_goals > user_goals else 1 if user_goals == opp_goals else 0

        player_result = {
            "opponent": opponent_row["username"],
            "score": f"{user_goals}-{opp_goals}",
            "result": "W" if user_goals > opp_goals else "D" if user_goals == opp_goals else "L",
        }
        opponent_result = {
            "opponent": user_row["username"],
            "score": f"{opp_goals}-{user_goals}",
            "result": "W" if opp_goals > user_goals else "D" if user_goals == opp_goals else "L",
        }

        player_stats["recent_results"] = self._append_recent_result(player_row["recent_results"], player_result)
        if not ai_match:
            opponent_stats["recent_results"] = self._append_recent_result(opponent_row["recent_results"], opponent_result)

        player_stats, player_cycle_message = self._apply_online_cycle(player_stats, user_row["username"], opponent_row["username"])
        opponent_stats, _ = self._apply_online_cycle(opponent_stats, opponent_row["username"], user_row["username"])
        timestamp = utc_iso(utc_now())

        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE online_divisions
                SET division_tier = ?, points = ?, wins = ?, draws = ?, losses = ?,
                    goals_for = ?, goals_against = ?, cycle_played = ?, cycle_points = ?,
                    reward_coins = ?, recent_results = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    player_stats["division_tier"],
                    player_stats["points"],
                    player_stats["wins"],
                    player_stats["draws"],
                    player_stats["losses"],
                    player_stats["goals_for"],
                    player_stats["goals_against"],
                    player_stats["cycle_played"],
                    player_stats["cycle_points"],
                    player_stats["reward_coins"],
                    player_stats["recent_results"],
                    timestamp,
                    user_row["id"],
                ),
            )
            if not ai_match:
                conn.execute(
                    """
                    UPDATE online_divisions
                    SET division_tier = ?, points = ?, wins = ?, draws = ?, losses = ?,
                        goals_for = ?, goals_against = ?, cycle_played = ?, cycle_points = ?,
                        reward_coins = ?, recent_results = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (
                        opponent_stats["division_tier"],
                        opponent_stats["points"],
                        opponent_stats["wins"],
                        opponent_stats["draws"],
                        opponent_stats["losses"],
                        opponent_stats["goals_for"],
                        opponent_stats["goals_against"],
                        opponent_stats["cycle_played"],
                        opponent_stats["cycle_points"],
                        opponent_stats["reward_coins"],
                        opponent_stats["recent_results"],
                        timestamp,
                        opponent_row["user_id"],
                    ),
                )
            conn.commit()
            self._write_backup(conn)

        refreshed = self.get_online_division_status(token)
        opponent_team = opponent_squad.get("team_name") if opponent_squad else opponent_row.get("username")
        opponent_rating = opponent_squad.get("squad_rating") if opponent_squad else None
        return {
            "match": {
                "opponent": opponent_row["username"],
                "opponent_team": opponent_team,
                "opponent_rating": opponent_rating,
                "opponent_is_ai": ai_match,
                "user_goals": user_goals,
                "opponent_goals": opp_goals,
                "result": player_result["result"],
                "cycle_message": player_cycle_message,
            },
            **refreshed,
        }

    def claim_online_division_reward(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        entry = self._ensure_online_entry(user_row["id"])
        reward = int(entry["reward_coins"] or 0)
        if reward <= 0:
            raise ValueError("No online division rewards ready to claim.")
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE online_divisions
                SET reward_coins = 0, updated_at = ?
                WHERE user_id = ?
                """,
                (timestamp, user_row["id"]),
            )
            conn.commit()
            self._write_backup(conn)
        refreshed = self.get_online_division_status(token)
        return {"reward_coins": reward, **refreshed}

    def register_user(self, display_name, username, password, developer_code=""):
        username = username.strip().lower()
        display_name = display_name.strip()
        if not display_name or not username or not password:
            raise ValueError("Display name, username, and password are required.")
        if not valid_username(username):
            raise ValueError("Username can only contain letters, numbers, _, -, ., @ and +.")
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)
        is_developer = 1 if developer_code == DEVELOPER_CODE else 0
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                raise ValueError("Username already exists.")
            cursor = conn.execute(
                """
                INSERT INTO users (
                    display_name, username, password_hash, password_salt,
                    is_developer, career_snapshot, fantasy_snapshot, last_mode,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, 'CAREER', ?, ?)
                """,
                (display_name, username, password_hash, salt, is_developer, timestamp, timestamp),
            )
            conn.commit()
            self._write_backup(conn)
            user_id = cursor.lastrowid
        token = self._make_session(user_id)
        return token, self.get_user_by_username(username, include_snapshots=True)

    def login_user(self, username, password, developer_code="", require_dev=False):
        username = username.strip().lower()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row or not self._verify_password(password, row["password_salt"], row["password_hash"]):
            raise PermissionError("Invalid username or password.")
        if require_dev and (not row["is_developer"] or developer_code != DEVELOPER_CODE):
            raise PermissionError("Developer code required.")
        token = self._make_session(row["id"])
        return token, self._serialize_user(row, include_snapshots=True)

    def get_user_by_username(self, username, include_snapshots=False):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
        return self._serialize_user(row, include_snapshots=include_snapshots) if row else None

    def get_user_by_token(self, token):
        if not token:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.*, s.expires_at
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = ?
                """,
                (token,),
            ).fetchone()
        if not row:
            return None
        expires_at = parse_iso(row["expires_at"])
        if not expires_at or expires_at < utc_now():
            with self._connect() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
            return None
        return row

    def save_snapshot(self, token, mode, snapshot):
        row = self.get_user_by_token(token)
        if not row:
            raise PermissionError("Invalid or expired session.")
        if mode not in ("CAREER", "FANTASY"):
            raise ValueError("Invalid mode.")
        column = "career_snapshot" if mode == "CAREER" else "fantasy_snapshot"
        with self.lock, self._connect() as conn:
            conn.execute(
                f"""
                UPDATE users
                SET {column} = ?, last_mode = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(snapshot), mode, utc_iso(utc_now()), row["id"]),
            )
            conn.commit()
            self._write_backup(conn)
        refreshed = self.get_user_by_username(row["username"])
        return refreshed

    def load_snapshot(self, token, mode):
        row = self.get_user_by_token(token)
        if not row:
            raise PermissionError("Invalid or expired session.")
        if mode not in ("CAREER", "FANTASY"):
            raise ValueError("Invalid mode.")
        column = "career_snapshot" if mode == "CAREER" else "fantasy_snapshot"
        snapshot_text = row[column]
        return json.loads(snapshot_text) if snapshot_text else None

    def list_users(self, token):
        row = self.get_user_by_token(token)
        if not row:
            raise PermissionError("Invalid or expired session.")
        if not row["is_developer"]:
            raise PermissionError("Developer access required.")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM users
                ORDER BY username ASC
                """
            ).fetchall()
        return [self._serialize_user(item) for item in rows]


STORE = CloudStore(DB_PATH)


class CloudRequestHandler(BaseHTTPRequestHandler):
    server_version = "FCFantasyCloud/1.0"

    def log_message(self, fmt, *args):
        return

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise ValueError("Invalid JSON body.")

    def _bearer_token(self):
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header.split(" ", 1)[1].strip()
        return ""

    def _query(self):
        return parse_qs(urlparse(self.path).query)

    def do_OPTIONS(self):
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/health":
                self._send_json(HTTPStatus.OK, {"ok": True, "service": "fc-fantasy-cloud"})
                return
            if parsed.path == "/api/profile":
                token = self._bearer_token()
                user_row = STORE.get_user_by_token(token)
                if not user_row:
                    self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Invalid or expired session."})
                    return
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "user": STORE._serialize_user(user_row, include_snapshots=True),
                    },
                )
                return
            if parsed.path == "/api/save":
                token = self._bearer_token()
                mode = (self._query().get("mode") or [""])[0].upper()
                snapshot = STORE.load_snapshot(token, mode)
                self._send_json(HTTPStatus.OK, {"mode": mode, "snapshot": snapshot})
                return
            if parsed.path == "/api/admin/users":
                token = self._bearer_token()
                users = STORE.list_users(token)
                self._send_json(HTTPStatus.OK, {"users": users})
                return
            if parsed.path == "/api/online-divisions":
                token = self._bearer_token()
                payload = STORE.get_online_division_status(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/online-tournaments":
                token = self._bearer_token()
                payload = STORE.get_online_tournament_status(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        except PermissionError as exc:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Internal server error."})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self._json_body()
            if parsed.path == "/api/register":
                token, user = STORE.register_user(
                    body.get("display_name", ""),
                    body.get("username", ""),
                    body.get("password", ""),
                    body.get("developer_code", ""),
                )
                self._send_json(HTTPStatus.CREATED, {"token": token, "user": user})
                return
            if parsed.path == "/api/login":
                token, user = STORE.login_user(
                    body.get("username", ""),
                    body.get("password", ""),
                    body.get("developer_code", ""),
                    bool(body.get("require_dev")),
                )
                self._send_json(HTTPStatus.OK, {"token": token, "user": user})
                return
            if parsed.path == "/api/online-divisions/play":
                token = self._bearer_token()
                payload = STORE.play_online_division(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/online-divisions/claim":
                token = self._bearer_token()
                payload = STORE.claim_online_division_reward(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/online-tournaments/play":
                token = self._bearer_token()
                payload = STORE.play_online_tournament(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/online-tournaments/claim":
                token = self._bearer_token()
                payload = STORE.claim_online_tournament_reward(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        except PermissionError as exc:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Internal server error."})

    def do_PUT(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/save":
                token = self._bearer_token()
                body = self._json_body()
                mode = str(body.get("mode", "")).upper()
                snapshot = body.get("snapshot")
                if not isinstance(snapshot, dict):
                    raise ValueError("Snapshot must be an object.")
                user = STORE.save_snapshot(token, mode, snapshot)
                self._send_json(HTTPStatus.OK, {"saved": True, "user": user})
                return
            if parsed.path == "/api/online-divisions/submit":
                token = self._bearer_token()
                payload = STORE.submit_online_division(token)
                self._send_json(HTTPStatus.OK, {"submitted": True, "entry": payload})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        except PermissionError as exc:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Internal server error."})


def run():
    host = os.environ.get("FC_CLOUD_HOST", "127.0.0.1")
    port = int(os.environ.get("FC_CLOUD_PORT") or os.environ.get("PORT") or "8080")
    server = ThreadingHTTPServer((host, port), CloudRequestHandler)
    print(f"FC Fantasy cloud server running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
