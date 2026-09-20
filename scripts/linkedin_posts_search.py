#!/usr/bin/env python3
"""
LinkedIn Posts Search & Extraction — Today's Hiring Posts

Navigates to LinkedIn Global Search -> Posts in headed Firefox,
filtered for the past 24 hours. Scans posts from today,
categorizing them into:
1. Email Outreach Posts (Must have a contact email; no comment-bait)
2. Draft / Other Posts (Saved for other cases: application links, portals, comment-bait)
"""

import sys
import os
import re
import time
import json
import random
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Set
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.firefox_connector import launch_firefox_context
from src.experience_extractor import extract_experience
from src.db import init_db, upsert_post, get_existing_post_identifiers, get_setting

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")
LINKEDIN_BASE = "https://www.linkedin.com"

# Patterns indicating a job seeker rather than a recruiter/hiring manager
JOB_SEEKER_PATTERNS = [
    r"#opentowork",
    r"open\s+to\s+work",
    r"actively\s+looking\s+for\s+(a\s+)?(job|role|opportunity|opportunities)",
    r"looking\s+for\s+(a\s+)?new\s+(role|job|opportunity|position)",
    r"seeking\s+(a\s+)?(new\s+)?(job|role|opportunity|position)",
    r"immediate\s+joiner",
    r"hire\s+me",
    r"please\s+(refer|share|support)\s+my\s+resume",
    r"looking\s+for\s+referral",
]

# Patterns indicating comment-bait / comment to get link
COMMENT_BAIT_PATTERNS = [
    r"comment\s+['\"]?(interested|yes|email|below|here|cfbr|fsd)['\"]?",
    r"drop\s+(your\s+)?(email|resume|cv)\s+(in\s+)?(the\s+)?comment",
    r"type\s+['\"]?interested['\"]?",
    r"comment\s+to\s+(apply|get\s+link|receive)",
    r"comment\s+below",
]


def human_sleep(min_s: float = 1.8, max_s: float = 3.5):
    """Sleep for a random duration to mimic human pacing."""
    time.sleep(random.uniform(min_s, max_s))


def human_scroll(page, distance: int = 400, steps: int = 5):
    """Scroll smoothly in small increments with natural jitter."""
    step_dist = distance / steps
    for _ in range(steps):
        jitter = random.randint(-15, 15)
        page.mouse.wheel(0, step_dist + jitter)
        time.sleep(random.uniform(0.08, 0.2))
    human_sleep(1.0, 2.2)


def build_posts_search_url(keywords: str) -> str:
    """Build LinkedIn search URL filtered for Posts posted in the past 24 hours."""
    encoded = quote(keywords)
    return (
        f"{LINKEDIN_BASE}/search/results/content/"
        f"?keywords={encoded}"
        f"&origin=GLOBAL_SEARCH_HEADER"
        f"&sortBy=%22date_posted%22"
        f"&datePosted=%22past-24h%22"
    )


def is_job_seeker_post(text: str) -> bool:
    """Detect if the post author is seeking a job."""
    lower_text = text.lower()
    return any(re.search(p, lower_text) for p in JOB_SEEKER_PATTERNS)


def is_comment_bait_post(text: str) -> bool:
    """Detect if the post asks users to comment to apply or receive details."""
    lower_text = text.lower()
    return any(re.search(p, lower_text) for p in COMMENT_BAIT_PATTERNS)


def is_posted_since_midnight(post_date: str, now: Optional[datetime] = None) -> Tuple[bool, float]:
    """
    Determine whether a post timestamp falls between today's 00:00 midnight and current time.
    Returns (is_since_midnight, hours_ago).
    """
    if not post_date:
        return True, 0.0

    if now is None:
        now = datetime.now()

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hours_since_midnight = (now - midnight).total_seconds() / 3600.0

    # Strip edit and privacy indicators e.g. "12h • Edited", "3h · Visible to anyone"
    clean = re.split(r"[•·]", post_date.strip().lower())[0].strip()

    if clean in ["just now", "now"]:
        return True, 0.0

    # Minutes: e.g. "5m", "45m", "15 min"
    m_match = re.match(r"^(\d+)\s*(?:m|min|minute|minutes)$", clean)
    if m_match:
        hours_ago = float(m_match.group(1)) / 60.0
        return hours_ago <= (hours_since_midnight + 0.5), hours_ago

    # Hours: e.g. "1h", "6h", "16h", "2 hr"
    h_match = re.match(r"^(\d+)\s*(?:h|hr|hour|hours)$", clean)
    if h_match:
        hours_ago = float(h_match.group(1))
        return hours_ago <= (hours_since_midnight + 0.5), hours_ago

    # Days, weeks, months, years: older than today 00:00
    d_match = re.match(r"^(\d+)\s*(?:d|day|days)$", clean)
    if d_match:
        return False, float(d_match.group(1)) * 24.0

    w_match = re.match(r"^(\d+)\s*(?:w|wk|week|weeks)$", clean)
    if w_match:
        return False, float(w_match.group(1)) * 168.0

    mo_match = re.match(r"^(\d+)\s*(?:mo|month|months)$", clean)
    if mo_match:
        return False, float(mo_match.group(1)) * 720.0

    return True, 0.0


def is_posted_today(post_date: str) -> bool:
    """Check if the post timestamp indicates it was posted since today's 00:00 midnight."""
    is_since_mid, _ = is_posted_since_midnight(post_date)
    return is_since_mid


def extract_emails(text: str) -> list[str]:
    """Extract valid email addresses from text."""
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(email_regex, text)
    seen = set()
    cleaned = []
    for email in matches:
        low = email.lower()
        if low not in seen:
            seen.add(low)
            cleaned.append(email)
    return cleaned


def extract_post_from_card(page, card_element, index: int = 0) -> dict:
    """Extract structured details from a LinkedIn post card."""
    card_text = card_element.inner_text().strip()

    # 1. Author Name & Profile Link
    author_links = card_element.locator('a[href*="/in/"]')
    author_name = ""
    author_profile = ""
    for i in range(author_links.count()):
        al = author_links.nth(i)
        txt = al.inner_text().strip()
        if txt and not author_name:
            author_name = txt.split("\n")[0].split("•")[0].strip()
            author_profile = al.get_attribute("href") or ""
            if "?" in author_profile:
                author_profile = author_profile.split("?")[0]

    # 2. Author Headline & Timestamp
    author_headline = ""
    post_date = ""
    lines = [line.strip() for line in card_text.split("\n") if line.strip()]

    for line in lines[:10]:
        if re.match(r"^\d+[hdmy]\b", line):
            post_date = line.split("•")[0].strip()
        elif (
            not author_headline
            and author_name
            and line != "Feed post"
            and author_name not in line
            and "Follow" not in line
            and not re.search(r"^[•·]?\s*(1st|2nd|3rd\+?)$", line)
            and not re.match(r"^\d+[hdmy]\b", line)
        ):
            author_headline = line

    # 3. Clean Post Body
    body_lines = []
    capture = False
    for line in lines:
        if "Follow" in line:
            capture = True
            continue
        if capture:
            if re.match(r"^\d+$", line) and len(body_lines) > 3:
                break
            body_lines.append(line)

    post_body = "\n".join(body_lines) if body_lines else card_text

    # 4. Extract Emails & External URLs
    emails = extract_emails(post_body)
    url_regex = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    found_urls = re.findall(url_regex, post_body)
    external_links = [u for u in found_urls if "linkedin.com" not in u]

    # 5. Extract Direct Post URL via Action Menu
    post_url = ""
    control_btn = card_element.locator('button[aria-label*="control menu"]').first
    if control_btn.count() > 0:
        try:
            control_btn.click()
            human_sleep(0.3, 0.6)
            copy_item = page.locator('text="Copy link to post"').first
            if copy_item.count() > 0 and copy_item.is_visible():
                copy_item.click()
                human_sleep(0.4, 0.7)
                res = subprocess.run(["pbpaste"], capture_output=True, text=True)
                copied = res.stdout.strip()
                if "http" in copied:
                    post_url = copied
        except Exception:
            pass

    if not post_url:
        activity_links = card_element.locator('a[href*="/feed/update/urn:li:activity:"]')
        if activity_links.count() > 0:
            post_url = activity_links.first.get_attribute("href") or ""

    exp = extract_experience(post_body)
    is_since_mid, hours_ago = is_posted_since_midnight(post_date)

    return {
        "index": index + 1,
        "author_name": author_name,
        "author_headline": author_headline,
        "author_profile": author_profile,
        "post_date": post_date,
        "post_url": post_url,
        "full_text": post_body,
        "detected_emails": emails,
        "detected_links": external_links,
        "experience": exp,
        "is_job_seeker": is_job_seeker_post(post_body),
        "is_comment_bait": is_comment_bait_post(post_body),
        "is_today": is_since_mid,
        "hours_ago": hours_ago,
    }


def main():
    # Initialize PostgreSQL table & settings
    init_db()

    # Load search keyword dynamically from database settings
    db_query = get_setting("search_query")
    query = (db_query or "Full stack developer").strip()
    search_url = build_posts_search_url(query)

    with sync_playwright() as playwright:
        print("[1/4] Launching Firefox (headed=True, human-like)...")
        context = launch_firefox_context(
            playwright,
            headless=False,
            sync_cookies_domains=["linkedin.com"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        print("[2/4] Navigating to LinkedIn Posts Search (Past 24h)...")
        page.goto(search_url, wait_until="commit", timeout=30000)
        human_sleep(3.5, 5.0)

        print(f"  Page Title: {page.title()}")

        # Check for Security Checkpoint / CAPTCHA
        captcha = page.locator("input#captcha-internal, iframe[title*='challenge'], #checkpointSubmitButton")
        if captcha.count() > 0 and captcha.first.is_visible():
            print("\n" + "!" * 60)
            print("  SECURITY CHALLENGE / CAPTCHA DETECTED!")
            print("  Please complete the challenge in the open browser window.")
            print("!" * 60 + "\n")
            page.wait_for_timeout(60000)

        # Verify login
        login_form = page.locator("form.login__form, input[name='session_key']")
        if login_form.count() > 0 and login_form.first.is_visible():
            print("✗ Not logged in to LinkedIn!")
            context.close()
            sys.exit(1)

        print("[3/4] Scanning feed posts...")
        page.wait_for_selector('[data-testid="lazy-column"]', timeout=20000)
        lazy_col = page.locator('[data-testid="lazy-column"]')

        # Preload existing identifiers from DB to skip already added posts
        existing_identifiers = get_existing_post_identifiers()
        print(f"  [DB Deduplication] Preloaded {len(existing_identifiers)} existing post signatures/URLs from database.")

        email_posts = []
        draft_posts = []
        processed_snippets = set()
        skipped_existing_count = 0
        consecutive_older_posts = 0

        # Human-like scrolling to collect all posts today from 00:00 midnight until now
        max_scroll_cycles = 60
        consecutive_no_new = 0
        total_scanned_count = 0

        for cycle in range(max_scroll_cycles):
            cards = lazy_col.locator('> div')
            total_cards = cards.count()

            print(f"  [Cycle {cycle+1}/{max_scroll_cycles}] Currently loaded cards: {total_cards}")

            for i in range(total_cards):
                card = cards.nth(i)
                if card.locator('a[href*="/in/"]').count() == 0:
                    continue

                card_text = card.inner_text().strip()
                if len(card_text) < 80:
                    continue

                # Snippet for in-session deduplication
                snippet = card_text[:120]
                if snippet in processed_snippets:
                    continue
                processed_snippets.add(snippet)
                total_scanned_count += 1

                data = extract_post_from_card(page, card, index=len(email_posts) + len(draft_posts))

                # Check if post is from today (00:00 midnight until now)
                if not data["is_today"]:
                    consecutive_older_posts += 1
                    print(f"    -> Post older than today 00:00 ({data['post_date']}, ~{data['hours_ago']:.1f}h ago). Count: {consecutive_older_posts}/2")
                    if consecutive_older_posts >= 2:
                        print(f"    -> Reached 2 consecutive posts older than today 00:00; stopping feed scan.")
                        consecutive_no_new = 999
                        break
                    continue
                else:
                    consecutive_older_posts = 0

                # Discard job seekers (#OpenToWork)
                if data["is_job_seeker"]:
                    print(f"    [Skipped] Job-seeker post by '{data['author_name']}'")
                    continue

                # Check if already added to database (URL or signature match)
                url_raw = data.get("post_url", "").strip()
                url_clean = url_raw.split("?")[0].rstrip("/") if url_raw else ""
                author_clean = data.get("author_name", "").strip().lower()
                text_clean = data.get("full_text", "").strip()[:60].lower()
                sig = f"{author_clean}:{text_clean}"

                is_duplicate = False
                if url_clean and url_clean in existing_identifiers:
                    is_duplicate = True
                elif url_raw and url_raw in existing_identifiers:
                    is_duplicate = True
                elif author_clean and text_clean and sig in existing_identifiers:
                    is_duplicate = True

                if is_duplicate:
                    skipped_existing_count += 1
                    print(f"    [Skipped - Already Added] '{data['author_name']}' ({data['post_date']}) already in database.")
                    continue

                # Experience string for logging
                exp_info = data["experience"]
                exp_label = exp_info["raw_text"] if exp_info["raw_text"] else exp_info["seniority_level"]

                # Categorize: Email Hiring Post vs Draft Post
                if data["detected_emails"] and not data["is_comment_bait"]:
                    data["category"] = "EMAIL_OUTREACH"
                    email_posts.append(data)
                    print(f"    ✓ [EMAIL OUTREACH] {data['author_name']} | Exp: {exp_label} | Emails: {data['detected_emails']} | Time: {data['post_date']}")
                else:
                    data["category"] = "DRAFT_PORTAL"
                    draft_posts.append(data)
                    reason = "No email (apply link / portal)" if not data["detected_emails"] else "Comment-to-apply bait"
                    print(f"    📋 [SAVED AS DRAFT] {data['author_name']} | Exp: {exp_label} | Reason: {reason} | Time: {data['post_date']}")

                # Persist to PostgreSQL (skip_if_exists=True ensures zero overwriting)
                try:
                    post_id, inserted = upsert_post(data, skip_if_exists=True)
                    if inserted:
                        if url_clean:
                            existing_identifiers.add(url_clean)
                        if url_raw:
                            existing_identifiers.add(url_raw)
                        if author_clean and text_clean:
                            existing_identifiers.add(sig)
                except Exception as e:
                    print(f"    (Warning: DB save error: {e})")

            if consecutive_no_new >= 999:
                break

            # Human-paced smooth scroll
            human_scroll(page, distance=random.randint(400, 650), steps=5)
            human_sleep(1.8, 3.0)

        print("\n[4/4] EXTRACTION SUMMARY:")
        print("=" * 68)
        print(f"  Total Today's New Posts Added:    {len(email_posts) + len(draft_posts)}")
        print(f"  - Direct Email Outreach Added:    {len(email_posts)}")
        print(f"  - Draft / Portal Posts Added:     {len(draft_posts)}")
        print(f"  - Previously Added (Skipped):     {skipped_existing_count}")
        print("=" * 68)

        total_new = len(email_posts) + len(draft_posts)
        crawl_stats = {
            "total_crawled": max(total_scanned_count, total_new + skipped_existing_count),
            "newly_added": total_new,
            "new_email_outreach": len(email_posts),
            "new_draft_portal": len(draft_posts),
            "skipped_already_added": skipped_existing_count,
            "skipped_other": max(0, total_scanned_count - total_new - skipped_existing_count)
        }
        print(f"__CRAWL_STATS__: {json.dumps(crawl_stats)}")

        # Save primary email outreach posts
        email_json_path = os.path.join(ARTIFACT_DIR, "scratch", "email_hiring_posts_today.json")
        os.makedirs(os.path.dirname(email_json_path), exist_ok=True)
        with open(email_json_path, "w") as f:
            json.dump(email_posts, f, indent=2)
        print(f"\n  ✓ Saved Email Outreach Posts to: {email_json_path}")

        # Save draft / portal posts
        draft_json_path = os.path.join(ARTIFACT_DIR, "scratch", "draft_other_posts_today.json")
        with open(draft_json_path, "w") as f:
            json.dump(draft_posts, f, indent=2)
        print(f"  ✓ Saved Draft / Other Posts to:   {draft_json_path}")

        # Save screenshot
        shot_path = os.path.join(ARTIFACT_DIR, "scratch", "linkedin_posts_today_batch.png")
        page.screenshot(path=shot_path, full_page=False)
        print(f"  ✓ Saved Screenshot to:            {shot_path}")

        print("\nKeeping Firefox open for 5 seconds...")
        human_sleep(4.0, 5.0)

        context.close()
        print("✓ Done.")


if __name__ == "__main__":
    main()
