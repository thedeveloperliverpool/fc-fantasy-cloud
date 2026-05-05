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
from urllib import error as urllib_error
from urllib import request as urllib_request
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
FOOTBALL_DATA_BASE = os.environ.get("FC_FOOTBALL_DATA_BASE", "https://api.football-data.org/v4").rstrip("/")
FOOTBALL_DATA_TOKEN = os.environ.get("FC_FOOTBALL_DATA_TOKEN", "").strip()
WEEKLY_FANTASY_COMPETITION = os.environ.get("FC_WEEKLY_FANTASY_COMPETITION", "PL").strip().upper() or "PL"
DEFAULT_ADMIN_SETTINGS = {
    "announcement": "",
    "maintenance_mode": False,
    "disabled_modes": {
        "tournaments": False,
        "market": False,
        "objectives": False,
    },
}


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


def normalize_person_name(value):
    if not value:
        return ""
    text = "".join(ch.lower() if ch.isalnum() else " " for ch in str(value))
    return " ".join(text.split())


def normalize_team_name(value):
    text = normalize_person_name(value)
    aliases = {
        "manchester city fc": "manchester city",
        "manchester city": "manchester city",
        "manchester united fc": "manchester united",
        "manchester united": "manchester united",
        "tottenham hotspur fc": "tottenham hotspur",
        "tottenham hotspur": "tottenham hotspur",
        "tottenham": "tottenham hotspur",
        "west ham united fc": "west ham united",
        "west ham united": "west ham united",
        "leicester city fc": "leicester city",
        "leicester city": "leicester city",
        "liverpool fc": "liverpool",
        "liverpool": "liverpool",
        "chelsea fc": "chelsea",
        "chelsea": "chelsea",
        "arsenal fc": "arsenal",
        "arsenal": "arsenal",
        "everton fc": "everton",
        "everton": "everton",
        "sunderland afc": "sunderland",
        "sunderland": "sunderland",
    }
    return aliases.get(text, text)


def iso_week_key(moment=None):
    target = moment or utc_now()
    year, week_num, _ = target.isocalendar()
    return f"{year}-W{week_num:02d}"


def iso_week_window(moment=None):
    target = moment or utc_now()
    week_start = target - timedelta(days=target.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


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
        self.live_league_cache = {}
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
                    is_banned INTEGER NOT NULL DEFAULT 0,
                    suspended_until TEXT,
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

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS weekly_fantasy (
                    user_id INTEGER NOT NULL,
                    week_key TEXT NOT NULL,
                    squad_json TEXT,
                    points INTEGER NOT NULL DEFAULT 0,
                    breakdown_json TEXT NOT NULL DEFAULT '{}',
                    top_card_key TEXT,
                    reward_json TEXT NOT NULL DEFAULT '{}',
                    reward_claimed INTEGER NOT NULL DEFAULT 0,
                    synced_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, week_key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            self._ensure_schema(conn)
            self._ensure_app_state(conn)
            conn.commit()
            self._restore_from_backup_if_needed(conn)

    def _ensure_schema(self, conn):
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "is_banned" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
        if "suspended_until" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN suspended_until TEXT")

    def _ensure_app_state(self, conn):
        for key, value in DEFAULT_ADMIN_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_state (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )

    def _write_backup(self, conn):
        users = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, display_name, username, password_hash, password_salt,
                       is_developer, is_banned, suspended_until, career_snapshot,
                       fantasy_snapshot, last_mode, created_at, updated_at
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
        weekly_fantasy = [
            dict(row)
            for row in conn.execute(
                """
                SELECT user_id, week_key, squad_json, points, breakdown_json, top_card_key,
                       reward_json, reward_claimed, synced_at, created_at, updated_at
                FROM weekly_fantasy
                ORDER BY user_id, week_key
                """
            ).fetchall()
        ]
        payload = {
            "users": users,
            "online_divisions": online_divisions,
            "online_tournaments": online_tournaments,
            "weekly_fantasy": weekly_fantasy,
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
        weekly_fantasy = payload.get("weekly_fantasy", []) if isinstance(payload, dict) else []
        for row in users:
            conn.execute(
                """
                INSERT OR REPLACE INTO users (
                    id, display_name, username, password_hash, password_salt,
                    is_developer, is_banned, suspended_until, career_snapshot,
                    fantasy_snapshot, last_mode, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("id"),
                    row.get("display_name"),
                    row.get("username"),
                    row.get("password_hash"),
                    row.get("password_salt"),
                    row.get("is_developer", 0),
                    row.get("is_banned", 0),
                    row.get("suspended_until"),
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
        for row in weekly_fantasy:
            conn.execute(
                """
                INSERT OR REPLACE INTO weekly_fantasy (
                    user_id, week_key, squad_json, points, breakdown_json, top_card_key,
                    reward_json, reward_claimed, synced_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("user_id"),
                    row.get("week_key"),
                    row.get("squad_json"),
                    row.get("points", 0),
                    row.get("breakdown_json", "{}"),
                    row.get("top_card_key"),
                    row.get("reward_json", "{}"),
                    row.get("reward_claimed", 0),
                    row.get("synced_at"),
                    row.get("created_at", utc_iso(utc_now())),
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
            "packs": len(snapshot.get("my_packs", [])) if isinstance(snapshot.get("my_packs"), list) else 0,
            "season_xp": snapshot.get("fantasy_season_xp", 0),
        }

    def _serialize_user(self, row, include_snapshots=False):
        fantasy_summary = self._snapshot_summary(row["fantasy_snapshot"])
        suspended_until = row["suspended_until"]
        suspended = False
        if suspended_until:
            until = parse_iso(suspended_until)
            suspended = bool(until and until > utc_now())
        payload = {
            "display_name": row["display_name"],
            "username": row["username"],
            "is_developer": bool(row["is_developer"]),
            "is_banned": bool(row["is_banned"]),
            "is_suspended": suspended,
            "suspended_until": suspended_until,
            "last_mode": row["last_mode"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "fantasy_summary": fantasy_summary,
        }
        if include_snapshots:
            payload["career_snapshot"] = json.loads(row["career_snapshot"]) if row["career_snapshot"] else None
            payload["fantasy_snapshot"] = json.loads(row["fantasy_snapshot"]) if row["fantasy_snapshot"] else None
        return payload

    def _football_data_json(self, path):
        if not FOOTBALL_DATA_TOKEN:
            raise ValueError("Weekly Fantasy requires FC_FOOTBALL_DATA_TOKEN on the cloud server.")
        req = urllib_request.Request(
            f"{FOOTBALL_DATA_BASE}{path}",
            headers={"X-Auth-Token": FOOTBALL_DATA_TOKEN},
            method="GET",
        )
        try:
            with urllib_request.urlopen(req, timeout=12) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib_error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}
            raise ValueError(payload.get("message") or payload.get("error") or f"football-data HTTP {exc.code}")
        except (urllib_error.URLError, TimeoutError):
            raise ValueError("football-data service unavailable.")

    def _live_league_season_label(self, competition):
        season = competition.get("currentSeason") or {}
        start_date = str(season.get("startDate") or "")
        end_date = str(season.get("endDate") or "")
        if len(start_date) >= 4 and len(end_date) >= 4:
            return f"{start_date[:4]}/{end_date[:4][-2:]}"
        if start_date:
            return start_date[:4]
        return "Current Season"

    def _live_league_match_row(self, match):
        home = ((match.get("homeTeam") or {}).get("name")) or "Home"
        away = ((match.get("awayTeam") or {}).get("name")) or "Away"
        utc_date = parse_iso(match.get("utcDate"))
        date_text = utc_iso(utc_date).replace("T", ", ")[:16].replace("-", "/") if utc_date else ""
        full_time = (match.get("score") or {}).get("fullTime") or {}
        status = str(match.get("status") or "").upper()
        if status == "FINISHED" and full_time.get("home") is not None and full_time.get("away") is not None:
            score_text = f"{int(full_time.get('home') or 0)}:{int(full_time.get('away') or 0)}"
        else:
            score_text = "//"
        return {
            "date": date_text,
            "home": home,
            "away": away,
            "label": f"{home} - {away}",
            "score": score_text,
            "odds": "//",
            "utcDate": match.get("utcDate"),
            "status": status,
        }

    def _live_league_scorer_row(self, row, index):
        player = row.get("player") or {}
        team = row.get("team") or {}
        goals = int(row.get("goals") or 0)
        assists = int(row.get("assists") or 0)
        played = int(row.get("playedMatches") or row.get("played") or max(1, goals + assists) or 1)
        return {
            "rank": index + 1,
            "name": player.get("name") or "Unknown",
            "team": team.get("name") or "",
            "played": played,
            "goals": goals,
            "assists": assists,
            "g_per_game": round(goals / max(1, played), 2),
            "a_per_game": round(assists / max(1, played), 2),
        }

    def get_live_league_status(self, competition_code="PL"):
        code = (competition_code or "PL").strip().upper() or "PL"
        cache = self.live_league_cache.get(code)
        now = utc_now()
        if cache and cache.get("expires_at") and cache["expires_at"] > now:
            return cache["payload"]
        payload = {
            "provider_ready": bool(FOOTBALL_DATA_TOKEN),
            "provider_name": "football-data.org",
            "competition_code": code,
            "competition_name": "Premier League",
            "season_label": "Current Season",
            "matchday": 0,
            "recent_matches": [],
            "next_matches": [],
            "standings": [],
            "scorers": [],
            "error": "",
        }
        if not FOOTBALL_DATA_TOKEN:
            payload["error"] = "Set FC_FOOTBALL_DATA_TOKEN on the cloud server."
            self.live_league_cache[code] = {"expires_at": now + timedelta(minutes=10), "payload": payload}
            return payload
        try:
            competition = self._football_data_json(f"/competitions/{code}")
            payload["competition_name"] = competition.get("name") or payload["competition_name"]
            payload["season_label"] = self._live_league_season_label(competition)
            current_season = competition.get("currentSeason") or {}
            payload["matchday"] = int(current_season.get("currentMatchday") or 0)

            standings_payload = self._football_data_json(f"/competitions/{code}/standings")
            standings_tables = standings_payload.get("standings") or []
            table = []
            for section in standings_tables:
                if str(section.get("type") or "").upper() == "TOTAL":
                    table = section.get("table") or []
                    break
            if not table and standings_tables:
                table = standings_tables[0].get("table") or []
            payload["standings"] = [
                {
                    "position": int(item.get("position") or idx + 1),
                    "team": ((item.get("team") or {}).get("name")) or "",
                    "played": int(item.get("playedGames") or 0),
                    "won": int(item.get("won") or 0),
                    "draw": int(item.get("draw") or 0),
                    "lost": int(item.get("lost") or 0),
                    "goal_diff": int(item.get("goalDifference") or 0),
                    "points": int(item.get("points") or 0),
                    "goals_for": int(item.get("goalsFor") or 0),
                    "goals_against": int(item.get("goalsAgainst") or 0),
                }
                for idx, item in enumerate(table[:12])
            ]

            season_start = current_season.get("startDate")
            season_end = current_season.get("endDate")
            query_bits = []
            if season_start:
                query_bits.append(f"dateFrom={str(season_start)[:10]}")
            if season_end:
                query_bits.append(f"dateTo={str(season_end)[:10]}")
            query = "&".join(query_bits)
            matches_path = f"/competitions/{code}/matches"
            if query:
                matches_path += f"?{query}"
            matches_payload = self._football_data_json(matches_path)
            matches = matches_payload.get("matches") or []
            recent_matches = []
            next_matches = []
            for match in matches:
                row = self._live_league_match_row(match)
                status = row.get("status")
                sort_key = parse_iso(match.get("utcDate")) or utc_now()
                row["sort_key"] = sort_key.isoformat()
                if status == "FINISHED":
                    recent_matches.append(row)
                elif status in ("SCHEDULED", "TIMED", "IN_PLAY", "PAUSED"):
                    next_matches.append(row)
            recent_matches.sort(key=lambda item: item.get("sort_key", ""), reverse=True)
            next_matches.sort(key=lambda item: item.get("sort_key", ""))
            payload["recent_matches"] = recent_matches[:10]
            payload["next_matches"] = next_matches[:10]

            scorers_payload = self._football_data_json(f"/competitions/{code}/scorers")
            scorers = scorers_payload.get("scorers") or []
            payload["scorers"] = [self._live_league_scorer_row(item, idx) for idx, item in enumerate(scorers[:12])]
            payload["provider_ready"] = True
            payload["error"] = ""
        except ValueError as exc:
            payload["error"] = str(exc)
        except Exception:
            payload["error"] = "Unable to load live league data."
        self.live_league_cache[code] = {"expires_at": now + timedelta(minutes=5), "payload": payload}
        return payload

    def _ensure_weekly_fantasy_entry(self, user_id, week_key=None):
        target_week = week_key or iso_week_key()
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO weekly_fantasy (
                    user_id, week_key, breakdown_json, reward_json, created_at, updated_at
                ) VALUES (?, ?, '{}', '{}', ?, ?)
                """,
                (user_id, target_week, timestamp, timestamp),
            )
            conn.commit()
            return conn.execute(
                "SELECT * FROM weekly_fantasy WHERE user_id = ? AND week_key = ?",
                (user_id, target_week),
            ).fetchone()

    def _serialize_weekly_fantasy_entry(self, row):
        if not row:
            return {}
        try:
            squad = json.loads(row["squad_json"]) if row["squad_json"] else []
        except Exception:
            squad = []
        try:
            breakdown = json.loads(row["breakdown_json"] or "{}")
        except Exception:
            breakdown = {}
        try:
            reward = json.loads(row["reward_json"] or "{}")
        except Exception:
            reward = {}
        week_start, week_end = iso_week_window()
        return {
            "week_key": row["week_key"],
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
            "squad": squad,
            "locked": bool(squad),
            "points": int(row["points"] or 0),
            "breakdown": breakdown,
            "top_card_key": row["top_card_key"],
            "reward": reward,
            "reward_claimed": bool(row["reward_claimed"]),
            "synced_at": row["synced_at"],
        }

    def _weekly_slot_accepts(self, slot_name, card):
        position = str(card.get("position", "")).upper()
        if slot_name == "GK":
            return position == "GK"
        if slot_name == "DEF":
            return position in ("RB", "CB", "LB", "RWB", "LWB")
        if slot_name == "MID":
            return position in ("CDM", "CM", "CAM", "LM", "RM")
        if slot_name == "ATT":
            return position in ("LW", "RW", "ST", "CF")
        return True

    def _validate_weekly_squad(self, squad):
        if not isinstance(squad, list) or len(squad) != 5:
            raise ValueError("Weekly Fantasy needs exactly 5 selected cards.")
        required_slots = ["GK", "DEF", "MID", "ATT", "FLEX"]
        seen_keys = set()
        for idx, slot_name in enumerate(required_slots):
            item = squad[idx] if idx < len(squad) else None
            if not isinstance(item, dict):
                raise ValueError("Weekly Fantasy squad entry is invalid.")
            if item.get("slot") != slot_name:
                raise ValueError("Weekly Fantasy squad slots are out of order.")
            if not item.get("card_key") or item["card_key"] in seen_keys:
                raise ValueError("Weekly Fantasy squad cannot use duplicate cards.")
            if not self._weekly_slot_accepts(slot_name, item):
                raise ValueError(f"{item.get('name', 'Card')} does not fit the {slot_name} slot.")
            seen_keys.add(item["card_key"])

    def _empty_weekly_stats(self):
        return {"appearances": 0, "goals": 0, "assists": 0, "yellow": 0, "red": 0, "clean_sheet": 0, "conceded": 0, "win": 0}

    def _extract_match_lineup_names(self, match, side):
        names = []
        lineups = match.get("lineups")
        if isinstance(lineups, dict):
            source = lineups.get(side) or []
            if isinstance(source, list):
                for item in source:
                    person = item.get("player") if isinstance(item, dict) else None
                    name = (person or item).get("name") if isinstance(person or item, dict) else None
                    if name:
                        names.append(name)
        team_blob = match.get(f"{side}Team") or {}
        source = team_blob.get("lineup") or team_blob.get("startingXI") or []
        if isinstance(source, list):
            for item in source:
                person = item.get("player") if isinstance(item, dict) else None
                name = (person or item).get("name") if isinstance(person or item, dict) else None
                if name:
                    names.append(name)
        return names

    def _weekly_stats_from_matches(self, matches):
        stats = {}

        def ensure_player(name, team):
            key = f"{normalize_person_name(name)}|{normalize_team_name(team)}"
            if key not in stats:
                stats[key] = self._empty_weekly_stats()
            return key

        for match in matches:
            home_team = ((match.get("homeTeam") or {}).get("name")) or ""
            away_team = ((match.get("awayTeam") or {}).get("name")) or ""
            full_time = (match.get("score") or {}).get("fullTime") or {}
            home_goals = int(full_time.get("home") or 0)
            away_goals = int(full_time.get("away") or 0)

            for name in self._extract_match_lineup_names(match, "home"):
                key = ensure_player(name, home_team)
                stats[key]["appearances"] += 1
                stats[key]["clean_sheet"] += 1 if away_goals == 0 else 0
                stats[key]["conceded"] += away_goals
                stats[key]["win"] += 1 if home_goals > away_goals else 0
            for name in self._extract_match_lineup_names(match, "away"):
                key = ensure_player(name, away_team)
                stats[key]["appearances"] += 1
                stats[key]["clean_sheet"] += 1 if home_goals == 0 else 0
                stats[key]["conceded"] += home_goals
                stats[key]["win"] += 1 if away_goals > home_goals else 0

            for goal in match.get("goals") or match.get("scorers") or []:
                scorer = goal.get("scorer") if isinstance(goal, dict) else None
                assist = goal.get("assist") if isinstance(goal, dict) else None
                team_name = ((goal.get("team") or {}).get("name")) if isinstance(goal, dict) else ""
                scorer_name = scorer.get("name") if isinstance(scorer, dict) else goal.get("scorer") if isinstance(goal, dict) else None
                assist_name = assist.get("name") if isinstance(assist, dict) else None
                if scorer_name:
                    if not team_name:
                        team_name = home_team if normalize_person_name(scorer_name) in [normalize_person_name(n) for n in self._extract_match_lineup_names(match, "home")] else away_team
                    stats[ensure_player(scorer_name, team_name)]["goals"] += 1
                if assist_name:
                    if not team_name:
                        team_name = home_team if normalize_person_name(assist_name) in [normalize_person_name(n) for n in self._extract_match_lineup_names(match, "home")] else away_team
                    stats[ensure_player(assist_name, team_name)]["assists"] += 1

            for booking in match.get("bookings") or []:
                player = booking.get("player") if isinstance(booking, dict) else None
                player_name = player.get("name") if isinstance(player, dict) else None
                team_name = ((booking.get("team") or {}).get("name")) if isinstance(booking, dict) else ""
                card_type = str(booking.get("card") or booking.get("cardType") or "").lower()
                if player_name:
                    target = stats[ensure_player(player_name, team_name)]
                    if "red" in card_type:
                        target["red"] += 1
                    else:
                        target["yellow"] += 1
        return stats

    def _score_weekly_card(self, card, stats):
        position = str(card.get("position", "ST")).upper()
        points = 0
        if stats["appearances"] > 0:
            points += 2
        if position == "GK" or position in ("RB", "CB", "LB", "RWB", "LWB"):
            points += stats["goals"] * 12
        elif position in ("CDM", "CM", "CAM", "LM", "RM"):
            points += stats["goals"] * 10
        else:
            points += stats["goals"] * 8
        points += stats["assists"] * 6
        if position == "GK" or position in ("RB", "CB", "LB", "RWB", "LWB"):
            points += stats["clean_sheet"] * 4
            points -= (stats["conceded"] // 2)
        points += stats["win"] * 2
        points -= stats["yellow"] * 3
        points -= stats["red"] * 8
        return points

    def _weekly_reward_for_points(self, points, squad_breakdown):
        top_card_key = None
        if squad_breakdown:
            top_card_key = max(squad_breakdown, key=lambda item: item.get("points", 0)).get("card_key")
        if points >= 95:
            return {"coins": 240, "pack_id": "elite_pick", "upgrade_delta": 3, "upgrade_card_key": top_card_key}
        if points >= 70:
            return {"coins": 160, "pack_id": "elite", "upgrade_delta": 2, "upgrade_card_key": top_card_key}
        if points >= 45:
            return {"coins": 100, "pack_id": "gold", "upgrade_delta": 1, "upgrade_card_key": top_card_key}
        return {"coins": 40, "pack_id": "", "upgrade_delta": 0, "upgrade_card_key": None}

    def get_weekly_fantasy_status(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        entry = self._ensure_weekly_fantasy_entry(user_row["id"])
        return {
            "entry": self._serialize_weekly_fantasy_entry(entry),
            "provider_ready": bool(FOOTBALL_DATA_TOKEN),
            "provider_name": "football-data.org",
        }

    def submit_weekly_fantasy_squad(self, token, squad):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        self._validate_weekly_squad(squad)
        entry = self._ensure_weekly_fantasy_entry(user_row["id"])
        if entry["squad_json"]:
            raise ValueError("Weekly Fantasy squad already locked for this week.")
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE weekly_fantasy
                SET squad_json = ?, updated_at = ?
                WHERE user_id = ? AND week_key = ?
                """,
                (json.dumps(squad), timestamp, user_row["id"], iso_week_key()),
            )
            conn.commit()
            self._write_backup(conn)
        return self.get_weekly_fantasy_status(token)

    def sync_weekly_fantasy_score(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        entry = self._ensure_weekly_fantasy_entry(user_row["id"])
        if not entry["squad_json"]:
            raise ValueError("Submit your Weekly Fantasy squad first.")
        squad = json.loads(entry["squad_json"])
        week_start, week_end = iso_week_window()
        matches = self._football_data_json(
            f"/competitions/{WEEKLY_FANTASY_COMPETITION}/matches?status=FINISHED&dateFrom={week_start.date().isoformat()}&dateTo={week_end.date().isoformat()}"
        ).get("matches", [])
        stats_map = self._weekly_stats_from_matches(matches)
        breakdown = []
        total_points = 0
        for item in squad:
            stat_key = f"{normalize_person_name(item.get('name'))}|{normalize_team_name(item.get('team'))}"
            player_stats = stats_map.get(stat_key, self._empty_weekly_stats())
            points = self._score_weekly_card(item, player_stats)
            total_points += points
            breakdown.append(
                {
                    "card_key": item.get("card_key"),
                    "name": item.get("name"),
                    "team": item.get("team"),
                    "slot": item.get("slot"),
                    "points": points,
                    "stats": player_stats,
                }
            )
        reward = self._weekly_reward_for_points(total_points, breakdown)
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE weekly_fantasy
                SET points = ?, breakdown_json = ?, top_card_key = ?, reward_json = ?, synced_at = ?, updated_at = ?
                WHERE user_id = ? AND week_key = ?
                """,
                (
                    total_points,
                    json.dumps({"players": breakdown}),
                    reward.get("upgrade_card_key"),
                    json.dumps(reward),
                    timestamp,
                    timestamp,
                    user_row["id"],
                    iso_week_key(),
                ),
            )
            conn.commit()
            self._write_backup(conn)
        return self.get_weekly_fantasy_status(token)

    def claim_weekly_fantasy_reward(self, token):
        user_row = self.get_user_by_token(token)
        if not user_row:
            raise PermissionError("Invalid or expired session.")
        entry = self._ensure_weekly_fantasy_entry(user_row["id"])
        if not entry["squad_json"]:
            raise ValueError("Submit your Weekly Fantasy squad first.")
        if entry["reward_claimed"]:
            raise ValueError("Weekly Fantasy reward already claimed.")
        try:
            reward = json.loads(entry["reward_json"] or "{}")
        except Exception:
            reward = {}
        if not reward:
            raise ValueError("Sync Weekly Fantasy points before claiming rewards.")
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE weekly_fantasy
                SET reward_claimed = 1, updated_at = ?
                WHERE user_id = ? AND week_key = ?
                """,
                (timestamp, user_row["id"], iso_week_key()),
            )
            conn.commit()
            self._write_backup(conn)
        status = self.get_weekly_fantasy_status(token)
        return {"reward": reward, **status}

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

    def _load_settings(self, conn=None):
        owns_conn = conn is None
        conn = conn or self._connect()
        try:
            rows = conn.execute("SELECT key, value FROM app_state").fetchall()
            settings = json.loads(json.dumps(DEFAULT_ADMIN_SETTINGS))
            for row in rows:
                try:
                    settings[row["key"]] = json.loads(row["value"])
                except Exception:
                    settings[row["key"]] = row["value"]
            if not isinstance(settings.get("disabled_modes"), dict):
                settings["disabled_modes"] = dict(DEFAULT_ADMIN_SETTINGS["disabled_modes"])
            return settings
        finally:
            if owns_conn:
                conn.close()

    def _save_settings(self, conn, settings):
        for key, value in settings.items():
            conn.execute(
                "INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )

    def _require_developer(self, token):
        row = self.get_user_by_token(token)
        if not row:
            raise PermissionError("Invalid or expired session.")
        if not row["is_developer"]:
            raise PermissionError("Developer access required.")
        return row

    def _check_user_access(self, row):
        if row["is_banned"]:
            raise PermissionError("This account has been banned.")
        if row["suspended_until"]:
            until = parse_iso(row["suspended_until"])
            if until and until > utc_now():
                raise PermissionError(f"Account suspended until {row['suspended_until']}.")

    def _build_default_fantasy_snapshot(self, row):
        return {
            "game_mode": "FANTASY",
            "fantasy_team_name": f"{row['display_name'] or row['username']} FC",
            "fantasy_roster": [],
            "fantasy_coins": 3000,
            "my_packs": [],
            "fantasy_season_xp": 0,
            "fantasy_season_claimed": 0,
            "fantasy_objectives": {},
            "fantasy_competitions": {},
            "fantasy_active_competition": "division",
            "fantasy_match_competition": "division",
            "current_theme": "Open",
            "team_lineups": {},
            "roster_data": {},
            "rating_cache": {},
            "event_evo_tokens": 0,
        }

    def _repair_fantasy_snapshot(self, snapshot, row=None):
        snapshot = dict(snapshot or {})
        default_team_name = f"{(row['display_name'] if row else '') or (row['username'] if row else 'Fantasy')} FC" if row else "Fantasy FC"
        team_name = snapshot.get("fantasy_team_name") or default_team_name
        roster = snapshot.get("fantasy_roster")
        if not isinstance(roster, list):
            roster = []
        lineup_entries = []
        reserve_entries = []
        used_numbers = set()
        for idx, card in enumerate(roster):
            if not isinstance(card, dict):
                continue
            name = str(card.get("name") or f"Player {idx + 1}")
            rating = int(card.get("rating", 60))
            number = int(card.get("number", idx + 1))
            while number in used_numbers:
                number += 1
            used_numbers.add(number)
            card["number"] = number
            entry = (name, number, rating)
            if len(lineup_entries) < 11:
                lineup_entries.append(entry)
            else:
                reserve_entries.append(entry)
        team_lineups = snapshot.get("team_lineups")
        if not isinstance(team_lineups, dict):
            team_lineups = {}
        roster_data = snapshot.get("roster_data")
        if not isinstance(roster_data, dict):
            roster_data = {}
        team_lineups[team_name] = lineup_entries
        roster_data[team_name] = reserve_entries
        snapshot["fantasy_team_name"] = team_name
        snapshot["fantasy_roster"] = roster
        snapshot["fantasy_coins"] = int(snapshot.get("fantasy_coins", 3000))
        packs = snapshot.get("my_packs")
        snapshot["my_packs"] = packs if isinstance(packs, list) else []
        snapshot["fantasy_season_xp"] = int(snapshot.get("fantasy_season_xp", 0))
        snapshot["fantasy_season_claimed"] = int(snapshot.get("fantasy_season_claimed", 0))
        snapshot["team_lineups"] = team_lineups
        snapshot["roster_data"] = roster_data
        return snapshot

    def _load_user_row_by_username(self, conn, username):
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
        if not row:
            raise ValueError("User not found.")
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
        with self._connect() as conn:
            settings = self._load_settings(conn)
        if settings.get("maintenance_mode") and developer_code != DEVELOPER_CODE:
            raise PermissionError("Cloud is in maintenance mode.")
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
                    is_developer, is_banned, suspended_until, career_snapshot,
                    fantasy_snapshot, last_mode, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, NULL, NULL, NULL, 'CAREER', ?, ?)
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
        with self._connect() as conn:
            settings = self._load_settings(conn)
        if settings.get("maintenance_mode") and not row["is_developer"]:
            raise PermissionError("Cloud is in maintenance mode.")
        if require_dev and (not row["is_developer"] or developer_code != DEVELOPER_CODE):
            raise PermissionError("Developer code required.")
        self._check_user_access(row)
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
        self._check_user_access(row)
        if mode not in ("CAREER", "FANTASY"):
            raise ValueError("Invalid mode.")
        column = "career_snapshot" if mode == "CAREER" else "fantasy_snapshot"
        if mode == "FANTASY":
            snapshot = self._repair_fantasy_snapshot(snapshot, row=row)
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
        self._check_user_access(row)
        if mode not in ("CAREER", "FANTASY"):
            raise ValueError("Invalid mode.")
        column = "career_snapshot" if mode == "CAREER" else "fantasy_snapshot"
        snapshot_text = row[column]
        return json.loads(snapshot_text) if snapshot_text else None

    def list_users(self, token):
        self._require_developer(token)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM users
                ORDER BY username ASC
                """
            ).fetchall()
            settings = self._load_settings(conn)
        return {
            "users": [self._serialize_user(item, include_snapshots=True) for item in rows],
            "settings": settings,
            "health": {
                "ok": True,
                "database_path": self.db_path,
                "user_count": len(rows),
            },
        }

    def public_config(self):
        with self._connect() as conn:
            settings = self._load_settings(conn)
        return {
            "announcement": settings.get("announcement", ""),
            "maintenance_mode": bool(settings.get("maintenance_mode")),
            "disabled_modes": settings.get("disabled_modes", {}),
            "weekly_fantasy_provider": "football-data.org",
            "weekly_fantasy_enabled": True,
            "weekly_fantasy_provider_ready": bool(FOOTBALL_DATA_TOKEN),
        }

    def admin_status(self, token):
        self._require_developer(token)
        with self._connect() as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            online_div_count = conn.execute("SELECT COUNT(*) FROM online_divisions").fetchone()[0]
            online_tour_count = conn.execute("SELECT COUNT(*) FROM online_tournaments").fetchone()[0]
            settings = self._load_settings(conn)
        return {
            "ok": True,
            "settings": settings,
            "metrics": {
                "users": user_count,
                "online_divisions": online_div_count,
                "online_tournaments": online_tour_count,
            },
        }

    def _grant_packs(self, snapshot, pack_id, amount):
        packs = snapshot.get("my_packs")
        if not isinstance(packs, list):
            packs = []
        if amount >= 0:
            packs.extend([pack_id] * amount)
        else:
            remove_count = abs(amount)
            kept = []
            removed = 0
            for item in packs:
                if item == pack_id and removed < remove_count:
                    removed += 1
                    continue
                kept.append(item)
            packs = kept
        snapshot["my_packs"] = packs

    def _add_card(self, snapshot, card):
        roster = snapshot.get("fantasy_roster")
        if not isinstance(roster, list):
            roster = []
        gifted = dict(card or {})
        gifted["rating"] = int(gifted.get("rating", 60))
        gifted["position"] = gifted.get("position", "ST")
        gifted["promo"] = gifted.get("promo", "Base")
        gifted["rarity"] = gifted.get("rarity", "Bronze")
        gifted["team"] = gifted.get("team", "")
        gifted["league"] = gifted.get("league", "")
        gifted["nation"] = gifted.get("nation", "")
        gifted["number"] = int(gifted.get("number", len(roster) + 1))
        gifted["card_key"] = gifted.get("card_key") or f"{gifted.get('name', 'Player')}|{gifted['promo']}|{gifted['rating']}|{gifted['position']}"
        roster.append(gifted)
        snapshot["fantasy_roster"] = roster

    def _remove_card(self, snapshot, card_key):
        roster = snapshot.get("fantasy_roster")
        if not isinstance(roster, list):
            snapshot["fantasy_roster"] = []
            return False
        removed = False
        kept = []
        for card in roster:
            if not removed and isinstance(card, dict) and card.get("card_key") == card_key:
                removed = True
                continue
            kept.append(card)
        snapshot["fantasy_roster"] = kept
        return removed

    def admin_user_action(self, token, username, action, payload=None):
        payload = payload or {}
        admin_row = self._require_developer(token)
        timestamp = utc_iso(utc_now())
        with self.lock, self._connect() as conn:
            target = self._load_user_row_by_username(conn, username)
            if target["username"] == admin_row["username"] and action in ("revoke_developer", "ban"):
                raise ValueError("You cannot remove your own developer access or ban yourself.")
            updates = {}
            fantasy_snapshot = json.loads(target["fantasy_snapshot"]) if target["fantasy_snapshot"] else None
            if action == "promote_developer":
                updates["is_developer"] = 1
            elif action == "revoke_developer":
                updates["is_developer"] = 0
            elif action == "ban":
                updates["is_banned"] = 1
            elif action == "unban":
                updates["is_banned"] = 0
            elif action == "suspend":
                days = max(1, int(payload.get("days", 7)))
                updates["suspended_until"] = utc_iso(utc_now() + timedelta(days=days))
            elif action == "unsuspend":
                updates["suspended_until"] = None
            elif action == "reset_password":
                new_password = str(payload.get("new_password") or "legend123").strip()
                if len(new_password) < 4:
                    raise ValueError("Password reset must be at least 4 characters.")
                salt = secrets.token_hex(16)
                updates["password_salt"] = salt
                updates["password_hash"] = self._hash_password(new_password, salt)
            elif action == "grant_coins":
                fantasy_snapshot = fantasy_snapshot or self._build_default_fantasy_snapshot(target)
                fantasy_snapshot["fantasy_coins"] = max(0, int(fantasy_snapshot.get("fantasy_coins", 0)) + int(payload.get("amount", 0)))
                updates["fantasy_snapshot"] = json.dumps(self._repair_fantasy_snapshot(fantasy_snapshot, row=target))
            elif action == "grant_packs":
                fantasy_snapshot = fantasy_snapshot or self._build_default_fantasy_snapshot(target)
                self._grant_packs(fantasy_snapshot, str(payload.get("pack_id") or "gold"), int(payload.get("amount", 1)))
                updates["fantasy_snapshot"] = json.dumps(self._repair_fantasy_snapshot(fantasy_snapshot, row=target))
            elif action == "add_card":
                fantasy_snapshot = fantasy_snapshot or self._build_default_fantasy_snapshot(target)
                self._add_card(fantasy_snapshot, payload.get("card") or {})
                updates["fantasy_snapshot"] = json.dumps(self._repair_fantasy_snapshot(fantasy_snapshot, row=target))
            elif action == "remove_card":
                fantasy_snapshot = fantasy_snapshot or self._build_default_fantasy_snapshot(target)
                removed = self._remove_card(fantasy_snapshot, str(payload.get("card_key") or ""))
                if not removed:
                    raise ValueError("Card not found on this account.")
                updates["fantasy_snapshot"] = json.dumps(self._repair_fantasy_snapshot(fantasy_snapshot, row=target))
            elif action == "repair_account":
                fantasy_snapshot = fantasy_snapshot or self._build_default_fantasy_snapshot(target)
                updates["fantasy_snapshot"] = json.dumps(self._repair_fantasy_snapshot(fantasy_snapshot, row=target))
            else:
                raise ValueError("Unknown admin user action.")
            updates["updated_at"] = timestamp
            assignments = ", ".join(f"{key} = ?" for key in updates.keys())
            conn.execute(
                f"UPDATE users SET {assignments} WHERE id = ?",
                tuple(updates.values()) + (target["id"],),
            )
            conn.commit()
            self._write_backup(conn)
            refreshed = conn.execute("SELECT * FROM users WHERE id = ?", (target["id"],)).fetchone()
        return self._serialize_user(refreshed, include_snapshots=True)

    def admin_settings_update(self, token, payload):
        self._require_developer(token)
        payload = payload or {}
        with self.lock, self._connect() as conn:
            settings = self._load_settings(conn)
            if "announcement" in payload:
                settings["announcement"] = str(payload.get("announcement") or "")[:240]
            if "maintenance_mode" in payload:
                settings["maintenance_mode"] = bool(payload.get("maintenance_mode"))
            if "disabled_modes" in payload and isinstance(payload.get("disabled_modes"), dict):
                merged = dict(settings.get("disabled_modes", {}))
                for key, value in payload["disabled_modes"].items():
                    merged[str(key)] = bool(value)
                settings["disabled_modes"] = merged
            self._save_settings(conn, settings)
            conn.commit()
        return settings

    def admin_tournament_action(self, token, username, action, payload=None):
        payload = payload or {}
        self._require_developer(token)
        with self.lock, self._connect() as conn:
            target = self._load_user_row_by_username(conn, username)
            if action == "reset_division":
                conn.execute(
                    """
                    INSERT INTO online_divisions (user_id, updated_at)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        division_tier = 10, points = 0, wins = 0, draws = 0, losses = 0,
                        goals_for = 0, goals_against = 0, cycle_played = 0, cycle_points = 0,
                        reward_coins = 0, recent_results = '[]', updated_at = excluded.updated_at
                    """,
                    (target["id"], utc_iso(utc_now())),
                )
            elif action == "reset_tournament":
                conn.execute(
                    """
                    INSERT INTO online_tournaments (user_id, updated_at)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        round = 1, wins = 0, losses = 0, matches_played = 0, reward_coins = 0,
                        updated_at = excluded.updated_at
                    """,
                    (target["id"], utc_iso(utc_now())),
                )
            elif action == "award_tournament_coins":
                amount = max(0, int(payload.get("amount", 0)))
                conn.execute(
                    """
                    INSERT INTO online_tournaments (user_id, reward_coins, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        reward_coins = reward_coins + excluded.reward_coins,
                        updated_at = excluded.updated_at
                    """,
                    (target["id"], amount, utc_iso(utc_now())),
                )
            else:
                raise ValueError("Unknown tournament action.")
            conn.commit()
            self._write_backup(conn)
        return {
            "user": self.get_user_by_username(username, include_snapshots=True),
            "division": self.get_online_division_status(token) if action == "reset_division" and username == self._require_developer(token)["username"] else None,
        }


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
                self._send_json(HTTPStatus.OK, {"ok": True, "service": "fc-fantasy-cloud", **STORE.public_config()})
                return
            if parsed.path == "/api/config":
                self._send_json(HTTPStatus.OK, STORE.public_config())
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
                payload = STORE.list_users(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/admin/status":
                token = self._bearer_token()
                payload = STORE.admin_status(token)
                self._send_json(HTTPStatus.OK, payload)
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
            if parsed.path == "/api/weekly-fantasy":
                token = self._bearer_token()
                payload = STORE.get_weekly_fantasy_status(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/live-league":
                competition = (self._query().get("competition") or ["PL"])[0]
                payload = STORE.get_live_league_status(competition)
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
            if parsed.path == "/api/weekly-fantasy/submit":
                token = self._bearer_token()
                payload = STORE.submit_weekly_fantasy_squad(token, body.get("squad"))
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/weekly-fantasy/sync":
                token = self._bearer_token()
                payload = STORE.sync_weekly_fantasy_score(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/weekly-fantasy/claim":
                token = self._bearer_token()
                payload = STORE.claim_weekly_fantasy_reward(token)
                self._send_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/admin/user-action":
                token = self._bearer_token()
                payload = STORE.admin_user_action(
                    token,
                    body.get("username", ""),
                    body.get("action", ""),
                    body,
                )
                self._send_json(HTTPStatus.OK, {"user": payload})
                return
            if parsed.path == "/api/admin/tournament-action":
                token = self._bearer_token()
                payload = STORE.admin_tournament_action(
                    token,
                    body.get("username", ""),
                    body.get("action", ""),
                    body,
                )
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
            if parsed.path == "/api/admin/settings":
                token = self._bearer_token()
                payload = STORE.admin_settings_update(token, self._json_body())
                self._send_json(HTTPStatus.OK, {"settings": payload})
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
