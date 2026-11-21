#!/usr/bin/env python3
"""
Batch Indeed Apply Test Runner
(scripts/test_indeed_apply_10.py)

Applies to 10 sample Indeed openings one by one:
- Verifies onsite Easy Apply vs External Apply ('Apply on company site').
- Marks external applications as NOT_FOUND ('External application required').
- Steps through SmartApply wizard (Resume selection, Contact info, Screening questions, Review).
- Looks up answers in the Question Bank for screening questions.
- BLOCKS and pauses application if any questions need answers, saving them to Question Bank (REQUIRES_QUESTIONNAIRE).
- Submits applications when all questions are answered or no questions are asked (APPLIED).
"""

import sys
import os
import time
import argparse
from typing import List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.services.firefox_connector import launch_firefox_context
from src.services.indeed_apply_service import execute_indeed_apply
from src.db.posts import get_post_by_id
from src.db.connection import get_connection
import psycopg2.extras


def fetch_ten_indeed_job_ids() -> List[str]:
    """Retrieve 10 Indeed jobs from the database (prioritizing DISCOVERED)."""
    conn = get_connection()
    ids = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT id, author_headline, author_name, status
                FROM posts
                WHERE category = 'INDEED_APPLY'
                ORDER BY
                    CASE WHEN status = 'DISCOVERED' THEN 0 ELSE 1 END,
                    created_at DESC
                LIMIT 10;
            """)
            rows = cur.fetchall()
            for r in rows:
                ids.append(r["id"])
    finally:
        conn.close()
    return ids


def main():
    parser = argparse.ArgumentParser(description="Test Indeed Apply automation on 10 sample openings.")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (default: False/headed)")
    parser.add_argument("--delay", type=float, default=6.0, help="Delay between job runs in seconds")
    parser.add_argument("--post-id", type=str, default="", help="Optional single post ID to test")
    args = parser.parse_args()

    post_ids = [args.post_id] if args.post_id else fetch_ten_indeed_job_ids()
    if not post_ids:
        print("❌ No Indeed job posts found in the database. Please run an Indeed discovery crawl first.")
        sys.exit(1)

    print("=" * 68)
    print("🚀 INDEED EASY APPLY TEST RUNNER — 10 POST SAMPLE")
    print(f"  Total Openings to Process: {len(post_ids)}")
    print(f"  Browser Mode:              {'Headless' if args.headless else 'Headed (Visible Window)'}")
    print(f"  Step Delay:                {args.delay}s")
    print("=" * 68)

    applied_count = 0
    questionnaire_count = 0
    not_found_count = 0
    failed_count = 0

    with sync_playwright() as playwright:
        print("\n[Init] Launching Firefox context...")
        context = launch_firefox_context(
            playwright,
            headless=args.headless,
            sync_cookies_domains=["indeed.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        for idx, post_id in enumerate(post_ids, start=1):
            post = get_post_by_id(post_id)
            if not post:
                print(f"[{idx}/{len(post_ids)}] Post #{post_id} not found in DB. Skipping.")
                continue

            title = post.get("author_headline") or "Software Engineer"
            company = post.get("author_name") or "Company"
            post_url = post.get("post_url") or ""

            print(f"\n{'='*68}")
            print(f"[{idx}/{len(post_ids)}] Processing: {title} @ {company}")
            print(f"  Post URL: {post_url}")
            print(f"{'='*68}")

            try:
                page.goto(post_url, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(2000)

                result = execute_indeed_apply(
                    page,
                    post_data=post,
                    logger=print,
                )

                st = result.get("status")
                if st == "APPLIED":
                    applied_count += 1
                    print(f"  🎉 [Outcome] Successfully Applied!")
                elif st == "REQUIRES_QUESTIONNAIRE":
                    questionnaire_count += 1
                    qs = result.get("questions") or []
                    print(f"  📋 [Outcome] Requires Questionnaire: {len(qs)} question(s) need answers.")
                elif st == "NOT_FOUND":
                    not_found_count += 1
                    print(f"  🚫 [Outcome] External ATS / Closed: {result.get('detail')}")
                else:
                    failed_count += 1
                    print(f"  ⚠️ [Outcome] Status: {st} ({result.get('detail')})")

            except Exception as e:
                print(f"  ❌ Error applying to {title}: {e}")
                failed_count += 1

            if idx < len(post_ids):
                print(f"  ⏳ Waiting {args.delay}s before next application...")
                time.sleep(args.delay)

        context.close()

    print("\n" + "=" * 68)
    print("📊 BATCH TEST EXECUTION SUMMARY:")
    print("=" * 68)
    print(f"  Total Jobs Processed:        {len(post_ids)}")
    print(f"  Successfully Applied:        {applied_count}")
    print(f"  Requires Questionnaire:     {questionnaire_count} (Blocked for answers & saved to Q-Bank)")
    print(f"  External ATS / Not Found:    {not_found_count} (Marked NOT_FOUND)")
    print(f"  Other / Incomplete:          {failed_count}")
    print("=" * 68)


if __name__ == "__main__":
    main()
