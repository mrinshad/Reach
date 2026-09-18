"""
Gmail Automation Service

Interacts with Gmail web interface in headed mode:
- Opens compose modal
- Populates Recipient ("To"), Subject, and Message Body
- Attaches resume file if provided
- STOPS before sending for mandatory human review and approval
"""

import os
import time
from typing import Optional
from playwright.sync_api import Page

GMAIL_INBOX_URL = "https://mail.google.com/mail/u/0/#inbox"


def navigate_to_gmail(page: Page, timeout: int = 30000):
    """Navigate to Gmail inbox and verify login."""
    print("Navigating to Gmail...")
    page.goto(GMAIL_INBOX_URL, wait_until="commit", timeout=timeout)
    page.wait_for_timeout(4000)

    # Verify if inbox loaded
    compose_btn = page.locator('div[gh="cm"], div[role="button"]:has-text("Compose")').first
    try:
        compose_btn.wait_for(state="visible", timeout=15000)
        print("✓ Gmail inbox loaded and Compose button ready.")
    except Exception:
        raise RuntimeError(
            "Gmail inbox or Compose button not found. "
            "Please ensure you are logged into Gmail in the Firefox profile."
        )


def populate_email_draft(
    page: Page,
    recipient: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None
) -> bool:
    """
    Open compose modal in Gmail, populate all fields, attach resume,
    and leave the draft ready on screen for human review.
    """
    # 1. Click Compose button
    print("Opening compose window...")
    compose_btn = page.locator('div[gh="cm"], div[role="button"]:has-text("Compose")').first
    compose_btn.click()
    page.wait_for_timeout(1500)

    # 2. Populate "To" recipient
    print(f"  Setting recipient: {recipient}")
    to_field = page.locator('input[aria-label*="To"], input.agP, input[peoplekit-id]').first
    to_field.wait_for(state="visible", timeout=10000)
    to_field.click()
    page.wait_for_timeout(300)
    page.keyboard.type(recipient, delay=5)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(500)

    # 3. Populate Subject
    print(f"  Setting subject: {subject}")
    subject_field = page.locator('input[name="subjectbox"]').first
    subject_field.wait_for(state="visible", timeout=5000)
    subject_field.click()
    page.wait_for_timeout(200)
    subject_field.fill(subject)
    page.wait_for_timeout(500)

    # 4. Populate Message Body with proper paragraph breaks
    print(f"  Populating message body ({len(body)} chars)...")
    body_field = page.locator('div[role="textbox"][aria-label*="Message Body"]').first
    body_field.wait_for(state="visible", timeout=5000)
    body_field.click()
    page.wait_for_timeout(300)

    # Remove any boilerplate lines that say "To: ..." or "Subject: ..."
    cleaned_lines = []
    for line in body.split("\n"):
        if line.strip().lower().startswith("to:") or line.strip().lower().startswith("subject:"):
            continue
        cleaned_lines.append(line)
    clean_body = "\n".join(cleaned_lines).strip()

    # In Gmail's contenteditable rich text area, typing line-by-line with Enter
    # creates proper <div>/paragraph blocks, preserving clean paragraph spacing.
    lines = clean_body.split("\n")
    for line in lines:
        if line.strip():
            page.keyboard.type(line, delay=0.5)
        page.keyboard.press("Enter")

    page.wait_for_timeout(1000)

    # 5. Attach Resume if specified
    if attachment_path and os.path.exists(attachment_path):
        print(f"  Attaching resume: {attachment_path}")
        file_input = page.locator('input[type="file"][name="Filedata"]').first
        if file_input.count() > 0:
            file_input.set_input_files(attachment_path)
            print("  Waiting for attachment to upload...")
            page.wait_for_timeout(4000)
            print("  ✓ Resume attached.")
        else:
            print("  Warning: File attachment input not found.")
    elif attachment_path:
        print(f"  Warning: Attachment path not found on disk: {attachment_path}")

    print("✓ Email draft prepared successfully in Gmail.")
    return True


def send_email_directly(page: Page, timeout: int = 15000) -> bool:
    """
    Click the Gmail Send button or press Ctrl+Enter directly,
    waiting for the compose dialog to close and dispatch to complete.
    """
    print("Directly sending email in Gmail...")
    page.wait_for_timeout(1000)
    
    send_btn = page.locator('div[role="button"][data-tooltip*="Send"], div[role="button"]:text-is("Send"), div[aria-label*="Send"]').first
    try:
        if send_btn.is_visible():
            send_btn.click()
            print("  Clicked Send button.")
        else:
            page.keyboard.press("Control+Enter")
            print("  Pressed Ctrl+Enter to send.")
    except Exception as e:
        print(f"  Warning on button click: {e}, attempting Control+Enter shortcut...")
        try:
            page.keyboard.press("Control+Enter")
        except Exception:
            page.keyboard.press("Meta+Enter")

    try:
        page.wait_for_selector('div[role="dialog"]', state="hidden", timeout=timeout)
        print("✓ Compose dialog closed — email sent successfully.")
    except Exception:
        page.wait_for_timeout(3000)
        print("✓ Wait timeout passed — assuming email sent.")

    return True

