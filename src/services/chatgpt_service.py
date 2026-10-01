"""
ChatGPT Custom GPT Automation Service

Interacts with the user's dedicated custom GPT conversation:
- Navigates to conversation
- Types raw JD text into ProseMirror editor (#prompt-textarea)
- Sends prompt and waits for streaming completion
- Extracts and parses the cold outreach email (Subject + Body)
"""

import re
import time
from typing import Tuple, Optional
from playwright.sync_api import Page

def get_default_chatgpt_url() -> str:
    """Retrieve custom GPT URL from database settings, falling back to config."""
    try:
        from src.db import get_setting
        val = get_setting("chatgpt_url")
        if val:
            return val
    except Exception:
        pass
    try:
        from src.config import load_config
        val = load_config().get("chatgpt_url")
        if val:
            return val
    except Exception:
        pass
    return "https://chatgpt.com"


def navigate_to_conversation(page: Page, url: Optional[str] = None, timeout: int = 30000):
    """Navigate to the dedicated custom GPT conversation and ensure ready state."""
    target_url = url or get_default_chatgpt_url()
    if not target_url or "example-chat-id" in target_url:
        raise ValueError(
            "ChatGPT Custom GPT URL is not configured. Please set your Custom GPT Chat Link in Settings or PostgreSQL."
        )
    print(f"Opening ChatGPT conversation...")
    page.goto(target_url, wait_until="commit", timeout=timeout)
    page.wait_for_timeout(5000)

    # Verify login
    login_btn = page.locator("button:has-text('Log in')")
    if login_btn.count() > 0 and login_btn.first.is_visible():
        raise RuntimeError("Not logged in to ChatGPT! Please log in manually in the Firefox window.")

    # Wait for prompt textarea
    page.wait_for_selector("#prompt-textarea", timeout=20000)
    print("✓ ChatGPT conversation loaded and prompt box ready.")


def is_unsuitable_response(raw_text: str) -> bool:
    """Check if ChatGPT returned an unsuitable / skip / non-engineering classification."""
    if not raw_text:
        return False
    t = raw_text.strip().lower()
    return bool(
        "unsuitable_jd" in t
        or t.startswith("not suitable")
        or "❌ not suitable" in t
        or "not suitable —" in t
        or "not suitable -" in t
        or "→ skip" in t
        or "-> skip" in t
        or ("classification:" in t and "skip" in t)
        or "recommendation: skip" in t
        or "not a software engineering" in t
        or "not a software developer" in t
        or "i'd skip this one" in t
        or "skip this one" in t
    )


def parse_email_response(raw_text: str) -> Tuple[str, str]:
    """
    Parse a ChatGPT generated application response into (subject, body).
    """
    if not raw_text:
        return "", ""

    clean_text = raw_text.strip()

    # Detect if ChatGPT reported the JD as unsuitable or skip
    if is_unsuitable_response(clean_text):
        return "UNSUITABLE_JD", clean_text

    # Strip conversational lead-ins or boilerplate labels like "Email\n\n", "Email Draft:\n\n"
    clean_text = re.sub(
        r"^(?:(?:Here(?:'s| is) (?:the )?(?:cold outreach )?email(?:\s+draft)?:?)|(?:Email(?:\s+Draft)?[:\s]*))\n+",
        "",
        clean_text,
        flags=re.IGNORECASE,
    ).strip()

    lines = clean_text.split("\n")
    subject = ""
    body_lines = []
    found_subject = False

    for line in lines:
        match = re.match(r"^(?:\*\*)?Subject(?:\*\*)?:\s*(.+)$", line.strip(), re.IGNORECASE)
        if match and not found_subject:
            subject = match.group(1).replace("**", "").strip()
            found_subject = True
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    # Strip any residual leading "Email\n\n" or "Subject:\n"
    body = re.sub(r"^(?:Email(?:\s+Draft)?[:\s]*\n+)+", "", body, flags=re.IGNORECASE).strip()

    if not subject:
        # Try extracting role from first sentence (e.g. "I'm writing to apply for the Full Stack Developer L2 position in Mumbai")
        role_match = re.search(r"apply(?:ing)? for the\s+([^,\.\n]+?)(?:\s+position|\s+role|\.|\n|$)", body, re.IGNORECASE)
        if role_match:
            extracted_role = role_match.group(1).strip()
            subject = f"Application for {extracted_role}"
        else:
            subject = "Application for Full Stack Developer"

    return subject, body


def is_direct_hiring_post(text: str) -> bool:
    """
    Check if the text contains clear markers of a direct recruiter/employer hiring post.
    Direct hiring posts should NEVER be labeled as 'Not a Direct Job Opening' or
    'Candidate Seeking Job (Not a Hiring Post)'.
    """
    if not text:
        return False
    t = text.lower()

    # Negative checks: explicit job seeker self-promotion
    if any(k in t for k in [
        "#opentowork",
        "open to work",
        "actively looking for a job",
        "actively looking for new opportunit",
        "actively looking for my next",
        "actively exploring",
        "exploring new opportunities",
        "exploring opportunities",
        "open to opportunities",
        "open to new opportunities",
        "open to remote",
        "open to roles",
        "looking for a job",
        "looking for job",
        "seeking a job",
        "seeking an opportunity",
        "seeking opportunities",
        "seeking a new role",
        "seeking my next opportunity",
        "looking for my next role",
        "hire me",
        "job wanted",
        "seeking referrals",
        "looking for referral",
        "sharing his resume",
        "sharing her resume",
        "sharing my resume",
        "sharing the cv",
        "sharing his cv",
        "sharing my cv",
        "recommend my son",
        "looking for an opportunity for my",
        "looking for a job opportunity for my",
    ]):
        return False

    # Positive hiring markers
    has_hiring_marker = bool(re.search(
        r"\b(?:hiring|we are hiring|we're hiring|job opening|urgently hiring|immediate requirement|"
        r"we are looking for|looking for an? experienced|join our team|apply now|to apply|"
        r"send your (?:cv|resume)|share your (?:cv|resume)|submit your (?:cv|resume)|"
        r"salary\s*:\s*[₹\$\d]|compensation\s*:\s*[₹\$\d]|work from office|hybrid|on-site|onsite)\b",
        t
    ))

    # Contact / apply channels
    has_apply_channel = bool(
        "@" in t or "whatsapp" in t or "email:" in t or "cv" in t or "resume" in t
    )

    # Developer / technical role titles
    has_job_role = bool(re.search(
        r"\b(?:developer|engineer|full\s*stack|software|frontend|backend|programmer|consultant)\b",
        t
    ))

    return has_hiring_marker and (has_apply_channel or has_job_role)


def normalize_rejection_reason(reason: str, gen_body: str = "", full_text: str = "") -> str:
    """
    Standardize raw or buggy rejection reasons into clean, uniform taxonomy labels.
    Guards against false negatives on authentic recruiter hiring posts.
    """
    if not reason and not gen_body:
        return "Unspecified"

    r_raw = (reason or "").strip()
    # Strip common boilerplate prefixes like UNSUITABLE_JD - or ❌
    r_raw = re.sub(r"^(?:UNSUITABLE_JD\s*[-—:]*\s*)?(?:❌\s*)?", "", r_raw, flags=re.IGNORECASE).strip()
    r_raw = re.sub(r"^(?:Not suitable|Unsuitable(?:\s*JD)?)\s*[-—:]+\s*", "", r_raw, flags=re.IGNORECASE).strip()
    r = r_raw.lower()
    body = (gen_body or "").strip()

    # 0. Check if it is a single-letter or very short corrupted reason (e.g. 'C', 'b', 's', 'h')
    if len(r_raw) <= 3 and body:
        # Strip prefixes from body
        body_clean = re.sub(r"^(?:UNSUITABLE_JD\s*[-—:]*\s*)?(?:❌\s*)?", "", body, flags=re.IGNORECASE).strip()
        body_clean = re.sub(r"^(?:Not suitable|Unsuitable(?:\s*JD)?)\s*[-—:]+\s*", "", body_clean, flags=re.IGNORECASE).strip()
        return normalize_rejection_reason(body_clean, "", full_text)

    # Check if the source post text indicates an undeniable direct hiring post
    is_direct = is_direct_hiring_post(full_text)

    # 1. Easy Apply Technical / Automation Constraints
    if "exceeded step limit" in r:
        return "Multi-step Questionnaire (Saved for Screening)"
    if "no easy apply button" in r:
        return "No Easy Apply Button"
    if "multi-step form" in r:
        return "Multi-step Form Required Manual Input"
    if r.startswith("questions:"):
        return "Requires Screening Questions"
    if "timeout" in r or "locator." in r or "page." in r:
        return "Browser Automation Timeout"

    # 2. Potential Scam / Spam
    if "scam" in r or "spam" in r:
        return "Potential Scam / Spam"

    # 3. Already Contacted / Unverified Posts
    if any(k in r for k in ["already send", "already sent", "already applied", "already contacted"]):
        return "Already Contacted / Sent"
    if "not reliable post" in r:
        return "Unverified / Low Reliability Post"

    # 4. Solicitations / Hotlists / Walk-ins / Not a Job
    if any(k in r for k in ["bench-sales", "bench sales", "hotlist", "hot-list", "c2c", "vendor solicitation", "partner"]):
        return "Vendor / Consultant Hotlist"
    # Strict candidate patterns: DO NOT match bare "candidate", which appears in almost every hiring post
    if any(k in r for k in [
        "candidate post",
        "candidate pos",
        "candidate seeking",
        "candidate looking for",
        "candidate's",
        "candidate’s",
        "seeking job",
        "seeking an opp",
        "open to opportunit",
        "#opentowork",
        "job wanted",
        "looking for a role",
        "looking for a job",
        "hire me",
        "actively looking for",
        "job-seeking",
        "job seeking",
        "cv-sharing",
        "referral post",
    ]):
        if not is_direct:
            return "Candidate Seeking Job (Not a Hiring Post)"
    if "freelance" in r:
        return "Freelance / Contract Offer"
    if "referral request" in r:
        return "Referral Request (Not a Job)"
    if "walk-in" in r or "walk in" in r:
        return "Walk-in Hiring Event"
    if "paid" in r and ("workshop" in r or "career" in r or "training" in r or "course" in r):
        return "Paid Training / Workshop (Not a Job)"
    if any(k in r for k in ["not a job", "not a direct job", "not an opening"]):
        if not is_direct:
            return "Not a Direct Job Opening"
    if any(k in r for k in ["recruiter post", "recruitment post", "staffing", "outsourcing", "consultan"]):
        return "Staffing / Recruiter Solicitation"

    # 5. Experience & Seniority Requirements (High priority to allow experience override)
    if is_experience_rejection(r) or is_experience_rejection(body):
        return "Experience Requirement Mismatch"

    # 6. Diversity / Gender / Eligibility Requirements
    if "female" in r or "women" in r:
        return "Diversity Requirement (Female Only)"
    if "certification" in r:
        return "Mandatory Certification Required"

    # 7. Non-Engineering Functional Roles
    if "qa" in r or "quality assurance" in r or "testing" in r or "sdet" in r:
        return "QA / Automation Testing Role"
    if any(k in r for k in ["content", "writing", "copywriting"]):
        return "Content & Technical Writing Role"
    if any(k in r for k in ["seo", "marketing", "ads"]):
        return "Marketing & Growth Role"
    if any(k in r for k in ["sales", "business development"]):
        return "Sales & Business Development Role"
    if any(k in r for k in ["hr", "human resources"]):
        return "HR & Operations Role"
    if any(k in r for k in ["design", "ui/ux", "ux", "visual design"]):
        return "UI/UX & Product Design Role"
    if any(k in r for k in ["law", "legal", "llb"]):
        return "Legal & Compliance Role"
    if any(k in r for k in ["film", "entertainment", "non-software", "non-engineering"]):
        return "Non-Engineering Role"
    if any(k in r for k in ["support", "helpdesk", "desktop"]):
        return "IT Support & Helpdesk Role"

    # 8. Work Authorization & Visa Constraints
    if any(k in r for k in [
        "w2", "work authorization", "visa", "green card", "usc-only", "usc or", "clearance",
        "ksa visa", "canada work", "us contractor", "us candidates", "us only", "usa only", "usa candidates"
    ]):
        return "Work Authorization / Visa Restriction"

    # 9. Onsite & Location Restrictions
    if any(k in r for k in [
        "onsite", "hybrid", "local", "location", "georgia", "charlotte", "plano", "dallas",
        "seattle", "tampa", "atlanta", "chicago", "new york", "jersey city", "irving",
        "columbus", "bengaluru", "chile", "dubai", "winnipeg", "ethiopia", "mohali",
        "us resident", "us roles", "usa-based", "google office", "connecticut", "texas",
        "toronto", "canada", "illinois", "schaumburg", "san francisco", "sf"
    ]):
        return "Location / Onsite Requirement Mismatch"

    # 10. Tech Stack Mismatch
    if "tech stack" in r or "stack" in r or any(k in r for k in [
        "sap", "uipath", "tibco", "avaloq", "kafka", "golang", "power apps", "ai/data",
        "embedded", "telecom", "transmit", "data engineering", "specialized", "salesforce"
    ]):
        return "Irrelevant Tech Stack / Skill Mismatch"

    # 11. Default Fallback
    if "not suitable" in r or "unspecified" in r or len(r_raw) <= 3:
        return "Not Suitable (General)"

    return r_raw[:48]


def clean_and_truncate_reason(text: str, max_chars: int = 48, max_words: int = 8) -> str:
    """
    Strip boilerplate prefixes and return a clean, uniform taxonomy label.
    """
    if not text:
        return "Not Suitable (General)"
    return normalize_rejection_reason(text)


def extract_unsuitable_reason(raw_text: str, full_text: str = "") -> str:
    """
    Extract clean, concise uniform reason string from an unsuitable JD response.
    """
    if not raw_text:
        return "Not Suitable (General)"
    return normalize_rejection_reason(raw_text, gen_body=raw_text, full_text=full_text)


def is_experience_rejection(reason_text: str) -> bool:
    """
    Check if an unsuitable classification or rejection reason is based on
    experience requirements, years of experience, seniority, or experience mismatch.
    """
    if not reason_text:
        return False
    t = reason_text.lower()
    if any(k in t for k in [
        "experience",
        "yoe",
        "exp mismatch",
        "experience mismatch",
        "excessive experience",
        "years of exp",
        "years exp",
        "seniority",
    ]):
        return True
    if re.search(r"\b\d+\s*[-–—+]?\s*(?:\d+\s*)?(?:years?|yrs?)\b", t):
        return True
    if re.search(r"\b(?:too senior|too junior|seniority mismatch|years required)\b", t):
        return True
    return False


EXPERIENCE_OVERRIDE_DIRECTIVE = (
    "\n\n[System Directive: Do NOT disqualify, skip, or classify as UNSUITABLE_JD based on years of experience, "
    "seniority level, or experience mismatch (even for 5+, 8+, 10+, 15+ years). Always generate a tailored "
    "application email focusing on relevant technical skills, frameworks, and projects. Only classify as "
    "UNSUITABLE_JD if this is a completely non-engineering role (e.g. Sales, HR, Marketing) or a vendor marketing hotlist/referral.]"
)


def _send_prompt_and_wait_response(
    page: Page,
    prompt_text: str,
    max_wait: int = 120,
    poll_interval: int = 2,
) -> Tuple[str, str]:
    """
    Internal helper to submit a prompt to the active ChatGPT conversation and wait for completion.
    """
    # 1. Record existing last assistant message ID and text
    existing_msgs = page.locator("[data-message-author-role='assistant']")
    initial_count = existing_msgs.count()
    last_msg_id = ""
    initial_last_text = ""
    if initial_count > 0:
        try:
            last_msg_id = existing_msgs.last.evaluate(
                "el => el.getAttribute('data-message-id') || ''"
            )
        except Exception:
            pass
        try:
            initial_last_text = existing_msgs.last.inner_text().strip()
        except Exception:
            pass

    # 2. Focus prompt box
    prompt_box = page.locator("#prompt-textarea")
    prompt_box.click()
    page.wait_for_timeout(300)

    # 3. Fast insert into ProseMirror contenteditable via native execCommand
    inserted = False
    try:
        inserted = page.evaluate("""(text) => {
            const el = document.querySelector('#prompt-textarea');
            if (!el) return false;
            el.focus();
            document.execCommand('selectAll', false, null);
            const ok = document.execCommand('insertText', false, text);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            return ok;
        }""", prompt_text.strip())
    except Exception as eval_err:
        print(f"    execCommand insert notice: {eval_err}")
        inserted = False

    # Verify text populated in prompt box
    current_prompt_text = ""
    try:
        current_prompt_text = prompt_box.inner_text().strip()
    except Exception:
        pass

    if not inserted or not current_prompt_text:
        # Fallback 1: fill locator
        try:
            prompt_box.fill(prompt_text.strip())
            current_prompt_text = prompt_box.inner_text().strip()
        except Exception:
            pass

    if not current_prompt_text:
        # Fallback 2: type line-by-line
        lines = prompt_text.strip().split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                page.keyboard.press("Shift+Enter")
            if line:
                page.keyboard.type(line, delay=1)

    page.wait_for_timeout(600)

    # 4. Click Send Button or press Enter
    sent = False
    send_btn_query = (
        "button[data-testid='send-button'], "
        "form button[aria-label='Send prompt'], "
        "form button[data-testid='send-button'], "
        "form button[data-testid='fruitjuice-send-button'], "
        "form button[type='submit']"
    )

    start_btn = time.time()
    while time.time() - start_btn < 4:
        btn = page.locator(send_btn_query).first
        if btn.count() > 0 and btn.is_visible():
            try:
                is_disabled = btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true'")
            except Exception:
                is_disabled = False
            if not is_disabled:
                try:
                    btn.click(timeout=3000)
                    sent = True
                    break
                except Exception:
                    pass
        time.sleep(0.4)

    if not sent:
        # Resilient fallback: press Enter in prompt box
        print("    Send button not clickable or delayed; pressing Enter in prompt box...")
        try:
            prompt_box.focus()
            page.keyboard.press("Enter")
            sent = True
        except Exception as enter_err:
            print(f"    Press Enter fallback failed: {enter_err}")

    page.wait_for_timeout(1000)

    # 5. Wait for Response Generation
    elapsed = 0
    response_text = ""

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        current_msgs = page.locator("[data-message-author-role='assistant']")
        current_count = current_msgs.count()

        if current_count > 0:
            last_msg = current_msgs.last
            try:
                new_last_id = last_msg.evaluate(
                    "el => el.getAttribute('data-message-id') || ''"
                )
            except Exception:
                new_last_id = ""

            try:
                current_last_text = last_msg.inner_text().strip()
            except Exception:
                current_last_text = ""

            # Check if a new message has arrived
            is_new_message = (
                (new_last_id and last_msg_id and new_last_id != last_msg_id)
                or current_count > initial_count
                or (current_last_text and current_last_text != initial_last_text)
            )

            if is_new_message:
                # Check if still streaming
                stop_btn = page.locator(
                    "button[aria-label='Stop generating'], "
                    "button[data-testid='stop-button'], "
                    "button[aria-label='Stop reasoning'], "
                    "button[aria-label*='Stop']"
                )
                if stop_btn.count() > 0 and stop_btn.first.is_visible():
                    print(f"    ...streaming response ({elapsed}s)")
                    continue

                # Finished streaming!
                md_el = last_msg.locator(".markdown")
                if md_el.count() > 0:
                    response_text = md_el.first.inner_text().strip()
                else:
                    response_text = current_last_text

                if response_text and response_text != initial_last_text:
                    print(f"    ✓ Received full response ({elapsed}s, {len(response_text)} chars)")
                    break

    if not response_text:
        # Fallback: only if a new message was actually produced
        current_msgs = page.locator("[data-message-author-role='assistant']")
        if current_msgs.count() > initial_count:
            last_msg = current_msgs.last
            md_el = last_msg.locator(".markdown")
            response_text = md_el.first.inner_text().strip() if md_el.count() > 0 else last_msg.inner_text().strip()
        else:
            raise TimeoutError("Timed out waiting for ChatGPT response (no new assistant reply was generated).")

    subject, body = parse_email_response(response_text)
    return subject, body


def send_jd_and_get_email(
    page: Page,
    jd_text: str,
    max_wait: int = 120,
    poll_interval: int = 2
) -> Tuple[str, str]:
    """
    Send the raw JD to ChatGPT along with the experience-override directive,
    and wait for the response.

    Returns:
        (subject, body)
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Cannot send empty JD text to ChatGPT.")

    full_prompt = jd_text.strip() + EXPERIENCE_OVERRIDE_DIRECTIVE
    return _send_prompt_and_wait_response(page, full_prompt, max_wait=max_wait, poll_interval=poll_interval)


def send_followup_and_get_email(
    page: Page,
    followup_text: str,
    max_wait: int = 120,
    poll_interval: int = 2
) -> Tuple[str, str]:
    """
    Send a follow-up directive/prompt to the same ChatGPT conversation
    and wait for the resulting response.

    Returns:
        (subject, body)
    """
    if not followup_text or not followup_text.strip():
        raise ValueError("Cannot send empty follow-up text to ChatGPT.")

    return _send_prompt_and_wait_response(page, followup_text.strip(), max_wait=max_wait, poll_interval=poll_interval)
