#!/usr/bin/env python3
"""
Infopark Jobs Search & Extraction — Today's Hiring Opportunities

Scrapes job opportunities from https://infopark.in/companies-job:
1. Paginates through listings table (Date of Posting, Job Title, Company, Deadline, Details URL).
2. Checks against database to skip already added jobs in O(1).
3. Navigates to each job's details page to extract:
   - Full Job Description (clean text)
   - Direct company/recruiter contact email(s)
   - Experience requirements (via extract_experience)
   - Application deadline and company profile
4. Persists into PostgreSQL (posts table) with category EMAIL_OUTREACH / DRAFT_PORTAL.
"""

import os
import sys
import re
import ssl
import time
import json
import html
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from src.db import init_db, upsert_post, get_existing_post_identifiers, update_post_status
from src.services.experience_extractor import extract_experience
from src.services.chatgpt_service import clean_and_truncate_reason

INFOPARK_JOBS_URL = "https://infopark.in/companies-job"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
# ---------------------------------------------------------------------------
# Pre-screen Rules — Role-title keyword patterns for known-irrelevant roles.
# (COMMENTED OUT: Retained as reference; all scraped jobs are preserved to
# reach out for opportunities using the candidate's full-stack profile.)
# ---------------------------------------------------------------------------
# PRE_SCREEN_RULES = [
#     ("Marketing role",     ["digital marketing", "performance marketing", "growth marketing",
#                              "marketing executive", "marketing specialist", "marketing manager",
#                              "marketing team lead", "marketing apprenticeship", "marketing intern",
#                              "affiliate marketing", "brand", "content marketing"]),
#     ("SEO role",           ["seo executive", "seo analyst", "seo specialist", "seo manager",
#                              "seo lead", "ai search", "agentic growth", "search engine optimization"]),
#     ("Sales / BD role",    ["business development", "sales development", "inside sales",
#                              "it sales", "sales executive", "sales specialist", "sales manager",
#                              "sales intern", "telecaller", "growth and sales", "sdr"]),
#     ("HR role",            ["hr executive", "hr recruiter", "hr intern", "human resource",
#                              "talent acquisition", "recruitment", "recruiter"]),
#     ("QA / Testing role",  ["qa engineer", "qa lead", "qa automation", "quality assurance",
#                              "qa trainee", "qa intern", "etl tester", "software qa",
#                              "quality control", "qa qc"]),
#     ("Design role",        ["digital designer", "visual designer", "ux writer", "ui designer",
#                              "graphic designer", "product designer"]),
#     ("Content / Writing",  ["content writer", "content writing", "content specialist",
#                              "copywriter", "technical writer", "ux writer"]),
#     ("Finance / Accounts", ["accountant", "accounting", "finance", "sage50", "procurement",
#                              "purchase executive"]),
#     ("Legal role",         ["legal content", "llb", "paralegal", "lawyer"]),
#     ("Non-IT / Ops",       ["hvac", "mechanical engineer", "civil engineer", "gps technician",
#                              "reliability monitoring", "floor manager", "registered nurse",
#                              "nurse", "medical", "healthcare", "nursing"]),
#     ("Support / Helpdesk", ["service desk", "it service desk", "helpdesk", "support engineer",
#                              "customer support"]),
#     ("Odoo / SAP specialist", ["odoo", "sap plm", "sap pdm", "sap consultant",
#                                "dynamics 365", "ms dynamics"]),
#     ("WordPress specialist", ["wordpress developer", "wordpress specialist"]),
#     ("Training / Course ad", ["it freshers", "digital marketing / it freshers",
#                                "shopify & hubspot", "technomaster", "training institute"]),
# ]
#
# def pre_screen_role(title: str, full_jd: str = "") -> Optional[str]:
#     """
#     Check if a job title matches known-irrelevant role categories.
#     Returns a concise rejection reason string if irrelevant, or None if OK to process.
#     Matching is case-insensitive on the job title.
#     """
#     title_lower = title.lower().strip()
#     for reason, keywords in PRE_SCREEN_RULES:
#         for kw in keywords:
#             if kw in title_lower:
#                 return clean_and_truncate_reason(reason)
#     return None


# Create SSL context that allows connecting even with self-signed certificate chains
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def fetch_html(url: str, timeout: int = 15) -> str:
    """Fetch URL content with standard user-agent and SSL handling."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def extract_emails_from_html(html_text: str) -> List[str]:
    """
    Extract valid recruiter/company email addresses from page content.
    Excludes system emails like info@infopark.in and asset false positives.
    """
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found = re.findall(email_regex, html_text)
    valid_emails = []
    seen = set()

    for e in found:
        low = e.lower().strip()
        # Exclude Infopark platform emails and asset extensions
        if low.endswith("infopark.in"):
            continue
        if any(low.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"]):
            continue
        if low not in seen:
            seen.add(low)
            valid_emails.append(e.strip())

    return valid_emails


def clean_html_to_text(raw_html: str) -> str:
    """Convert raw HTML block into clean formatted plain text."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    # Replace line break tags
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?(?:p|div|h\d|li|tr)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Normalize whitespace
    lines = [line.strip() for line in text.split('\n')]
    cleaned = '\n'.join(line for line in lines if line)
    return cleaned.strip()


def parse_job_detail_page(detail_url: str) -> Dict[str, Any]:
    """
    Fetch and parse the Infopark job detail page.
    Extracts JD, company email, company profile link, and deadline.
    """
    detail_html = fetch_html(detail_url)

    # 1. Company Contact Email
    # Try looking specifically in .carer-box or .contact first for recruiter email
    carer_box_match = re.search(r'<div class="carer-box">(.*?)<div class="comp-job-deatiil">', detail_html, re.DOTALL)
    company_email = ""
    if carer_box_match:
        carer_emails = extract_emails_from_html(carer_box_match.group(1))
        if carer_emails:
            company_email = carer_emails[0]

    contact_box_match = re.search(r'<div class="contact">(.*?)</div>', detail_html, re.DOTALL)
    contact_email = ""
    if contact_box_match:
        contact_emails = extract_emails_from_html(contact_box_match.group(1))
        if contact_emails:
            contact_email = contact_emails[0]

    # Combine all valid unique emails found on detail page
    all_page_emails = extract_emails_from_html(detail_html)
    emails = []
    if company_email:
        emails.append(company_email)
    if contact_email and contact_email not in emails:
        emails.append(contact_email)
    for em in all_page_emails:
        if em not in emails:
            emails.append(em)

    # 2. Company Profile link
    company_profile = ""
    profile_match = re.search(r'<a\s+href="([^"]+/companies/profile/[^"]+)"', detail_html)
    if profile_match:
        company_profile = profile_match.group(1)

    # 3. Full Job Description (inside .comp-job-deatiil -> .deatil-box)
    jd_raw = ""
    detail_box_match = re.search(r'<div class="deatil-box">(.*?)</div>\s*</div>', detail_html, re.DOTALL)
    if detail_box_match:
        jd_raw = detail_box_match.group(1)
    else:
        # Fallback to entire comp-job-deatiil
        comp_match = re.search(r'<div class="comp-job-deatiil">(.*?)</div>\s*</div>\s*</div>', detail_html, re.DOTALL)
        if comp_match:
            jd_raw = comp_match.group(1)

    jd_clean = clean_html_to_text(jd_raw)

    return {
        "full_text": jd_clean,
        "contact_emails": emails,
        "company_profile": company_profile,
    }


def parse_job_listings_page(page_html: str) -> List[Dict[str, str]]:
    """
    Parse the table rows on an Infopark listing page.
    Returns list of dicts: {post_date, job_title, company_name, last_date, detail_url}
    """
    jobs = []
    # Pattern matching table rows:
    # <tr>
    #   <td class="head">18-09-2026</td>
    #   <td class="head">UX Writer (Growth)</td>
    #   <td class="date">Mozilor Technologies Pvt. Ltd.</td>
    #   <td>19 Sep 2026</td>
    #   <td class="btn-sec"><a href="...">...</a></td>
    # </tr>
    row_pattern = re.compile(
        r'<tr>\s*<td class="head">([^<]+)</td>\s*<td class="head">([^<]+)</td>\s*<td class="date">([^<]+)</td>\s*<td>([^<]*)</td>\s*<td class="btn-sec">\s*<a href="([^"]+)"',
        re.DOTALL
    )

    matches = row_pattern.findall(page_html)
    for post_date, job_title, company_name, last_date, detail_url in matches:
        jobs.append({
            "post_date": post_date.strip(),
            "job_title": html.unescape(job_title.strip()),
            "company_name": html.unescape(company_name.strip()),
            "last_date": last_date.strip(),
            "detail_url": detail_url.strip(),
        })

    return jobs


def scrape_infopark_jobs(
    target_date: Optional[str] = None,
    max_pages: int = 15,
    stop_on_older_date: bool = True
) -> Dict[str, Any]:
    """
    Main scraping function for Infopark jobs.
    - target_date: 'DD-MM-YYYY' (e.g. '18-09-2026'). If None, defaults to today.
    - max_pages: Maximum number of pagination pages to scan.
    - stop_on_older_date: Stop paginating once encountering dates older than target_date.
    """
    if target_date is None:
        target_date = datetime.now().strftime("%d-%m-%Y")

    print("=" * 68)
    print("  Infopark Jobs Search — Sourcing Today's Opportunities")
    print("=" * 68)
    print(f"  Source URL:       {INFOPARK_JOBS_URL}")
    print(f"  Target Date:      {target_date} (Today's postings)")
    print(f"  Max Pages:        {max_pages}")
    print("=" * 68)
    print()

    # Initialize DB table
    init_db()

    # Preload existing identifiers into in-memory set
    existing_identifiers = get_existing_post_identifiers()
    print(f"  [DB Deduplication] Preloaded {len(existing_identifiers)} existing post signatures/URLs from database.")

    total_scanned = 0
    added_email_outreach = 0
    added_draft_portal = 0
    skipped_existing = 0
    skipped_other_date = 0

    new_jobs = []

    for page_num in range(1, max_pages + 1):
        page_url = f"{INFOPARK_JOBS_URL}?page={page_num}"
        print(f"\n[Page {page_num}/{max_pages}] Fetching: {page_url}...")

        try:
            html_content = fetch_html(page_url)
        except Exception as err:
            print(f"  ✗ Failed to fetch page {page_num}: {err}")
            break

        listings = parse_job_listings_page(html_content)
        if not listings:
            print("  No more job rows found on this page. Reached end of listings.")
            break

        print(f"  Found {len(listings)} job opportunities on page {page_num}.")

        consecutive_older = 0
        should_stop = False

        for job in listings:
            total_scanned += 1
            post_date = job["post_date"]
            title = job["job_title"]
            company = job["company_name"]
            detail_url = job["detail_url"]
            last_date = job["last_date"]

            # Date check
            if target_date and post_date != target_date:
                consecutive_older += 1
                skipped_other_date += 1
                # Infopark is ordered newest first. If we encounter multiple older date entries, stop.
                if stop_on_older_date and consecutive_older >= 3:
                    print(f"  -> Encountered postings from earlier date ({post_date}); completed today's jobs.")
                    should_stop = True
                    break
                continue
            else:
                consecutive_older = 0

            # 1. Fast O(1) deduplication check before fetching detail page
            clean_url = detail_url.split("?")[0].rstrip("/")
            sig = f"{company.strip().lower()}:{title.strip().lower()}"
            if (clean_url in existing_identifiers) or (detail_url in existing_identifiers) or (sig in existing_identifiers):
                skipped_existing += 1
                print(f"  ⏩ [Skipped - Already Added] {company} | {title}")
                continue

            # 2. Fetch Detail Page
            try:
                details = parse_job_detail_page(detail_url)
                time.sleep(0.15)  # respectful micro-delay
            except Exception as d_err:
                print(f"  ✗ Error loading detail page for {title} ({company}): {d_err}")
                continue

            full_jd = details["full_text"]
            emails = details["contact_emails"]
            company_profile = details.get("company_profile") or ""

            if not full_jd:
                # If JD empty, build fallback description
                full_jd = f"{title} at {company}.\nApplication Deadline: {last_date}."

            # 3. Extract Experience
            exp_info = extract_experience(full_jd)
            exp_label = exp_info["raw_text"] if exp_info["raw_text"] else exp_info["seniority_level"]

            # 4. Categorize: EMAIL_OUTREACH vs DRAFT_PORTAL
            if emails:
                category = "EMAIL_OUTREACH"
                added_email_outreach += 1
                cat_tag = "✓ [EMAIL OUTREACH]"
            else:
                category = "DRAFT_PORTAL"
                added_draft_portal += 1
                cat_tag = "📋 [SAVED AS DRAFT]"

            # Headline with role and deadline
            headline = f"{title}"
            if last_date:
                headline += f" • Deadline: {last_date}"

            post_record = {
                "author_name": company,
                "author_headline": headline,
                "author_profile": company_profile,
                "post_date": post_date,
                "post_url": detail_url,
                "full_text": full_jd,
                "detected_emails": emails,
                "detected_links": [detail_url],
                "experience": exp_info,
                "category": category,
                "location": "Kochi",
            }

            # 5. Pre-screen by role title (COMMENTED OUT: We preserve all jobs to send opportunity emails with candidate's stack)
            # prescreened_reason = pre_screen_role(title, full_jd)
            # if prescreened_reason:
            #     # Save as REJECTED immediately — skip ChatGPT entirely
            #     post_record["category"] = category  # keep category for ref
            #     try:
            #         post_id, inserted = upsert_post(post_record, skip_if_exists=True)
            #         if post_id:
            #             update_post_status(post_id, "REJECTED", rejection_reason=prescreened_reason)
            #             existing_identifiers.add(clean_url)
            #             existing_identifiers.add(detail_url)
            #             existing_identifiers.add(sig)
            #         print(f"  🚫 [Pre-Screened / Rejected] {company} | {title} | ❌ {prescreened_reason}")
            #     except Exception as db_err:
            #         print(f"  (Warning: DB save error during pre-screen: {db_err})")
            #     continue

            # 6. Persist to PostgreSQL (suitable role — queued for ChatGPT)
            try:
                post_id, inserted = upsert_post(post_record, skip_if_exists=True)
                if inserted:
                    existing_identifiers.add(clean_url)
                    existing_identifiers.add(detail_url)
                    existing_identifiers.add(sig)
                    new_jobs.append(post_record)
                    print(f"  {cat_tag} {company} | {title} | Exp: {exp_label} | Emails: {emails}")
                else:
                    skipped_existing += 1
                    print(f"  ⏩ [Skipped - Already In DB] {company} | {title}")
            except Exception as db_err:
                print(f"  (Warning: DB save error: {db_err})")

        if should_stop:
            break

    print("\n" + "=" * 68)
    print("  EXTRACTION SUMMARY:")
    print("=" * 68)
    print(f"  Total Opportunities Scanned:      {total_scanned}")
    print(f"  - Direct Email Outreach Added:    {added_email_outreach}")
    print(f"  - Draft / Portal Jobs Added:      {added_draft_portal}")
    print(f"  - Previously Added (Skipped):     {skipped_existing}")
    print(f"  - Other Dates (Skipped):          {skipped_other_date}")
    print("=" * 68)

    crawl_stats = {
        "total_crawled": total_scanned,
        "newly_added": len(new_jobs),
        "new_email_outreach": added_email_outreach,
        "new_draft_portal": added_draft_portal,
        "skipped_already_added": skipped_existing,
        "skipped_other": skipped_other_date,
    }
    print(f"__CRAWL_STATS__: {json.dumps(crawl_stats)}")

    return {
        "total_scanned": total_scanned,
        "new_email_outreach": added_email_outreach,
        "new_draft_portal": added_draft_portal,
        "skipped_existing": skipped_existing,
        "new_jobs_count": len(new_jobs),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape jobs from Infopark")
    parser.add_argument("--date", type=str, default=None, help="Target date (DD-MM-YYYY), defaults to today")
    parser.add_argument("--max-pages", type=int, default=15, help="Maximum pages to scan (default 15)")
    parser.add_argument("--all-dates", action="store_true", help="Do not stop on older dates")

    args = parser.parse_args()
    scrape_infopark_jobs(
        target_date=args.date if not args.all_dates else None,
        max_pages=args.max_pages,
        stop_on_older_date=not args.all_dates
    )


if __name__ == "__main__":
    main()
