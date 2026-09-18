#!/usr/bin/env python3
"""
Test Playwright Firefox with ChatGPT in Headless mode with Session Persistence.

This script:
1. Launches Firefox persistently in HEADLESS mode.
2. Syncs your active ChatGPT login session from your desktop Firefox profile.
3. Navigates to https://chatgpt.com.
4. Verifies you are logged in (prompt box ready, no 'Log in' prompt).
5. Persists the session in ~/.playwright_firefox_profile so future runs stay logged in.
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.firefox_connector import (
    launch_firefox_context,
    open_or_get_tab,
    DEFAULT_PROFILE_DIR,
)


def main():
    print("=" * 60)
    print("  Playwright Firefox — ChatGPT Headless Session Test")
    print("=" * 60)
    print(f"Persistent profile: {DEFAULT_PROFILE_DIR}")
    print()

    with sync_playwright() as playwright:
        print("[1/3] Launching Firefox (headless) with session sync...")
        context = launch_firefox_context(
            playwright,
            headless=True,
            sync_cookies_domains=["chatgpt.com", "openai.com"],
        )

        page = open_or_get_tab(context)

        print("[2/3] Navigating to https://chatgpt.com...")
        start_time = time.time()
        try:
            response = page.goto("https://chatgpt.com", wait_until="commit", timeout=25000)
            elapsed = round(time.time() - start_time, 2)
            status = response.status if response else "unknown"
            print(f"✓ Navigation completed in {elapsed}s (HTTP {status})")
        except Exception as e:
            print(f"✗ Navigation error: {e}")
            context.close()
            sys.exit(1)

        print("[3/3] Verifying authenticated session...")
        # Brief pause for UI hydration
        page.wait_for_timeout(5000)
        title = page.title()
        url = page.url
        print(f"  Page title: {title}")
        print(f"  Current URL: {url}")
        print()

        login_buttons = page.locator("button:has-text('Log in')")
        has_login = login_buttons.count() > 0 and login_buttons.first.is_visible()

        prompt_box = page.locator("#prompt-textarea, [data-testid='prompt-textarea'], div[contenteditable='true']")
        has_prompt = prompt_box.count() > 0 and prompt_box.first.is_visible()

        if has_prompt and not has_login:
            print("🎉 SUCCESS: You are fully LOGGED IN to ChatGPT!")
            print("  ✓ Prompt box is active and ready for input.")
            print("  ✓ Login state has been saved to your persistent profile.")
            print("  ✓ Future automation runs will NOT require logging in again.")
        elif not has_login:
            print("✓ SUCCESS: Logged in (no 'Log in' prompt displayed).")
            print("  ✓ Session saved to persistent profile.")
        else:
            print("⚠ Notice: Session tokens not yet active. Please log in once from your desktop Firefox.")

        context.close()
        print()
        print("✓ Context closed cleanly. Session saved.")


if __name__ == "__main__":
    main()
