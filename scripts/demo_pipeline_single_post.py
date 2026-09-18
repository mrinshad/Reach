#!/usr/bin/env python3
"""
End-to-End Pipeline Demonstration Script

1. Fetches a random pending hiring post from PostgreSQL (database: linkedin_scrapper).
2. Launches headed Firefox (headless=False) so you can watch live.
3. Sends the raw JD to your dedicated ChatGPT custom GPT conversation.
4. Captures the generated cold outreach email and saves it to PostgreSQL.
5. Navigates to Gmail, opens a new compose window.
6. Populates Recipient, Subject, properly formatted Body, and attaches your resume.
7. STOPS and leaves the draft open for your inspection without sending.
"""

import sys
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.firefox_connector import launch_firefox_context
from src.chatgpt_service import navigate_to_conversation, send_jd_and_get_email
from src.gmail_service import navigate_to_gmail, populate_email_draft
from src.db import save_chatgpt_response, get_connection
from src.config import load_config

DEFAULT_RESUME_PATH = load_config().get("resume_path", "resumes/Test_Resume.pdf")
ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")


def get_random_pending_post():
    """Retrieve 1 random post from DB that has an email and needs generation."""
    sql = """
    SELECT * FROM posts
    WHERE category = 'EMAIL_OUTREACH'
      AND generated_body IS NULL
      AND array_length(contact_emails, 1) > 0
    ORDER BY RANDOM()
    LIMIT 1;
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return dict(row) if row else None


def main():
    print("=" * 70)
    print("  LIVE DEMO: Random Post -> ChatGPT -> Gmail Draft (No Auto-Send)")
    print("=" * 70)

    # 1. Fetch random pending post
    post = get_random_pending_post()
    if not post:
        print("✗ No pending posts found in database. All posts already processed!")
        sys.exit(0)

    post_id = post["id"]
    author = post["author_name"]
    recipient = post["contact_emails"][0]
    exp_label = post.get("raw_experience") or post.get("seniority_level") or "N/A"

    print(f"  Selected Post ID:  {post_id}")
    print(f"  Author / Recruiter:{author}")
    print(f"  Recipient Email:   {recipient}")
    print(f"  Experience:        {exp_label}")
    print(f"  Post JD Length:    {len(post['full_text'])} chars")
    print("=" * 70)
    print()

    with sync_playwright() as playwright:
        print("[1/4] Launching Firefox (headed=True)...")
        context = launch_firefox_context(
            playwright,
            headless=False,
            sync_cookies_domains=["chatgpt.com", "openai.com", "google.com", "gmail.com"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        # 2. ChatGPT Interaction
        print("\n[2/4] Navigating to ChatGPT custom GPT conversation...")
        navigate_to_conversation(page)

        print(f"  Sending JD for post by '{author}'...")
        subject, body = send_jd_and_get_email(page, post["full_text"], max_wait=120)

        if not body:
            print("✗ Failed to receive email body from ChatGPT.")
            context.close()
            sys.exit(1)

        print("  ✓ Response received from ChatGPT!")
        print(f"    Subject: {subject}")

        # 3. Save to PostgreSQL
        print("\n[3/4] Saving generated email to PostgreSQL...")
        save_chatgpt_response(post_id, subject, body)
        print(f"  ✓ Database record updated for post {post_id} (status: EMAIL_GENERATED).")

        # 4. Open Gmail & Populate Draft
        print("\n[4/4] Opening Gmail and composing draft (will NOT send)...")
        navigate_to_gmail(page)

        populate_email_draft(
            page=page,
            recipient=recipient,
            subject=subject,
            body=body,
            attachment_path=DEFAULT_RESUME_PATH if os.path.exists(DEFAULT_RESUME_PATH) else None,
        )

        # Screenshot of the draft
        shot_path = os.path.join(ARTIFACT_DIR, "scratch", "demo_gmail_draft_review.png")
        page.screenshot(path=shot_path, full_page=False)
        print(f"  ✓ Saved screenshot to: {shot_path}")

        print("\n" + "=" * 70)
        print("  VERIFICATION CHECKPOINT: DRAFT READY ON YOUR SCREEN")
        print("=" * 70)
        print("  The Firefox window is displaying your newly generated draft.")
        print(f"  - Recipient:  {recipient}")
        print(f"  - Subject:    {subject}")
        print(f"  - Attachment: {DEFAULT_RESUME_PATH if os.path.exists(DEFAULT_RESUME_PATH) else '(None)'}")
        print("  - Policy:     STOPPED — NO EMAIL WAS SENT.")
        print("-" * 70)
        print("  Keeping browser open for 60 seconds so you can inspect...")
        print("=" * 70)

        time.sleep(60)
        context.close()
        print("✓ Demo finished cleanly.")


if __name__ == "__main__":
    main()
