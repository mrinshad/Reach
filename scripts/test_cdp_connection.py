#!/usr/bin/env python3
"""
Test CDP connection to existing Chrome.

This script:
1. Copies your Chrome profile for CDP use (if not already done)
2. Launches Chrome with CDP enabled
3. Connects Playwright via CDP
4. Lists all open tabs (titles + URLs)
5. Disconnects cleanly

Does NOT navigate, modify tabs, or access credentials.
Your original Chrome profile is never modified.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.services.chrome_connector import (
    prepare_cdp_profile,
    launch_chrome_with_cdp,
    connect_to_chrome,
    list_open_tabs,
    DEFAULT_CDP_PORT,
)


def main():
    port = DEFAULT_CDP_PORT
    print("=" * 60)
    print("  CDP Connection Test")
    print("=" * 60)
    print()

    # Step 1: Prepare CDP profile
    print("[1/4] Preparing CDP profile...")
    try:
        prepare_cdp_profile()
    except RuntimeError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    print()

    # Step 2: Launch Chrome with CDP
    print("[2/4] Launching Chrome with CDP...")
    try:
        launch_chrome_with_cdp(port)
    except RuntimeError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    print()

    # Step 3: Connect Playwright
    print("[3/4] Connecting Playwright via CDP...")
    pw = sync_playwright().start()
    try:
        browser = connect_to_chrome(pw, port)
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        pw.stop()
        sys.exit(1)
    print()

    # Step 4: List open tabs
    print("[4/4] Open tabs in Chrome:")
    print("-" * 60)
    tabs = list_open_tabs(browser)
    if not tabs:
        print("  (no tabs found)")
    else:
        for i, tab in enumerate(tabs, 1):
            title = tab["title"] or "(untitled)"
            url = tab["url"]
            print(f"  {i}. {title}")
            print(f"     {url}")
            print()

    print("-" * 60)
    print(f"Total tabs: {len(tabs)}")
    print()

    # Disconnect cleanly (does not close Chrome)
    browser.close()
    pw.stop()
    print("✓ Disconnected cleanly. Chrome remains open.")
    print()
    print("NOTE: Chrome is now running with your copied profile.")
    print("      Log in to LinkedIn/ChatGPT/Gmail if sessions expired.")
    print("      Your original Chrome profile was not modified.")


if __name__ == "__main__":
    main()
