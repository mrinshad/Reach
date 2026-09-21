"""
Health & Session Status Service

Checks authentication and connectivity status for LinkedIn, ChatGPT, Gmail,
and the local PostgreSQL database without interrupting background automation.
"""

import os
import time
import shutil
import sqlite3
from typing import Dict, Any

from src.db import get_connection

FIREFOX_PROFILE_DIR = os.path.expanduser("~/.playwright_firefox_profile")


def check_firefox_session_cookies() -> Dict[str, bool]:
    """
    Safely inspect persistent Firefox cookies to verify active login sessions
    for LinkedIn, ChatGPT, and Gmail.
    """
    cookie_file = os.path.join(FIREFOX_PROFILE_DIR, "cookies.sqlite")
    results = {
        "linkedin": False,
        "chatgpt": False,
        "gmail": False,
    }

    if not os.path.exists(cookie_file):
        return results

    # Copy to temporary database to prevent database locking
    tmp_db = f"/tmp/health_cookies_{os.getpid()}.sqlite"
    try:
        shutil.copy2(cookie_file, tmp_db)
        con = sqlite3.connect(tmp_db)
        cur = con.cursor()
        now = int(time.time())

        # 1. Check LinkedIn: li_at cookie
        cur.execute("""
            SELECT expiry FROM moz_cookies 
            WHERE host LIKE '%linkedin.com%' AND name = 'li_at'
        """)
        li_row = cur.fetchone()
        if li_row:
            expiry = li_row[0]
            if expiry == 0 or expiry > now or (expiry > 1e11 and (expiry / 1000) > now):
                results["linkedin"] = True

        # 2. Check ChatGPT: session token
        cur.execute("""
            SELECT expiry FROM moz_cookies 
            WHERE (host LIKE '%chatgpt.com%' OR host LIKE '%openai.com%')
              AND name LIKE '__Secure-next-auth.session-token%'
        """)
        cg_row = cur.fetchone()
        if cg_row:
            expiry = cg_row[0]
            if expiry == 0 or expiry > now or (expiry > 1e11 and (expiry / 1000) > now):
                results["chatgpt"] = True

        # 3. Check Gmail: Google session cookies
        cur.execute("""
            SELECT expiry FROM moz_cookies 
            WHERE host LIKE '%google.com%' AND name IN ('SSID', 'SAPISID', 'SID')
        """)
        gm_row = cur.fetchone()
        if gm_row:
            results["gmail"] = True

        con.close()
    except Exception as e:
        print(f"Health check cookie warning: {e}")
    finally:
        if os.path.exists(tmp_db):
            try:
                os.remove(tmp_db)
            except OSError:
                pass

    return results


def check_database_health() -> bool:
    """Check if local PostgreSQL database is reachable."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return True
    except Exception:
        return False


def get_system_health() -> Dict[str, Any]:
    """Return consolidated health indicators for all external dependencies."""
    sessions = check_firefox_session_cookies()
    db_ok = check_database_health()

    issues = []
    if not sessions["chatgpt"]:
        issues.append("ChatGPT is not logged in. Please log in once in Firefox.")
    if not sessions["gmail"]:
        issues.append("Gmail is not logged in. Please log in once in Firefox.")
    if not db_ok:
        issues.append("PostgreSQL database connection failed.")

    return {
        "infopark": {
            "connected": True,
            "label": "Online & Ready",
        },
        "linkedin": {
            "connected": sessions["linkedin"],
            "label": "Logged In" if sessions["linkedin"] else "Optional",
        },
        "chatgpt": {
            "connected": sessions["chatgpt"],
            "label": "Logged In" if sessions["chatgpt"] else "Not Logged In",
        },
        "gmail": {
            "connected": sessions["gmail"],
            "label": "Logged In" if sessions["gmail"] else "Not Logged In",
        },
        "database": {
            "connected": db_ok,
            "label": "Connected" if db_ok else "Disconnected",
        },
        "has_issues": len(issues) > 0,
        "issues": issues,
    }
