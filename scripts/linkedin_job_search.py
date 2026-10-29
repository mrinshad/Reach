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
    extract_all_search_job_cards,
    ensure_search_location,
    wait_for_job_cards_loaded,
    execute_easy_apply,
    human_sleep,
)
from src.db.posts import upsert_post, update_post_status, get_dismissed_role_titles, check_title_previously_dismissed
from src.db.settings import get_setting
from src.config import load_config

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
LINKEDIN_BASE = "https://www.linkedin.com"


def parse_args():
    parser = argparse.ArgumentParser(description="LinkedIn Easy Apply Job Crawler & Collector")
    parser.add_argument("--query", "-q", default=None, help="Job title or keywords")
    parser.add_argument("--location", "-l", default=None, help="Target location")
    parser.add_argument("--time-filter", "-t", default=None, help="Time filter: 24h, week, month, all")
    parser.add_argument("--max-jobs", "-m", type=int, default=None, help="Max jobs to process")
    parser.add_argument("--cycles", "-c", type=int, default=None, help="Number of scroll discovery cycles (default: 8)")
    parser.add_argument("--pacing", "-p", default="safe", choices=["safe", "slow", "standard"], help="Delay between job submissions")
    parser.add_argument("--headless", action="store_true", default=None, help="Run headless")
    parser.add_argument("--headed", dest="headless", action="store_false", help="Run headed")
    parser.add_argument("--auto-apply", action="store_true", default=False, help="Automatically submit applications during crawl (default: False, collect only for review)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape without submitting applications")
    return parser.parse_args()


def scroll_job_list(page, cycles: int = 8):
    """Scroll the job list container to load occluded job cards based on discovery cycles."""
    for c in range(cycles):
        print(f"  [Cycle {c+1}/{cycles}] Scrolling job listings container...")
        page.evaluate("""() => {
            const el = document.querySelector('div[data-testid="lazy-column"]') ||
                       document.querySelector('.scaffold-layout__list-container') ||
                       document.querySelector('.jobs-search-results-list');
            if (el) el.scrollTop += 500;
            else window.scrollBy(0, 500);
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

    limit_str = os.environ.get("SCRAPER_LIMIT")
    cycles_env = os.environ.get("SCRAPER_CYCLES")

    try:
        cycles = args.cycles if args.cycles is not None else (int(cycles_env) if cycles_env else 8)
    except Exception:
        cycles = 8

    try:
        if args.max_jobs is not None:
            max_jobs = args.max_jobs
        elif limit_str:
            max_jobs = int(limit_str)
        elif cycles and cycles > 10:
            max_jobs = cycles * 5
        else:
            max_jobs = 50
    except Exception:
        max_jobs = 50

    pacing = (args.pacing or os.environ.get("SCRAPER_PACING") or "safe").lower()

    auto_apply = args.auto_apply or (os.environ.get("SCRAPER_AUTO_APPLY", "").lower() in ("true", "1", "yes"))
    is_headless = args.headless if args.headless is not None else config.get("headless", True)
    resume_path = config.get("resume_path", "")

    search_url = build_easy_apply_search_url(query, location, time_filter)

    print("=" * 66)
    if auto_apply:
        print("  LinkedIn Job Portal — Easy Apply Autonomous Crawler")
    else:
        print("  LinkedIn Job Portal — Easy Apply Discovery & Collector")
    print("=" * 66)
    print(f"  Keywords:    {query}")
    print(f"  Location:    {location}")
    print(f"  Filter:      {time_filter}")
    print(f"  Max Jobs:    {max_jobs}")
    print(f"  Cycles:      {cycles}")
    print(f"  Mode:        {'Auto-Apply' if auto_apply else 'Collect Only (Ready to Apply)'}")
    if auto_apply:
        print(f"  Pacing:      {pacing}")
    print(f"  Headless:    {is_headless}")
    print(f"  Search URL:  {search_url}")
    print("=" * 66)
    print()

    discovered_count = 0
    applied_count = 0
    questionnaire_count = 0
    closed_count = 0
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
        page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        # Login check
        if page.locator("form.login__form, input[name='session_key']").count() > 0:
            print("❌ Error: Not logged in to LinkedIn. Please log in via Connected Services.")
            context.close()
            sys.exit(1)
        print("  ✓ Logged in to LinkedIn")

        # Verify and lock in requested location
        ensure_search_location(page, location, logger=print)

        # Wait for job cards to load (replacing skeleton placeholder)
        print("  Waiting for job cards to load...")
        wait_for_job_cards_loaded(page, timeout_ms=15000, logger=print)

        # Cumulative discovery across cycles & pagination
        print(f"[3/4] Discovering Easy Apply job cards ({cycles} cycles requested, target: {max_jobs} jobs)...")
        collected_jobs_map = {}
        for c in extract_all_search_job_cards(page, max_jobs=max_jobs):
            collected_jobs_map[c["job_id"]] = c

        page_num = 0
        no_new_cycles = 0
        cycle_idx = 0

        while cycle_idx < cycles and len(collected_jobs_map) < max_jobs:
            cycle_idx += 1
            print(f"  [Cycle {cycle_idx}/{cycles}] Scrolling/discovering cards ({len(collected_jobs_map)}/{max_jobs} collected)...")
            page.evaluate("""() => {
                const el = document.querySelector('div[data-testid="lazy-column"]') ||
                           document.querySelector('.scaffold-layout__list-container') ||
                           document.querySelector('.jobs-search-results-list');
                if (el) el.scrollTop += 600;
                else window.scrollBy(0, 600);
            }""")
            page.wait_for_timeout(800)

            prev_count = len(collected_jobs_map)
            for c in extract_all_search_job_cards(page, max_jobs=max_jobs):
                collected_jobs_map[c["job_id"]] = c

            if len(collected_jobs_map) >= max_jobs:
                break

            if len(collected_jobs_map) == prev_count:
                no_new_cycles += 1
                if no_new_cycles >= 2:
                    page_num += 1
                    start_offset = page_num * 25
                    next_url = f"{search_url}&start={start_offset}"
                    print(f"  📄 Advancing to LinkedIn search results page {page_num + 1} (start={start_offset})...")
                    try:
                        page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(2000)
                        wait_for_job_cards_loaded(page, timeout_ms=8000, logger=print)
                        
                        new_page_cards = extract_all_search_job_cards(page, max_jobs=max_jobs)
                        before_add = len(collected_jobs_map)
                        for c in new_page_cards:
                            collected_jobs_map[c["job_id"]] = c
                        
                        if len(collected_jobs_map) == before_add:
                            print("  ℹ️ No more jobs found on subsequent pages; reached end of search results.")
                            break
                        no_new_cycles = 0
                    except Exception as e:
                        print(f"  ⚠️ Pagination error: {e}")
                        break
            else:
                no_new_cycles = 0

        extracted_jobs = list(collected_jobs_map.values())[:max_jobs]
        total_found = len(extracted_jobs)
        print(f"  ✓ Found {total_found} visible job cards across {page_num + 1} page(s).")

        if total_found == 0:
            diag_path = os.path.join(ARTIFACT_DIR, "scratch", "easy_apply_zero_cards.png")
            os.makedirs(os.path.dirname(diag_path), exist_ok=True)
            page.screenshot(path=diag_path)
            print(f"  ⚠️ No job cards loaded on this search page. Diagnostic screenshot saved to: {diag_path}")
            context.close()
            sys.exit(0)

        print(f"\n[4/4] Processing {len(extracted_jobs)} Easy Apply listings...")
        dismissed_titles = get_dismissed_role_titles()
        auto_dismissed_count = 0

        for idx, job in enumerate(extracted_jobs, start=1):
            title = job["title"]
            company = job["company"]
            loc = job["location"] or location
            job_url = job["url"]
            job_id = job.get("job_id") or hashlib.sha256(job_url.encode()).hexdigest()[:12]

            print(f"\n[{idx}/{len(extracted_jobs)}] {title} @ {company}")
            print(f"  Location: {loc} | URL: {job_url}")

            # Check if this role was previously dismissed by the user
            is_prev_dismissed, dismiss_reason = check_title_previously_dismissed(title, dismissed_titles)
            if is_prev_dismissed:
                post_id = f"easy_apply_{job_id}"
                post_record = {
                    "id": post_id,
                    "post_url": job_url,
                    "author_name": company,
                    "author_headline": title,
                    "location": loc,
                    "full_text": f"Role: {title}\nCompany: {company}\nLocation: {loc}\nDirect Application Link: {job_url}",
                    "category": "EASY_APPLY",
                    "status": "REJECTED",
                    "rejection_reason": dismiss_reason,
                }
                upsert_post(post_record)
                auto_dismissed_count += 1
                print(f"  ✕ {dismiss_reason}")
                continue

            # Click card or navigate to load full details
            full_text = ""
            try:
                card_link = page.locator(f"[componentkey*='{job_id}'], a[href*='{job_id}']").first if job_id else None
                if card_link and card_link.count() > 0:
                    card_link.click(force=True)
                    page.wait_for_timeout(1800)

                desc_text = page.evaluate("""() => {
                    const all = Array.from(document.querySelectorAll('div, h2, h3, section'));
                    const aboutHeader = all.find(el => (el.innerText || '').trim() === 'About the job');
                    if (aboutHeader && aboutHeader.parentElement) {
                        return aboutHeader.parentElement.innerText.replace(/^About the job\\s*/i, '').trim();
                    }
                    const descEl = document.querySelector('.jobs-description-content__text, .jobs-box__html-content, article.jobs-description__container, .jobs-description__content');
                    return descEl ? descEl.innerText.trim() : '';
                }""")
                if desc_text:
                    full_text = desc_text
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

            if not auto_apply or args.dry_run:
                discovered_count += 1
                print(f"  ✓ Saved to queue as Ready to Apply (DISCOVERED)")
                page.wait_for_timeout(random.randint(600, 1200))
                continue

            # Auto-Apply mode requested: attempt Easy Apply submission
            discovered_count += 1
            status, detail = execute_easy_apply(page, job_url, resume_path, logger=print)

            if status == "APPLIED":
                update_post_status(post_id, "APPLIED")
                applied_count += 1
                print("  🎉 Status: APPLIED")
            elif status == "NOT_FOUND":
                update_post_status(post_id, "NOT_FOUND", rejection_reason=detail)
                closed_count += 1
                print(f"  🚫 Status: NOT_FOUND ({detail})")
            elif status == "RATE_LIMITED":
                from src.db.settings import set_setting
                is_daily = "today’s easy apply limit" in detail.lower() or "today's easy apply limit" in detail.lower() or "continue applying tomorrow" in detail.lower()
                if is_daily:
                    import datetime
                    now_dt = datetime.datetime.now()
                    tomorrow_1am = (now_dt + datetime.timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0)
                    paused_until = max(int(tomorrow_1am.timestamp()), int(time.time() + 8 * 3600))
                    clean_detail = (
                        "You reached today’s Easy Apply limit\n\n"
                        "Great effort applying today. We limit Easy Apply submissions to help ensure each application gets the right attention. "
                        "Save this job and continue applying tomorrow. Learn more"
                    )
                    set_setting("easy_apply_paused_until", str(paused_until))
                    set_setting("easy_apply_safeguard_reason", clean_detail)
                    set_setting("easy_apply_limit_type", "daily_limit")
                else:
                    paused_until = int(time.time() + 3600)
                    clean_detail = detail
                    set_setting("easy_apply_paused_until", str(paused_until))
                    set_setting("easy_apply_safeguard_reason", clean_detail)
                    set_setting("easy_apply_limit_type", "fast_pace")
                print(f"  🚨 {clean_detail}")
                print("  🛑 LinkedIn limit detected. Halting crawl immediately to protect your account.")
                break
            elif status == "REQUIRES_QUESTIONNAIRE":
                update_post_status(post_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=detail)
                questionnaire_count += 1
                print(f"  📌 Saved for Screening (REQUIRES_QUESTIONNAIRE): {detail}")
            else:
                update_post_status(post_id, "DISCOVERED", rejection_reason=detail)
                skipped_count += 1
                print(f"  ℹ️ Ready in queue (DISCOVERED): {detail}")

            if idx < len(extracted_jobs):
                if pacing == "slow":
                    print("  ⏳ Extra slow pacing safeguard: Pausing 75–120s...")
                    human_sleep(75.0, 120.0)
                elif pacing == "standard":
                    print("  ⏳ Moderate pacing: Pausing 30–45s...")
                    human_sleep(30.0, 45.0)
                else:  # safe (default)
                    print("  ⏳ Safe human pacing safeguard: Pausing 45–75s...")
                    human_sleep(45.0, 75.0)

        # Print summary
        print("\n" + "=" * 66)
        if auto_apply:
            print("  CRAWLER SUMMARY:")
            print("=" * 66)
            print(f"  Total Cards Processed:      {len(extracted_jobs)}")
            print(f"  Discovered & Ingested:      {discovered_count}")
            print(f"  Auto-Dismissed (Dismissed): {auto_dismissed_count}")
            print(f"  Successfully Applied:       {applied_count}")
            print(f"  Saved for Screening (Q's):  {questionnaire_count}")
            print(f"  Closed / Not Found:         {closed_count}")
            print(f"  Ready in Queue:             {skipped_count}")
        else:
            print("  JOB COLLECTOR SUMMARY:")
            print("=" * 66)
            print(f"  Total Cards Processed:      {len(extracted_jobs)}")
            print(f"  Saved to Ready Queue:       {discovered_count}")
            print(f"  Auto-Dismissed (Dismissed): {auto_dismissed_count}")
        print("=" * 66)

        crawl_stats = {
            "total_crawled": len(extracted_jobs),
            "newly_added": discovered_count,
            "ready_in_queue": discovered_count,
            "auto_dismissed": auto_dismissed_count,
        }
        if auto_apply:
            crawl_stats.update({
                "applied": applied_count,
                "requires_questionnaire": questionnaire_count,
                "closed": closed_count,
            })
        print(f"__CRAWL_STATS__: {json.dumps(crawl_stats)}")

        context.close()
        print("✓ Done.")


if __name__ == "__main__":
    main()
