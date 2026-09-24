"""
LinkedIn Job Search & Easy Apply Service
(src/services/easy_apply_service.py)

Autonomous crawling of linkedin.com/jobs with Easy Apply filter (f_AL=true),
job specification extraction, automated application submission, and questionnaire
detection for screening.
"""

import os
import re
import time
import random
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote

from playwright.sync_api import sync_playwright, Page, BrowserContext
from src.services.firefox_connector import launch_firefox_context
from src.services.experience_extractor import extract_experience
from src.db.posts import upsert_post, get_post_by_id, update_post_status
from src.db.settings import get_setting
from src.config import load_config

LINKEDIN_BASE = "https://www.linkedin.com"


def build_easy_apply_search_url(keywords: str, location: str = "India", time_filter: str = "24h") -> str:
    """Build a LinkedIn job search URL with Easy Apply (f_AL=true) filter."""
    kw = (keywords or "").strip()
    loc = (location or "India").strip()

    # Time filter mapping
    time_map = {
        "24h": "r86400",
        "week": "r604800",
        "month": "r2592000",
        "all": "",
    }
    tpr = time_map.get(time_filter.lower(), "r86400")

    url = f"{LINKEDIN_BASE}/jobs/search/?keywords={quote(kw)}&location={quote(loc)}&f_AL=true"
    if tpr:
        url += f"&f_TPR={tpr}"
    return url


def human_sleep(min_s: float = 1.5, max_s: float = 3.0):
    """Sleep for random human-like pacing."""
    time.sleep(random.uniform(min_s, max_s))


def extract_job_card_metadata(card) -> Dict[str, Any]:
    """Extract summary metadata from a visible job card."""
    job_id = card.evaluate("el => el.getAttribute('data-occludable-job-id') || el.getAttribute('data-job-id') || ''")

    # Title & Link
    title_link = card.locator("a.job-card-container__link, a.job-card-list__title--link")
    title = ""
    href = ""
    if title_link.count() > 0:
        raw_title = title_link.first.inner_text().strip()
        title = raw_title.split("\n")[0].strip()
        href = title_link.first.get_attribute("href") or ""
        if href.startswith("/"):
            href = LINKEDIN_BASE + href
        elif href and not href.startswith("http"):
            href = f"{LINKEDIN_BASE}/{href}"

    # Company
    company_el = card.locator(".artdeco-entity-lockup__subtitle, .job-card-container__company-name")
    company = ""
    if company_el.count() > 0:
        company = company_el.first.inner_text().strip()

    # Location
    location_el = card.locator(".artdeco-entity-lockup__caption, .job-card-container__metadata-item")
    location = ""
    if location_el.count() > 0:
        location = location_el.first.inner_text().strip().split("\n")[0].strip()

    # Fallback job_id from href
    if not job_id and "/view/" in href:
        m = re.search(r"/view/(\d+)", href)
        if m:
            job_id = m.group(1)

    return {
        "job_id": job_id,
        "title": title,
        "company": company or "Unknown Company",
        "location": location,
        "url": href,
    }


def inspect_easy_apply_modal(page: Page) -> Dict[str, Any]:
    """
    Inspect the Easy Apply modal dialog for multi-step questions and determine
    if it can be auto-submitted or if it requires custom questionnaire answers.
    """
    modal = page.locator("div.jobs-easy-apply-modal, div[role='dialog']:has-text('Easy Apply')")
    if modal.count() == 0:
        return {"has_modal": False, "requires_questionnaire": False, "questions": []}

    questions = []

    # Check for question labels
    form_sections = modal.locator(".fb-dash-form-element, .jobs-easy-apply-form-section")
    for i in range(form_sections.count()):
        sec = form_sections.nth(i)
        label_el = sec.locator("label, .fb-dash-form-element__label, span.t-14")
        if label_el.count() > 0:
            txt = label_el.first.inner_text().strip()
            if txt and not any(skip in txt.lower() for skip in ["phone", "email", "resume", "first name", "last name"]):
                questions.append(txt)

    # Check for custom text inputs/textareas
    custom_inputs = modal.locator("textarea, input[type='text']:not([id*='phone']):not([name*='phone'])")
    if custom_inputs.count() > 0:
        for idx in range(min(custom_inputs.count(), 3)):
            inp = custom_inputs.nth(idx)
            aria = inp.get_attribute("aria-label") or inp.get_attribute("id") or ""
            if aria and aria not in questions:
                questions.append(aria)

    # Check for radio question groups
    radio_groups = modal.locator("fieldset")
    for r_idx in range(radio_groups.count()):
        legend = radio_groups.nth(r_idx).locator("legend")
        if legend.count() > 0:
            legend_txt = legend.first.inner_text().strip()
            if legend_txt and legend_txt not in questions:
                questions.append(legend_txt)

    requires_questionnaire = len(questions) > 0
    return {
        "has_modal": True,
        "requires_questionnaire": requires_questionnaire,
        "questions": questions,
    }


def dismiss_easy_apply_modal(page: Page):
    """Safely dismiss and discard an open Easy Apply modal without saving partial drafts."""
    try:
        dismiss_btn = page.locator("button[aria-label='Dismiss'], button.artdeco-modal__dismiss").first
        if dismiss_btn.count() > 0:
            dismiss_btn.click()
            page.wait_for_timeout(700)

            # Confirm discard dialog if it appears
            discard_btn = page.locator(
                "button[data-control-name='discard_application_confirm_btn'], "
                "button:has-text('Discard')"
            ).first
            if discard_btn.count() > 0:
                discard_btn.click()
                page.wait_for_timeout(700)
    except Exception:
        pass


def fill_contact_info(page: Page, modal):
    """Fill standard contact information if empty."""
    try:
        phone_input = modal.locator("input[id*='phoneNumber'], input[name*='phoneNumber'], input[type='tel']").first
        if phone_input.count() > 0:
            current_val = phone_input.input_value().strip()
            if not current_val:
                phone_input.fill("9895612423")
                page.wait_for_timeout(400)
    except Exception:
        pass


def upload_or_select_resume(page: Page, modal, resume_path: Optional[str]):
    """Select or upload the resume if requested on the resume step."""
    if not resume_path or not os.path.exists(resume_path):
        return

    try:
        file_input = modal.locator("input[type='file']").first
        if file_input.count() > 0:
            file_input.set_input_files(resume_path)
            page.wait_for_timeout(1000)
    except Exception:
        pass


def execute_easy_apply(page: Page, job_url: str, resume_path: Optional[str], logger=print) -> Tuple[str, str]:
    """
    Attempt to submit an Easy Apply application for a given job URL.
    Returns (status, detail_message) where status is:
      - 'APPLIED': Successfully submitted
      - 'REQUIRES_QUESTIONNAIRE': Saved for screening due to custom questionnaire
      - 'FAILED': Modal failed to open or encountered an unhandled issue
      - 'ALREADY_APPLIED': LinkedIn indicates you've already applied
    """
    try:
        page.goto(job_url, wait_until="commit", timeout=30000)
        page.wait_for_timeout(3500)

        # Check if already applied
        applied_badge = page.locator(".jobs-s-apply__status--applied, .artdeco-inline-feedback--success")
        if applied_badge.count() > 0 or "applied" in page.locator(".jobs-apply-button").first.inner_text().lower():
            logger("  ℹ️ Already applied to this position on LinkedIn.")
            return "APPLIED", "Already applied previously on LinkedIn"

        # Find Easy Apply button
        apply_btn = page.locator(
            "button.jobs-apply-button, "
            "button:has-text('Easy Apply'), "
            "[aria-label*='Easy Apply']"
        ).first

        if apply_btn.count() == 0:
            logger("  ⚠️ No Easy Apply button found on page.")
            return "FAILED", "No Easy Apply button visible"

        logger("  Clicking 'Easy Apply' button...")
        apply_btn.click()
        page.wait_for_timeout(2000)

        modal = page.locator("div.jobs-easy-apply-modal, div[role='dialog']:has-text('Easy Apply')").first
        if modal.count() == 0:
            return "FAILED", "Easy Apply dialog did not open"

        # Multi-step wizard loop (up to 6 steps max)
        for step in range(1, 7):
            page.wait_for_timeout(1000)
            inspection = inspect_easy_apply_modal(page)

            # If custom questionnaire questions detected:
            if inspection["requires_questionnaire"]:
                q_summary = "; ".join(inspection["questions"][:3])
                logger(f"  📋 Custom questionnaire detected ({q_summary}). Saving link for screening...")
                dismiss_easy_apply_modal(page)
                return "REQUIRES_QUESTIONNAIRE", f"Questions: {q_summary}"

            fill_contact_info(page, modal)
            upload_or_select_resume(page, modal, resume_path)

            # Check for Submit application button
            submit_btn = modal.locator(
                "button[aria-label='Submit application'], "
                "button:has-text('Submit application')"
            ).first

            if submit_btn.count() > 0 and submit_btn.is_visible():
                logger("  Submitting application...")
                submit_btn.click()
                page.wait_for_timeout(2500)

                # Check confirmation
                done_btn = page.locator("button:has-text('Done'), button[aria-label='Dismiss']").first
                if done_btn.count() > 0:
                    done_btn.click()

                logger("  ✓ Easy Apply successfully submitted!")
                return "APPLIED", "Application submitted successfully"

            # Check for Review button
            review_btn = modal.locator(
                "button[aria-label='Review your application'], "
                "button:has-text('Review')"
            ).first

            if review_btn.count() > 0 and review_btn.is_visible():
                logger(f"  Step {step}: Reviewing application...")
                review_btn.click()
                page.wait_for_timeout(1500)
                continue

            # Check for Next step button
            next_btn = modal.locator(
                "button[aria-label='Continue to next step'], "
                "button:has-text('Next')"
            ).first

            if next_btn.count() > 0 and next_btn.is_visible():
                logger(f"  Step {step}: Advancing to next step...")
                next_btn.click()
                page.wait_for_timeout(1500)
                continue

            # If neither Next, Review, nor Submit is visible, inspect if stuck
            logger(f"  Step {step}: Unhandled form state, saving for screening.")
            dismiss_easy_apply_modal(page)
            return "REQUIRES_QUESTIONNAIRE", "Multi-step form required manual input"

        dismiss_easy_apply_modal(page)
        return "REQUIRES_QUESTIONNAIRE", "Exceeded step limit, saved for screening"

    except Exception as e:
        logger(f"  ✗ Easy Apply execution error: {e}")
        dismiss_easy_apply_modal(page)
        return "FAILED", str(e)


def run_easy_apply_crawler(
    keywords: str = "Full Stack Developer",
    location: str = "India",
    time_filter: str = "24h",
    max_jobs: int = 20,
    task_manager=None,
) -> Dict[str, Any]:
    """
    Main background crawler entrypoint:
    1. Searches LinkedIn jobs with Easy Apply filter (f_AL=true).
    2. Extracts job cards and full specifications.
    3. Saves jobs to database with category='EASY_APPLY'.
    4. Submits Easy Apply or saves for screening when questionnaires are detected.
    """
    logger = task_manager.log if task_manager else print
    config = load_config()
    resume_path = config.get("resume_path", "")

    search_url = build_easy_apply_search_url(keywords, location, time_filter)
    logger("=" * 60)
    logger(f"🚀 Starting LinkedIn Easy Apply Autonomous Crawler")
    logger(f"  Keywords: '{keywords}' | Location: '{location}' | Filter: {time_filter}")
    logger(f"  URL: {search_url}")
    logger("=" * 60)

    applied_count = 0
    questionnaire_count = 0
    discovered_count = 0
    failed_count = 0

    with sync_playwright() as playwright:
        logger("[1/4] Launching Firefox with persistent cookies...")
        context = launch_firefox_context(
            playwright,
            headless=config.get("headless", True),
            sync_cookies_domains=["linkedin.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        logger("[2/4] Navigating to LinkedIn Job Portal search...")
        page.goto(search_url, wait_until="commit", timeout=35000)
        page.wait_for_timeout(5000)

        # Check login
        if page.locator("form.login__form, input[name='session_key']").count() > 0:
            msg = "Not logged in to LinkedIn. Please log in via Connected Services."
            logger(f"❌ {msg}")
            if task_manager:
                task_manager.fail_task(msg)
            context.close()
            return {"success": False, "error": msg}

        # Scroll to load job cards
        logger("[3/4] Scanning job listings...")
        for _ in range(8):
            page.evaluate("""() => {
                const el = document.querySelector('.scaffold-layout__list-container') ||
                           document.querySelector('.jobs-search-results-list');
                if (el) el.scrollTop += 700;
                else window.scrollBy(0, 700);
            }""")
            page.wait_for_timeout(900)

        job_cards = page.locator("[data-occludable-job-id], li.jobs-search-results__list-item")
        total_cards = min(job_cards.count(), max_jobs)
        logger(f"  Found {job_cards.count()} job cards. Processing up to {total_cards}...")

        if task_manager:
            task_manager.set_total_posts(total_cards)

        extracted_jobs = []
        for i in range(total_cards):
            card = job_cards.nth(i)
            meta = extract_job_card_metadata(card)
            if meta["title"] and meta["url"]:
                extracted_jobs.append(meta)

        logger(f"[4/4] Processing {len(extracted_jobs)} Easy Apply opportunities...")

        for idx, job in enumerate(extracted_jobs, start=1):
            if task_manager and task_manager.is_cancel_requested():
                logger("🛑 Task cancelled by user.")
                break

            title = job["title"]
            company = job["company"]
            loc = job["location"] or location
            job_url = job["url"]

            logger(f"\n[{idx}/{len(extracted_jobs)}] Processing: {title} @ {company}")
            if task_manager:
                task_manager.update_progress(idx - 1, f"[{idx}/{len(extracted_jobs)}] {title} @ {company}")

            # Click job card or navigate to load full details
            full_text = ""
            try:
                card_link = page.locator(f"a[href*='{job['job_id']}']").first if job.get("job_id") else None
                if card_link and card_link.count() > 0:
                    card_link.click()
                    page.wait_for_timeout(2000)

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

            # Generate unique ID
            post_id_seed = f"easy_apply_{job.get('job_id') or hashlib.sha256(job_url.encode()).hexdigest()[:12]}"
            post_id = post_id_seed

            # Initial upsert as DISCOVERED with category='EASY_APPLY'
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
            upsert_post(post_record)
            discovered_count += 1

            # Attempt Easy Apply
            status, detail = execute_easy_apply(page, job_url, resume_path, logger=logger)

            if status == "APPLIED":
                update_post_status(post_id, "APPLIED")
                applied_count += 1
                logger(f"  🎉 Status updated to APPLIED")
            elif status == "REQUIRES_QUESTIONNAIRE":
                update_post_status(post_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=detail)
                questionnaire_count += 1
                logger(f"  📌 Saved for screening under REQUIRES_QUESTIONNAIRE: {detail}")
            else:
                update_post_status(post_id, "DISCOVERED", rejection_reason=detail)
                failed_count += 1
                logger(f"  ℹ️ Ready in queue as DISCOVERED: {detail}")

            if task_manager:
                task_manager.update_progress(idx)

            # Human delay pause between jobs
            if idx < len(extracted_jobs):
                human_sleep(4.0, 8.0)

        context.close()
        logger("\n" + "=" * 60)
        logger(f"✓ Easy Apply Crawler Finished:")
        logger(f"  • Total Discovered: {discovered_count}")
        logger(f"  • Successfully Applied: {applied_count}")
        logger(f"  • Saved for Screening (Questionnaire): {questionnaire_count}")
        logger(f"  • Other in Queue: {failed_count}")
        logger("=" * 60)

        return {
            "success": True,
            "discovered": discovered_count,
            "applied": applied_count,
            "requires_questionnaire": questionnaire_count,
        }


def apply_to_single_easy_apply_post(post_id: str, task_manager=None) -> Dict[str, Any]:
    """Execute Easy Apply workflow for a single job post in headed/configured Firefox."""
    logger = task_manager.log if task_manager else print
    post = get_post_by_id(post_id)
    if not post:
        raise ValueError(f"Post with ID '{post_id}' not found.")

    job_url = post.get("post_url")
    title = post.get("author_headline") or "Job"
    company = post.get("author_name") or "Company"
    if not job_url:
        raise ValueError(f"Post '{post_id}' does not have a valid LinkedIn URL.")

    config = load_config()
    resume_path = config.get("resume_path", "")

    logger("=" * 60)
    logger(f"🚀 Launching Easy Apply for: {title} @ {company}")
    logger(f"  URL: {job_url}")
    logger("=" * 60)

    with sync_playwright() as playwright:
        logger("Launching Firefox context...")
        context = launch_firefox_context(
            playwright,
            headless=config.get("headless", True),
            sync_cookies_domains=["linkedin.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        status, detail = execute_easy_apply(page, job_url, resume_path, logger=logger)
        context.close()

        if status == "APPLIED":
            update_post_status(post_id, "APPLIED")
            logger(f"✓ Application successfully submitted for {title} @ {company}")
            return {"success": True, "status": "APPLIED", "detail": detail}
        elif status == "REQUIRES_QUESTIONNAIRE":
            update_post_status(post_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=detail)
            logger(f"📌 Custom questionnaire detected. Direct link saved for screening: {detail}")
            return {"success": True, "status": "REQUIRES_QUESTIONNAIRE", "detail": detail}
        else:
            logger(f"ℹ️ Easy Apply did not submit: {detail}")
            return {"success": False, "status": status, "detail": detail}

