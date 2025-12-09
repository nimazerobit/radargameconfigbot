import sqlite3
from pathlib import Path
from typing import Optional, Any, Dict, Tuple, List
import time

class DB:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            # users 
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                user_hash TEXT UNIQUE,
                usage_count INTEGER DEFAULT 0,
                created_at INTEGER,
                last_active INTEGER,
                banned INTEGER DEFAULT 0
            );
            """)

            # radargame
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS radargame (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                password TEXT,
                token TEXT,
                is_active INTEGER DEFAULT 0,
                created_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
            """)

            conn.commit()

    # ——— users ———
    def count_users(self) -> int:
        with self._connect() as con:
            cur = con.cursor()
            return cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_users_page(self, limit: int, offset: int):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(
                "SELECT * FROM users ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return cur.fetchall()
        
    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            return cursor.fetchone()

    def upsert_user(self, user_id: int, username: Optional[str], full_name: str, user_hash: str, now_ts: int) -> sqlite3.Row:
        with self._connect() as conn:
            cursor = conn.cursor()
            existing = self.get_user(user_id)
            if existing:
                cursor.execute("""UPDATE users SET username=?, full_name=?, last_active=?
                               WHERE user_id=?""", (username, full_name, now_ts, user_id))
            else:
                cursor.execute("""INSERT INTO users (user_id, username, full_name, user_hash, created_at, last_active)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (user_id, username, full_name, user_hash, now_ts, now_ts))
            conn.commit()
        return self.get_user(user_id)
    
    def add_user_usage(self, user_id: int) -> sqlite3.Row:
        with self._connect() as conn:
            cursor = conn.cursor()
            existing = self.get_user(user_id)
            if existing:
                cursor.execute("UPDATE users SET usage_count = usage_count + 1 WHERE user_id=?", (user_id))
            conn.commit()
        return self.get_user(user_id)

    def set_ban(self, user_id: int, banned: bool):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if banned else 0, user_id))
            conn.commit()

    def find_user_by_any(self, key: str) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            cursor = conn.cursor()
            if key.isdigit():
                cursor.execute("SELECT * FROM users WHERE user_id=?", (int(key),))
            elif key.startswith('@'):
                cursor.execute("SELECT * FROM users WHERE username=?", (key[1:],))
            else:
                cursor.execute("SELECT * FROM users WHERE user_hash=?", (key,))
            return cursor.fetchone()

    def stats_for_user(self, user_id: int) -> Dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_at, last_active, user_hash, username, full_name, usage_count, banned FROM users WHERE user_id=?", (user_id,))
            user_data = cursor.fetchone()
            radargame_count = cursor.execute("SELECT COUNT(*) FROM radargame WHERE user_id=?", (user_id,)).fetchone()[0]
            return {
                "username": user_data["username"] if user_data else None,
                "full_name": user_data["full_name"] if user_data else None,
                "user_hash": user_data["user_hash"] if user_data else None,
                "radargame_count": radargame_count if radargame_count else None,
                "usage_count": user_data["usage_count"] if user_data else None,
                "created_at": user_data["created_at"] if user_data else None,
                "last_active": user_data["last_active"] if user_data else None,
                "banned": user_data["banned"] if user_data else None,
            }

    # ===== radargame =====
    def add_radargame_account(self, user_id: int, username: str, password: str, token=None):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO radargame (user_id, username, password, token, created_at) VALUES (?, ?, ?, ?, ?)",
                           (user_id, username, password, token, int(time.time())))
            conn.commit()
        self.set_active_radargame(user_id, username)

    def radargame_username_exists(self, user_id: int, account_username: str) -> bool:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM radargame WHERE user_id=? AND username=?", (user_id, account_username))
            count = cursor.fetchone()[0]
            return count > 0
        
    def set_active_radargame(self, user_id: int, account_username: str) -> bool:
        with self._connect() as conn:
            cursor = conn.cursor()
            # deactivate all existing accounts for the user
            cursor.execute("UPDATE radargame SET is_active = 0 WHERE user_id = ?", (user_id,))
            # then activate the chosen account
            cursor.execute("UPDATE radargame SET is_active = 1 WHERE user_id = ? AND username = ?", (user_id, account_username))
            conn.commit()
            activated_count = cursor.rowcount
        return activated_count > 0

    def get_user_radargame_accounts(self, user_id: int):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM radargame WHERE user_id = ?", (user_id,))
            return cursor.fetchall()
        
    def get_active_radargame_account(self, user_id: int):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM radargame WHERE user_id = ? AND is_active = 1 LIMIT 1", (user_id,))
            return cursor.fetchone()

    def delete_radargame_account(self, user_id: int, account_username: str) -> bool:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM radargame WHERE user_id=? AND username=?", (user_id, account_username))
            conn.commit()
            return cursor.rowcount > 0

    def delete_all_radargame_accounts_for_user(self, user_id: int) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM radargame WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount
