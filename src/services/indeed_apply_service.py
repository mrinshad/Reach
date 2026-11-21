"""
Indeed Job Portal & Indeed Apply Automation Service Module
(src/services/indeed_apply_service.py)

Handles autonomous Indeed job discovery with "Easily apply" (DSQF7) filtering,
in-stream recruiter email harvesting from Job Descriptions (funneled directly to Review & Drafts),
Question Bank screening automation, and multi-step Indeed Apply submission wizard.
"""

import os
import re
import time
import json
import random
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

from src.services.firefox_connector import launch_firefox_context
from src.services.experience_extractor import extract_experience
from src.db.posts import (
    upsert_post,
    update_post_status,
    get_post_by_id,
    get_dismissed_role_titles,
    check_title_previously_dismissed,
)
from src.db.question_bank import (
    lookup_answer_for_question,
    upsert_screening_question,
)
from src.services.question_bank_service import match_option_to_answer
from src.services.chatgpt_service import ask_chatgpt_for_reason_for_applying
from src.db.settings import get_setting
from src.config import load_config, is_headless

INDEED_BASE_URL = "https://www.indeed.com"
INDEED_IN_BASE_URL = "https://in.indeed.com"

# Blacklisted generic email domains / prefixes that are not recruiter emails
EXCLUDED_EMAIL_DOMAINS = {
    "indeed.com",
    "indeedemail.com",
    "sentry.io",
    "w3.org",
    "example.com",
    "schema.org",
    "google.com",
    "apple.com",
    "github.com",
}


def build_indeed_search_url(
    keywords: str,
    location: str = "India",
    time_filter: str = "24h",
    start: int = 0,
) -> str:
    """
    Construct an Indeed job search URL with the 'Easily apply' filter (sc=0kf:attr(DSQF7);)
    and optional posted-date recency filter.
    """
    import urllib.parse

    kw_clean = (keywords or "").strip()
    loc_clean = (location or "India").strip()

    # Time recency filter for Indeed (fromage parameter)
    tf_low = (time_filter or "").lower().strip()
    fromage = ""
    if tf_low in ("24h", "1", "today", "past 24 hours"):
        fromage = "1"
    elif tf_low in ("week", "7", "past week"):
        fromage = "7"
    elif tf_low in ("14", "14d", "14 days", "2 weeks"):
        fromage = "14"
    elif tf_low in ("month", "30", "past month"):
        fromage = "30"

    # Base URL choice: if searching in India, default to in.indeed.com for localized jobs
    base = INDEED_IN_BASE_URL if "india" in loc_clean.lower() else INDEED_BASE_URL

    params = [
        ("q", kw_clean),
        ("l", loc_clean),
        ("sc", "0kf:attr(DSQF7);"),  # Indeed's easily apply filter attribute
    ]
    if fromage:
        params.append(("fromage", fromage))
    if start > 0:
        params.append(("start", str(start)))

    query_str = urllib.parse.urlencode(params)
    return f"{base}/jobs?{query_str}"


def extract_emails_from_text(text: str) -> List[str]:
    """
    Extract valid recruiter/contact email addresses from job description text.
    Filters out Indeed system emails and common generic spam patterns.
    """
    if not text:
        return []
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    raw_matches = re.findall(email_regex, text)
    cleaned: List[str] = []
    seen: Set[str] = set()

    for em in raw_matches:
        low = em.lower().strip().rstrip(".,;:)")
        if not low or "@" not in low:
            continue
        domain = low.split("@", 1)[1]
        if domain in EXCLUDED_EMAIL_DOMAINS:
            continue
        if any(low.endswith("." + ex) for ex in EXCLUDED_EMAIL_DOMAINS):
            continue
        if any(prefix in low for prefix in ["no-reply@", "noreply@", "donotreply@"]):
            continue
        if low not in seen:
            seen.add(low)
            cleaned.append(low)
    return cleaned


def is_job_title_relevant(title: str, query: str) -> Tuple[bool, str]:
    """
    Verify if an Indeed job title matches the user's targeted keywords.
    Rejects completely irrelevant categories and prevents applying for executive/staff
    or senior roles when targeting entry/mid level roles.
    """
    if not title:
        return False, "Missing job title"

    t_low = title.lower()
    q_low = (query or "").lower().strip()

    # Disallow common false-positive job listings
    irrelevant_keywords = [
        "driver", "cook", "chef", "nurse", "waiter", "security guard",
        "carpenter", "plumber", "electrician", "telecaller", "cashier",
        "receptionist", "data entry", "bpo", "housekeeping"
    ]
    for irr in irrelevant_keywords:
        if irr in t_low and irr not in q_low:
            return False, f"Irrelevant non-tech role: '{irr}'"

    # Executive / Senior leadership filters when query is for developer/engineer
    if any(k in q_low for k in ["developer", "engineer", "frontend", "backend", "full stack", "fullstack", "react", "python", "software"]):
        senior_roles = [
            "director", "vp", "vice president", "head of", "principal engineer",
            "staff engineer", "engineering manager", "cto", "architect"
        ]
        for sr in senior_roles:
            if sr in t_low and sr not in q_low:
                return False, f"Executive / Staff leadership role: '{sr}'"

    # Token match check
    q_tokens = [tok for tok in re.split(r"[\s,\-/+]+", q_low) if len(tok) > 2 and tok not in ["and", "for", "with", "the"]]
    if q_tokens:
        matched = [tok for tok in q_tokens if tok in t_low]
        # Allow if at least one key skill / title token is present
        if not matched and not any(kw in t_low for kw in ["software", "developer", "engineer", "stack", "frontend", "backend", "programmer"]):
            return False, f"Title '{title}' does not match target keywords '{query}'"

    return True, "Relevant"


def human_sleep(min_s: float = 1.5, max_s: float = 3.0, cancel_check=None):
    """Sleep with jitter and periodic cancellation checking."""
    total = random.uniform(min_s, max_s)
    step = 0.25
    elapsed = 0.0
    while elapsed < total:
        if cancel_check and cancel_check():
            break
        time.sleep(min(step, total - elapsed))
        elapsed += step


def detect_cloudflare_challenge(page: Page) -> bool:
    """
    Detect whether Indeed is currently presenting a Cloudflare Turnstile / Ray ID challenge:
    - 'Additional Verification Required'
    - 'Your Ray ID for this request is'
    - 'Troubleshooting Cloudflare Errors'
    - 'Just a moment...'
    - Challenge stage / turnstile wrapper elements
    """
    try:
        title = (page.title() or "").lower()
        if "just a moment" in title or "attention required" in title or "cloudflare" in title:
            return True

        body_check = page.evaluate("""() => {
            const b = document.body;
            if (!b) return false;
            const txt = (b.innerText || '').toLowerCase();
            if (txt.includes('additional verification required') && (txt.includes('ray id') || txt.includes('cloudflare'))) return true;
            if (txt.includes('troubleshooting cloudflare errors')) return true;
            if (txt.includes('verify you are human') && (txt.includes('cloudflare') || txt.includes('turnstile') || txt.includes('ray id'))) return true;
            return false;
        }""")
        if body_check:
            return True

        cf_loc = page.locator("#challenge-stage, #challenge-running, iframe[src*='challenges.cloudflare.com'], [data-translate='turnstile_wrapper']").first
        if cf_loc.count() > 0 and cf_loc.is_visible():
            return True
    except Exception:
        pass
    return False


def handle_cloudflare_or_captcha_pause(
    page: Page,
    logger=print,
    task_manager=None,
    max_wait_seconds: int = 300,
) -> bool:
    """
    If Cloudflare verification is detected, pause and wait for the user to manually solve it in the browser.
    Emits watchdog heartbeat logs every 15s to keep background tasks alive.
    Returns True if verification succeeded/cleared, False if timed out or cancelled.
    """
    if not detect_cloudflare_challenge(page):
        return True

    logger("\n" + "=" * 66)
    logger("  🛡️ CLOUDFLARE VERIFICATION DETECTED ON INDEED")
    logger("  'Additional Verification Required' (Ray ID / Cloudflare Turnstile)")
    logger("  ⚠️ Automation paused for manual user approval in the browser.")
    logger("=" * 66)

    from src.config import is_headless
    if is_headless():
        logger("  ⚠️ Notice: Browser is currently running in HEADLESS mode!")
        logger("  Please switch to visible mode in the Reach Dashboard (toggle Headless to OFF)")
        logger("  so you can see the browser window and complete the verification.")

    start_time = time.time()
    last_heartbeat = start_time
    poll_interval = 2.0

    while time.time() - start_time < max_wait_seconds:
        # Check if user cancelled task
        if task_manager and hasattr(task_manager, "is_cancel_requested") and task_manager.is_cancel_requested():
            logger("  🛑 Task cancelled by user while waiting for Cloudflare verification.")
            return False

        if task_manager and hasattr(task_manager, "check_pause"):
            task_manager.check_pause()

        page.wait_for_timeout(int(poll_interval * 1000))

        now = time.time()
        # Periodic watchdog heartbeat to reset inactivity timer and inform user
        if now - last_heartbeat >= 15.0:
            elapsed = int(now - start_time)
            remaining = max(0, int(max_wait_seconds - elapsed))
            logger(f"  ⏳ Cloudflare challenge active: Waiting for manual approval in browser ({elapsed}s elapsed, {remaining}s remaining)...")
            if task_manager and hasattr(task_manager, "log"):
                task_manager.log(f"Waiting for manual Cloudflare approval in browser ({elapsed}s)...")
            last_heartbeat = now

        # Check if challenge is resolved
        if not detect_cloudflare_challenge(page):
            page.wait_for_timeout(2000)
            if not detect_cloudflare_challenge(page):
                logger("  🎉 ✓ Cloudflare verification completed! Resuming Indeed workflow...")
                return True

    logger(f"  ⏱️ Timed out waiting for Cloudflare verification after {max_wait_seconds}s.")
    return False


def wait_for_indeed_job_cards_loaded(page: Page, timeout_ms: int = 15000, logger=print, task_manager=None) -> bool:
    """Wait until Indeed job cards or results container render on the page, checking for Cloudflare."""
    handle_cloudflare_or_captcha_pause(page, logger=logger, task_manager=task_manager)
    selectors = [
        "div.job_seen_beacon",
        "td.resultContent",
        "div.cardOutline",
        "div[data-testid='jobsearch-JobComponent']",
        "ul.css-zu9cdh",
        "div#mosaic-provider-jobcards",
    ]
    for sel in selectors:
        try:
            page.wait_for_selector(sel, state="attached", timeout=timeout_ms // len(selectors))
            return True
        except Exception:
            pass
    return False


def extract_indeed_job_card_metadata(card) -> Dict[str, Any]:
    """Extract metadata from an individual Indeed search job card element."""
    title = ""
    company = ""
    location = ""
    job_key = ""
    job_url = ""
    snippet = ""
    has_easily_apply = False
    is_already_applied = False

    # 1. Job Title & URL / Key
    try:
        title_el = card.locator("h2.jobTitle span, a.jcs-JobTitle span, h2.jobTitle a, h2.jobTitle").first
        if title_el.count() > 0:
            title = title_el.inner_text().strip()

        link_el = card.locator("a.jcs-JobTitle, a[data-jk], h2.jobTitle a").first
        if link_el.count() > 0:
            job_key = link_el.get_attribute("data-jk") or ""
            href = link_el.get_attribute("href") or ""
            if not job_key and "jk=" in href:
                m = re.search(r"jk=([a-zA-Z0-9]+)", href)
                if m:
                    job_key = m.group(1)
            if job_key:
                job_url = f"{INDEED_BASE_URL}/viewjob?jk={job_key}"
            elif href.startswith("http"):
                job_url = href
            elif href:
                job_url = f"{INDEED_BASE_URL}{href}"
    except Exception:
        pass

    # 2. Company Name
    try:
        comp_el = card.locator("[data-testid='company-name'], span.css-1h7uxdj, span.companyName, span[data-testid='company-name']").first
        if comp_el.count() > 0:
            company = comp_el.inner_text().strip()
    except Exception:
        pass

    # 3. Location
    try:
        loc_el = card.locator("[data-testid='text-location'], div.companyLocation, div.css-1restdh").first
        if loc_el.count() > 0:
            location = loc_el.inner_text().strip()
    except Exception:
        pass

    # 4. Snippet
    try:
        snip_el = card.locator("div.job-snippet, table.jobCardShelfContainer, ul.css-15027au").first
        if snip_el.count() > 0:
            snippet = snip_el.inner_text().strip()
    except Exception:
        pass

    # 5. Check Easily Apply Indicator
    try:
        full_card_text = card.inner_text().lower()
        if "easily apply" in full_card_text or "apply with indeed" in full_card_text:
            has_easily_apply = True
        elif card.locator("[data-testid='indeedApply'], span.iaIcon, span.css-123y4s8").count() > 0:
            has_easily_apply = True
    except Exception:
        pass

    # 6. Check if card indicates already applied
    try:
        full_card_text = card.inner_text().lower()
        if re.search(r"\bapplied\b", full_card_text):
            is_already_applied = True
        elif card.locator("span.myJobsState, span[class*='myJobsState'], [data-testid='applied-badge']").count() > 0:
            is_already_applied = True
    except Exception:
        pass

    return {
        "title": title,
        "company": company or "Company",
        "location": location,
        "job_key": job_key,
        "job_url": job_url,
        "snippet": snippet,
        "has_easily_apply": has_easily_apply,
        "is_already_applied": is_already_applied,
    }


def harvest_jd_text_and_emails(
    page: Page,
    job_key: Optional[str] = None,
    post_url: Optional[str] = None,
    logger=print,
) -> Tuple[str, List[str]]:
    """
    Harvest full job description text and run regex email extraction.
    Checks the right-hand preview pane or navigates directly to the viewjob page if needed.
    Returns: (full_text, list_of_contact_emails)
    """
    jd_text = ""
    # Look for JD container in current page (preview pane or standalone viewjob)
    jd_selectors = [
        "div#jobDescriptionText",
        "div[data-testid='jobsearch-JobComponent-description']",
        "div.jobsearch-JobComponent-description",
        "div.jobsearch-jobDescriptionText",
    ]
    for sel in jd_selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                txt = el.inner_text().strip()
                if txt and len(txt) > len(jd_text):
                    jd_text = txt
        except Exception:
            pass

    # If preview pane not rendered, open standalone if post_url provided and not already on that page
    if not jd_text and post_url and (post_url not in page.url and page.url not in post_url):
        try:
            logger(f"  Fetching full JD text directly from {post_url}...")
            resp = page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1500)
            if detect_indeed_closed_or_404(page, response=resp):
                logger(f"  ⚠️ Listing is expired or 404 Not Found. Skipping JD fetch.")
                return "", []
            for sel in jd_selectors:
                el = page.locator(sel).first
                if el.count() > 0:
                    txt = el.inner_text().strip()
                    if txt:
                        jd_text = txt
                        break
        except Exception as e:
            logger(f"  Notice fetching JD page: {e}")

    emails = extract_emails_from_text(jd_text)
    return jd_text, emails


def detect_indeed_closed_or_404(page: Page, response: Optional[Any] = None) -> Optional[str]:
    """
    Check if the Indeed job page indicates a 404 Not Found, deleted listing, or expired position.
    Returns:
      - String description (e.g. 'Job expired or removed (404 Page Not Found)', 'This job has expired on Indeed') if closed/404.
      - None if the job is open and valid.
    """
    # 1. Network response status check (404 Not Found or 410 Gone)
    try:
        if response and hasattr(response, "status") and response.status in (404, 410):
            return "Job expired or removed (404 Page Not Found)"
    except Exception:
        pass

    # 2. Document Title check
    try:
        title = page.title()
        if "not found | indeed" in title.lower() or "404 - indeed" in title.lower():
            return "Job expired or removed (404 Page Not Found)"
    except Exception:
        pass

    # 3. URL redirect check (redirected away from viewjob to root homepage)
    try:
        cur_url = (page.url or "").split("?")[0].rstrip("/")
        if re.search(r"^https?://[a-z0-9\.\-]*indeed\.com$", cur_url):
            return "Job listing expired or redirected to homepage"
    except Exception:
        pass

    # 4. DOM checks for 404 Heading & Text Content
    try:
        is_404 = page.evaluate("""() => {
            const h1 = document.querySelector('h1');
            if (h1) {
                const h1Text = h1.innerText || '';
                if (/we can['’]t find this page/i.test(h1Text) || /^404/i.test(h1Text.trim())) {
                    return true;
                }
            }
            const bodyText = document.body ? document.body.innerText : '';
            if (/we can['’]t find this page/i.test(bodyText) && /doesn['’]t exist/i.test(bodyText)) {
                return true;
            }
            return false;
        }""")
        if is_404:
            return "Job expired or removed (404 Page Not Found)"
    except Exception:
        pass

    # 5. DOM checks for Expired / Closed Job Banners
    try:
        expired_reason = page.evaluate("""() => {
            const expiredEl = document.querySelector('.jobsearch-JobInfoHeader-expiredNotice, div[data-testid="expired-job-banner"], .jobsearch-JobComponent-expired');
            if (expiredEl && expiredEl.innerText.trim()) {
                return expiredEl.innerText.trim();
            }
            const bodyText = document.body ? document.body.innerText : '';
            if (/this job has expired on indeed/i.test(bodyText)) {
                return 'This job has expired on Indeed';
            }
            if (/this job is no longer available/i.test(bodyText)) {
                return 'This job is no longer available';
            }
            if (/the job you are looking for is no longer available/i.test(bodyText)) {
                return 'The job you are looking for is no longer available';
            }
            if (/job has been closed/i.test(bodyText)) {
                return 'Job has been closed';
            }
            return null;
        }""")
        if expired_reason:
            return expired_reason if isinstance(expired_reason, str) else "Job expired or closed on Indeed"
    except Exception:
        pass

    return None


def detect_indeed_apply_button(page: Page) -> Tuple[Optional[Any], bool]:
    """
    Locate the Indeed Apply button on the current job page/pane or detect external ATS apply.
    Returns: (apply_element, is_external_apply)
    """
    # 1. Dismiss cookie banners if present
    try:
        cookie_btn = page.locator("#onetrust-accept-btn-handler, button#onetrust-accept-btn-handler").first
        if cookie_btn.count() > 0 and cookie_btn.is_visible():
            cookie_btn.click(timeout=1500)
            page.wait_for_timeout(400)
    except Exception:
        pass

    # 2. Check for onsite Indeed Apply button or link
    btn_selectors = [
        "button#indeedApplyButton",
        "a.jobsearch-IndeedApplyButton-newDesign",
        "a[href*='smartapply.indeed.com']",
        "div#indeedApplyButtonContainer button",
        "div#indeedApplyButtonContainer a",
        "button.ia-IndeedApplyButton",
        "button[data-testid='indeed-apply-button']",
        "a[data-testid='indeed-apply-button']",
        "button:has-text('Apply now')",
        "a:has-text('Apply now')",
        "button:has-text('Easily apply')",
        "a:has-text('Easily apply')",
        "span:has-text('Apply now')",
    ]
    for sel in btn_selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                return el, False
        except Exception:
            pass

    # 3. Check for external ATS apply ('Apply on company site')
    ext_selectors = [
        "a:has-text('Apply on company site')",
        "button:has-text('Apply on company site')",
        "a[data-testid*='apply-on-company-site']",
        "button[data-testid*='apply-on-company-site']",
        "span:has-text('Apply on company site')",
        "a:has-text('Apply directly')",
    ]
    for sel in ext_selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                return el, True
        except Exception:
            pass

    return None, False


def execute_indeed_apply(
    page: Page,
    post_data: Dict[str, Any],
    resume_path: Optional[str] = None,
    logger=print,
    cancel_check=None,
) -> Dict[str, Any]:
    """
    Multi-step Indeed Apply Automation Runner:
    1. Scans the full JD and extracts recruiter contact emails.
    2. Detects if the job is Onsite Indeed Apply vs External ATS ('Apply on company site').
       - If External: Marks status as NOT_FOUND ('External application required') like LinkedIn.
    3. Handles multi-step SmartApply wizard:
       - Resume selection (checks resume radio & advances with real non-honeypot continue button).
       - Contact info (phone/email/name verification).
       - Screening Questionnaires (checks Question Bank; answers matching questions, blocks & saves unrecorded ones).
       - Review & Final Application Submission.
    4. Updates database status to 'APPLIED' upon successful submission.
    """
    job_id = post_data.get("id") or ""
    job_title = post_data.get("author_headline") or "Software Engineer"
    company_name = post_data.get("author_name") or "Company"
    post_url = post_data.get("post_url") or ""
    current_emails = list(post_data.get("contact_emails") or [])

    logger("=" * 60)
    logger(f"🎯 Starting Indeed Apply for: {job_title} @ {company_name}")
    logger(f"  Post URL: {post_url}")
    logger("=" * 60)

    # 0. Early check for 404 Not Found or Expired listing
    closed_reason = detect_indeed_closed_or_404(page)
    if closed_reason:
        logger(f"  🚫 {closed_reason}. Aborting application.")
        if job_id:
            update_post_status(job_id, "NOT_FOUND", rejection_reason=closed_reason)
        return {"status": "NOT_FOUND", "detail": closed_reason}

    # 1. In-stream JD harvesting & email extraction
    jd_text, discovered_emails = harvest_jd_text_and_emails(page, post_url=post_url, logger=logger)
    all_emails = list(set(current_emails + discovered_emails))

    if discovered_emails:
        logger(f"  📧 In-Stream Discovery: Found recruiter email(s) in JD: {', '.join(discovered_emails)}")
        logger(f"  ✓ Candidate automatically available in 'Review & Drafts' for AI Cover Letter dispatch!")

    # Save JD text and extracted emails back to DB
    if (discovered_emails or jd_text) and job_id:
        try:
            exp_data = extract_experience(jd_text) if jd_text else {}
            upsert_post(
                post_data={
                    "id": job_id,
                    "post_url": post_url,
                    "author_name": company_name,
                    "author_headline": job_title,
                    "location": post_data.get("location") or "",
                    "full_text": jd_text or post_data.get("full_text") or "",
                    "contact_emails": all_emails,
                    "min_experience": exp_data.get("min_years"),
                    "max_experience": exp_data.get("max_years"),
                    "category": "INDEED_APPLY",
                    "status": post_data.get("status") or "DISCOVERED",
                }
            )
        except Exception as e:
            logger(f"  Notice updating post with JD emails: {e}")

    # 2. Locate Apply Button & verify eligibility
    apply_btn, is_external = detect_indeed_apply_button(page)
    if is_external:
        logger(f"  ℹ️ Position redirects to external company ATS ('Apply on company site'). Preserving JD and emails.")
        if job_id:
            update_post_status(job_id, "NOT_FOUND", rejection_reason="External application required (Apply on company site)")
        return {"status": "NOT_FOUND", "detail": "External application required (Apply on company site)"}

    if not apply_btn:
        # Re-check if page is a 404 or expired before falling back to generic reason
        recheck_closed = detect_indeed_closed_or_404(page)
        final_reason = recheck_closed or "Apply button not available"
        logger(f"  ⚠️ No Indeed Easy Apply button found for {job_title} @ {company_name} ({final_reason}).")
        if job_id:
            update_post_status(job_id, "NOT_FOUND", rejection_reason=final_reason)
        return {"status": "NOT_FOUND", "detail": final_reason}

    # 3. Click Apply Now
    logger("  [Step 1/4] Clicking 'Apply now'...")
    try:
        apply_href = apply_btn.get_attribute("href") or ""
        apply_btn.click(force=True)
        page.wait_for_timeout(2500)

        # If page did not navigate and href is a smartapply link, navigate directly
        if apply_href and "smartapply.indeed.com" in apply_href and "smartapply" not in page.url:
            page.goto(apply_href, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
    except Exception as e:
        logger(f"  ❌ Failed to click Apply button: {e}")
        return {"status": "FAILED", "detail": str(e)}

    # Check for new tabs if Indeed opened in a new window
    target_page = page
    if len(page.context.pages) > 1:
        target_page = page.context.pages[-1]
        target_page.bring_to_front()
        target_page.wait_for_timeout(2000)

    # 4. Multi-step modal navigation loop
    max_steps = 15
    current_step = 0
    unanswered_questions: List[str] = []

    while current_step < max_steps:
        current_step += 1
        if cancel_check and cancel_check():
            logger("  ⏹️ Process cancelled by user.")
            return {"status": "CANCELLED", "detail": "Cancelled by user"}

        logger(f"  [Step {current_step}] Current URL: {target_page.url}")

        # Wait up to 6s for step hydration (ignoring hidden honeypots)
        try:
            target_page.locator("button[data-testid='continue-button']:visible, button[data-testid*='submit']:visible, button:not([data-testid*='hp']):has-text('Continue'):visible, button:not([data-testid*='hp']):has-text('Review your application'):visible, input:visible, select:visible, textarea:visible").first.wait_for(timeout=6000)
        except Exception:
            pass

        target_page.wait_for_timeout(1500)
        current_url = target_page.url.lower()

        # A. Check for Application Submitted confirmation
        if (
            target_page.locator("h1:has-text('Your application has been submitted'), div:has-text('Application submitted'), h1:has-text('Application submitted')").count() > 0
            or "post-apply" in current_url
            or "confirmation" in current_url
        ):
            logger(f"  🎉 [Success] Application successfully submitted on Indeed for {job_title} @ {company_name}!")
            if job_id:
                update_post_status(job_id, "APPLIED")
            return {"status": "APPLIED", "detail": "Submitted successfully"}

        # B. Check for Accept Terms modal / Checkbox
        tos_checkbox = target_page.locator("input[type='checkbox'][name*='term'], input[type='checkbox'][id*='term'], input[type='checkbox'][aria-label*='term']").first
        if tos_checkbox.count() > 0 and not tos_checkbox.is_checked():
            logger("  [Wizard] Checking Terms of Service agreement checkbox...")
            tos_checkbox.check(force=True)
            target_page.wait_for_timeout(1000)

        acc_btn = target_page.locator("button:has-text('Accept Terms'), button:has-text('Accept'), button:has-text('I agree'), button:has-text('Agree and continue')").first
        if acc_btn.count() > 0 and acc_btn.is_visible():
            logger("  [Wizard] Accepting updated Terms of Service...")
            acc_btn.click(force=True)
            target_page.wait_for_timeout(3000)
            continue

        # C. Check for Resume Tailoring modal bypass
        tailor_btn = target_page.locator("button:has-text('Continue without tailoring'), button:text-is('Skip'), button:has-text('Skip this step'), button:has-text('Skip question'), button:has-text('No thanks'), button:has-text('Keep current resume'), button:has-text('Keep original resume')").first
        if tailor_btn.count() > 0 and tailor_btn.is_visible():
            btn_txt = tailor_btn.inner_text().strip()
            if "skip to main" not in btn_txt.lower():
                old_u = target_page.url
                logger(f"  [Wizard] Dismissing tailoring suggestion ('{btn_txt}')...")
                tailor_btn.click(force=True)
                try:
                    target_page.wait_for_url(lambda u: u != old_u, timeout=12000)
                except Exception:
                    target_page.wait_for_timeout(3500)
                target_page.wait_for_timeout(1000)
                continue

        # D. Check for Missing Qualifications / Not Applicable Interstitial
        cont_anyway_btn = target_page.locator("button:has-text('Continue anyway'), button:has-text('Apply anyway'), button:has-text('Continue applying')").first
        missing_qual_txt = target_page.locator(":has-text('qualifications you may be missing'), :has-text('missing qualifications'), :has-text('not meet all qualifications')").first
        if (cont_anyway_btn.count() > 0 and cont_anyway_btn.is_visible()) or (missing_qual_txt.count() > 0 and missing_qual_txt.is_visible()):
            logger("  [Wizard] Qualification warning screen detected ('Not applicable' / missing qualifications)...")
            reason_box = target_page.locator("textarea:visible, input[type='text']:visible").first
            if reason_box.count() > 0 and not reason_box.input_value().strip():
                logger("  [Wizard] Requesting reason for applying from ChatGPT...")
                gen_reason = ask_chatgpt_for_reason_for_applying(
                    target_page.context,
                    jd_text=jd_text or post_data.get("full_text") or "",
                    logger=logger,
                )
                reason_box.fill(gen_reason)
                logger(f"  ✓ Filled reason for applying: {gen_reason[:60]}...")
            if cont_anyway_btn.count() > 0 and cont_anyway_btn.is_visible():
                logger(f"  [Wizard] Clicking '{cont_anyway_btn.inner_text().strip()}'...")
                cont_anyway_btn.click(force=True)
                target_page.wait_for_timeout(3500)
                continue

        # E. Check for Final Review / Submit Step
        if "review-module" in current_url or target_page.locator("button[data-testid*='submit']:visible, button:not([data-testid*='hp']):has-text('Submit your application'):visible, button:not([data-testid*='hp']):has-text('Submit application'):visible").count() > 0:
            logger("  [Step 4/4] Review screen reached. Waiting for final submission button to mount...")

            # Wait for Indeed's 'Preparing review' progress bar to complete
            try:
                target_page.wait_for_selector(":has-text('Preparing review')", state="detached", timeout=20000)
            except Exception:
                pass

            # Check for reCAPTCHA challenge
            recaptcha_el = target_page.locator("iframe[src*='recaptcha'], [title*='reCAPTCHA'], :has-text('I\\'m not a robot')").first
            if recaptcha_el.count() > 0 and recaptcha_el.is_visible():
                logger("  🛡️ Indeed reCAPTCHA challenge detected on review step ('I'm not a robot').")
                logger("  ⚠️ Anti-Bot Safety Policy: Bot solving of CAPTCHA challenges is strictly avoided.")
                logger("  Application paused for user verification. Please complete submission in a visible browser.")
                if job_id:
                    update_post_status(job_id, "REQUIRES_QUESTIONNAIRE", rejection_reason="Verification Required: Indeed reCAPTCHA ('I\\'m not a robot')")
                return {"status": "REQUIRES_QUESTIONNAIRE", "detail": "reCAPTCHA verification required"}

            try:
                target_page.wait_for_selector(
                    "button:not([data-testid*='hp'])[data-testid='submit-application-button'], button:not([data-testid*='hp']):has-text('Submit your application'), button:not([data-testid*='hp']):has-text('Submit application')",
                    state="visible",
                    timeout=20000,
                )
            except Exception:
                pass

            submit_selectors = [
                "button:not([data-testid*='hp'])[data-testid='submit-application-button']:visible",
                "button:not([data-testid*='hp'])[data-testid='review-page-submit-button']:visible",
                "button:not([data-testid*='hp'])[data-testid*='submit']:visible",
                "button:not([data-testid*='hp']):has-text('Submit your application'):visible",
                "button:not([data-testid*='hp']):has-text('Submit application'):visible",
                "button:not([data-testid*='hp']):has-text('Submit'):visible",
                "button[type='submit']:not([data-testid*='hp']):visible",
                "button:not([data-testid*='hp'])[data-testid='continue-button']:visible",
            ]
            submit_btn = None
            for s_sel in submit_selectors:
                el = target_page.locator(s_sel).first
                if el.count() > 0 and el.is_visible():
                    submit_btn = el
                    break

            if submit_btn:
                # Scroll to bottom to trigger review completion and check any required non-recaptcha checkboxes
                try:
                    target_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    target_page.wait_for_timeout(1000)
                    for cb in target_page.locator("input[type='checkbox']:visible").all():
                        cb_id = (cb.get_attribute("id") or "").lower()
                        if "recaptcha" in cb_id:
                            continue
                        if not cb.is_checked():
                            cb_lbl = target_page.locator(f"label[for='{cb_id}']").first if cb_id else None
                            if cb_lbl and cb_lbl.count() > 0:
                                cb_lbl.click(force=True)
                            else:
                                cb.click(force=True)
                            logger("  ✓ Checked required confirmation checkbox on review page")
                except Exception:
                    pass

                # Check again if reCAPTCHA appeared after scroll
                recaptcha_el = target_page.locator("iframe[src*='recaptcha'], [title*='reCAPTCHA'], :has-text('I\\'m not a robot')").first
                if recaptcha_el.count() > 0 and recaptcha_el.is_visible():
                    logger("  🛡️ Indeed reCAPTCHA challenge detected on review step ('I'm not a robot').")
                    logger("  Application paused for user verification. Please complete submission in a visible browser.")
                    if job_id:
                        update_post_status(job_id, "REQUIRES_QUESTIONNAIRE", rejection_reason="Verification Required: Indeed reCAPTCHA ('I\\'m not a robot')")
                    return {"status": "REQUIRES_QUESTIONNAIRE", "detail": "reCAPTCHA verification required"}

                # Wait up to 20s for submit button to become enabled
                logger(f"  Waiting for '{submit_btn.inner_text().strip()}' to become enabled...")
                for _ in range(20):
                    if submit_btn.is_enabled():
                        break
                    target_page.wait_for_timeout(1000)

                btn_txt = submit_btn.inner_text().strip()
                logger(f"  Clicking '{btn_txt}' to submit application (enabled={submit_btn.is_enabled()})...")
                submit_btn.scroll_into_view_if_needed()
                submit_btn.click(force=True)

                # Wait up to 15s for submission confirmation to render
                try:
                    target_page.wait_for_selector(
                        "h1:has-text('submitted'), div:has-text('submitted'), h1:has-text('sent'), div:has-text('sent'), div:has-text('Application submitted'), :has-text('Your application has been submitted'), :has-text('Application submitted')",
                        timeout=15000,
                    )
                except Exception:
                    target_page.wait_for_timeout(3000)

                if (
                    target_page.locator("h1:has-text('submitted'), div:has-text('submitted'), div:has-text('Application submitted'), div:has-text('Your application has been submitted'), div:has-text('Application sent'), :has-text('Your application was sent')").count() > 0
                    or any(k in target_page.url.lower() for k in ["post-apply", "postapply", "confirmation", "applied"])
                ):
                    logger(f"  🎉 [Success] Application successfully submitted on Indeed for {job_title} @ {company_name}!")
                    if job_id:
                        update_post_status(job_id, "APPLIED")
                    return {"status": "APPLIED", "detail": "Submitted successfully"}

        # F. Resume Selection Step
        if "resume-selection" in current_url or target_page.locator(":has-text('Review your resume'), :has-text('Select a resume')").count() > 0:
            logger("  [Wizard] Resume selection step detected. Verifying uploaded resume...")
            try:
                resume_radio = target_page.locator("input[name*='resume-selection'], input[type='radio'][name*='resume']").first
                if resume_radio.count() > 0 and not resume_radio.is_checked():
                    resume_radio.check(force=True)
                    logger("  ✓ Checked primary uploaded resume on Indeed")
                elif resume_path and os.path.exists(resume_path):
                    file_input = target_page.locator("input[type='file']").first
                    if file_input.count() > 0:
                        file_input.set_input_files(resume_path)
                        logger(f"  ✓ Uploaded resume file: {os.path.basename(resume_path)}")
            except Exception as e:
                logger(f"  Notice during resume selection: {e}")

            cont_btn = target_page.locator("button[data-testid='continue-button']").first
            if cont_btn.count() > 0 and cont_btn.is_visible():
                old_u = target_page.url
                logger("  Clicking 'Continue' to advance past resume selection...")
                try:
                    cont_btn.scroll_into_view_if_needed(timeout=2000)
                    cont_btn.click(force=True, timeout=5000)
                    try:
                        target_page.wait_for_url(lambda u: u != old_u, timeout=12000)
                    except Exception:
                        target_page.wait_for_timeout(3500)
                    target_page.wait_for_timeout(1000)
                except Exception as e:
                    logger(f"  Notice advancing past resume: {e}")
                continue

        # G. Contact Information Step
        if "contact-info" in current_url or target_page.locator("input[type='tel'], input#input-phoneNumber").count() > 0:
            try:
                phone_inp = target_page.locator("input[type='tel'], input#input-phoneNumber, input[name*='phone']").first
                if phone_inp.count() > 0 and not phone_inp.input_value().strip():
                    phone_inp.fill("9895612423")
                    logger("  ✓ Filled default contact phone number")
            except Exception:
                pass

        # H. Screening Questions Handling
        unanswered_questions = []
        processed_prompts = set()
        try:
            form_fields = target_page.locator("fieldset, div.ia-Questions-item, div[class*='question'], div[data-testid*='question']").all()
            for field in form_fields:
                # 1. Skip child option wrappers (e.g., individual radio/checkbox container divs)
                try:
                    is_child_option = field.evaluate("""(el) => {
                        // If it's a child of a fieldset and not the fieldset itself, it's an option item
                        if (el.tagName !== 'FIELDSET' && el.closest('fieldset')) {
                            return true;
                        }
                        // If it's a child of single-select-question and not the question container itself
                        const ssq = el.closest('[data-testid="single-select-question"]');
                        if (ssq && el !== ssq) {
                            return true;
                        }
                        // If it's a child of ia-Questions-item
                        const qItem = el.closest('div.ia-Questions-item');
                        if (qItem && el !== qItem) {
                            return true;
                        }
                        // If it only wraps a single radio or checkbox and its label text matches all text
                        const inputs = el.querySelectorAll('input[type="radio"], input[type="checkbox"]');
                        const labels = el.querySelectorAll('label');
                        if (inputs.length === 1 && labels.length === 1) {
                            if (el.innerText.trim() === labels[0].innerText.trim()) return true;
                        }
                        return false;
                    }""")
                    if is_child_option:
                        continue
                except Exception:
                    pass

                # 2. Extract clean question prompt (legend first, header/title second, label third)
                prompt_raw = ""
                try:
                    prompt_raw = field.evaluate("""(el) => {
                        const leg = el.querySelector('legend');
                        if (leg && leg.innerText.trim().length > 2) return leg.innerText.trim();
                        const lblSpan = el.querySelector('[data-testid*="question-label"]');
                        if (lblSpan && lblSpan.innerText.trim().length > 2) return lblSpan.innerText.trim();
                        const hdr = el.querySelector('[class*="header"], [class*="title"], h2, h3, h4');
                        if (hdr && hdr.innerText.trim().length > 2) return hdr.innerText.trim();
                        const labels = el.querySelectorAll('label');
                        for (let l of labels) {
                            const forId = l.getAttribute('for');
                            if (forId) {
                                const inp = document.getElementById(forId);
                                if (inp && (inp.type === 'radio' || inp.type === 'checkbox')) continue;
                            }
                            if (l.innerText.trim().length > 2) return l.innerText.trim();
                        }
                        return '';
                    }""")
                except Exception:
                    lbl_el = field.locator("legend, label, span[class*='header'], h3").first
                    prompt_raw = lbl_el.inner_text().strip() if lbl_el.count() > 0 else ""

                if not prompt_raw:
                    continue

                prompt = re.sub(r"\s*\*+\s*required", "", prompt_raw, flags=re.IGNORECASE)
                prompt = re.sub(r"\s*\*+", "", prompt).strip()
                if not prompt or len(prompt) < 3:
                    continue

                if prompt.lower() in processed_prompts:
                    continue
                processed_prompts.add(prompt.lower())

                low_prompt = prompt.lower()
                # Check for reason for applying open question
                if any(k in low_prompt for k in ["reason for applying", "why are you applying", "why should we hire", "why are you interested", "tell us why you", "good fit", "cover letter"]):
                    logger(f"  [Screening] Prompt asks for reason for applying: '{prompt[:45]}...'")
                    gen_reason = ask_chatgpt_for_reason_for_applying(
                        target_page.context,
                        jd_text=jd_text or post_data.get("full_text") or "",
                        logger=logger,
                    )
                    inp = field.locator("textarea, input[type='text']").first
                    if inp.count() > 0:
                        inp.fill(gen_reason)
                        logger(f"  ✓ Auto-filled reason from ChatGPT: {gen_reason[:60]}...")
                    continue

                ans, _ = lookup_answer_for_question(prompt)

                # 1. Radio button question
                radios = field.locator("input[type='radio']").all()
                if radios:
                    extracted_options = []
                    for r in radios:
                        r_id = r.get_attribute("id") or ""
                        r_lbl = field.locator(f"label[for='{r_id}']").first if r_id else None
                        r_text = (r_lbl.inner_text() if r_lbl and r_lbl.count() > 0 else r.get_attribute("value") or "").strip()
                        if r_text and r_text not in extracted_options:
                            extracted_options.append(r_text)

                    if ans:
                        matched = False
                        matched_opt_text = match_option_to_answer(ans, extracted_options, prompt)
                        for r in radios:
                            r_id = r.get_attribute("id") or ""
                            r_lbl = field.locator(f"label[for='{r_id}']").first if r_id else None
                            r_text = (r_lbl.inner_text() if r_lbl and r_lbl.count() > 0 else r.get_attribute("value") or "").strip()
                            if (
                                (matched_opt_text and r_text.lower() == matched_opt_text.lower())
                                or ans.lower() == r_text.lower()
                                or (ans.lower() in ("yes", "y", "true") and "yes" in r_text.lower())
                                or (ans.lower() in ("no", "n", "false") and "no" in r_text.lower())
                                or (ans.lower() in r_text.lower() and len(ans) > 3)
                                or (r_text.lower() in ans.lower() and len(r_text) > 3)
                            ):
                                if r_lbl and r_lbl.count() > 0:
                                    r_lbl.click(force=True)
                                else:
                                    r.click(force=True)
                                matched = True
                                sel_text = matched_opt_text or ans
                                logger(f"  ✓ Radio answered from Question Bank for '{prompt[:40]}...': {sel_text}")
                                break
                        if not matched:
                            upsert_screening_question(prompt, sample_job=job_title, options=extracted_options)
                            unanswered_questions.append(prompt)
                    else:
                        upsert_screening_question(prompt, sample_job=job_title, options=extracted_options)
                        unanswered_questions.append(prompt)
                    continue

                # 2. Standard Dropdown question (<select>)
                sel = field.locator("select").first
                if sel.count() > 0:
                    extracted_options = []
                    for opt in sel.locator("option").all():
                        otxt = opt.inner_text().strip()
                        if otxt and otxt.lower() not in ("select an option", "select", "choose", "-- select --", ""):
                            extracted_options.append(otxt)

                    if ans:
                        matched = False
                        matched_opt_text = match_option_to_answer(ans, extracted_options, prompt)
                        for opt in sel.locator("option").all():
                            otxt = opt.inner_text().strip()
                            if (
                                (matched_opt_text and otxt.lower() == matched_opt_text.lower())
                                or ans.lower() == otxt.lower()
                                or ans.lower() in otxt.lower()
                                or otxt.lower() in ans.lower()
                            ):
                                sel.select_option(value=opt.get_attribute("value"))
                                matched = True
                                sel_text = matched_opt_text or ans
                                logger(f"  ✓ Dropdown answered from Question Bank for '{prompt[:40]}...': {sel_text}")
                                break
                        if not matched:
                            upsert_screening_question(prompt, sample_job=job_title, options=extracted_options)
                            unanswered_questions.append(prompt)
                    else:
                        upsert_screening_question(prompt, sample_job=job_title, options=extracted_options)
                        unanswered_questions.append(prompt)
                    continue

                # 3. Custom Mosaic select dropdown (e.g. data-testid="single-select-question-select-list" or [role='combobox'])
                custom_sel = field.locator("[data-testid*='select-list'], [role='combobox'], div[id*='single-select-question']").first
                if custom_sel.count() > 0 and custom_sel.is_visible():
                    try:
                        cur_val = (custom_sel.inner_text() or "").strip()
                        if ans and ans.lower() in cur_val.lower():
                            logger(f"  ✓ Custom Select already answered with '{ans}'")
                            continue

                        custom_sel.scroll_into_view_if_needed(timeout=1000)
                        custom_sel.click(force=True)
                        target_page.wait_for_timeout(500)
                        opts_els = target_page.locator("li[role='option'], div[role='option'], [role='option']").all()
                        extracted_options = []
                        for opt_el in opts_els:
                            otxt = opt_el.inner_text().strip()
                            if otxt and otxt.lower() not in ("select an option", "select", "choose", "") and otxt not in extracted_options:
                                extracted_options.append(otxt)

                        if ans:
                            matched = False
                            for opt_el in opts_els:
                                otxt = opt_el.inner_text().strip().lower()
                                if ans.lower() == otxt or ans.lower() in otxt or otxt in ans.lower():
                                    opt_el.scroll_into_view_if_needed(timeout=1000)
                                    opt_el.click(force=True)
                                    matched = True
                                    logger(f"  ✓ Custom Select answered from Question Bank for '{prompt[:40]}...': {ans}")
                                    target_page.wait_for_timeout(500)
                                    break
                            if not matched:
                                target_page.keyboard.press("Escape")
                                upsert_screening_question(prompt, sample_job=job_title, options=extracted_options)
                                unanswered_questions.append(prompt)
                        else:
                            target_page.keyboard.press("Escape")
                            upsert_screening_question(prompt, sample_job=job_title, options=extracted_options)
                            unanswered_questions.append(prompt)
                        continue
                    except Exception as err_sel:
                        logger(f"  Notice processing custom dropdown: {err_sel}")

                # 4. Checkbox question
                checkboxes = field.locator("input[type='checkbox']").all()
                if len(checkboxes) > 1:
                    extracted_options = []
                    for cb in checkboxes:
                        cb_id = cb.get_attribute("id") or ""
                        cb_lbl = field.locator(f"label[for='{cb_id}']").first if cb_id else None
                        cb_text = (cb_lbl.inner_text() if cb_lbl and cb_lbl.count() > 0 else cb.get_attribute("value") or "").strip()
                        if cb_text and cb_text not in extracted_options:
                            extracted_options.append(cb_text)
                    if ans:
                        for cb in checkboxes:
                            cb_id = cb.get_attribute("id") or ""
                            cb_lbl = field.locator(f"label[for='{cb_id}']").first if cb_id else None
                            cb_text = (cb_lbl.inner_text() if cb_lbl and cb_lbl.count() > 0 else cb.get_attribute("value") or "").strip().lower()
                            if ans.lower() in cb_text or cb_text in ans.lower():
                                if cb_lbl and cb_lbl.count() > 0:
                                    cb_lbl.click(force=True)
                                else:
                                    cb.click(force=True)
                                logger(f"  ✓ Checkbox checked from Question Bank for '{prompt[:40]}...': {ans}")
                    else:
                        upsert_screening_question(prompt, sample_job=job_title, options=extracted_options)
                        unanswered_questions.append(prompt)
                    continue

                # 5. Text / Number inputs
                inp = field.locator("input[type='text'], input[type='number'], textarea").first
                if inp.count() > 0 and not inp.input_value().strip():
                    if ans:
                        clean_ans = ans.strip()
                        if inp.get_attribute("type") == "number":
                            digits = re.findall(r"\d+", clean_ans)
                            clean_ans = digits[0] if digits else "3"
                        inp.fill(clean_ans)
                        logger(f"  ✓ Input answered from Question Bank for '{prompt[:40]}...': {clean_ans}")
                    else:
                        upsert_screening_question(prompt, sample_job=job_title)
                        unanswered_questions.append(prompt)
        except Exception as e:
            logger(f"  Notice processing screening form step: {e}")

        # BLOCKING RULE: If unanswered questions prevent advancing, pause application
        if unanswered_questions:
            logger(f"  📋 Unanswered screening questions encountered ({len(unanswered_questions)} questions).")
            logger(f"  Saved to Screening Question Bank. Pausing this application for human review.")
            if job_id:
                update_post_status(job_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=f"Questions: {'; '.join(unanswered_questions)}")
            return {"status": "REQUIRES_QUESTIONNAIRE", "questions": unanswered_questions}

        # I. Advance with real non-honeypot Continue / Next / Review / Submit button
        target_page.wait_for_timeout(1000)
        advanced = False

        candidate_selectors = [
            "button:has-text('Submit your application'):visible",
            "button:has-text('Submit application'):visible",
            "button:has-text('Review your application'):visible",
            "button[data-testid='continue-button']:visible",
            "button:not([data-testid*='hp']):has-text('Continue'):visible",
            "button:not([data-testid*='hp']):has-text('Next'):visible",
        ]

        for sel_btn in candidate_selectors:
            adv_locator = target_page.locator(sel_btn)
            if adv_locator.count() > 0:
                for idx in range(adv_locator.count()):
                    btn = adv_locator.nth(idx)
                    try:
                        tid = (btn.get_attribute("data-testid") or "").lower()
                        if "hp" in tid:
                            continue
                        txt = btn.inner_text().strip()
                        if not txt or any(k in txt.lower() for k in ["skip", "close", "report", "clear", "save and close"]):
                            continue
                        if btn.is_visible() and btn.is_enabled():
                            old_url = target_page.url
                            logger(f"  [Step {current_step}] Advancing via '{txt}'...")
                            btn.scroll_into_view_if_needed(timeout=1000)
                            btn.click(force=True)
                            try:
                                target_page.wait_for_url(lambda u: u != old_url, timeout=10000)
                            except Exception:
                                target_page.wait_for_timeout(2500)
                            target_page.wait_for_timeout(1000)
                            advanced = True
                            break
                    except Exception:
                        pass
                if advanced:
                    break

        if not advanced:
            logger("  ⚠️ No further advancement button found in wizard.")
            break

    # Final check for submitted confirmation
    target_page.wait_for_timeout(2000)
    if (
        target_page.locator("h1:has-text('submitted'), div:has-text('submitted'), div:has-text('Application submitted'), div:has-text('Your application has been submitted'), div:has-text('Application sent')").count() > 0
        or any(k in target_page.url.lower() for k in ["post-apply", "postapply", "confirmation", "applied"])
    ):
        logger("  🎉 [Success] Application successfully submitted on Indeed!")
        if job_id:
            update_post_status(job_id, "APPLIED")
        return {"status": "APPLIED", "detail": "Submitted successfully"}

    if job_id:
        existing_post = get_post_by_id(job_id) or {}
        existing_reason = existing_post.get("rejection_reason") or ""
        if existing_reason and "Questions:" in existing_reason:
            final_reason = existing_reason
        elif "review-module" in target_page.url.lower():
            final_reason = "Application Review reached (Pending submission verification)"
        else:
            final_reason = "Additional verification or input required to advance wizard"
        update_post_status(job_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=final_reason)
    return {"status": "REQUIRES_QUESTIONNAIRE", "detail": "Additional input required"}


def run_indeed_apply_crawler(
    keywords: str = "Full Stack Developer",
    location: str = "India",
    time_filter: str = "24h",
    cycles: int = 8,
    max_jobs: int = 50,
    pacing: str = "safe",
    auto_apply: bool = False,
    task_manager=None,
) -> Dict[str, Any]:
    """
    Main autonomous Indeed job collector:
    1. Opens Indeed in visible persistent Firefox context (headless=False).
    2. Discovers and scrolls through available job openings on the page.
    3. Bidirectional cross-platform rejection sync:
       - Checks each role against all previously dismissed roles (from LinkedIn or Indeed).
       - Automatically auto-dismisses and rejects matching roles (status='REJECTED').
    4. For matching/active roles:
       - Clicks card to harvest full JD text and right-pane specifications.
       - Extracts recruiter contact emails from JD text.
       - Parses required years of experience / fresher flags.
       - Saves to database with category='INDEED_APPLY', status='DISCOVERED' (Ready to Apply).
    5. Emits real-time progress, summary metrics, and __CRAWL_STATS__ JSON for the dashboard.
    """
    logger = task_manager.log if task_manager else print
    config = load_config()

    kw_clean = (keywords or "").strip()
    loc_clean = (location or "India").strip()
    base_domain = "https://in.indeed.com" if "india" in loc_clean.lower() else "https://www.indeed.com"
    scroll_cycles = int(cycles) if cycles and int(cycles) > 0 else 8
    target_max = int(max_jobs) if max_jobs and int(max_jobs) > 0 else 50
    active_headless = is_headless()

    if kw_clean:
        from urllib.parse import urlencode
        params = {"q": kw_clean}
        if loc_clean:
            params["l"] = loc_clean
        tf = (time_filter or "24h").lower().strip()
        if tf in ("24h", "1d", "day"):
            params["fromage"] = "1"
        elif tf in ("3d", "3days"):
            params["fromage"] = "3"
        elif tf in ("7d", "week", "1w"):
            params["fromage"] = "7"
        elif tf in ("14d", "2w"):
            params["fromage"] = "14"

        # Prioritize onsite Easy Apply jobs
        params["sc"] = "0kf:attr(DS3S6);"
        target_url = f"{base_domain}/jobs?{urlencode(params)}"
    else:
        # Default direct listing without search input
        target_url = base_domain

    logger("=" * 66)
    logger("🚀 Indeed Job Portal — Autonomous Job Collector")
    logger(f"  Target URL:       {target_url}")
    logger(f"  Search Query:     {kw_clean if kw_clean else '(Direct Feed / No Query)'}")
    logger(f"  Location:         {loc_clean}")
    logger(f"  Max Openings:     {target_max}")
    logger(f"  Scroll Cycles:    {scroll_cycles}")
    logger(f"  Headless Mode:    {'True (Silent Background)' if active_headless else 'False (Visible Desktop Window)'}")
    logger(f"  Cross-Platform:   Unified Rejection Sync with LinkedIn Enabled")
    logger("=" * 66)

    discovered_count = 0
    auto_dismissed_count = 0
    emails_harvested_count = 0

    with sync_playwright() as playwright:
        logger(f"[1/3] Launching persistent Firefox context (headless={active_headless})...")
        context = launch_firefox_context(
            playwright,
            headless=active_headless,
            sync_cookies_domains=["indeed.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        logger(f"[2/3] Navigating to Indeed ({target_url})...")
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
        except Exception as e:
            logger(f"  ⚠️ Notice during page navigation: {e}")

        # Check for Cloudflare challenge before proceeding
        handle_cloudflare_or_captcha_pause(page, logger=logger, task_manager=task_manager)

        # Wait for job cards to render
        logger("  Waiting for job cards to load...")
        wait_for_indeed_job_cards_loaded(page, timeout_ms=12000, logger=logger, task_manager=task_manager)

        # Multi-cycle scrolling to discover cards across the page
        logger(f"[3/3] Scanning and extracting job cards ({scroll_cycles} discovery cycles)...")
        collected_cards_map: Dict[str, Dict[str, Any]] = {}

        # Initial pass
        raw_cards = page.locator("div.job_seen_beacon, td.resultContent, div.cardOutline").all()
        for c in raw_cards:
            try:
                meta = extract_indeed_job_card_metadata(c)
                jk = meta.get("job_key") or (hashlib.sha256(meta.get("job_url", "").encode()).hexdigest()[:12] if meta.get("job_url") else "")
                if jk and jk not in collected_cards_map:
                    meta["card_locator"] = c
                    collected_cards_map[jk] = meta
            except Exception:
                pass

        stagnant_cycles = 0

        for cycle_idx in range(1, scroll_cycles + 1):
            if len(collected_cards_map) >= target_max:
                logger(f"  ✓ Target max jobs limit ({target_max}) reached.")
                break

            prev_count = len(collected_cards_map)
            logger(f"  [Cycle {cycle_idx}/{scroll_cycles}] Scrolling feed ({prev_count} cards collected)...")

            # Scroll dynamically towards the next batch of cards
            page.evaluate("""() => {
                const cards = document.querySelectorAll('div.job_seen_beacon, td.resultContent, div.cardOutline');
                if (cards.length > 0) {
                    cards[cards.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
                } else {
                    window.scrollBy(0, 1200);
                }
            }""")
            page.wait_for_timeout(1400)

            cur_raw = page.locator("div.job_seen_beacon, td.resultContent, div.cardOutline").all()
            for c in cur_raw:
                try:
                    meta = extract_indeed_job_card_metadata(c)
                    jk = meta.get("job_key") or (hashlib.sha256(meta.get("job_url", "").encode()).hexdigest()[:12] if meta.get("job_url") else "")
                    if jk and jk not in collected_cards_map:
                        meta["card_locator"] = c
                        collected_cards_map[jk] = meta
                except Exception:
                    pass

            new_count = len(collected_cards_map)
            if new_count == prev_count:
                stagnant_cycles += 1

                # Check if bottom of feed has been reached
                try:
                    is_at_bottom = page.evaluate("() => (window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 400)")
                except Exception:
                    is_at_bottom = False

                next_btn = page.locator("a[data-testid='pagination-page-next'], a[aria-label='Next Page'], nav[aria-label*='pagination'] a:has-text('Next')").first
                has_next = False
                try:
                    has_next = next_btn.count() > 0 and next_btn.is_visible()
                except Exception:
                    pass

                if is_at_bottom and not has_next and stagnant_cycles >= 2:
                    logger(f"  🏁 Reached end of listings ({new_count} cards collected). All available jobs on Indeed loaded.")
                    break
                elif has_next and stagnant_cycles >= 2:
                    logger(f"  [Pagination] Reached end of current page ({new_count} cards). Navigating to Next Page...")
                    try:
                        next_btn.click(force=True)
                        page.wait_for_timeout(3000)
                        stagnant_cycles = 0
                    except Exception as e:
                        logger(f"  Notice navigating to next page: {e}")
                        break
                elif stagnant_cycles >= 3:
                    logger(f"  🏁 Feed exhausted: no new job cards after {stagnant_cycles} consecutive scroll cycles ({new_count} cards collected). Exiting discovery early.")
                    break
            else:
                stagnant_cycles = 0

        extracted_jobs = list(collected_cards_map.values())[:target_max]
        total_found = len(extracted_jobs)
        logger(f"  Discovered {total_found} unique Indeed job openings. Ingesting specifications...")

        if task_manager and hasattr(task_manager, "set_total_posts"):
            task_manager.set_total_posts(total_found)

        # Load dismissed role titles from entire DB (LinkedIn + Indeed cross-platform sync)
        dismissed_titles = get_dismissed_role_titles()
        logger(f"  Loaded {len(dismissed_titles)} previously dismissed roles for cross-platform matching.")

        for idx, job in enumerate(extracted_jobs, start=1):
            if task_manager and hasattr(task_manager, "is_cancel_requested") and task_manager.is_cancel_requested():
                logger("🛑 Task cancelled by user.")
                break

            title = job.get("title") or "Software Engineer"
            company = job.get("company") or "Company"
            job_loc = job.get("location") or location or "India"
            job_key = job.get("job_key") or hashlib.sha256(f"{title}:{company}".encode()).hexdigest()[:12]
            job_url = job.get("job_url") or f"https://in.indeed.com/viewjob?jk={job_key}"
            post_id = f"ind_{job_key}"

            logger(f"\n[{idx}/{total_found}] {title} @ {company}")
            logger(f"  Location: {job_loc} | Key: {job_key}")
            if task_manager and hasattr(task_manager, "update_progress"):
                task_manager.update_progress(idx - 1, f"[{idx}/{total_found}] {title} @ {company}")

            # 1. Bidirectional Cross-Platform Rejection Check
            is_prev_dismissed, dismiss_reason = check_title_previously_dismissed(title, dismissed_titles)
            if is_prev_dismissed:
                logger(f"  ✕ {dismiss_reason}")
                post_record = {
                    "id": post_id,
                    "post_url": job_url,
                    "author_name": company,
                    "author_headline": title,
                    "location": job_loc,
                    "full_text": f"Role: {title}\nCompany: {company}\nLocation: {job_loc}\nDirect Application Link: {job_url}",
                    "category": "INDEED_APPLY",
                    "status": "REJECTED",
                    "rejection_reason": dismiss_reason,
                }
                upsert_post(post_record)
                auto_dismissed_count += 1
                if task_manager and hasattr(task_manager, "update_progress"):
                    task_manager.update_progress(idx)
                continue

            # 2. Check if card indicates already applied on Indeed
            if job.get("is_already_applied"):
                logger(f"  ✓ Card indicates already applied on Indeed. Saved to Cancelled history.")
                post_record = {
                    "id": post_id,
                    "post_url": job_url,
                    "author_name": company,
                    "author_headline": title,
                    "location": job_loc,
                    "full_text": f"Role: {title}\nCompany: {company}\nLocation: {job_loc}\nNotice: Already applied on Indeed",
                    "category": "INDEED_APPLY",
                    "status": "REJECTED",
                    "rejection_reason": "Already applied on Indeed",
                    "is_already_applied": True,
                }
                upsert_post(post_record)
                if task_manager and hasattr(task_manager, "update_progress"):
                    task_manager.update_progress(idx)
                continue

            # 3. Exact Opening Duplicate Pre-Check
            from src.db.posts import is_post_already_saved
            if is_post_already_saved(post_url=job_url, author_name=company):
                logger(f"  ℹ️ Exact job opening already in database ({post_id}). Skipping duplicate.")
                if task_manager and hasattr(task_manager, "update_progress"):
                    task_manager.update_progress(idx)
                continue

            # 4. Click card to open JD pane and harvest details
            full_text = ""
            card_loc = job.get("card_locator")
            try:
                if card_loc:
                    card_loc.click(timeout=3500)
                    page.wait_for_timeout(1400)
                else:
                    link_el = page.locator(f"a[data-jk='{job_key}'], a[href*='{job_key}']").first
                    if link_el.count() > 0:
                        link_el.click(timeout=3500)
                        page.wait_for_timeout(1400)

                # Check Cloudflare challenge if click triggered a verification prompt
                handle_cloudflare_or_captcha_pause(page, logger=logger, task_manager=task_manager)

                # Check if preview pane indicates already applied
                pane_applied = page.evaluate("""() => {
                    const pane = document.querySelector('#jobsearch-ViewjobPaneWrapper, .jobsearch-ViewjobPaneWrapper, #viewJobSSRRoot, body');
                    if (!pane) return false;
                    const txt = (pane.innerText || '').toLowerCase();
                    return txt.includes('you applied to this job') || txt.includes('applied on indeed');
                }""")
                if pane_applied:
                    logger("  ✓ Preview pane confirms already applied on Indeed. Saved to Cancelled history.")
                    post_record = {
                        "id": post_id,
                        "post_url": job_url,
                        "author_name": company,
                        "author_headline": title,
                        "location": job_loc,
                        "full_text": f"Role: {title}\nCompany: {company}\nLocation: {job_loc}\nNotice: Already applied on Indeed",
                        "category": "INDEED_APPLY",
                        "status": "REJECTED",
                        "rejection_reason": "Already applied on Indeed",
                        "is_already_applied": True,
                    }
                    upsert_post(post_record)
                    if task_manager and hasattr(task_manager, "update_progress"):
                        task_manager.update_progress(idx)
                    continue

                # Check if the opened preview pane indicates the job has expired or is a 404
                pane_expired = page.evaluate("""() => {
                    const pane = document.querySelector('#jobsearch-ViewjobPaneWrapper, .jobsearch-ViewjobPaneWrapper, #viewJobSSRRoot, body');
                    if (!pane) return null;
                    const txt = pane.innerText || '';
                    if (/this job has expired on indeed/i.test(txt)) return 'This job has expired on Indeed';
                    if (/this job is no longer available/i.test(txt)) return 'This job is no longer available';
                    if (/the job you are looking for is no longer available/i.test(txt)) return 'The job you are looking for is no longer available';
                    if (/job has been closed/i.test(txt)) return 'Job has been closed';
                    if (/we can['’]t find this page/i.test(txt)) return 'Job expired or removed (404 Page Not Found)';
                    return null;
                }""")
                if pane_expired:
                    logger(f"  🚫 {pane_expired}. Marking post as NOT_FOUND.")
                    post_record = {
                        "id": post_id,
                        "post_url": job_url,
                        "author_name": company,
                        "author_headline": title,
                        "location": job_loc,
                        "full_text": f"Role: {title}\nCompany: {company}\nLocation: {job_loc}\nNotice: {pane_expired}",
                        "category": "INDEED_APPLY",
                        "status": "NOT_FOUND",
                        "rejection_reason": pane_expired,
                    }
                    upsert_post(post_record)
                    if task_manager and hasattr(task_manager, "update_progress"):
                        task_manager.update_progress(idx)
                    continue

                desc_text = page.evaluate("""() => {
                    const pane = document.querySelector('#jobsearch-ViewjobPaneWrapper, .jobsearch-ViewjobPaneWrapper, #viewJobSSRRoot');
                    if (pane) {
                        const desc = pane.querySelector('#jobDescriptionText, [id*="jobDescription"], .jobsearch-jobDescriptionText');
                        if (desc) return desc.innerText.trim();
                        return pane.innerText.trim();
                    }
                    const standaloneDesc = document.querySelector('#jobDescriptionText, .jobsearch-jobDescriptionText');
                    if (standaloneDesc) return standaloneDesc.innerText.trim();
                    return '';
                }""")
                if desc_text:
                    full_text = desc_text
            except Exception as e:
                pass

            if not full_text:
                full_text = job.get("snippet") or f"Role: {title}\nCompany: {company}\nLocation: {job_loc}\nDirect Application Link: {job_url}"

            # 3. Extract recruiter contact emails and experience
            emails = extract_emails_from_text(full_text)
            if emails:
                emails_harvested_count += len(emails)
                logger(f"  📧 Harvested recruiter email(s): {', '.join(emails)}")

            exp_info = extract_experience(full_text)
            min_exp = exp_info.get("min_years")
            max_exp = exp_info.get("max_years")
            raw_exp = exp_info.get("raw_text")
            is_fresher = exp_info.get("is_fresher", False)

            # 4. Ingest into database as Ready to Apply (DISCOVERED)
            post_record = {
                "id": post_id,
                "post_url": job_url,
                "author_name": company,
                "author_headline": title,
                "location": job_loc,
                "full_text": full_text,
                "contact_emails": emails,
                "min_experience": min_exp,
                "max_experience": max_exp,
                "raw_experience": raw_exp,
                "is_fresher": is_fresher,
                "category": "INDEED_APPLY",
                "status": "DISCOVERED",
            }
            upsert_post(post_record)
            discovered_count += 1
            logger(f"  ✓ Saved to queue as Ready to Apply (DISCOVERED)")

            if task_manager and hasattr(task_manager, "update_progress"):
                task_manager.update_progress(idx)

            page.wait_for_timeout(random.randint(400, 900))

        context.close()

    # Print summary
    logger("\n" + "=" * 66)
    logger("  INDEED JOB COLLECTOR SUMMARY:")
    logger("=" * 66)
    logger(f"  Total Cards Processed:      {total_found}")
    logger(f"  Saved to Ready Queue:       {discovered_count}")
    logger(f"  Auto-Dismissed (Dismissed): {auto_dismissed_count}")
    logger(f"  Recruiter Emails Harvested: {emails_harvested_count}")
    logger("=" * 66)

    crawl_stats = {
        "total_crawled": total_found,
        "newly_added": discovered_count,
        "ready_in_queue": discovered_count,
        "auto_dismissed": auto_dismissed_count,
        "emails_harvested": emails_harvested_count,
    }
    logger(f"__CRAWL_STATS__: {json.dumps(crawl_stats)}")

    return {
        "success": True,
        **crawl_stats,
    }


def apply_to_single_indeed_post(post_id: str, task_manager=None) -> Dict[str, Any]:
    """Execute Indeed Apply for a single post from the dashboard queue."""
    logger = task_manager.log if task_manager else print
    post = get_post_by_id(post_id)
    if not post:
        logger(f"❌ Post #{post_id} not found in database.")
        return {"status": "FAILED", "detail": "Post not found"}

    config = load_config()
    resume_path = config.get("resume_path", "")

    with sync_playwright() as playwright:
        context = launch_firefox_context(
            playwright,
            headless=is_headless(),
            sync_cookies_domains=["indeed.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        post_url = post.get("post_url") or ""
        logger(f"Navigating to Indeed job: {post_url}...")
        resp = None
        try:
            resp = page.goto(post_url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(2000)
            handle_cloudflare_or_captcha_pause(page, logger=logger)
        except Exception as e:
            logger(f"Error loading post URL: {e}")
            context.close()
            return {"status": "FAILED", "detail": str(e)}

        closed_reason = detect_indeed_closed_or_404(page, response=resp)
        if closed_reason:
            logger(f"🚫 {closed_reason}. Updating post #{post_id} status to NOT_FOUND.")
            update_post_status(post_id, "NOT_FOUND", rejection_reason=closed_reason)
            context.close()
            return {"status": "NOT_FOUND", "detail": closed_reason}

        res = execute_indeed_apply(
            page,
            post_data=post,
            resume_path=resume_path,
            logger=logger,
        )
        context.close()
        return res


def apply_to_batch_indeed_posts(
    post_ids: List[str],
    pacing: str = "safe",
    task_manager=None,
) -> Dict[str, Any]:
    """Sequential batch runner for Indeed Apply submissions with human pacing."""
    logger = task_manager.log if task_manager else print
    config = load_config()
    resume_path = config.get("resume_path", "")
    pacing_mode = (pacing or "safe").lower()

    total = len(post_ids)
    applied = 0
    questionnaires = 0
    failed = 0

    if task_manager:
        task_manager.start_task(
            f"Batch Indeed Apply ({total} jobs)",
            total_items=total,
            short_name="Batch Indeed Apply",
            snippet=f"{total} jobs",
        )

    logger(f"🚀 Starting batch Indeed Apply for {total} selected jobs (Pacing: {pacing_mode})...")

    with sync_playwright() as playwright:
        context = launch_firefox_context(
            playwright,
            headless=is_headless(),
            sync_cookies_domains=["indeed.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        for idx, pid in enumerate(post_ids):
            if task_manager:
                task_manager.check_pause()
                if task_manager.is_cancel_requested():
                    logger("🛑 Batch Indeed Apply stopped upon user request.")
                    break

            post = get_post_by_id(pid)
            if not post:
                continue

            title = post.get("author_headline") or "Job"
            company = post.get("author_name") or "Company"
            post_url = post.get("post_url") or ""

            if task_manager:
                if hasattr(task_manager, "update_progress"):
                    task_manager.update_progress(completed=idx, current_step=f"[{idx+1}/{total}] {title} @ {company}")
                elif hasattr(task_manager, "update_step"):
                    task_manager.update_step(f"[{idx+1}/{total}] {title} @ {company}", completed_items=idx)

            logger(f"[{idx+1}/{total}] Processing: {title} @ {company}...")
            try:
                resp = page.goto(post_url, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(2000)
                handle_cloudflare_or_captcha_pause(page, logger=logger, task_manager=task_manager)

                closed_reason = detect_indeed_closed_or_404(page, response=resp)
                if closed_reason:
                    logger(f"  🚫 {closed_reason}. Status -> NOT_FOUND.")
                    update_post_status(pid, "NOT_FOUND", rejection_reason=closed_reason)
                    failed += 1
                    time.sleep(random.uniform(2, 3))
                    continue

                res = execute_indeed_apply(
                    page,
                    post_data=post,
                    resume_path=resume_path,
                    logger=logger,
                    cancel_check=task_manager.is_cancel_requested if task_manager else None,
                )
                st = res.get("status")
                if st == "APPLIED":
                    applied += 1
                elif st == "REQUIRES_QUESTIONNAIRE":
                    questionnaires += 1
                else:
                    failed += 1

                if idx < total - 1:
                    delay = random.uniform(45, 75) if pacing_mode == "safe" else (random.uniform(75, 120) if pacing_mode == "slow" else random.uniform(30, 45))
                    logger(f"  ⏳ Pacing delay ({pacing_mode}): waiting {delay:.1f}s before next application...")
                    time.sleep(delay)

            except Exception as e:
                logger(f"  ❌ Error applying to {title}: {e}")
                failed += 1

        context.close()

    if task_manager:
        task_manager.finish_task(
            f"Batch Indeed Apply completed: {applied} applied, {questionnaires} screening, {failed} closed/failed."
        )

    return {
        "total": total,
        "applied": applied,
        "questionnaires": questionnaires,
        "failed": failed,
    }
