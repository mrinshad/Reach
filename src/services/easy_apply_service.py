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
from src.db.question_bank import lookup_answer_for_question, upsert_screening_question
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


def human_sleep(min_s: float = 1.5, max_s: float = 3.0, cancel_check=None):
    """Sleep for random human-like pacing with optional cancellation check."""
    target = random.uniform(min_s, max_s)
    if cancel_check is None:
        time.sleep(target)
    else:
        elapsed = 0.0
        while elapsed < target:
            if cancel_check():
                break
            step = min(1.0, target - elapsed)
            time.sleep(step)
            elapsed += step


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

    # Canonical clean URL
    if job_id:
        clean_url = f"{LINKEDIN_BASE}/jobs/view/{job_id}/"
    else:
        clean_url = href.split("?")[0] if href else ""

    return {
        "job_id": job_id,
        "title": title,
        "company": company or "Unknown Company",
        "location": location,
        "url": clean_url,
    }


def inspect_easy_apply_modal(page: Page) -> Dict[str, Any]:
    """
    Inspect the Easy Apply modal dialog for multi-step questions and determine
    if it can be auto-submitted or if it requires custom questionnaire answers.
    Collects all questions including basic profile questions (phone, email, etc.).
    """
    questions = []
    custom_questions = []

    # Filter out pure UI chrome / non-questions
    standard_skip = [
        "select language", "search", "photo", "terms", "agree", "privacy", "drag and drop", "upload resume"
    ]
    
    # Common standard profile items that LinkedIn usually auto-fills from user account
    basic_profile_terms = [
        "first name", "last name", "phone", "mobile", "email", "resume",
        "country code", "contact info", "headline", "summary"
    ]

    def add_question(raw_label: str):
        cleaned = raw_label.strip()
        if not cleaned or len(cleaned) < 2:
            return
        cleaned_low = cleaned.lower()
        if any(skip in cleaned_low for skip in standard_skip):
            return
        if cleaned not in questions:
            questions.append(cleaned)
        # Check if it is a custom question (not auto-filled standard basic info)
        is_basic = any(b in cleaned_low for b in basic_profile_terms)
        if not is_basic and cleaned not in custom_questions:
            custom_questions.append(cleaned)

    # Check visible form labels
    try:
        labels = page.locator("label:visible").all()
        for l in labels:
            try:
                txt = l.inner_text().strip()
                add_question(txt)
            except Exception:
                pass
    except Exception:
        pass

    # Check visible inputs, selects, and textareas with custom aria labels
    try:
        inputs = page.locator("input:visible, select:visible, textarea:visible").all()
        for inp in inputs:
            try:
                aria = inp.get_attribute("aria-label") or inp.get_attribute("placeholder") or ""
                add_question(aria)
            except Exception:
                pass
    except Exception:
        pass

    # Check fieldsets / radio groups
    try:
        radio_groups = page.locator("fieldset:visible").all()
        for rg in radio_groups:
            try:
                legend = rg.locator("legend")
                if legend.count() > 0:
                    ltxt = legend.first.inner_text().strip()
                    add_question(ltxt)
            except Exception:
                pass
    except Exception:
        pass

    requires_questionnaire = len(custom_questions) > 0
    return {
        "has_modal": True,
        "requires_questionnaire": requires_questionnaire,
        "questions": questions,
        "custom_questions": custom_questions,
    }


def check_linkedin_rate_limit(page: Page) -> Optional[str]:
    """
    Check if LinkedIn has displayed an automated activity or fast pace rate limit warning.
    Returns a safeguard message if detected, or None.
    """
    rate_limit_keywords = [
        "applying at a fast pace",
        "briefly paused easy apply",
        "safeguard against automated",
        "automated inauthentic activities",
        "risk of restriction",
        "paused easy apply",
        "unusual activity from your account",
    ]
    try:
        body_text = page.locator("body").inner_text(timeout=2000)
        body_lower = body_text.lower()
        for kw in rate_limit_keywords:
            if kw in body_lower:
                return "LinkedIn Safeguard: Easy Apply briefly paused due to fast pace. Automation halted to protect account."
    except Exception:
        pass
    return None


def dismiss_easy_apply_modal(page: Page):
    """Safely dismiss and discard an open Easy Apply modal without saving partial drafts."""
    try:
        dismiss_btn = page.locator("button[aria-label='Dismiss'], button.artdeco-modal__dismiss").first
        if dismiss_btn.count() > 0 and dismiss_btn.is_visible():
            dismiss_btn.click()
            page.wait_for_timeout(800)

            # Confirm discard dialog if it appears
            discard_btn = page.locator(
                "button[data-control-name='discard_application_confirm_btn'], "
                "button:has-text('Discard')"
            ).first
            if discard_btn.count() > 0 and discard_btn.is_visible():
                discard_btn.click()
                page.wait_for_timeout(600)
    except Exception:
        pass


def fill_contact_info(page: Page):
    """Fill standard contact information if empty using synthetic typing."""
    try:
        phone_input = page.locator("input[type='tel'], input[id*='phone'], input[name*='phone']").first
        if phone_input.count() > 0 and phone_input.is_visible():
            current_val = phone_input.input_value().strip()
            if not current_val:
                phone_input.click()
                phone_input.press_sequentially("9895612423", delay=30)
                page.wait_for_timeout(300)
    except Exception:
        pass

    try:
        city_input = page.locator("input[id*='city'], input[name*='city'], input[placeholder*='city']").first
        if city_input.count() > 0 and city_input.is_visible():
            current_val = city_input.input_value().strip()
            if not current_val:
                city_input.click()
                city_input.press_sequentially("Malappuram", delay=25)
                page.wait_for_timeout(600)
                
                # Explicitly click the floating autocomplete suggestion to close the popover
                options = page.locator("[data-floating-ui-portal] p, [data-floating-ui-portal] li, [data-floating-ui-portal] [role='option'], .basic-typeahead__selectable-list li").all()
                if options:
                    try:
                        options[0].click(timeout=2000)
                    except Exception:
                        city_input.press("ArrowDown")
                        city_input.press("Enter")
                else:
                    city_input.press("ArrowDown")
                    city_input.press("Enter")
                page.wait_for_timeout(300)
    except Exception:
        pass


def upload_or_select_resume(page: Page, resume_path: Optional[str]):
    """Select or upload the resume if requested on the resume step."""
    if not resume_path or not os.path.exists(resume_path):
        return

    try:
        file_input = page.locator("input[type='file']").first
        if file_input.count() > 0:
            file_input.set_input_files(resume_path)
            page.wait_for_timeout(1000)
    except Exception:
        pass


def resolve_field_value(
    prompt: str,
    raw_answer: Optional[str] = None,
    itype: str = "text",
    inputmode: str = "",
    maxlength: Optional[str] = None,
    max_attr: Optional[str] = None,
    pattern: str = "",
    is_dummy_mode: bool = False,
) -> str:
    """
    Resolve and sanitize field values to prevent validation and 'exceeded limit' errors on LinkedIn.
    Supports:
    - Phone / Mobile / Tel: Exactly 10 digits (e.g. '9895612423').
    - Postal code: Exactly 6 digits (e.g. '676505').
    - Years of experience / numeric / notice / salary:
      Extracts clean numbers, handles 'no experience' -> '0', clamps 0..30 for years,
      respects maxlength, and ensures no non-digits are sent to numeric inputs.
    - URLs / portfolios: Valid URL, truncated to maxlength.
    - City / location: Clean string, truncated to maxlength.
    - Generic text / textareas: Clean short string, truncated to maxlength.
    - Compliant placeholder values when is_dummy_mode=True to allow advancing through multi-step forms.
    """
    p_low = (prompt or "").lower().strip()
    ans = (raw_answer or "").strip() if raw_answer is not None else ""
    itype_low = (itype or "text").lower().strip()
    imode_low = (inputmode or "").lower().strip()

    max_len = None
    if maxlength:
        try:
            max_len = int(maxlength)
        except Exception:
            pass

    max_val = None
    if max_attr:
        try:
            max_val = int(max_attr)
        except Exception:
            pass

    # 1. Phone / Tel / Mobile (10 digits)
    if itype_low == "tel" or any(k in p_low for k in ["phone", "mobile", "contact number", "telephone"]):
        if ans and not is_dummy_mode:
            digits = re.sub(r"\D", "", ans)
            if len(digits) >= 10:
                val = digits[-10:]
            elif digits:
                val = "9895612423"
            else:
                val = "9895612423"
        else:
            val = "9895612423"
        if max_len:
            val = val[:max_len]
        return val

    # 2. Postal / Zip Code (6 digits)
    if any(k in p_low for k in ["postal", "zip", "pin code", "pincode"]):
        if ans and not is_dummy_mode:
            digits = re.sub(r"\D", "", ans)
            val = digits[:6] if digits else "676505"
        else:
            val = "676505"
        if max_len:
            val = val[:max_len]
        return val

    # 3. Numeric / Experience / Notice / Salary / Years
    is_numeric_field = (
        itype_low == "number"
        or imode_low == "numeric"
        or ("[0-9]" in pattern)
        or (max_len is not None and max_len <= 4)
        or any(k in p_low for k in [
            "year", "years", "experience", "how many", "how much", "in days",
            "notice", "notice period", "months", "ctc", "salary", "compensation",
            "lpa", "inr", "pricing execution", "pricing"
        ])
    )

    if is_numeric_field:
        # A. Notice Period
        if "notice" in p_low or "in days" in p_low or "days" in p_low:
            if ans and not is_dummy_mode:
                if any(w in ans.lower() for w in ["immediate", "ready", "0", "zero", "none"]):
                    val = "0"
                else:
                    digits = re.findall(r"\d+", ans)
                    val = digits[0][:3] if digits else "30"
            else:
                val = "30"
            if max_len:
                val = val[:max_len]
            return val

        # B. Salary / CTC / Compensation
        if any(k in p_low for k in ["ctc", "salary", "lpa", "compensation"]):
            if ans and not is_dummy_mode:
                digits = re.findall(r"\d+", ans)
                val = digits[0] if digits else "1200000"
            else:
                val = "1200000"
            if max_len:
                val = val[:max_len]
            return val

        # C. Years of Experience (General or Specific skill like Pricing Execution Engine)
        if any(k in p_low for k in ["year", "experience", "how many", "pricing", "pricing execution"]) or (max_len is not None and max_len <= 3):
            if ans and not is_dummy_mode:
                # Check for explicit negation first: "no experience", "0", "none", "haven't"
                low_ans = ans.lower()
                has_negation = bool(re.search(r"\b(no|none|never|zero|0|fresher|haven't|not\s+have|without)\b", low_ans))
                if has_negation and ("no experience" in low_ans or "0" in low_ans or "none" in low_ans or "without" in low_ans):
                    val = "0"
                else:
                    digits = re.findall(r"\d+", ans)
                    if digits:
                        num = int(digits[0])
                        # Clamp to reasonable range 0..30
                        num = min(max(0, num), 30)
                        val = str(num)
                    else:
                        val = "0"
            else:
                # Compliant small integer dummy to move to next
                val = "2"
            if max_val is not None:
                try:
                    val = str(min(int(val), max_val))
                except Exception:
                    pass
            if max_len:
                val = val[:max_len]
            return val or "0"

        # D. Generic numbers
        if ans and not is_dummy_mode:
            digits = re.findall(r"\d+", ans)
            val = digits[0][:4] if digits else "1"
        else:
            val = "1"
        if max_len:
            val = val[:max_len]
        return val or "1"

    # 4. URL / Website / Portfolio / LinkedIn / GitHub
    if any(k in p_low for k in ["website", "portfolio", "github", "linkedin", "profile link", "url"]) or itype_low == "url":
        if ans and not is_dummy_mode:
            val = ans
        elif "github" in p_low:
            val = "https://github.com/mrinshad"
        elif "linkedin" in p_low:
            val = "https://www.linkedin.com/in/rinshad"
        else:
            val = "https://github.com/mrinshad"
        if max_len:
            val = val[:max_len]
        return val

    # 5. City / Location / Address
    if any(k in p_low for k in ["city", "location", "address", "state"]):
        if ans and not is_dummy_mode:
            val = ans
        else:
            val = "Malappuram"
        if max_len:
            val = val[:max_len]
        return val

    # 6. Generic Text / Textarea
    if ans and not is_dummy_mode:
        val = ans
    else:
        # Compliant dummy string
        if any(p_low.startswith(w) for w in ["are you", "do you", "can you", "will you", "have you", "is"]):
            val = "Yes"
        else:
            val = "Yes"
    if max_len:
        val = val[:max_len]
    return val


def handle_screening_form_step(
    page: Page,
    job_label: Optional[str] = None,
    fill_dummies_to_advance: bool = True,
    logger=print
) -> Dict[str, Any]:
    """
    Inspect the current step of the Easy Apply modal for questionnaire elements:
    - Text and numeric inputs
    - Dropdowns (<select>)
    - Radio button groups (<fieldset>)
    - Checkboxes

    For each element:
    1. Extracts the question prompt.
    2. Checks if the field is already satisfied.
    3. Looks up the answer in the DB Question Bank.
    4. If answered, auto-fills / selects / checks the matching option with sanitized values.
    5. If unanswered:
       - Records the question in PostgreSQL screening_questions with status='PENDING'.
       - If fill_dummies_to_advance=True: fills compliant, properly-typed placeholder values
         (10 digits for phone, small integer for experience, clean string for text, valid option for selects/radios)
         to allow clicking 'Next' and discovering remaining questions across all steps.
    """
    answered = []
    unanswered = []
    filled_placeholders = []

    # Standard items to skip as questions
    standard_skip = [
        "select language", "search", "photo", "terms", "agree", "privacy", "drag and drop", "upload resume"
    ]
    # Basic items already handled by fill_contact_info
    basic_profile_terms = [
        "first name", "last name", "phone", "mobile", "email", "resume",
        "country code", "contact info", "headline", "summary"
    ]

    def is_skip(text: str) -> bool:
        t = (text or "").lower().strip()
        if not t or len(t) < 2:
            return True
        return any(s in t for s in standard_skip)

    # 1. Inspect Fieldsets (Radio Groups)
    try:
        fieldsets = page.locator(".jobs-easy-apply-modal fieldset:visible, div[role='dialog'] fieldset:visible").all()
        for fs in fieldsets:
            try:
                legend_el = fs.locator("legend").first
                prompt = legend_el.inner_text().strip() if legend_el.count() > 0 else ""
                if not prompt or is_skip(prompt):
                    continue

                # Collect available options from radio group
                radio_labels = fs.locator("label, .fb-radio-label, .artdeco-radio-button__label").all()
                extracted_options = []
                for ro in radio_labels:
                    try:
                        txt = ro.inner_text().strip()
                        if txt and len(txt) < 80 and txt not in extracted_options:
                            extracted_options.append(txt)
                    except Exception:
                        pass

                # Check DB Question Bank for answer first
                ans, qdict = lookup_answer_for_question(prompt)
                is_explicit_empty = (ans == "__EMPTY__") or (qdict and qdict.get("status") == "ANSWERED" and not ans)

                if is_explicit_empty:
                    answered.append(f"{prompt} -> (empty)")
                    logger(f"  ✓ Left radio choice empty for '{prompt}' as configured")
                    continue

                clicked = False
                if ans:
                    ans_low = ans.lower().strip()

                    # Exact text match first
                    for opt in radio_labels:
                        opt_txt = opt.inner_text().strip().lower()
                        if opt_txt == ans_low:
                            if opt.locator("input[type='radio']:checked").count() == 0:
                                opt.click()
                            clicked = True
                            break

                    # Substring match if exact didn't match
                    if not clicked:
                        for opt in radio_labels:
                            opt_txt = opt.inner_text().strip().lower()
                            if (opt_txt and opt_txt in ans_low) or (ans_low and ans_low in opt_txt):
                                if opt.locator("input[type='radio']:checked").count() == 0:
                                    opt.click()
                                clicked = True
                                break

                    # Keyword match for Yes / No
                    if not clicked:
                        if any(w in ans_low for w in ["yes", "true", "comfortable", "immediate", "open"]):
                            yes_opt = fs.locator("label:has-text('Yes'), input[value='Yes']").first
                            if yes_opt.count() > 0:
                                yes_opt.click()
                                clicked = True
                        elif any(w in ans_low for w in ["no", "false", "not comfortable"]):
                            no_opt = fs.locator("label:has-text('No'), input[value='No']").first
                            if no_opt.count() > 0:
                                no_opt.click()
                                clicked = True

                    if clicked:
                        answered.append(f"{prompt} -> {ans}")
                        logger(f"  ✓ Radio selected for '{prompt}': {ans}")
                        page.wait_for_timeout(250)
                    else:
                        upsert_screening_question(prompt, sample_job=job_label, options=extracted_options)
                        unanswered.append(prompt)
                else:
                    # No answer in Question Bank
                    checked_count = fs.locator("input[type='radio']:checked").count()
                    is_basic = any(b in prompt.lower() for b in basic_profile_terms)
                    if not is_basic:
                        upsert_screening_question(prompt, sample_job=job_label, options=extracted_options)
                        unanswered.append(prompt)

                    # If still not clicked and dummy mode enabled to advance step
                    if checked_count == 0 and fill_dummies_to_advance:
                        yes_opt = fs.locator("label:has-text('Yes'), input[value='Yes']").first
                        if yes_opt.count() > 0:
                            yes_opt.click()
                            clicked = True
                        elif radio_labels:
                            radio_labels[0].click()
                            clicked = True
                        if clicked:
                            filled_placeholders.append(prompt)
                            logger(f"  ℹ️ Selected compliant placeholder radio for '{prompt}' to advance step")
                            page.wait_for_timeout(250)
            except Exception as e:
                logger(f"  Notice inspecting fieldset: {e}")
    except Exception:
        pass

    # 2. Inspect Dropdowns (<select>)
    try:
        selects = page.locator(".jobs-easy-apply-modal select:visible, div[role='dialog'] select:visible").all()
        for sel in selects:
            try:
                # Find prompt
                sel_id = sel.get_attribute("id") or ""
                prompt = ""
                if sel_id:
                    lbl = page.locator(f"label[for='{sel_id}']").first
                    if lbl.count() > 0:
                        prompt = lbl.inner_text().strip()
                if not prompt:
                    prompt = sel.get_attribute("aria-label") or sel.locator("xpath=preceding::label[1]").inner_text().strip()

                if not prompt or is_skip(prompt):
                    continue

                # Collect dropdown options
                sel_opts = sel.locator("option").all()
                extracted_options = []
                for so in sel_opts:
                    try:
                        txt = so.inner_text().strip()
                        if txt and txt.lower() not in ["", "select", "select an option", "please select"] and len(txt) < 80 and txt not in extracted_options:
                            extracted_options.append(txt)
                    except Exception:
                        pass

                # Check DB Question Bank for answer first
                ans, qdict = lookup_answer_for_question(prompt)
                is_explicit_empty = (ans == "__EMPTY__") or (qdict and qdict.get("status") == "ANSWERED" and not ans)

                if is_explicit_empty:
                    answered.append(f"{prompt} -> (empty)")
                    logger(f"  ✓ Left dropdown empty for '{prompt}' as configured")
                    continue

                matched_opt_val = None
                if ans:
                    ans_low = ans.lower().strip()
                    for opt in sel_opts:
                        otxt = opt.inner_text().strip().lower()
                        oval = (opt.get_attribute("value") or "").strip().lower()
                        if otxt == ans_low or oval == ans_low or (otxt and otxt in ans_low):
                            matched_opt_val = opt.get_attribute("value")
                            break

                    if matched_opt_val is not None:
                        if sel.input_value() != matched_opt_val:
                            sel.select_option(value=matched_opt_val)
                        answered.append(f"{prompt} -> {ans}")
                        logger(f"  ✓ Dropdown selected for '{prompt}': {ans}")
                        page.wait_for_timeout(250)
                    else:
                        upsert_screening_question(prompt, sample_job=job_label, options=extracted_options)
                        unanswered.append(prompt)
                else:
                    # No answer in Question Bank
                    curr_val = sel.input_value()
                    curr_text = sel.locator("option:checked").inner_text().strip() if sel.locator("option:checked").count() > 0 else ""
                    has_selection = curr_val and curr_text.lower() not in ["", "select", "select an option", "please select"]
                    is_basic = any(b in prompt.lower() for b in basic_profile_terms)

                    if not is_basic:
                        upsert_screening_question(prompt, sample_job=job_label, options=extracted_options)
                        unanswered.append(prompt)

                    # Fallback to advance step if unselected
                    if not has_selection and fill_dummies_to_advance:
                        fallback_val = None
                        for opt in sel_opts:
                            otxt = opt.inner_text().strip().lower()
                            oval = (opt.get_attribute("value") or "").strip()
                            if oval and otxt not in ["", "select", "select an option", "please select"]:
                                if "yes" in otxt:
                                    fallback_val = oval
                                    break
                                if fallback_val is None:
                                    fallback_val = oval
                        if fallback_val is not None:
                            sel.select_option(value=fallback_val)
                            filled_placeholders.append(prompt)
                            logger(f"  ℹ️ Selected compliant placeholder dropdown option for '{prompt}' to advance step")
                            page.wait_for_timeout(250)
            except Exception as e:
                logger(f"  Notice inspecting select: {e}")
    except Exception:
        pass

    # 3. Inspect Text, Number, Tel, and Textarea Inputs
    try:
        inputs = page.locator(
            ".jobs-easy-apply-modal input[type='text']:visible, "
            ".jobs-easy-apply-modal input[type='number']:visible, "
            ".jobs-easy-apply-modal input[type='tel']:visible, "
            ".jobs-easy-apply-modal textarea:visible"
        ).all()

        for inp in inputs:
            try:
                itype = (inp.get_attribute("type") or "text").lower()
                if itype in ["radio", "checkbox", "file", "hidden"]:
                    continue

                inp_id = inp.get_attribute("id") or ""
                prompt = ""
                if inp_id:
                    lbl = page.locator(f"label[for='{inp_id}']").first
                    if lbl.count() > 0:
                        prompt = lbl.inner_text().strip()
                if not prompt:
                    prompt = inp.get_attribute("aria-label") or inp.get_attribute("placeholder") or ""

                if not prompt or is_skip(prompt):
                    continue

                # Attributes for strict validation adherence
                inputmode = inp.get_attribute("inputmode") or ""
                maxlength = inp.get_attribute("maxlength") or ""
                max_attr = inp.get_attribute("max") or ""
                pattern = inp.get_attribute("pattern") or ""

                ans, qdict = lookup_answer_for_question(prompt)
                is_explicit_empty = (ans == "__EMPTY__") or (qdict and qdict.get("status") == "ANSWERED" and not ans)

                if is_explicit_empty:
                    if inp.input_value().strip():
                        inp.click()
                        inp.fill("")
                    answered.append(f"{prompt} -> (empty)")
                    logger(f"  ✓ Left input empty for '{prompt}' as configured")
                    page.wait_for_timeout(150)
                    continue

                if ans:
                    fill_val = resolve_field_value(
                        prompt,
                        raw_answer=ans,
                        itype=itype,
                        inputmode=inputmode,
                        maxlength=maxlength,
                        max_attr=max_attr,
                        pattern=pattern,
                        is_dummy_mode=False
                    )
                    curr_val = inp.input_value().strip()
                    if curr_val != fill_val:
                        inp.click()
                        inp.fill("")
                        inp.press_sequentially(fill_val, delay=15)
                    answered.append(f"{prompt} -> {fill_val}")
                    logger(f"  ✓ Filled input for '{prompt}': {fill_val}")
                    page.wait_for_timeout(200)
                else:
                    curr_val = inp.input_value().strip()
                    is_basic = any(b in prompt.lower() for b in basic_profile_terms)

                    # Fix existing overflow if any
                    if curr_val and maxlength and len(curr_val) > int(maxlength):
                        clean_val = curr_val[:int(maxlength)]
                        inp.click()
                        inp.fill("")
                        inp.press_sequentially(clean_val, delay=15)

                    if not is_basic:
                        upsert_screening_question(prompt, sample_job=job_label)
                        unanswered.append(prompt)

                    if not curr_val and fill_dummies_to_advance:
                        fill_val = resolve_field_value(
                            prompt,
                            raw_answer=None,
                            itype=itype,
                            inputmode=inputmode,
                            maxlength=maxlength,
                            max_attr=max_attr,
                            pattern=pattern,
                            is_dummy_mode=True
                        )
                        inp.click()
                        inp.fill("")
                        inp.press_sequentially(fill_val, delay=15)
                        filled_placeholders.append(prompt)
                        logger(f"  ℹ️ Filled placeholder for '{prompt}': {fill_val} to advance step")
                        page.wait_for_timeout(200)
            except Exception as e:
                logger(f"  Notice inspecting input: {e}")
    except Exception:
        pass

    return {
        "can_proceed": True,
        "had_unanswered": len(unanswered) > 0,
        "answered": answered,
        "unanswered": unanswered,
        "filled_placeholders": filled_placeholders,
    }


def execute_easy_apply(
    page: Page,
    job_url: str,
    resume_path: Optional[str],
    logger=print,
    job_label: Optional[str] = None
) -> Tuple[str, str]:
    """
    Attempt to submit an Easy Apply application for a given job URL.
    Auto-fills screening questions from DB Question Bank.
    If unhandled or unanswered questions appear, harvests questions across all steps
    using compliant placeholders to advance without exceeding limits, saves them
    to DB screening_questions with status='PENDING', and safely dismisses the modal
    WITHOUT submitting dummy values.
    Returns (status, detail_message) where status is:
      - 'APPLIED': Successfully submitted
      - 'REQUIRES_QUESTIONNAIRE': Saved for screening due to custom questionnaire
      - 'FAILED': Modal failed to open or encountered an unhandled issue
      - 'ALREADY_APPLIED': LinkedIn indicates you've already applied
      - 'RATE_LIMITED': LinkedIn displayed fast pace safeguard pause notice
    """
    try:
        page.goto(job_url, wait_until="domcontentloaded", timeout=30000)

        # Check for LinkedIn fast pace safeguard notice
        rate_limit_msg = check_linkedin_rate_limit(page)
        if rate_limit_msg:
            logger(f"  🚨 {rate_limit_msg}")
            return "RATE_LIMITED", rate_limit_msg
        
        # Check if already applied
        applied_badge = page.locator(
            ".jobs-s-apply__status--applied, "
            ".artdeco-inline-feedback--success, "
            ".jobs-apply-button--disabled, "
            "button:has-text('Applied')"
        )
        if applied_badge.count() > 0:
            logger("  ℹ️ Already applied to this position on LinkedIn.")
            return "APPLIED", "Already applied previously on LinkedIn"

        # Wait for Easy Apply button
        try:
            page.wait_for_selector(
                "button:has-text('Easy Apply'), [aria-label*='Easy Apply'], button.jobs-apply-button",
                timeout=7000
            )
        except Exception:
            pass

        apply_btn = page.locator(
            "button:has-text('Easy Apply'), "
            "[aria-label*='Easy Apply'], "
            "button.jobs-apply-button"
        ).first

        if apply_btn.count() == 0 or not apply_btn.is_visible():
            if page.locator("button:has-text('Applied')").count() > 0:
                logger("  ℹ️ Already applied to this position on LinkedIn.")
                return "APPLIED", "Already applied previously on LinkedIn"
            logger("  ⚠️ No Easy Apply button found on page.")
            return "FAILED", "No Easy Apply button visible"

        logger("  Clicking 'Easy Apply' button...")
        apply_btn.click()
        try:
            page.wait_for_selector(
                "button:has-text('Next'), button:has-text('Submit'), button:has-text('Review'), input[type='tel'], input[type='text']",
                timeout=9000
            )
        except Exception:
            page.wait_for_timeout(3000)

        # Check rate limit right after opening dialog
        rate_limit_msg = check_linkedin_rate_limit(page)
        if rate_limit_msg:
            logger(f"  🚨 {rate_limit_msg}")
            dismiss_easy_apply_modal(page)
            return "RATE_LIMITED", rate_limit_msg

        dismiss_btn = page.locator("button[aria-label='Dismiss'], button.artdeco-modal__dismiss").first
        if dismiss_btn.count() == 0:
            logger("  ⚠️ Easy Apply dialog did not open.")
            return "FAILED", "Easy Apply dialog did not open"

        all_unanswered_questions: List[str] = []
        had_unanswered = False

        # Multi-step wizard loop (up to 8 steps max)
        for step in range(1, 9):
            # Check rate limit on each step
            rate_limit_msg = check_linkedin_rate_limit(page)
            if rate_limit_msg:
                logger(f"  🚨 {rate_limit_msg}")
                dismiss_easy_apply_modal(page)
                return "RATE_LIMITED", rate_limit_msg

            # Wait for content or step transition to stabilize
            try:
                page.wait_for_selector(
                    "button:has-text('Next'), button:has-text('Submit'), button:has-text('Review')",
                    timeout=5000
                )
            except Exception:
                page.wait_for_timeout(1500)

            # Auto-fill standard contact info
            fill_contact_info(page)
            upload_or_select_resume(page, resume_path)

            # Check and auto-fill custom screening questions on this step
            screening_result = handle_screening_form_step(
                page, job_label=job_label, fill_dummies_to_advance=True, logger=logger
            )
            if screening_result.get("unanswered"):
                for uq in screening_result["unanswered"]:
                    if uq not in all_unanswered_questions:
                        all_unanswered_questions.append(uq)
                had_unanswered = True

            if screening_result.get("answered"):
                ans_list = screening_result["answered"]
                logger(f"  ✓ Step {step}: Auto-filled {len(ans_list)} screening question(s) from Question Bank")

            # Check and resolve any inline feedback errors (e.g. exceeded limit or invalid format)
            try:
                err_inputs = page.locator(".jobs-easy-apply-modal input.artdeco-inline-feedback--error, .jobs-easy-apply-modal [data-test-form-element-error-messages]").all()
                for err_el in err_inputs:
                    try:
                        inp_box = err_el.locator("xpath=preceding::input[1]").first
                        if inp_box.count() > 0:
                            inp_box.click()
                            inp_box.fill("0")
                    except Exception:
                        pass
            except Exception:
                pass

            # Natural human pause before next action
            page.wait_for_timeout(random.randint(1000, 1800))

            # Check for Submit application button
            submit_btn = page.locator(
                "button[aria-label='Submit application'], "
                "button:has-text('Submit application'), "
                "button:has-text('Submit')"
            ).first

            if submit_btn.count() > 0:
                try:
                    submit_btn.scroll_into_view_if_needed()
                except Exception:
                    pass
                if submit_btn.is_visible():
                    # CRITICAL SAFETY GUARD: If application contained unanswered questions that were
                    # filled with placeholders to traverse steps, DO NOT SUBMIT TO RECRUITER.
                    if had_unanswered or len(all_unanswered_questions) > 0:
                        q_summary = "; ".join(all_unanswered_questions)
                        logger(f"  📋 Successfully traversed all steps and cataloged {len(all_unanswered_questions)} screening question(s): {q_summary}")
                        logger("  🛑 Dismissing modal without submitting to protect applicant integrity. Questions saved to Question Bank.")
                        dismiss_easy_apply_modal(page)
                        return "REQUIRES_QUESTIONNAIRE", f"Questions: {q_summary}"

                    logger("  Submitting application...")
                    try:
                        submit_btn.click(timeout=5000)
                    except Exception:
                        submit_btn.click(force=True, timeout=5000)
                    page.wait_for_timeout(2500)

                    # Check confirmation
                    done_btn = page.locator("button:has-text('Done'), button[aria-label='Dismiss']").first
                    if done_btn.count() > 0 and done_btn.is_visible():
                        done_btn.click()

                    logger("  ✓ Easy Apply successfully submitted!")
                    return "APPLIED", "Application submitted successfully"

            # Check for Review button
            review_btn = page.locator(
                "button[aria-label='Review your application'], "
                "button:has-text('Review')"
            ).first

            if review_btn.count() > 0:
                try:
                    review_btn.scroll_into_view_if_needed()
                except Exception:
                    pass
                if review_btn.is_visible():
                    logger(f"  Step {step}: Reviewing application...")
                    try:
                        review_btn.click(timeout=5000)
                    except Exception:
                        review_btn.click(force=True, timeout=5000)
                    page.wait_for_timeout(random.randint(1500, 2500))
                    continue

            # Check for Next step button
            next_btn = page.locator(
                "button[aria-label='Continue to next step'], "
                "button:has-text('Next')"
            ).first

            if next_btn.count() > 0:
                try:
                    next_btn.scroll_into_view_if_needed()
                except Exception:
                    pass
                if next_btn.is_visible():
                    logger(f"  Step {step}: Advancing to next step...")
                    try:
                        next_btn.click(timeout=5000)
                    except Exception:
                        next_btn.click(force=True, timeout=5000)
                    page.wait_for_timeout(random.randint(1500, 2500))
                    continue

            # If neither Next, Review, nor Submit is visible, inspect if stuck
            inspection = inspect_easy_apply_modal(page)
            all_q = inspection["questions"] or inspection["custom_questions"]
            if all_q:
                for q in all_q:
                    upsert_screening_question(q, sample_job=job_label)
                    if q not in all_unanswered_questions:
                        all_unanswered_questions.append(q)
            q_summary = "; ".join(all_unanswered_questions) if all_unanswered_questions else "Multi-step form required manual input"
            logger(f"  Step {step}: Multi-step questionnaire saved for screening ({q_summary}).")
            dismiss_easy_apply_modal(page)
            return "REQUIRES_QUESTIONNAIRE", f"Questions: {q_summary}"

        inspection = inspect_easy_apply_modal(page)
        all_q = inspection["questions"] or inspection["custom_questions"]
        if all_q:
            for q in all_q:
                upsert_screening_question(q, sample_job=job_label)
                if q not in all_unanswered_questions:
                    all_unanswered_questions.append(q)
        q_summary = "; ".join(all_unanswered_questions) if all_unanswered_questions else "Questions: Screening Questionnaire required"
        dismiss_easy_apply_modal(page)
        return "REQUIRES_QUESTIONNAIRE", f"Questions: {q_summary}"

    except Exception as e:
        logger(f"  ✗ Easy Apply execution error: {e}")
        dismiss_easy_apply_modal(page)
        return "FAILED", str(e)


def run_easy_apply_crawler(
    keywords: str = "Full Stack Developer",
    location: str = "India",
    time_filter: str = "24h",
    max_jobs: int = 20,
    cycles: Optional[int] = 8,
    pacing: Optional[str] = "safe",
    task_manager=None,
) -> Dict[str, Any]:
    """
    Main background crawler entrypoint:
    1. Searches LinkedIn jobs with Easy Apply filter (f_AL=true).
    2. Extracts job cards and full specifications with dynamic scroll cycles.
    3. Saves jobs to database with category='EASY_APPLY'.
    4. Submits Easy Apply with human safe pacing or saves for screening when questionnaires are detected.
    5. Aborts immediately if LinkedIn displays fast pace safeguard warnings.
    """
    logger = task_manager.log if task_manager else print
    config = load_config()
    resume_path = config.get("resume_path", "")

    scroll_cycles = int(cycles) if cycles and int(cycles) > 0 else 8
    pacing_mode = (pacing or "safe").lower()

    search_url = build_easy_apply_search_url(keywords, location, time_filter)
    logger("=" * 60)
    logger(f"🚀 Starting LinkedIn Easy Apply Autonomous Crawler")
    logger(f"  Keywords: '{keywords}' | Location: '{location}' | Filter: {time_filter}")
    logger(f"  Discovery Cycles: {scroll_cycles} | Pacing Mode: {pacing_mode}")
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

        # Scroll to load job cards based on manual/dynamic cycles
        logger(f"[3/4] Scanning job listings ({scroll_cycles} discovery cycles)...")
        for cycle_idx in range(scroll_cycles):
            logger(f"  [Cycle {cycle_idx + 1}/{scroll_cycles}] Scrolling job listings container...")
            page.evaluate("""() => {
                const el = document.querySelector('.scaffold-layout__list-container') ||
                           document.querySelector('.jobs-search-results-list');
                if (el) el.scrollTop += 700;
                else window.scrollBy(0, 700);
            }""")
            page.wait_for_timeout(950)

        job_cards = page.locator("[data-occludable-job-id], li.jobs-search-results__list-item")
        total_cards = min(job_cards.count(), max_jobs)
        logger(f"  Found {job_cards.count()} job cards across {scroll_cycles} cycles. Processing up to {total_cards}...")

        if task_manager and hasattr(task_manager, "set_total_posts"):
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
            status, detail = execute_easy_apply(
                page, job_url, resume_path, logger=logger, job_label=f"{title} @ {company}"
            )

            if status == "APPLIED":
                update_post_status(post_id, "APPLIED")
                applied_count += 1
                logger(f"  🎉 Status updated to APPLIED")
            elif status == "RATE_LIMITED":
                from src.db.settings import set_setting
                # Pause Easy Apply and alert
                set_setting("easy_apply_paused_until", str(int(time.time() + 3600)))
                set_setting("easy_apply_safeguard_reason", detail)
                logger(f"  🚨 {detail}")
                logger("  🛑 LinkedIn safeguard pause detected. Halting crawl immediately to protect your account.")
                if task_manager:
                    task_manager.fail_task(detail)
                break
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

            # Safe human delay pause between jobs to protect against rate limits
            if idx < len(extracted_jobs):
                cancel_fn = task_manager.is_cancel_requested if task_manager else None
                if pacing_mode == "slow":
                    logger(f"  ⏳ Extra slow pacing safeguard: Pausing 75–120 seconds before next job...")
                    human_sleep(75.0, 120.0, cancel_check=cancel_fn)
                elif pacing_mode == "standard":
                    logger(f"  ⏳ Moderate pacing: Pausing 30–45 seconds before next job...")
                    human_sleep(30.0, 45.0, cancel_check=cancel_fn)
                else:  # safe (default)
                    logger(f"  ⏳ Safe human pacing safeguard: Pausing 45–75 seconds before next job...")
                    human_sleep(45.0, 75.0, cancel_check=cancel_fn)

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

        status, detail = execute_easy_apply(
            page, job_url, resume_path, logger=logger, job_label=f"{title} @ {company}"
        )
        context.close()

        if status == "APPLIED":
            update_post_status(post_id, "APPLIED", rejection_reason="")
            logger(f"✓ Application successfully submitted for {title} @ {company}")
            return {"success": True, "status": "APPLIED", "detail": detail}
        elif status == "RATE_LIMITED":
            from src.db.settings import set_setting
            set_setting("easy_apply_paused_until", str(int(time.time() + 3600)))
            set_setting("easy_apply_safeguard_reason", detail)
            logger(f"🚨 {detail}")
            return {"success": False, "status": "RATE_LIMITED", "detail": detail}
        elif status == "REQUIRES_QUESTIONNAIRE":
            update_post_status(post_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=detail)
            logger(f"📌 Custom questionnaire detected. Direct link saved for screening: {detail}")
            return {"success": True, "status": "REQUIRES_QUESTIONNAIRE", "detail": detail}
        else:
            logger(f"ℹ️ Easy Apply did not submit: {detail}")
            return {"success": False, "status": status, "detail": detail}


def apply_to_batch_easy_apply_posts(
    post_ids: List[str],
    pacing: str = "safe",
    task_manager: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Sequentially run Easy Apply submissions for a batch of posts using a single persistent Firefox session.
    Auto-fills screening questions from Question Bank, submits applications when all questions are answered,
    and paces requests with safe human delays.
    """
    total = len(post_ids)
    if total == 0:
        return {"success": True, "total": 0, "applied": 0, "questionnaire": 0, "failed": 0}

    logger = task_manager.log if task_manager else print

    if is_cooldown_active():
        msg = "LinkedIn Easy Apply is currently paused due to rate-limit safeguard cooldown."
        logger(f"🚨 {msg}")
        if task_manager:
            task_manager.fail_task(msg)
        return {"success": False, "status": "RATE_LIMITED", "detail": msg}

    config = load_config()
    resume_path = config.get("resume_path", "")
    headless = config.get("headless", True)

    applied_count = 0
    questionnaire_count = 0
    failed_count = 0

    if task_manager:
        task_manager.start_task(f"Batch Easy Apply ({total} jobs)", total_items=total)

    logger("=" * 60)
    logger(f"🚀 Launching Batch Easy Apply for {total} job(s) in Firefox (pacing={pacing})")
    logger("=" * 60)

    with sync_playwright() as playwright:
        logger("Launching Firefox persistent context...")
        context = launch_firefox_context(
            playwright,
            headless=headless,
            sync_cookies_domains=["linkedin.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        for idx, post_id in enumerate(post_ids, 1):
            if task_manager and task_manager.is_cancel_requested():
                logger("🛑 Batch Easy Apply stopped upon user request.")
                break

            post = get_post_by_id(post_id)
            if not post:
                logger(f"⚠️ Post '{post_id}' not found in database, skipping.")
                failed_count += 1
                continue

            job_url = post.get("post_url")
            title = post.get("author_headline") or f"Job #{post_id[:8]}"
            company = post.get("author_name") or "Company"

            if not job_url:
                logger(f"⚠️ Post '{post_id}' does not have a valid LinkedIn URL, skipping.")
                failed_count += 1
                continue

            logger("\n" + "-" * 50)
            logger(f"[{idx}/{total}] Processing Easy Apply: {title} @ {company}")
            logger(f"  URL: {job_url}")

            status, detail = execute_easy_apply(
                page, job_url, resume_path, logger=logger, job_label=f"{title} @ {company}"
            )

            if status == "APPLIED":
                update_post_status(post_id, "APPLIED", rejection_reason="")
                applied_count += 1
                logger(f"  🎉 Application successfully submitted! Status -> APPLIED")
            elif status == "RATE_LIMITED":
                from src.db.settings import set_setting
                set_setting("easy_apply_paused_until", str(int(time.time() + 3600)))
                set_setting("easy_apply_safeguard_reason", detail)
                logger(f"  🚨 Safeguard rate-limit triggered: {detail}")
                if task_manager:
                    task_manager.fail_task(detail)
                break
            elif status == "REQUIRES_QUESTIONNAIRE":
                update_post_status(post_id, "REQUIRES_QUESTIONNAIRE", rejection_reason=detail)
                questionnaire_count += 1
                logger(f"  📌 Saved for screening under REQUIRES_QUESTIONNAIRE: {detail}")
            else:
                failed_count += 1
                logger(f"  ℹ️ Application did not submit: {detail}")

            if task_manager:
                task_manager.update_progress(idx)

            # Safe human delay between applications
            if idx < total:
                cancel_fn = task_manager.is_cancel_requested if task_manager else None
                if pacing == "slow":
                    logger("  ⏳ Extra slow pacing safeguard: Pausing 75–120s before next job...")
                    human_sleep(75.0, 120.0, cancel_check=cancel_fn)
                elif pacing == "standard":
                    logger("  ⏳ Moderate pacing: Pausing 25–40s before next job...")
                    human_sleep(25.0, 40.0, cancel_check=cancel_fn)
                else:  # safe (default)
                    logger("  ⏳ Safe human pacing safeguard: Pausing 40–70s before next job...")
                    human_sleep(40.0, 70.0, cancel_check=cancel_fn)

        context.close()

    logger("\n" + "=" * 60)
    logger(f"✨ Batch Easy Apply completed: {applied_count} submitted, {questionnaire_count} need questionnaire answers, {failed_count} skipped/failed.")
    logger("=" * 60)

    return {
        "success": True,
        "total": total,
        "applied": applied_count,
        "questionnaire": questionnaire_count,
        "failed": failed_count,
    }


