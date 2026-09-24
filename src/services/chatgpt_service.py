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


def is_unsuitable_response(raw_text: str) -> bool:
    """Check if ChatGPT returned an unsuitable / skip / non-engineering classification."""
    if not raw_text:
        return False
    t = raw_text.strip().lower()
    return bool(
        "unsuitable_jd" in t
        or t.startswith("not suitable")
        or "❌ not suitable" in t
        or "not suitable —" in t
        or "not suitable -" in t
        or "→ skip" in t
        or "-> skip" in t
        or ("classification:" in t and "skip" in t)
        or "recommendation: skip" in t
        or "not a software engineering" in t
        or "not a software developer" in t
        or "i'd skip this one" in t
        or "skip this one" in t
    )


def parse_email_response(raw_text: str) -> Tuple[str, str]:
    """
    Parse a ChatGPT generated application response into (subject, body).
    """
    if not raw_text:
        return "", ""

    clean_text = raw_text.strip()

    # Detect if ChatGPT reported the JD as unsuitable or skip
    if is_unsuitable_response(clean_text):
        return "UNSUITABLE_JD", clean_text

    # Strip conversational lead-ins or boilerplate labels like "Email\n\n", "Email Draft:\n\n"
    clean_text = re.sub(
        r"^(?:(?:Here(?:'s| is) (?:the )?(?:cold outreach )?email(?:\s+draft)?:?)|(?:Email(?:\s+Draft)?[:\s]*))\n+",
        "",
        clean_text,
        flags=re.IGNORECASE,
    ).strip()

    lines = clean_text.split("\n")
    subject = ""
    body_lines = []
    found_subject = False

    for line in lines:
        match = re.match(r"^(?:\*\*)?Subject(?:\*\*)?:\s*(.+)$", line.strip(), re.IGNORECASE)
        if match and not found_subject:
            subject = match.group(1).replace("**", "").strip()
            found_subject = True
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    # Strip any residual leading "Email\n\n" or "Subject:\n"
    body = re.sub(r"^(?:Email(?:\s+Draft)?[:\s]*\n+)+", "", body, flags=re.IGNORECASE).strip()

    if not subject:
        # Try extracting role from first sentence (e.g. "I'm writing to apply for the Full Stack Developer L2 position in Mumbai")
        role_match = re.search(r"apply(?:ing)? for the\s+([^,\.\n]+?)(?:\s+position|\s+role|\.|\n|$)", body, re.IGNORECASE)
        if role_match:
            extracted_role = role_match.group(1).strip()
            subject = f"Application for {extracted_role}"
        else:
            subject = "Application for Full Stack Developer"

    return subject, body


def clean_and_truncate_reason(text: str, max_chars: int = 48, max_words: int = 8) -> str:
    """
    Strip boilerplate prefixes and truncate to a concise label.
    e.g. "Classification: BUSINESS DEVELOPMENT / SALES → Skip." -> "Business Development / Sales"
    e.g. "This is a Business Development / Sales role, not a software engineering role." -> "Business Development / Sales role"
    """
    if not text:
        return "Not suitable"
    t = text.strip()

    # Check for Classification: XYZ → Skip
    class_match = re.search(r"Classification:\s*([^→\-\n\.]+?)(?:\s*[→\-]+\s*Skip|\.|$)", t, flags=re.IGNORECASE)
    if class_match:
        label = class_match.group(1).strip()
        if label:
            if label.isupper():
                label = " / ".join("QA" if part.strip().upper() == "QA" else part.strip().title() for part in label.split("/"))
            return label[:max_chars].strip()

    # Check for "This is a <Role>, not a software..."
    role_match = re.search(r"This is an?\s+([^,\n\.]+?)(?:,\s*not a software|\.\s*The core)?", t, flags=re.IGNORECASE)
    if role_match:
        return role_match.group(1).strip()[:max_chars]

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
    Extract clean, concise reason string from an unsuitable JD response.
    First checks for an explicit Classification tag anywhere in the text,
    then evaluates the role description or first line.
    """
    if not raw_text:
        return "Not suitable"

    # 1. Search full text for explicit Classification: ... -> Skip tag
    class_match = re.search(r"Classification:\s*([^→\-\n\.]+?)(?:\s*[→\-]+\s*Skip|\.|$)", raw_text, flags=re.IGNORECASE)
    if class_match:
        label = class_match.group(1).strip()
        if label:
            if label.isupper():
                label = " / ".join("QA" if part.strip().upper() == "QA" else part.strip().title() for part in label.split("/"))
            return label[:48].strip()

    # 2. Check for "This is a <Role>, not a software..."
    role_match = re.search(r"This is an?\s+([^,\n\.]+?)(?:,\s*not a software|\.\s*The core)?", raw_text, flags=re.IGNORECASE)
    if role_match:
        return role_match.group(1).strip()[:48]

    # 3. Fallback to clean_and_truncate_reason on first non-empty line
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    first_line = lines[0] if lines else ""
    return clean_and_truncate_reason(first_line)


def send_jd_and_get_email(
    page: Page,
    jd_text: str,
    max_wait: int = 120,
    poll_interval: int = 2
) -> Tuple[str, str]:
    """
    Send the raw JD to ChatGPT and wait for the response.

    Returns:
        (subject, body)
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Cannot send empty JD text to ChatGPT.")

    # 1. Record existing last assistant message ID and text
    existing_msgs = page.locator("[data-message-author-role='assistant']")
    initial_count = existing_msgs.count()
    last_msg_id = ""
    initial_last_text = ""
    if initial_count > 0:
        try:
            last_msg_id = existing_msgs.last.evaluate(
                "el => el.getAttribute('data-message-id') || ''"
            )
        except Exception:
            pass
        try:
            initial_last_text = existing_msgs.last.inner_text().strip()
        except Exception:
            pass

    # 2. Focus prompt box
    prompt_box = page.locator("#prompt-textarea")
    prompt_box.click()
    page.wait_for_timeout(300)

    # 3. Fast insert into ProseMirror contenteditable via native execCommand
    inserted = False
    try:
        inserted = page.evaluate("""(text) => {
            const el = document.querySelector('#prompt-textarea');
            if (!el) return false;
            el.focus();
            document.execCommand('selectAll', false, null);
            const ok = document.execCommand('insertText', false, text);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            return ok;
        }""", jd_text.strip())
    except Exception as eval_err:
        print(f"    execCommand insert notice: {eval_err}")
        inserted = False

    # Verify text populated in prompt box
    current_prompt_text = ""
    try:
        current_prompt_text = prompt_box.inner_text().strip()
    except Exception:
        pass

    if not inserted or not current_prompt_text:
        # Fallback 1: fill locator
        try:
            prompt_box.fill(jd_text.strip())
            current_prompt_text = prompt_box.inner_text().strip()
        except Exception:
            pass

    if not current_prompt_text:
        # Fallback 2: type line-by-line
        lines = jd_text.strip().split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                page.keyboard.press("Shift+Enter")
            if line:
                page.keyboard.type(line, delay=1)

    page.wait_for_timeout(600)

    # 4. Click Send Button or press Enter
    sent = False
    send_btn_query = (
        "button[data-testid='send-button'], "
        "form button[aria-label='Send prompt'], "
        "form button[data-testid='send-button'], "
        "form button[data-testid='fruitjuice-send-button'], "
        "form button[type='submit']"
    )

    start_btn = time.time()
    while time.time() - start_btn < 4:
        btn = page.locator(send_btn_query).first
        if btn.count() > 0 and btn.is_visible():
            try:
                is_disabled = btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true'")
            except Exception:
                is_disabled = False
            if not is_disabled:
                try:
                    btn.click(timeout=3000)
                    sent = True
                    break
                except Exception:
                    pass
        time.sleep(0.4)

    if not sent:
        # Resilient fallback: press Enter in prompt box
        print("    Send button not clickable or delayed; pressing Enter in prompt box...")
        try:
            prompt_box.focus()
            page.keyboard.press("Enter")
            sent = True
        except Exception as enter_err:
            print(f"    Press Enter fallback failed: {enter_err}")

    page.wait_for_timeout(1000)

    # 5. Wait for Response Generation
    elapsed = 0
    response_text = ""

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        current_msgs = page.locator("[data-message-author-role='assistant']")
        current_count = current_msgs.count()

        if current_count > 0:
            last_msg = current_msgs.last
            try:
                new_last_id = last_msg.evaluate(
                    "el => el.getAttribute('data-message-id') || ''"
                )
            except Exception:
                new_last_id = ""

            try:
                current_last_text = last_msg.inner_text().strip()
            except Exception:
                current_last_text = ""

            # Check if a new message has arrived
            is_new_message = (
                (new_last_id and last_msg_id and new_last_id != last_msg_id)
                or current_count > initial_count
                or (current_last_text and current_last_text != initial_last_text)
            )

            if is_new_message:
                # Check if still streaming
                stop_btn = page.locator(
                    "button[aria-label='Stop generating'], "
                    "button[data-testid='stop-button'], "
                    "button[aria-label='Stop reasoning'], "
                    "button[aria-label*='Stop']"
                )
                if stop_btn.count() > 0 and stop_btn.first.is_visible():
                    print(f"    ...streaming response ({elapsed}s)")
                    continue

                # Finished streaming!
                md_el = last_msg.locator(".markdown")
                if md_el.count() > 0:
                    response_text = md_el.first.inner_text().strip()
                else:
                    response_text = current_last_text

                if response_text and response_text != initial_last_text:
                    print(f"    ✓ Received full response ({elapsed}s, {len(response_text)} chars)")
                    break

    if not response_text:
        # Fallback: only if a new message was actually produced
        current_msgs = page.locator("[data-message-author-role='assistant']")
        if current_msgs.count() > initial_count:
            last_msg = current_msgs.last
            md_el = last_msg.locator(".markdown")
            response_text = md_el.first.inner_text().strip() if md_el.count() > 0 else last_msg.inner_text().strip()
        else:
            raise TimeoutError("Timed out waiting for ChatGPT response (no new assistant reply was generated).")

    subject, body = parse_email_response(response_text)
    return subject, body
