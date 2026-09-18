#!/usr/bin/env python3
"""
Send a sample JD + template to a specific ChatGPT conversation and capture the response.

Runs in HEADED mode so the user can watch the interaction live.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.firefox_connector import launch_firefox_context
from src.chatgpt_service import get_default_chatgpt_url

CHATGPT_CONVERSATION_URL = get_default_chatgpt_url()

SAMPLE_JD = """\
Job Title: Senior Full Stack Developer
Company: TechVista Solutions
Location: Remote (India)
Type: Full-time

About the Role:
We are looking for a Senior Full Stack Developer with 4+ years of experience to join our product engineering team. You will be responsible for building scalable web applications using modern technologies.

Requirements:
- 4+ years of experience with React.js / Next.js
- Strong backend experience with Node.js / Express / NestJS
- Database: PostgreSQL, MongoDB, Redis
- Experience with cloud services (AWS / GCP)
- Familiarity with CI/CD pipelines, Docker, Kubernetes
- Good understanding of system design and microservices architecture

Nice to Have:
- Experience with GraphQL
- Contributions to open-source projects
- Experience leading a small team

Compensation: 18-28 LPA based on experience"""

ARTIFACT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "artifacts"
)


def main():
    prompt_text = SAMPLE_JD


    print("=" * 60)
    print("  ChatGPT Conversation — Send JD & Capture Response")
    print("=" * 60)
    print()

    with sync_playwright() as playwright:
        print("[1/5] Launching Firefox (headed)...")
        context = launch_firefox_context(
            playwright,
            headless=False,
            sync_cookies_domains=["chatgpt.com", "openai.com"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        print(f"[2/5] Opening conversation...")
        page.goto(CHATGPT_CONVERSATION_URL, wait_until="commit", timeout=30000)
        page.wait_for_timeout(5000)
        print(f"  Title: {page.title()}")
        print(f"  URL: {page.url}")

        # Verify login
        login_btn = page.locator("button:has-text('Log in')")
        if login_btn.count() > 0 and login_btn.first.is_visible():
            print("✗ Not logged in!")
            context.close()
            sys.exit(1)
        print("  ✓ Logged in")

        # Track the last assistant message ID so we can detect a new one reliably
        existing_msgs = page.locator("[data-message-author-role='assistant']")
        initial_count = existing_msgs.count()
        last_msg_id = ""
        if initial_count > 0:
            last_msg_id = existing_msgs.last.evaluate(
                "el => el.getAttribute('data-message-id') || ''"
            )
        print(f"  Existing assistant messages: {initial_count}, last ID: {last_msg_id[:20]}")

        # ----- Type the prompt -----
        print("[3/5] Typing prompt...")
        prompt_box = page.locator("#prompt-textarea")
        prompt_box.click()
        page.wait_for_timeout(500)

        # ProseMirror contenteditable needs keyboard.type (not fill)
        # Type line-by-line: Shift+Enter for newlines inside the prompt box
        lines = prompt_text.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                page.keyboard.press("Shift+Enter")
            page.keyboard.type(line, delay=5)

        page.wait_for_timeout(1000)
        print("  ✓ Prompt typed")

        # ----- Send -----
        print("[4/5] Sending prompt...")
        send_btn = page.locator("button[data-testid='send-button']")
        send_btn.wait_for(state="visible", timeout=5000)
        send_btn.click()
        print("  ✓ Send button clicked")

        # ----- Wait for response -----
        print("  Waiting for response (up to 120s)...")
        max_wait = 120
        poll_interval = 3
        elapsed = 0
        response_text = ""

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            current_msgs = page.locator("[data-message-author-role='assistant']")
            current_count = current_msgs.count()

            if current_count > 0:
                new_last_id = current_msgs.last.evaluate(
                    "el => el.getAttribute('data-message-id') || ''"
                )

                # A new assistant message appeared if the ID changed or count grew
                if new_last_id != last_msg_id:
                    # Check if still streaming (stop button visible)
                    stop_btn = page.locator(
                        "button[aria-label='Stop generating'], "
                        "button[data-testid='stop-button'], "
                        "button[aria-label='Stop reasoning']"
                    )
                    if stop_btn.count() > 0 and stop_btn.first.is_visible():
                        print(f"  Generating... ({elapsed}s)")
                        continue

                    # Done streaming — extract the last assistant message
                    last_msg = current_msgs.last
                    md_el = last_msg.locator(".markdown")
                    if md_el.count() > 0:
                        response_text = md_el.first.inner_text()
                    else:
                        response_text = last_msg.inner_text()
                    print(f"  ✓ Response received after {elapsed}s ({len(response_text)} chars)")
                    break

            print(f"  Waiting... ({elapsed}s)")

        if not response_text:
            # Last-ditch: grab whatever the last assistant message says now
            current_msgs = page.locator("[data-message-author-role='assistant']")
            if current_msgs.count() > 0:
                last_msg = current_msgs.last
                md_el = last_msg.locator(".markdown")
                response_text = md_el.first.inner_text() if md_el.count() > 0 else last_msg.inner_text()

        # ----- Save results -----
        print("[5/5] Saving results...")

        # Screenshot
        screenshot_path = os.path.join(ARTIFACT_DIR, "chatgpt_response_screenshot.png")
        page.screenshot(path=screenshot_path, full_page=False)
        print(f"  Screenshot saved: {screenshot_path}")

        # Response text
        response_path = os.path.join(ARTIFACT_DIR, "scratch", "chatgpt_response.txt")
        os.makedirs(os.path.dirname(response_path), exist_ok=True)
        with open(response_path, "w") as f:
            f.write(response_text)
        print(f"  Response saved: {response_path}")

        print()
        print("=" * 60)
        print("  CHATGPT RESPONSE:")
        print("=" * 60)
        print(response_text if response_text else "(empty — no response captured)")
        print("=" * 60)

        print("\nKeeping Firefox open for 10 seconds...")
        time.sleep(10)

        context.close()
        print("✓ Done.")


if __name__ == "__main__":
    main()
