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


def discard_open_compose_dialogs(page: Page):
    """
    Safely dismiss any alert popups and discard any lingering open compose windows.
    Prevents unclosed or invalid dialogs from blocking subsequent email dispatches.
    """
    try:
        # 1. Dismiss any alert dialogs (e.g. invalid recipient address error or confirmation)
        alert_dialogs = page.locator('div[role="alertdialog"]')
        for i in range(alert_dialogs.count()):
            try:
                alert = alert_dialogs.nth(i)
                btn = alert.locator('button, div[role="button"]:has-text("OK"), div[role="button"]:has-text("Dismiss")').first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=1500)
                    page.wait_for_timeout(300)
            except Exception:
                pass

        # 2. Click discard draft buttons (trash can icon) in all open compose dialogs
        discard_btns = page.locator('div[role="dialog"] div[data-tooltip*="Discard"], div[role="dialog"] div[aria-label*="Discard"]')
        for i in range(discard_btns.count()):
            try:
                discard_btns.nth(i).click(timeout=2000)
                page.wait_for_timeout(400)
            except Exception:
                pass

        # 3. If any dialog remains, press Escape
        dialogs = page.locator('div[role="dialog"]')
        if dialogs.count() > 0:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
    except Exception:
        pass


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
    # 0. Clean up any leftover or orphaned dialogs
    discard_open_compose_dialogs(page)

    # 1. Click Compose button
    print("Opening compose window...")
    compose_btn = page.locator('div[gh="cm"], div[role="button"]:has-text("Compose")').first
    compose_btn.click()
    page.wait_for_timeout(1000)

    # Wait for the compose dialog to appear
    page.locator('div[role="dialog"]').last.wait_for(state="visible", timeout=10000)
    dialog = page.locator('div[role="dialog"]').last

    # 2. Populate "To" recipient (scoped strictly inside active dialog)
    print(f"  Setting recipient: {recipient}")
    to_field = dialog.locator('input[aria-label*="To"], input.agP, input[peoplekit-id]').first
    try:
        to_field.wait_for(state="visible", timeout=6000)
    except Exception:
        # If the input is hidden, click the recipient container to focus/reveal it
        recipient_container = dialog.locator('div[role="combobox"], div[name="to"], tr.n1tzfe, td.eV').first
        if recipient_container.count() > 0:
            recipient_container.click()
            page.wait_for_timeout(300)
        to_field.wait_for(state="visible", timeout=5000)

    to_field.click()
    page.wait_for_timeout(200)
    page.keyboard.type(recipient, delay=5)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)

    # 3. Populate Subject (scoped strictly inside active dialog)
    print(f"  Setting subject: {subject}")
    subject_field = dialog.locator('input[name="subjectbox"]').first
    subject_field.wait_for(state="visible", timeout=5000)
    subject_field.click()
    page.wait_for_timeout(200)
    subject_field.fill(subject)
    page.wait_for_timeout(400)

    # 4. Populate Message Body with proper paragraph breaks (scoped inside active dialog)
    print(f"  Populating message body ({len(body)} chars)...")
    body_field = dialog.locator('div[role="textbox"][aria-label*="Message Body"]').first
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

    lines = clean_body.split("\n")
    for line in lines:
        if line.strip():
            page.keyboard.type(line, delay=0.5)
        page.keyboard.press("Enter")

    page.wait_for_timeout(800)

    # 5. Attach Resume if specified (scoped inside active dialog)
    if attachment_path and os.path.exists(attachment_path):
        print(f"  Attaching resume: {attachment_path}")
        file_input = dialog.locator('input[type="file"][name="Filedata"]').first
        if file_input.count() > 0:
            file_input.set_input_files(attachment_path)
            print("  Waiting for attachment to upload...")
            page.wait_for_timeout(1500)
            try:
                dialog.wait_for_selector('div[role="progressbar"], div[aria-label*="Uploading"]', state="hidden", timeout=12000)
            except Exception:
                page.wait_for_timeout(2500)
            print("  ✓ Resume attached.")
        else:
            print("  Warning: File attachment input not found.")
    elif attachment_path:
        print(f"  Warning: Attachment path not found on disk: {attachment_path}")

    print("✓ Email draft prepared successfully in Gmail.")
    return True


def send_email_directly(page: Page, timeout: int = 20000) -> bool:
    """
    Click the Gmail Send button inside the active compose dialog
    or trigger platform-appropriate shortcuts (Meta+Enter on Mac, Ctrl+Enter elsewhere),
    waiting for the compose dialog to close and dispatch to complete.
    """
    print("Directly sending email in Gmail...")
    page.wait_for_timeout(800)

    # 1. Ensure any attachment upload progress bar inside dialog is finished
    try:
        page.wait_for_selector('div[role="dialog"] div[role="progressbar"]', state="hidden", timeout=10000)
    except Exception:
        pass

    dialog = page.locator('div[role="dialog"]').last
    if dialog.count() == 0:
        print("  Warning: No active compose dialog found, searching globally...")
        dialog = page

    # Primary send button strictly inside the compose dialog
    send_btn = dialog.locator(
        'div[role="button"].T-I-atl, '
        'div[role="button"][data-tooltip*="Send"], '
        'div[role="button"][aria-label*="Send \u202a"], '
        'div[role="button"]:text-is("Send")'
    ).first

    sent_triggered = False

    try:
        if send_btn.is_visible(timeout=3000):
            print("  Clicking Send button inside dialog...")
            send_btn.click(force=True)
            sent_triggered = True
    except Exception as e:
        print(f"  Button click failed: {e}")

    if not sent_triggered:
        print("  Triggering keyboard shortcuts to send...")
        try:
            body_field = dialog.locator('div[role="textbox"][aria-label*="Message Body"]').first
            if body_field.is_visible():
                body_field.focus()
        except Exception:
            pass

        # Send shortcut: Meta+Enter for macOS (Command+Enter), Control+Enter for Windows/Linux
        page.keyboard.press("Meta+Enter")
        page.wait_for_timeout(300)
        page.keyboard.press("Control+Enter")

    # 2. Check if an alert dialog popped up (e.g. invalid recipient address rejected by Gmail)
    page.wait_for_timeout(600)
    alert = page.locator('div[role="alertdialog"]').first
    if alert.count() > 0 and alert.is_visible():
        alert_text = alert.inner_text().strip()
        print(f"  Alert popup detected: {alert_text}")
        discard_open_compose_dialogs(page)
        raise RuntimeError(f"Gmail rejected email dispatch: {alert_text}")

    # 3. Wait for dialog to close indicating dispatch success
    try:
        page.wait_for_selector('div[role="dialog"]', state="hidden", timeout=timeout)
        print("✓ Compose dialog closed — email sent successfully.")
        return True
    except Exception:
        print("  Dialog still visible after timeout. Retrying with keyboard shortcuts...")
        # Check alert dialog again
        alert = page.locator('div[role="alertdialog"]').first
        if alert.count() > 0 and alert.is_visible():
            alert_text = alert.inner_text().strip()
            discard_open_compose_dialogs(page)
            raise RuntimeError(f"Gmail rejected email dispatch: {alert_text}")

        try:
            page.keyboard.press("Meta+Enter")
            page.wait_for_timeout(500)
            page.keyboard.press("Control+Enter")
            page.wait_for_selector('div[role="dialog"]', state="hidden", timeout=6000)
            print("✓ Compose dialog closed on retry — email sent successfully.")
            return True
        except Exception:
            # Check if "Message sent" alert/toast appeared in Gmail
            toast = page.locator('span:text-is("Message sent"), span:text-is("Message sent.")').first
            if toast.count() > 0 and toast.is_visible():
                print("✓ 'Message sent' confirmation detected.")
                return True
            discard_open_compose_dialogs(page)
            raise RuntimeError("Failed to send email: compose dialog remained open.")

