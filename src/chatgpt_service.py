"""
ChatGPT Custom GPT Automation Service

Interacts with the user's dedicated custom GPT conversation:
- Navigates to conversation
- Types raw JD text into ProseMirror editor (#prompt-textarea)
- Sends prompt and waits for streaming completion
- Extracts and parses the cold outreach email (Subject + Body)
"""

import re
import time
from typing import Tuple, Optional
from playwright.sync_api import Page

def get_default_chatgpt_url() -> str:
    """Retrieve custom GPT URL from database settings, falling back to config."""
    try:
        from src.db import get_setting
        val = get_setting("chatgpt_url")
        if val:
            return val
    except Exception:
        pass
    try:
        from src.config import load_config
        val = load_config().get("chatgpt_url")
        if val:
            return val
    except Exception:
        pass
    return "https://chatgpt.com"


def navigate_to_conversation(page: Page, url: Optional[str] = None, timeout: int = 30000):
    """Navigate to the dedicated custom GPT conversation and ensure ready state."""
    target_url = url or get_default_chatgpt_url()
    if not target_url or "example-chat-id" in target_url:
        raise ValueError(
            "ChatGPT Custom GPT URL is not configured. Please set your Custom GPT Chat Link in Settings or PostgreSQL."
        )
    print(f"Opening ChatGPT conversation...")
    page.goto(target_url, wait_until="commit", timeout=timeout)
    page.wait_for_timeout(5000)

    # Verify login
    login_btn = page.locator("button:has-text('Log in')")
    if login_btn.count() > 0 and login_btn.first.is_visible():
        raise RuntimeError("Not logged in to ChatGPT! Please log in manually in the Firefox window.")

    # Wait for prompt textarea
    page.wait_for_selector("#prompt-textarea", timeout=20000)
    print("✓ ChatGPT conversation loaded and prompt box ready.")


def parse_email_response(raw_text: str) -> Tuple[str, str]:
    """
    Parse a ChatGPT generated application response into (subject, body).
    """
    if not raw_text:
        return "", ""

    clean_text = raw_text.strip()

    # Detect if ChatGPT reported the JD as unsuitable (e.g. female candidates only, etc.)
    if "UNSUITABLE_JD" in clean_text or clean_text.lower().startswith("not suitable") or "❌ not suitable" in clean_text.lower() or "not suitable —" in clean_text.lower():
        return "UNSUITABLE_JD", clean_text

    lines = raw_text.split("\n")
    subject = ""
    body_lines = []
    found_subject = False

    for line in lines:
        match = re.match(r"^(?:\*\*)?Subject(?:\*\*)?:\s*(.+)$", line.strip(), re.IGNORECASE)
        if match and not found_subject:
            subject = match.group(1).replace("**", "").strip()
            found_subject = True
            continue
        if found_subject:
            body_lines.append(line)
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if not subject:
        # Fallback if no explicit subject line
        subject = "Application for Full Stack Developer"

    return subject, body


def clean_and_truncate_reason(text: str, max_chars: int = 48, max_words: int = 8) -> str:
    """
    Strip boilerplate prefixes and truncate to a concise label.
    e.g. "Not suitable — This is an HR role requiring an MBA/MHRM..." -> "HR role requiring an MBA/MHRM..."
    """
    if not text:
        return "Not suitable"
    t = text.strip()
    # Strip UNSUITABLE_JD / ❌ prefix
    t = re.sub(r"^(?:UNSUITABLE_JD\s*[-—:]*\s*)?(?:❌\s*)?", "", t, flags=re.IGNORECASE).strip()
    # Strip "Not suitable — " / "Not suitable - " prefix variants
    t = re.sub(r"^(?:Not suitable|Unsuitable(?:\s*JD)?)\s*[-—:]+\s*", "", t, flags=re.IGNORECASE).strip()
    if not t:
        return "Not suitable"

    words = t.split()
    t_lower = t.lower()
    # For scam/potential scam/spam reasons, preserve context up to 100 characters
    if "scam" in t_lower or "spam" in t_lower:
        if len(t) > 100:
            return t[:97].rstrip() + "..."
        return t

    if len(words) > max_words or len(t) > max_chars:
        # Take up to max_words and also respect max_chars
        truncated = " ".join(words[:max_words])
        if len(truncated) > max_chars - 3:
            truncated = truncated[: max_chars - 3].rstrip()
            if " " in truncated:
                truncated = truncated.rsplit(" ", 1)[0]
        return truncated.rstrip(".,;:-—") + "..."
    return t


def extract_unsuitable_reason(raw_text: str) -> str:
    """
    Extract clean, concise reason string from an unsuitable JD response, e.g.:
    "UNSUITABLE_JD - ❌ Not suitable — {reason}" -> concise truncated reason
    "❌ Not suitable — Female candidates only" -> "Female candidates only"
    """
    if not raw_text:
        return "Not suitable"
    first_line = raw_text.strip().splitlines()[0].strip()
    return clean_and_truncate_reason(first_line)



def send_jd_and_get_email(
    page: Page,
    jd_text: str,
    max_wait: int = 120,
    poll_interval: int = 3
) -> Tuple[str, str]:
    """
    Send the raw JD to ChatGPT and wait for the response.

    Returns:
        (subject, body)
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Cannot send empty JD text to ChatGPT.")

    # 1. Record existing last assistant message ID
    existing_msgs = page.locator("[data-message-author-role='assistant']")
    initial_count = existing_msgs.count()
    last_msg_id = ""
    if initial_count > 0:
        last_msg_id = existing_msgs.last.evaluate(
            "el => el.getAttribute('data-message-id') || ''"
        )

    # 2. Focus prompt box
    prompt_box = page.locator("#prompt-textarea")
    prompt_box.click()
    page.wait_for_timeout(400)

    # 3. Type line-by-line (ProseMirror contenteditable)
    lines = jd_text.strip().split("\n")
    for i, line in enumerate(lines):
        if i > 0:
            page.keyboard.press("Shift+Enter")
        if line:
            page.keyboard.type(line, delay=3)

    page.wait_for_timeout(800)

    # 4. Click Send Button
    send_btn = page.locator("button[data-testid='send-button']")
    send_btn.wait_for(state="visible", timeout=6000)
    send_btn.click()

    # 5. Wait for Response Generation
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

            # New message appeared
            if new_last_id != last_msg_id or current_count > initial_count:
                # Check if still streaming
                stop_btn = page.locator(
                    "button[aria-label='Stop generating'], "
                    "button[data-testid='stop-button'], "
                    "button[aria-label='Stop reasoning']"
                )
                if stop_btn.count() > 0 and stop_btn.first.is_visible():
                    print(f"    ...streaming response ({elapsed}s)")
                    continue

                # Finished streaming!
                last_msg = current_msgs.last
                md_el = last_msg.locator(".markdown")
                if md_el.count() > 0:
                    response_text = md_el.first.inner_text().strip()
                else:
                    response_text = last_msg.inner_text().strip()

                if response_text:
                    print(f"    ✓ Received full response ({elapsed}s, {len(response_text)} chars)")
                    break

    if not response_text:
        # Fallback: grab whatever the last assistant message says
        current_msgs = page.locator("[data-message-author-role='assistant']")
        if current_msgs.count() > 0:
            last_msg = current_msgs.last
            md_el = last_msg.locator(".markdown")
            response_text = md_el.first.inner_text().strip() if md_el.count() > 0 else last_msg.inner_text().strip()

    subject, body = parse_email_response(response_text)
    return subject, body
