#!/usr/bin/env python3
"""
ChatGPT Batch Email Generation Script

Reads pending job posts from PostgreSQL (category='EMAIL_OUTREACH'),
navigates to your dedicated ChatGPT custom GPT conversation in headed Firefox,
and generates personalized outreach emails post-by-post with human pacing.
"""

import sys
import os
import time
import argparse
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.services.firefox_connector import launch_firefox_context
from src.services.chatgpt_service import navigate_to_conversation, send_jd_and_get_email, extract_unsuitable_reason
from src.db import get_pending_email_posts, save_chatgpt_response, update_post_status, update_post_email


def main():
    parser = argparse.ArgumentParser(description="Generate outreach emails for pending job posts via ChatGPT.")
    parser.add_argument("--limit", type=int, default=3, help="Max posts to process in this run (default: 3).")
    parser.add_argument("--all", action="store_true", help="Process all pending posts.")
    parser.add_argument("--delay", type=int, default=10, help="Pause seconds between posts (default: 10s).")
    args = parser.parse_args()

    limit = None if args.all else args.limit

    print("=" * 68)
    print("  ChatGPT Batch Outreach Email Generation (Headed)")
    print("=" * 68)

    # 1. Fetch pending posts from PostgreSQL
    pending_posts = get_pending_email_posts(limit=limit)
    total_pending = len(pending_posts)

    if total_pending == 0:
        print("No pending posts found requiring outreach emails. Everything is up to date!")
        sys.exit(0)

    print(f"  Found {total_pending} pending posts to process in this run.")
    print("=" * 68)
    print()

    # 2. Launch Firefox in headed mode
    with sync_playwright() as playwright:
        print("[1/3] Launching Firefox (headed=True)...")
        context = launch_firefox_context(
            playwright,
            headless=False,
            sync_cookies_domains=["chatgpt.com", "openai.com"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        # 3. Open ChatGPT conversation
        print("[2/3] Opening dedicated ChatGPT custom GPT conversation...")
        navigate_to_conversation(page)

        print(f"\n[3/3] Generating emails for {total_pending} posts...")
        print("-" * 68)

        successful = 0
        failed = 0

        for i, post in enumerate(pending_posts):
            post_id = post["id"]
            author = post["author_name"]
            emails = post.get("contact_emails", [])
            email_dest = emails[0] if emails else "None"
            exp_label = post.get("raw_experience") or post.get("seniority_level") or "N/A"

            print(f"\n[{i+1}/{total_pending}] Processing post by '{author}'")
            print(f"  Recruiter Email: {email_dest}")
            print(f"  Experience:      {exp_label}")
            print(f"  Post Length:     {len(post['full_text'])} chars")

            try:
                update_post_status(post_id, "GENERATING_EMAIL")

                # Send raw JD only
                subject, body = send_jd_and_get_email(page, post["full_text"], max_wait=120)

                if subject == "UNSUITABLE_JD" or (body and ("UNSUITABLE_JD" in body or "❌ not suitable" in body.lower() or "not suitable —" in body.lower())):
                    reason = extract_unsuitable_reason(body)
                    update_post_status(post_id, "REJECTED", rejection_reason=reason)
                    update_post_email(post_id, "UNSUITABLE_JD", body)
                    print(f"  🚫 [Auto-Cancelled] Unsuitable JD for '{author}': {reason}")
                elif body:
                    save_chatgpt_response(post_id, subject, body)
                    successful += 1
                    print(f"  ✓ Saved Email to DB for '{author}'!")
                    print(f"    Subject: {subject}")
                    preview = body[:180].replace("\n", " ")
                    print(f"    Body preview: {preview}...")
                else:
                    print(f"  ✗ Failed: Empty response received for post {post_id}")
                    failed += 1

            except Exception as e:
                print(f"  ✗ Error generating email for post {post_id}: {e}")
                failed += 1

            # Pause between posts for account safety & rate limits
            if i < total_pending - 1:
                sleep_s = args.delay + random.uniform(1.5, 4.5)
                print(f"  Waiting {sleep_s:.1f}s before next post...")
                time.sleep(sleep_s)

        print("\n" + "=" * 68)
        print("  BATCH EXECUTION COMPLETE")
        print(f"  Successfully generated & saved: {successful}")
        print(f"  Failed:                         {failed}")
        print("=" * 68)

        print("\nKeeping Firefox open for 5 seconds...")
        time.sleep(5)
        context.close()
        print("✓ Done.")


if __name__ == "__main__":
    main()
