"""
Firefox connector module using Playwright's persistent context.

This module provides a clean interface to launch Firefox with a persistent user
data directory so cookies, local storage, and login sessions (ChatGPT, LinkedIn)
are preserved across runs without handling credentials in code.
"""

import os
import glob
import time
import shutil
import sqlite3
import signal
import subprocess
from typing import Optional, List, Dict, Any
from playwright.sync_api import Playwright, BrowserContext, Page

DEFAULT_PROFILE_DIR = os.path.expanduser("~/.playwright_firefox_profile")
DESKTOP_FIREFOX_PROFILES_DIR = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")


def get_default_firefox_profile_dir() -> str:
    """Return the default path to the persistent Firefox profile directory."""
    os.makedirs(DEFAULT_PROFILE_DIR, exist_ok=True)
    return DEFAULT_PROFILE_DIR


def find_desktop_firefox_profile() -> Optional[str]:
    """Locate the user's primary desktop Firefox profile directory."""
    if not os.path.exists(DESKTOP_FIREFOX_PROFILES_DIR):
        return None

    # Check for release profiles first
    candidates = glob.glob(os.path.join(DESKTOP_FIREFOX_PROFILES_DIR, "*.default-release*"))
    if not candidates:
        candidates = glob.glob(os.path.join(DESKTOP_FIREFOX_PROFILES_DIR, "*.default*"))

    # Return the most recently modified profile that contains cookies.sqlite
    valid = [p for p in candidates if os.path.exists(os.path.join(p, "cookies.sqlite"))]
    if valid:
        valid.sort(key=lambda p: os.path.getmtime(os.path.join(p, "cookies.sqlite")), reverse=True)
        return valid[0]

    return None


def extract_desktop_cookies(domains: List[str]) -> List[Dict[str, Any]]:
    """
    Safely extract cookies for specified domains from the desktop Firefox profile.
    Uses a temporary copy to avoid database locks.
    """
    profile_path = find_desktop_firefox_profile()
    if not profile_path:
        return []

    src_db = os.path.join(profile_path, "cookies.sqlite")
    if not os.path.exists(src_db):
        return []

    tmp_db = f"/tmp/moz_cookies_sync_{os.getpid()}.sqlite"
    try:
        shutil.copy2(src_db, tmp_db)
        con = sqlite3.connect(tmp_db)
        cur = con.cursor()

        where_clauses = " OR ".join(["host LIKE ?" for _ in domains])
        params = [f"%{d}%" for d in domains]
        query = f"""
            SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
            WHERE {where_clauses}
        """
        cur.execute(query, params)

        cookies = []
        now = int(time.time())
        for row in cur.fetchall():
            name, value, host, path, expiry, is_secure, is_httponly, same_site = row

            # Convert millisecond expiry to seconds
            if expiry and expiry > 1e11:
                expiry_sec = int(expiry / 1000)
            elif expiry and expiry > 0:
                expiry_sec = int(expiry)
            else:
                expiry_sec = -1

            if expiry_sec != -1 and expiry_sec < now:
                continue

            same_site_str = "None"
            if same_site == 1:
                same_site_str = "Lax"
            elif same_site == 2:
                same_site_str = "Strict"

            cookies.append({
                "name": name,
                "value": value,
                "domain": host,
                "path": path,
                "secure": bool(is_secure),
                "httpOnly": bool(is_httponly),
                "sameSite": same_site_str,
                "expires": expiry_sec,
            })

        con.close()
        return cookies
    except Exception as e:
        print(f"Warning: Could not read desktop Firefox cookies: {e}")
        return []
    finally:
        if os.path.exists(tmp_db):
            try:
                os.remove(tmp_db)
            except OSError:
                pass


def cleanup_stale_profile_locks(profile_dir: str, force: bool = False):
    """
    Safely terminate any lingering or orphaned Firefox processes bound to profile_dir
    and remove stale lock files so persistent context launches cleanly.
    """
    current_pid = os.getpid()
    parent_pid = os.getppid()

    # 1. Terminate lingering processes using this profile
    try:
        res = subprocess.run(
            ["pgrep", "-f", profile_dir],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if res.returncode == 0 and res.stdout:
            pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
            stale_pids = [p for p in pids if p != current_pid and p != parent_pid]
            if stale_pids:
                print(f"Cleaning up {len(stale_pids)} lingering Firefox process(es) for profile: {stale_pids}")
                for pid in stale_pids:
                    try:
                        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
                    except OSError:
                        pass

                # Allow processes up to 1 second to release lock and exit
                time.sleep(1.0)

                # Check and force kill any remaining
                for pid in stale_pids:
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
                time.sleep(0.3)
    except Exception as e:
        print(f"Note: Error during process cleanup for profile: {e}")

    # 2. Remove stale lock files
    for lock_name in [".parentlock", "parent.lock", "lock"]:
        lock_path = os.path.join(profile_dir, lock_name)
        if os.path.exists(lock_path) or os.path.islink(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass


def launch_firefox_context(
    playwright: Playwright,
    profile_dir: Optional[str] = None,
    headless: bool = False,
    sync_cookies_domains: Optional[List[str]] = None,
) -> BrowserContext:
    """
    Launch a persistent Firefox browser context.

    All session cookies, local storage, and credentials entered manually
    by the user remain saved in profile_dir.

    Args:
        playwright: Active Playwright instance.
        profile_dir: Path to Firefox persistent profile directory.
        headless: Whether to run in headless mode (default: False).
        sync_cookies_domains: Optional list of domains (e.g. ['chatgpt.com', 'openai.com'])
                              to import cookies from desktop Firefox if available.

    Returns:
        BrowserContext instance.
    """
    if profile_dir is None:
        profile_dir = get_default_firefox_profile_dir()
    else:
        os.makedirs(profile_dir, exist_ok=True)

    cleanup_stale_profile_locks(profile_dir)

    print(f"Launching Firefox persistent context...")
    print(f"  Profile directory: {profile_dir}")
    print(f"  Headless: {headless}")

    try:
        context = playwright.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            viewport={"width": 1280, "height": 800},
        )
    except Exception as e:
        err_msg = str(e)
        if "Failed to launch the browser process" in err_msg or "exitCode=0" in err_msg:
            print(f"Warning: Persistent context launch failed ({err_msg}). Forcing process cleanup and retrying...")
            cleanup_stale_profile_locks(profile_dir, force=True)
            time.sleep(1.0)
            context = playwright.firefox.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=headless,
                viewport={"width": 1280, "height": 800},
            )
        else:
            raise

    if sync_cookies_domains:
        desktop_cookies = extract_desktop_cookies(sync_cookies_domains)
        if desktop_cookies:
            print(f"  Syncing {len(desktop_cookies)} session cookies from desktop Firefox...")
            context.add_cookies(desktop_cookies)

    return context


def open_or_get_tab(context: BrowserContext, url_substr: str = "") -> Page:
    """
    Return an existing tab matching url_substr, or the first page, or create a new page.
    """
    for page in context.pages:
        if url_substr and url_substr in page.url:
            return page

    if context.pages:
        return context.pages[0]

    return context.new_page()
