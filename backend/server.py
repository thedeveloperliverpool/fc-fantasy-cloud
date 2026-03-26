import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cloud_accounts.db")
DEVELOPER_CODE = "Reve1@+ion"
SESSION_TTL_DAYS = 30
PBKDF2_ROUNDS = 200_000


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


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
                """
            )

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

    def register_user(self, display_name, username, password, developer_code=""):
        username = username.strip().lower()
        display_name = display_name.strip()
        if not display_name or not username or not password:
            raise ValueError("Display name, username, and password are required.")
        if not all(ch.isalnum() or ch in ("_", "-") for ch in username):
            raise ValueError("Username can only contain letters, numbers, _ and -.")
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
