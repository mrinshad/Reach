#!/usr/bin/env python3
"""
LinkedIn Job Search — Extract job listings from search results.

Navigates to LinkedIn job search, scrolls to load all visible cards,
and extracts title, company, location, and URL for each listing.
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.services.firefox_connector import launch_firefox_context

ARTIFACT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "artifacts"
)

LINKEDIN_BASE = "https://www.linkedin.com"


def build_search_url(keywords: str, location: str = "India") -> str:
    """Build a LinkedIn job search URL."""
    from urllib.parse import quote
    return (
        f"{LINKEDIN_BASE}/jobs/search/"
        f"?keywords={quote(keywords)}"
        f"&location={quote(location)}"
        f"&f_TPR=r604800"  # Past week
    )


def extract_job_cards(page) -> list[dict]:
    """Extract all visible job card data from the current page."""
    cards = page.locator("[data-occludable-job-id]")
    total = cards.count()
    jobs = []

    for i in range(total):
        card = cards.nth(i)
        job_id = card.evaluate("el => el.getAttribute('data-occludable-job-id') || ''")

        # Title + URL
        title_link = card.locator("a.job-card-container__link")
        title = ""
        href = ""
        if title_link.count() > 0:
            raw_text = title_link.first.inner_text().strip()
            title = raw_text.split('\n')[0].strip()
            href = title_link.first.get_attribute("href") or ""
            if href.startswith("/"):
                href = LINKEDIN_BASE + href

        # Company
        company_el = card.locator(".artdeco-entity-lockup__subtitle")
        company = ""
        if company_el.count() > 0:
            company = company_el.first.inner_text().strip()

        # Location
        location_el = card.locator(".artdeco-entity-lockup__caption")
        location = ""
        if location_el.count() > 0:
            location = location_el.first.inner_text().strip().split('\n')[0].strip()

        if title:
            jobs.append({
                "index": i + 1,
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": href,
            })

    return jobs


def scroll_to_load_all(page, target_count: int = 25):
    """Scroll the job list sidebar to lazy-load all cards."""
    list_container = page.locator("ul.scaffold-layout__list-container, div.jobs-search-results-list")
    if list_container.count() == 0:
        # Fallback: scroll the whole page
        for _ in range(10):
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(800)
        return

    # Scroll inside the list container
    for _ in range(15):
        current = page.locator("[data-occludable-job-id]").count()
        if current >= target_count:
            break
        page.evaluate("""() => {
            const el = document.querySelector('.scaffold-layout__list-container') 
                     || document.querySelector('.jobs-search-results-list');
            if (el) el.scrollTop += 600;
        }""")
        page.wait_for_timeout(800)


def main():
    keywords = "Full stack developer"
    search_url = build_search_url(keywords)

    print("=" * 60)
    print("  LinkedIn Job Search — Extract Listings")
    print("=" * 60)
    print(f"  Keywords: {keywords}")
    print(f"  URL: {search_url}")
    print()

    with sync_playwright() as playwright:
        print("[1/3] Launching Firefox (headed)...")
        context = launch_firefox_context(
            playwright,
            headless=False,
            sync_cookies_domains=["linkedin.com"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        print("[2/3] Navigating to LinkedIn job search...")
        page.goto(search_url, wait_until="commit", timeout=30000)
        page.wait_for_timeout(6000)

        print(f"  Title: {page.title()}")

        # Verify login
        login_form = page.locator("form.login__form, input[name='session_key']")
        if login_form.count() > 0:
            print("✗ Not logged in to LinkedIn!")
            context.close()
            sys.exit(1)
        print("  ✓ Logged in")

        # Scroll to load all cards
        print("  Scrolling to load all job cards...")
        scroll_to_load_all(page, target_count=25)
        page.wait_for_timeout(2000)

        print("[3/3] Extracting job listings...")
        jobs = extract_job_cards(page)
        print(f"  ✓ Extracted {len(jobs)} job listings")

        # Save JSON
        json_path = os.path.join(ARTIFACT_DIR, "scratch", "linkedin_jobs.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(jobs, f, indent=2)
        print(f"  Saved JSON: {json_path}")

        # Screenshot
        screenshot_path = os.path.join(ARTIFACT_DIR, "linkedin_jobs_search.png")
        page.screenshot(path=screenshot_path, full_page=False)
        print(f"  Screenshot saved: {screenshot_path}")

        # Print summary
        print()
        print("=" * 60)
        print(f"  EXTRACTED {len(jobs)} JOB LISTINGS:")
        print("=" * 60)
        for job in jobs:
            print(f"  {job['index']:2d}. {job['title']}")
            print(f"      {job['company']} — {job['location']}")
            print()
        print("=" * 60)

        print("\nKeeping Firefox open for 10 seconds...")
        time.sleep(10)

        context.close()
        print("✓ Done.")


if __name__ == "__main__":
    main()
