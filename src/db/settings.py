"""
PostgreSQL Settings & Key-Value Configuration Store.
"""

import os
import json
from typing import Optional, Dict
from src.db.connection import get_connection, DEFAULT_DB_URL

def get_setting(key: str, default: Optional[str] = None, db_url: str = DEFAULT_DB_URL) -> Optional[str]:
    """Retrieve a configuration value by key from the database settings table."""
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM settings WHERE key = %s LIMIT 1;", (key,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    return str(row[0])
    except Exception as e:
        print(f"Warning: Could not get db setting '{key}': {e}")
    return default


def set_setting(key: str, value: str, db_url: str = DEFAULT_DB_URL) -> None:
    """Insert or update a configuration key-value in the database settings table."""
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP;
            """, (key, str(value)))
        conn.commit()


def get_all_settings(db_url: str = DEFAULT_DB_URL) -> Dict[str, str]:
    """Retrieve all configuration key-values from the database settings table."""
    results = {}
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT key, value FROM settings;")
                for k, v in cur.fetchall():
                    results[k] = v
    except Exception as e:
        print(f"Warning: Could not fetch all db settings: {e}")
    return results


def seed_default_settings(db_url: str = DEFAULT_DB_URL) -> None:
    """Seed initial settings into database from config.json if not present."""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_file = os.path.join(root_dir, "config.json")
    chatgpt_val = ""
    search_val = "Full stack developer"

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("chatgpt_url"):
                    chatgpt_val = cfg["chatgpt_url"]
                if cfg.get("search_query"):
                    search_val = cfg["search_query"]
        except Exception:
            pass

    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                if search_val:
                    cur.execute(
                        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING;",
                        ("search_query", search_val)
                    )
                if chatgpt_val:
                    cur.execute(
                        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING;",
                        ("chatgpt_url", chatgpt_val)
                    )
            conn.commit()
    except Exception as e:
        print(f"Warning: Could not seed settings: {e}")
