#!/usr/bin/env python3
"""
LinkedIn Job Search & Easy Apply Crawler
(scripts/linkedin_job_search.py)

Standalone CLI and subprocess runner for autonomous LinkedIn Job Search
with Easy Apply (f_AL=true) filtering, database ingestion into category='EASY_APPLY',
and questionnaire detection for screening.
"""

import sys
import os
import re
import time
import json
import random
import argparse
import hashlib
from typing import Optional, Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.services.firefox_connector import launch_firefox_context
from src.services.experience_extractor import extract_experience
from src.services.easy_apply_service import (
    build_easy_apply_search_url,
    extract_job_card_metadata,
    execute_easy_apply,
    human_sleep,
)
from src.db.posts import upsert_post, update_post_status
from src.db.settings import get_setting
from src.config import load_config

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
LINKEDIN_BASE = "https://www.linkedin.com"


def parse_args():
    parser = argparse.ArgumentParser(description="LinkedIn Easy Apply Job Crawler")
    parser.add_argument("--query", "-q", default=None, help="Job title or keywords")
    parser.add_argument("--location", "-l", default=None, help="Target location")
    parser.add_argument("--time-filter", "-t", default=None, help="Time filter: 24h, week, month, all")
    parser.add_argument("--max-jobs", "-m", type=int, default=None, help="Max jobs to process")
    parser.add_argument("--headless", action="store_true", default=None, help="Run headless")
    parser.add_argument("--headed", dest="headless", action="store_false", help="Run headed")
    parser.add_argument("--dry-run", action="store_true", help="Scrape without submitting applications")
    return parser.parse_args()


def scroll_job_list(page, target_count: int = 25):
    """Scroll the job list container to load occluded job cards."""
    for _ in range(8):
        page.evaluate("""() => {
            const el = document.querySelector('.scaffold-layout__list-container') ||
                       document.querySelector('.jobs-search-results-list');
            if (el) el.scrollTop += 650;
            else window.scrollBy(0, 650);
        }""")
        page.wait_for_timeout(800)


def main():
    args = parse_args()
    config = load_config()

    # Priority: CLI argument > Env Var > DB Setting > Default
    query = (
        args.query
        or os.environ.get("SCRAPER_SEARCH_QUERY")
        or get_setting("search_query", "Full Stack Developer")
        or "Full Stack Developer"
    ).strip()

    location = (
        args.location
        or os.environ.get("SCRAPER_LOCATION")
        or get_setting("search_location", "India")
        or "India"
    ).strip()

    time_filter = (
        args.time_filter
        or os.environ.get("SCRAPER_TIME_FILTER")
        or "24h"
    ).strip()

    limit_str = os.environ.get("SCRAPER_LIMIT") or "20"
    try:
        max_jobs = args.max_jobs or int(limit_str)
    except Exception:
        max_jobs = 20

    is_headless = args.headless if args.headless is not None else config.get("headless", True)
    resume_path = config.get("resume_path", "")

    search_url = build_easy_apply_search_url(query, location, time_filter)

    print("=" * 66)
    print("  LinkedIn Job Portal — Easy Apply Autonomous Crawler")
    print("=" * 66)
    print(f"  Keywords:    {query}")
    print(f"  Location:    {location}")
    print(f"  Filter:      {time_filter}")
    print(f"  Max Jobs:    {max_jobs}")
    print(f"  Headless:    {is_headless}")
    print(f"  Search URL:  {search_url}")
    print("=" * 66)
    print()

    discovered_count = 0
    applied_count = 0
    questionnaire_count = 0
    skipped_count = 0

    with sync_playwright() as playwright:
        print("[1/4] Launching Firefox context with persistent cookies...")
        context = launch_firefox_context(
            playwright,
            headless=is_headless,
            sync_cookies_domains=["linkedin.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("[2/4] Navigating to LinkedIn Job Portal search...")
        page.goto(search_url, wait_until="commit", timeout=35000)
        page.wait_for_timeout(5000)

        # Login check
        if page.locator("form.login__form, input[name='session_key']").count() > 0:
            print("❌ Error: Not logged in to LinkedIn. Please log in via Connected Services.")
            context.close()
            sys.exit(1)
        print("  ✓ Logged in to LinkedIn")

        print("[3/4] Scrolling and extracting Easy Apply job cards...")
        card_selectors = [
            "[data-occludable-job-id]",
            "li.jobs-search-results__list-item",
            "div.job-card-container",
            "div.base-card",
            "div[data-job-id]",
        ]
        combined_selector = ", ".join(card_selectors)

        try:
            page.wait_for_selector(combined_selector, timeout=12000)
        except Exception:
            pass

        scroll_job_list(page, target_count=max_jobs)
        page.wait_for_timeout(2000)

        cards = page.locator(combined_selector)
        total_found = cards.count()
        print(f"  ✓ Found {total_found} visible job cards.")

        if total_found == 0:
            diag_path = os.path.join(ARTIFACT_DIR, "scratch", "easy_apply_zero_cards.png")
            os.makedirs(os.path.dirname(diag_path), exist_ok=True)
            page.screenshot(path=diag_path)
            print(f"  ⚠️ No job cards loaded on this search page. Diagnostic screenshot saved to: {diag_path}")
            context.close()
            sys.exit(0)

        seen_job_ids = set()
        extracted_jobs = []
        for i in range(total_found):
            if len(extracted_jobs) >= max_jobs:
                break
            card = cards.nth(i)
            meta = extract_job_card_metadata(card)
            jid = meta.get("job_id") or meta.get("url")
            if not jid or jid in seen_job_ids:
                continue
            if meta["title"] and meta["url"]:
                seen_job_ids.add(jid)
                extracted_jobs.append(meta)

        print(f"\n[4/4] Processing {len(extracted_jobs)} unique Easy Apply listings...")

        for idx, job in enumerate(extracted_jobs, start=1):
            title = job["title"]
            company = job["company"]
            loc = job["location"] or location
            job_url = job["url"]
            job_id = job.get("job_id") or hashlib.sha256(job_url.encode()).hexdigest()[:12]

            print(f"\n[{idx}/{len(extracted_jobs)}] {title} @ {company}")
            print(f"  Location: {loc} | URL: {job_url}")

            # Click card or navigate to load full details
            full_text = ""
            try:
                card_link = page.locator(f"a[href*='{job_id}']").first if job_id else None
                if card_link and card_link.count() > 0:
                    card_link.click()
                    page.wait_for_timeout(1800)

                desc_el = page.locator(".jobs-description-content__text, .jobs-box__html-content, article.jobs-description__container").first
                if desc_el.count() > 0:
                    full_text = desc_el.inner_text().strip()
            except Exception:
                pass

            if not full_text:
                full_text = f"Role: {title}\nCompany: {company}\nLocation: {loc}\nDirect Application Link: {job_url}"

            # Extract experience
            exp_info = extract_experience(full_text)
            min_exp = exp_info.get("min_experience")
            max_exp = exp_info.get("max_experience")
            raw_exp = exp_info.get("raw_experience")
            is_fresher = exp_info.get("is_fresher", False)

            post_id = f"easy_apply_{job_id}"
            post_record = {
                "id": post_id,
                "post_url": job_url,
                "author_name": company,
                "author_headline": title,
                "location": loc,
                "full_text": full_text,
                "min_experience": min_exp,
                "max_experience": max_exp,
                "raw_experience": raw_exp,
                "is_fresher": is_fresher,
                "category": "EASY_APPLY",
                "status": "DISCOVERED",
            }
            db_post_id, was_created = upsert_post(post_record)
            if db_post_id:
                post_id = db_post_id
            discovered_count += 1

            if args.dry_run:
                print("  ℹ️ [Dry Run] Ingested job as DISCOVERED without applying.")
                continue

            # Attempt Easy Apply submission
            status, detail = execute_easy_apply(page, job_url, resume_path, logger=print)

            if status == "APPLIED":
                update_post_status(post_id, "APPLIED")
                applied_count += 1
                print("  🎉 Status: APPLIED")
            elif status == "REQUIRES_QUESTIONNAIRE":
                update_post_status(post_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=detail)
                questionnaire_count += 1
                print(f"  📌 Saved for Screening (REQUIRES_QUESTIONNAIRE): {detail}")
            else:
                update_post_status(post_id, "DISCOVERED", rejection_reason=detail)
                skipped_count += 1
                print(f"  ℹ️ Ready in queue (DISCOVERED): {detail}")

            if idx < len(extracted_jobs):
                human_sleep(3.5, 7.0)

        # Print summary
        print("\n" + "=" * 66)
        print("  CRAWLER SUMMARY:")
        print("=" * 66)
        print(f"  Total Ingested:             {discovered_count}")
        print(f"  Successfully Applied:       {applied_count}")
        print(f"  Saved for Screening (Q's):  {questionnaire_count}")
        print(f"  Ready in Queue:             {skipped_count}")
        print("=" * 66)

        crawl_stats = {
            "total_crawled": discovered_count,
            "newly_added": discovered_count,
            "applied": applied_count,
            "requires_questionnaire": questionnaire_count,
            "ready_in_queue": skipped_count,
        }
        print(f"__CRAWL_STATS__: {json.dumps(crawl_stats)}")

        context.close()
        print("✓ Done.")


if __name__ == "__main__":
    main()
