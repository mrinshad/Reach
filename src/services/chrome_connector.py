"""
Chrome CDP connector — connects Playwright to an existing Chrome browser.

Since Chrome 136+, remote debugging is blocked on the default profile directory
for security (anti-infostealer protection). This module works around that by
copying your existing Chrome profile into a separate automation directory,
then launching Chrome with --user-data-dir pointing to that copy.

Your original Chrome profile is NEVER modified.
No credentials are stored or accessed by this code.

Usage:
    1. Quit Chrome if it's running.
    2. Call prepare_cdp_profile() to copy your profile for CDP use.
    3. Call launch_chrome_with_cdp() to launch Chrome with CDP enabled.
    4. Log in to LinkedIn, ChatGPT, Gmail if sessions expired.
    5. Call connect_to_chrome() to get a Playwright browser handle.
"""

import os
import shutil
import subprocess
import time
import urllib.request
import json


CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_CDP_PORT = 9222

# Original Chrome profile
CHROME_DEFAULT_DATA_DIR = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome"
)

# Separate directory for CDP-enabled Chrome
CDP_DATA_DIR = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome-CDP"
)


def is_cdp_available(port: int = DEFAULT_CDP_PORT) -> bool:
    """Check if Chrome is already listening on the CDP port."""
    try:
        url = f"http://localhost:{port}/json/version"
        req = urllib.request.urlopen(url, timeout=3)
        data = json.loads(req.read())
        print(f"  CDP active — Chrome {data.get('Browser', 'unknown')}")
        return True
    except Exception:
        return False


def is_chrome_running() -> bool:
    """Check if any Chrome browser process is running (not helper/renderer)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "Google Chrome.app/Contents/MacOS/Google Chrome"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def prepare_cdp_profile(force_refresh: bool = False) -> str:
    """
    Copy the existing Chrome profile into a separate directory for CDP use.

    Since Chrome 136+ blocks remote debugging on the default profile directory,
    we copy the profile to a separate location. This preserves all cookies,
    sessions, and login states.

    Args:
        force_refresh: If True, delete and re-copy even if the CDP profile
                       already exists.

    Returns:
        The path to the CDP-enabled profile directory.
    """
    if is_chrome_running():
        raise RuntimeError(
            "Chrome is currently running. Please quit Chrome (Cmd+Q) first.\n"
            "We need to copy profile data while Chrome is not running."
        )

    if not os.path.exists(CHROME_DEFAULT_DATA_DIR):
        raise RuntimeError(
            f"Chrome default profile not found at:\n"
            f"  {CHROME_DEFAULT_DATA_DIR}\n"
            "Make sure Chrome has been used at least once."
        )

    if os.path.exists(CDP_DATA_DIR) and not force_refresh:
        print(f"✓ CDP profile already exists at: {CDP_DATA_DIR}")
        print("  Use force_refresh=True to re-copy from the original profile.")
        return CDP_DATA_DIR

    # Remove old CDP profile if it exists
    if os.path.exists(CDP_DATA_DIR):
        print(f"  Removing old CDP profile...")
        shutil.rmtree(CDP_DATA_DIR)

    print(f"  Copying Chrome profile for CDP use...")
    print(f"  From: {CHROME_DEFAULT_DATA_DIR}")
    print(f"  To:   {CDP_DATA_DIR}")

    # Copy the entire profile directory
    # Using copytree to preserve all session data, cookies, etc.
    shutil.copytree(
        CHROME_DEFAULT_DATA_DIR,
        CDP_DATA_DIR,
        symlinks=True,
        ignore_dangling_symlinks=True,
    )

    # Remove the SingletonLock/SingletonCookie/SingletonSocket files
    # These lock files would prevent Chrome from starting with this dir
    for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock_path = os.path.join(CDP_DATA_DIR, lock_file)
        if os.path.exists(lock_path) or os.path.islink(lock_path):
            os.remove(lock_path)

    print(f"✓ CDP profile ready at: {CDP_DATA_DIR}")
    return CDP_DATA_DIR


def launch_chrome_with_cdp(port: int = DEFAULT_CDP_PORT) -> bool:
    """
    Launch Chrome with --remote-debugging-port using the CDP profile copy.

    Returns True if Chrome is ready with CDP enabled.
    """
    # Already available?
    if is_cdp_available(port):
        print(f"✓ Chrome already running with CDP on port {port}")
        return True

    # Chrome running but without CDP — user needs to quit it first
    if is_chrome_running():
        raise RuntimeError(
            "Chrome is running but CDP is not enabled.\n"
            "Please quit Chrome (Cmd+Q) and try again."
        )

    # Ensure CDP profile exists
    if not os.path.exists(CDP_DATA_DIR):
        raise RuntimeError(
            "CDP profile not found. Call prepare_cdp_profile() first."
        )

    # Launch Chrome with CDP flag and the separate profile
    print(f"Launching Chrome with CDP on port {port}...")
    print(f"  Using profile: {CDP_DATA_DIR}")

    subprocess.Popen(
        [
            CHROME_PATH,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={CDP_DATA_DIR}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for CDP to become available
    for attempt in range(20):
        time.sleep(1)
        if is_cdp_available(port):
            print(f"✓ Chrome launched with CDP on port {port}")
            return True
        if attempt < 19:
            print(f"  Waiting for Chrome... ({attempt + 1}s)")

    raise RuntimeError(
        "Chrome launched but CDP did not become available within 20 seconds."
    )


def connect_to_chrome(playwright, port: int = DEFAULT_CDP_PORT):
    """
    Connect Playwright to Chrome via CDP.

    Args:
        playwright: A Playwright instance from sync_playwright().start()
        port: The CDP debugging port

    Returns:
        browser: A Playwright Browser connected via CDP
    """
    if not is_cdp_available(port):
        raise RuntimeError(
            f"CDP is not available on port {port}.\n"
            "Call launch_chrome_with_cdp() first."
        )

    cdp_url = f"http://localhost:{port}"
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    print(f"✓ Playwright connected to Chrome via CDP at {cdp_url}")
    return browser


def list_open_tabs(browser) -> list[dict]:
    """
    List all open tabs in the connected browser.

    Returns a list of dicts with 'title' and 'url' for each tab.
    """
    tabs = []
    for context in browser.contexts:
        for page in context.pages:
            tabs.append({
                "title": page.title(),
                "url": page.url,
            })
    return tabs
