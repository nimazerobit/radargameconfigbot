import sqlite3
from pathlib import Path
import datetime

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
                password TEXT,
                created_at TEXT
            );
            """)

            conn.commit()

    # ——— users ———
    def save_user(self, user_id, username, password):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("REPLACE INTO users (user_id, username, password, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, username, password, datetime.datetime.now().isoformat()))
            conn.commit()

    def get_user(self, user_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, password FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
        return result
        
    def get_all_users(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM users")
            users = cursor.fetchall()
        return users
        
    def get_all_user_info(self, user_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
        return result