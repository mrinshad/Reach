#!/usr/bin/env python3
"""
Gmail Draft Preparation Script — Human Approval Mandatory

Retrieves an email draft from PostgreSQL, opens Gmail in headed Firefox,
populates the Recipient, Subject, Body, and attaches your resume.
Stops and leaves the window open for your manual review and approval before sending.
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.firefox_connector import launch_firefox_context
from src.gmail_service import navigate_to_gmail, populate_email_draft
from src.db import get_posts, update_post_status, get_connection
from src.config import load_config

DEFAULT_RESUME_PATH = load_config().get("resume_path", "resumes/Test_Resume.pdf")


def mark_post_sent(post_id: str):
    """Mark post as SENT with timestamp in PostgreSQL."""
    sql = """
    UPDATE posts SET
        status = 'SENT',
        approved_at = CURRENT_TIMESTAMP,
        sent_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (post_id,))
        conn.commit()
    print(f"✓ Post {post_id} marked as SENT in database.")


def main():
    parser = argparse.ArgumentParser(description="Prepare outreach email draft in Gmail for review.")
    parser.add_argument("--post-id", type=str, help="Specific post ID to prepare email for.")
    parser.add_argument("--resume", type=str, default=DEFAULT_RESUME_PATH, help="Path to resume PDF.")
    args = parser.parse_args()

    print("=" * 68)
    print("  Gmail Email Draft Preparation (Headed — Human Review)")
    print("=" * 68)

    # 1. Retrieve the post from PostgreSQL
    if args.post_id:
        with get_connection() as conn:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM posts WHERE id = %s;", (args.post_id,))
                row = cur.fetchone()
                target_post = dict(row) if row else None
    else:
        # Default: get latest post with EMAIL_GENERATED status
        posts = get_posts(status="EMAIL_GENERATED", limit=1)
        target_post = posts[0] if posts else None

    if not target_post:
        print("✗ No post found with status 'EMAIL_GENERATED'.")
        print("Please generate an email draft first using scripts/process_posts_with_chatgpt.py.")
        sys.exit(1)

    post_id = target_post["id"]
    author = target_post["author_name"]
    emails = target_post.get("contact_emails", [])
    recipient = emails[0] if emails else ""
    subject = target_post.get("generated_subject", "Application for Full Stack Developer")
    body = target_post.get("generated_body", "")

    if not recipient:
        print(f"✗ Post by '{author}' does not have a contact email.")
        sys.exit(1)

    print(f"  Target Post ID:   {post_id}")
    print(f"  Author / Contact: {author}")
    print(f"  Recipient:        {recipient}")
    print(f"  Subject:          {subject}")
    print(f"  Resume Path:      {args.resume}")
    print("=" * 68)
    print()

    # 2. Launch Firefox in headed mode
    with sync_playwright() as playwright:
        print("[1/2] Launching Firefox (headed=True)...")
        context = launch_firefox_context(
            playwright,
            headless=False,
            sync_cookies_domains=["google.com", "gmail.com"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        # 3. Open Gmail & Populate Compose
        print("[2/2] Opening Gmail and populating draft...")
        navigate_to_gmail(page)
        populate_email_draft(
            page=page,
            recipient=recipient,
            subject=subject,
            body=body,
            attachment_path=args.resume if os.path.exists(args.resume) else None,
        )

        # 4. Mandatory Human Review & Approval
        print("\n" + "=" * 68)
        print("  MANDATORY HUMAN REVIEW: DRAFT READY IN GMAIL")
        print("=" * 68)
        print("  The email draft is open on your screen right now.")
        print(f"  - Recipient:  {recipient}")
        print(f"  - Subject:    {subject}")
        print(f"  - Attachment: {args.resume if os.path.exists(args.resume) else '(None)'}")
        print("-" * 68)
        print("  You can review, edit, and click 'Send' manually in Gmail.")
        print("  Press Enter in this terminal when you have reviewed or sent the email,")
        print("  or type 'cancel' to exit without marking as sent:")
        print("=" * 68)

        # Wait for user input in console (or wait up to 120s if running non-interactively)
        try:
            user_input = input(">> Did you send the email? (y/n/cancel): ").strip().lower()
            if user_input in ["y", "yes", "sent"]:
                mark_post_sent(post_id)
            else:
                print("Draft preserved without marking as sent.")
        except EOFError:
            print("\nNon-interactive mode: Leaving browser open for 60 seconds for review...")
            time.sleep(60)

        context.close()
        print("✓ Session completed cleanly.")


if __name__ == "__main__":
    main()
