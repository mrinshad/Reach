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
from typing import Tuple, Optional, List
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


DEFAULT_CHATGPT_QUESTION_URL = (
    "https://chatgpt.com/g/g-p-6a6af7de9a388191ba79d3cb135d6bc6-important/c/6a8fb276-b04c-83ee-92e1-89ef66d86bcd"
)


def get_chatgpt_question_url() -> str:
    """Retrieve custom GPT URL for question answering from database settings or default."""
    try:
        from src.db import get_setting
        val = get_setting("chatgpt_question_url")
        if val and val.strip():
            return val.strip()
    except Exception:
        pass
    try:
        from src.config import load_config
        val = load_config().get("chatgpt_question_url")
        if val and val.strip():
            return val.strip()
    except Exception:
        pass
    return DEFAULT_CHATGPT_QUESTION_URL


PROMPT_LEAK_PHRASES = [
    "write the tailored cold outreach",
    "focus on the candidate",
    "never invent experience",
    "bridge skill requirements",
    "prompting chatgpt",
    "role mentions",
    "experience-based cancellation is disabled",
    "write the email anyway",
    "tailored cold outreach application email",
    "submitting jd for",
]


def is_valid_email_draft(subject: str, body: str) -> Tuple[bool, str]:
    """
    Validate that an email draft has legitimate applicant outreach content
    and does not contain prompt echoes, meta-instructions, or garbage.
    Returns (is_valid, failure_reason).
    """
    if not subject or not subject.strip():
        return False, "Empty subject"
    if subject.strip().upper() == "UNSUITABLE_JD":
        return False, "Unsuitable JD"
    if not body or len(body.strip()) < 80:
        return False, "Email body too short (<80 characters)"

    body_lower = body.lower()
    subject_lower = subject.lower()

    # Reject prompt leaks or echoed instructions
    for phrase in PROMPT_LEAK_PHRASES:
        if phrase in body_lower or phrase in subject_lower:
            return False, f"Contains prompt meta-instruction: '{phrase}'"

    # Reject if body starts like a prompt directive
    if body_lower.startswith("write ") or body_lower.startswith("please write ") or body_lower.startswith("prompt:"):
        return False, "Starts with prompt directive instead of greeting"

    return True, "Valid"


def clean_chatgpt_answer(raw_text: str) -> str:
    """Clean and sanitize ChatGPT's raw response to extract only the answer."""
    if not raw_text:
        return ""
    ans = raw_text.strip()
    # Strip markdown code fences if wrapped
    ans = re.sub(r"^```[a-zA-Z]*\n?", "", ans)
    ans = re.sub(r"\n?```$", "", ans)
    # Strip leading blockquotes
    ans = re.sub(r"^>\s*", "", ans)
    # Strip quotes, backticks, asterisks, spaces
    ans = ans.strip("`'\"* \t\n")
    # Strip "Answer: " or "Ans: " prefix
    ans = re.sub(r"^(?:answer|ans)\s*:\s*", "", ans, flags=re.IGNORECASE).strip()
    ans = ans.strip("`'\"* \t\n")
    # Strip trailing period if it is a short answer (e.g. "Yes." -> "Yes", "5." -> "5")
    if len(ans.split()) <= 4 and ans.endswith(".") and not ans.endswith(".."):
        ans = ans[:-1].strip()
    return ans


def is_dont_know_response(text: str) -> bool:
    """Check if ChatGPT returned DONT_KNOW or user_response_needed indicating manual screening is required."""
    if not text:
        return False
    norm = text.lower().strip()
    norm = re.sub(r"[`'*_]", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return (
        "dont_know" in norm
        or "dont know" in norm
        or "don't know" in norm
        or "user_response_needed" in norm
        or "user response needed" in norm
        or norm == "dont_know"
        or norm == "dont know"
        or norm == "user_response_needed"
    )


def is_unreasonable_response(text: str) -> bool:
    """Check if ChatGPT returned WTF indicating the question is unreasonable/spam/abusive."""
    if not text:
        return False
    norm = text.lower().strip()
    norm = re.sub(r"[`'*_]", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    tokens = norm.split()
    return (
        "wtf" in tokens
        or norm == "wtf"
        or norm.startswith("wtf")
        or "unreasonable" in norm
    )


def is_chatgpt_error_response(text: str) -> bool:
    """Check if ChatGPT returned a client-side or network error banner instead of a real response."""
    if not text:
        return False
    t = text.lower().strip()
    return any(err in t for err in [
        "this response couldn't load",
        "this response couldn’t load",
        "something went wrong",
        "an error occurred",
        "failed to generate",
        "unable to load conversation",
        "unable to load",
        "network error",
        "there was an error",
        "our systems are currently",
    ])


def is_user_response_needed(text: str) -> bool:
    """Check if ChatGPT returned user_response_needed or DONT_KNOW."""
    return is_dont_know_response(text)


def dismiss_chatgpt_overlays(page: Page):
    """Dismiss any onboarding modals, banners, or dialogs blocking the ChatGPT composer."""
    dismiss_selectors = [
        "button:has-text('Okay, let\\'s go')",
        "button:has-text('Got it')",
        "button:has-text('Next')",
        "button:has-text('Done')",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('Stay logged out')",
        "button:has-text('Continue without logging in')",
        "button[aria-label='Close dialog']",
        "button[aria-label='Close']",
        "button[aria-label*='Close canvas' i]",
        "button[aria-label*='Close writing block' i]",
        "button[data-testid='close-canvas-button']",
        "div[role='dialog'] button:has-text('Close')",
    ]
    for sel in dismiss_selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=800)
                page.wait_for_timeout(300)
        except Exception:
            pass


PROMPT_BOX_SELECTOR = (
    "#prompt-textarea, "
    "[data-testid='prompt-textarea'], "
    "form[data-chatgpt-composer] div.ProseMirror[contenteditable='true'], "
    "form div.ProseMirror[contenteditable='true'], "
    "div.ProseMirror[role='textbox'][contenteditable='true']:not([contenteditable='false']), "
    "div[contenteditable='true'][role='textbox']"
)

SEND_BTN_SELECTOR = (
    "button[aria-label='Send'], "
    "form[data-chatgpt-composer] button[type='submit'], "
    "button[data-testid='send-button'], "
    "form button[aria-label='Send prompt'], "
    "form button[data-testid='send-button'], "
    "form button[data-testid='fruitjuice-send-button'], "
    "form button[type='submit']"
)


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

    # Dismiss any transient retry prompts or banners if present
    retry_btn = page.locator("button:has-text('Retry')")
    if retry_btn.count() > 0 and retry_btn.last.is_visible():
        try:
            retry_btn.last.click(timeout=1500)
            page.wait_for_timeout(2000)
        except Exception:
            pass

    # Wait for prompt box (supports new ChatGPT ProseMirror composer and legacy #prompt-textarea)
    page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=20000)
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


def clean_email_body(body: str) -> str:
    """
    Clean an email body by:
    1. Stripping leading ChatGPT / Canvas UI artifacts (e.g. 'Send', 'Send email',
       'Connect email', 'Recipients', 'Draft', 'Email Draft:', etc.).
    2. Detecting the candidate's signature block and trimming any assistant chatter,
       prompt reflections, notes, or canvas action buttons that appear after it.
    """
    if not body:
        return ""

    raw_lines = body.strip().split("\n")
    # 1. Strip leading lines that are UI artifacts / headers
    start_idx = 0
    leading_artifact_pattern = re.compile(
        r"^(?:send(?:\s+email)?|connect email.*|recipients.*|email(?:\s+draft)?[:\s]*|draft[:\s]*|to[:\s]+.*|from[:\s]+.*|cc[:\s]+.*|bcc[:\s]+.*|(?:\*\*)?subject(?:\*\*)?:.*|```.*|---)$",
        re.IGNORECASE,
    )
    while start_idx < len(raw_lines):
        line = raw_lines[start_idx].strip()
        if not line:
            start_idx += 1
            continue
        if leading_artifact_pattern.match(line):
            start_idx += 1
            continue
        break

    lines = raw_lines[start_idx:]
    if not lines:
        return ""

    # 2. Look for signature block and trim anything following it
    sign_off_pattern = re.compile(
        r"^(?:\*\*)?(?:(?:best|warm|kind|with)?\s*regards|sincerely(?:\s+yours)?|thanks\s*(?:&|and)\s*regards|thanks|thank\s+you|best|cheers|respectfully|yours\s+(?:sincerely|faithfully))(?:\*\*)?\b[,\s]*",
        re.IGNORECASE,
    )

    sign_off_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if sign_off_pattern.match(line):
            sign_off_idx = i
            break

    if sign_off_idx != -1:
        contact_line_pattern = re.compile(
            r"^(?:(?:\+?\d[\d\s\-\(\)\.]{7,}\d)|.*@.*\..*|(?:phone|tel|mobile|cell|email|linkedin|github|portfolio|website|web)[:\s].*|https?://.*|linkedin\.com/.*|github\.com/.*|(?:full[\s\-]stack|software|frontend|backend|web|devops|cloud)?\s*(?:developer|engineer|consultant|architect|specialist))\b",
            re.IGNORECASE,
        )

        sig_end_idx = sign_off_idx
        sign_off_line = lines[sign_off_idx].strip()
        has_name_on_same_line = bool(
            re.search(
                r"^(?:\*\*)?(?:(?:best|warm|kind|with)?\s*regards|sincerely(?:\s+yours)?|thanks\s*(?:&|and)\s*regards|thanks|thank\s+you|best|cheers)(?:\*\*)?[,\s]+[A-Za-z]+",
                sign_off_line,
                re.IGNORECASE,
            )
        )

        curr = sign_off_idx + 1
        name_found = has_name_on_same_line

        while curr < len(lines):
            cline = lines[curr].strip()
            if not cline:
                # Allow up to 1 blank line before name
                if not name_found and (curr + 1 < len(lines)) and lines[curr + 1].strip():
                    curr += 1
                    continue
                else:
                    break

            if not name_found:
                if not re.match(
                    r"^(?:note:|ps:|p\.s\.|let me know|hope this|good luck|feel free|why this|copy|edit|regenerate|share|---)",
                    cline,
                    re.IGNORECASE,
                ):
                    name_found = True
                    sig_end_idx = curr
                    curr += 1
                    continue
                else:
                    break
            else:
                # Name already found. Check if this is contact info / title / candidate detail
                if contact_line_pattern.match(cline) or ("rinshad" in cline.lower()):
                    sig_end_idx = curr
                    curr += 1
                    continue
                else:
                    # Anything else is commentary or UI artifact
                    break

        lines = lines[: sig_end_idx + 1]

    return "\n".join(lines).strip()


def parse_email_response(raw_text: str) -> Tuple[str, str]:
    """
    Parse a ChatGPT generated application response into (subject, body).
    Supports both standard Markdown responses and Canvas writing block formatting.
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

    # Strip Canvas UI boilerplate headers
    clean_text = re.sub(r"^Connect email(?:\s+[^\n]+)?\n+", "", clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"^Recipients\s*\n+", "", clean_text, flags=re.IGNORECASE).strip()

    lines = [l.rstrip() for l in clean_text.split("\n")]
    filtered_lines = []
    subject = ""

    # Check if first non-empty line contains an Application title or Subject line
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    if idx < len(lines):
        first_line = lines[idx].strip()
        sub_match = re.match(r"^(?:\*\*)?Subject(?:\*\*)?:\s*(.+)$", first_line, re.IGNORECASE)
        app_match = re.match(r"^(?:Application|Outreach|Cold Outreach)\s*[-–—:]\s*(.+)$", first_line, re.IGNORECASE)
        if sub_match:
            subject = sub_match.group(1).replace("**", "").strip()
            idx += 1
        elif app_match or first_line.lower().startswith("application for "):
            subject = first_line.replace("**", "").strip()
            idx += 1

    for line in lines[idx:]:
        l_str = line.strip()
        # Skip Canvas metadata lines like "Connect email", "Recipients", "Send", or solitary "Email"
        if re.match(r"^(?:Email|Connect email|Recipients|Send(?:\s+email)?)(?:\s+[^\n]+)?$", l_str, re.IGNORECASE):
            continue
        sub_match = re.match(r"^(?:\*\*)?Subject(?:\*\*)?:\s*(.+)$", l_str, re.IGNORECASE)
        if sub_match and not subject:
            subject = sub_match.group(1).replace("**", "").strip()
            continue
        filtered_lines.append(line)

    body = "\n".join(filtered_lines).strip()
    # Strip any residual leading "Email\n\n" or "Subject:\n"
    body = re.sub(r"^(?:Email(?:\s+Draft)?[:\s]*\n+)+", "", body, flags=re.IGNORECASE).strip()
    body = clean_email_body(body)

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


def clean_and_truncate_reason(text: str, max_chars: int = 100, max_words: int = 14) -> str:
    """
    Extract clean, concise reason directly from ChatGPT's unsuitable response text.
    Strips boilerplate prefixes (UNSUITABLE_JD, ❌, Not suitable —, Reason:),
    and truncates cleanly at word boundaries if excessive.
    e.g. "UNSUITABLE_JD - Java Specialized" -> "Java Specialized"
    e.g. "UNSUITABLE_JD - ❌ Not suitable — SEO role" -> "SEO role"
    """
    if not text:
        return "Unsuitable JD"
    t = text.strip()

    # Check for Classification: XYZ → Skip
    class_match = re.search(r"Classification:\s*([^→\-\n\.]+?)(?:\s*[→\-]+\s*Skip|\.|$)", t, flags=re.IGNORECASE)
    if class_match:
        label = class_match.group(1).strip()
        if label:
            if label.isupper():
                label = " / ".join("QA" if part.strip().upper() == "QA" else part.strip().title() for part in label.split("/"))
            return label[:max_chars].strip()

    # Strip UNSUITABLE_JD / ❌ prefix
    t = re.sub(r"^(?:UNSUITABLE_JD\s*[-—:]*\s*)?(?:❌\s*)?", "", t, flags=re.IGNORECASE).strip()
    # Strip "Not suitable — " / "Not suitable - " / "Unsuitable JD -" prefix variants
    t = re.sub(r"^(?:Not suitable|Unsuitable(?:\s*JD)?)\s*[-—:]+\s*", "", t, flags=re.IGNORECASE).strip()
    # Strip leading "Reason:\s*"
    t = re.sub(r"^Reason\s*:\s*", "", t, flags=re.IGNORECASE).strip()
    # Strip leading/trailing quotes, backticks, asterisks, dashes
    t = t.strip("`*\"' \t\n-—:")
    if not t or len(t) <= 2:
        return "Unsuitable JD"

    words = t.split()
    t_lower = t.lower()
    # For scam/potential scam/spam reasons, preserve context up to 100 characters
    if "scam" in t_lower or "spam" in t_lower:
        if len(t) > 100:
            return t[:97].rstrip() + "..."
        return t

    if len(words) > max_words or len(t) > max_chars:
        # Take up to max_words and also respect max_chars
        truncated = " ".join(words[:max_words])
        if len(truncated) > max_chars - 3:
            truncated = truncated[: max_chars - 3].rstrip()
            if " " in truncated:
                truncated = truncated.rsplit(" ", 1)[0]
        return truncated.rstrip(".,;:-—") + "..."
    return t.rstrip(".,;:-—")


def extract_unsuitable_reason(raw_text: str, full_text: str = "") -> str:
    """
    Extract clean, concise reason string directly from an unsuitable JD response from ChatGPT.
    """
    if not raw_text:
        return "Unsuitable JD"
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    if not lines:
        return "Unsuitable JD"
    t = lines[0]
    # If line 0 is strictly "UNSUITABLE_JD" or "UNSUITABLE" without any reason, look at line 1
    if re.fullmatch(r"^UNSUITABLE(?:_JD)?$", t, flags=re.IGNORECASE) and len(lines) > 1:
        t = lines[1]
    return clean_and_truncate_reason(t)


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
    "\n\n[System Directive: Generate application emails ONLY for JDs with at least 70% alignment with my primary stack: "
    "React.js, Next.js, TypeScript, JavaScript, Node.js, Express.js, PostgreSQL, Prisma, Python, GCP, Azure, and DevOps. "
    "Evaluate core technical requirements, not keyword overlap. "
    "Exclude unrelated specialized roles (e.g., Java, SAP, Salesforce, ServiceNow, Oracle DBA, Azure Developer).\n\n"
    "Never reject based on experience or seniority. ALWAYS reject non-engineering roles and vendor marketing hotlists/referrals.\n\n"
    "For all unsuitable JDs, output ONLY: `UNSUITABLE_JD - [1–2 word reason]`.\n\n"
    "For qualifying JDs, generate a tailored application email.]"
)


def _send_prompt_and_wait_response(
    page: Page,
    prompt_text: str,
    max_wait: int = 120,
    poll_interval: int = 2,
) -> Tuple[str, str]:
    """
    Internal helper to submit a prompt to the active ChatGPT conversation and wait for completion.
    Supports both traditional streaming chat messages and Canvas writing blocks.
    """
    # 1. Record existing state before sending prompt
    wbs_loc = page.locator("[data-testid='chatgpt-writing-block'], .group\\/writing-block-surface")
    initial_wb_count = wbs_loc.count()
    initial_wb_text = ""
    if initial_wb_count > 0:
        try:
            initial_wb_text = wbs_loc.last.inner_text().strip()
        except Exception:
            pass

    ASSISTANT_MSG_SELECTOR = (
        "[data-message-author-role='assistant'], "
        "[data-markdown-text-style='assistant-message'], "
        "div[data-dil-message-id]:not([data-message-author-role='user'])"
    )

    existing_msgs = page.locator(ASSISTANT_MSG_SELECTOR)
    initial_count = existing_msgs.count()
    last_msg_id = ""
    initial_last_text = ""
    if initial_count > 0:
        try:
            last_msg_id = existing_msgs.last.evaluate(
                "el => el.getAttribute('data-dil-message-id') || el.getAttribute('data-message-id') || el.closest('[data-dil-message-id]')?.getAttribute('data-dil-message-id') || ''"
            )
        except Exception:
            pass
        try:
            initial_last_text = existing_msgs.last.inner_text().strip()
        except Exception:
            pass

    # 2. Focus prompt box (prioritize bottom chat composer #prompt-textarea)
    prompt_box = page.locator(PROMPT_BOX_SELECTOR).last
    try:
        prompt_box.click(force=True, timeout=3000)
    except Exception:
        try:
            prompt_box.focus()
        except Exception:
            pass
    page.wait_for_timeout(300)

    # 3. Fast & Safe insert into ProseMirror contenteditable
    # (Avoid bare keyboard.type on multiline text because Playwright sends Enter keydown for \n,
    # which causes ChatGPT to prematurely submit before the full prompt is typed)
    inserted = False
    try:
        inserted = page.evaluate("""({sel, text}) => {
            const els = Array.from(document.querySelectorAll(sel));
            const el = els.find(e => e.getAttribute('contenteditable') === 'true' || e.tagName === 'TEXTAREA') || els[els.length - 1];
            if (!el) return false;
            el.focus();

            // Method A: Synthetic Clipboard paste event (ProseMirror native multiline handler)
            try {
                const dt = new DataTransfer();
                dt.setData('text/plain', text);
                const ev = new ClipboardEvent('paste', { bubbles: true, cancelable: true, clipboardData: dt });
                el.dispatchEvent(ev);
                if (el.innerText && el.innerText.trim().length > 10) return true;
            } catch (e) {}

            // Method B: execCommand
            try {
                document.execCommand('selectAll', false, null);
                const ok = document.execCommand('insertText', false, text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                if (ok && el.innerText && el.innerText.trim().length > 10) return true;
            } catch (e) {}

            return false;
        }""", {"sel": PROMPT_BOX_SELECTOR, "text": prompt_text.strip()})
    except Exception as eval_err:
        print(f"    execCommand/paste insert notice: {eval_err}")
        inserted = False

    # Verify text populated in prompt box
    current_prompt_text = ""
    try:
        current_prompt_text = prompt_box.inner_text().strip()
    except Exception:
        pass

    if not inserted or not current_prompt_text:
        # Fallback 1: keyboard.insert_text (sends input event without bare Enter keypresses)
        try:
            prompt_box.focus()
            page.keyboard.insert_text(prompt_text.strip())
            current_prompt_text = prompt_box.inner_text().strip()
        except Exception:
            pass

    if not current_prompt_text:
        # Fallback 2: type line-by-line with safe Shift+Enter (prevents premature submit)
        try:
            prompt_box.focus()
            lines = prompt_text.strip().split("\n")
            for i, line in enumerate(lines):
                if i > 0:
                    page.keyboard.press("Shift+Enter")
                    page.wait_for_timeout(20)
                if line:
                    page.keyboard.insert_text(line)
            current_prompt_text = prompt_box.inner_text().strip()
        except Exception:
            pass

    page.wait_for_timeout(600)

    # 4. Click Send Button or press Enter
    sent = False
    start_btn = time.time()
    while time.time() - start_btn < 4:
        btn = page.locator(SEND_BTN_SELECTOR).first
        if btn.count() > 0 and btn.is_visible():
            try:
                is_disabled = btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true' || el.classList.contains('opacity-50')")
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

    # 5. Wait for Response Generation (handles streaming stop button, writing blocks, and assistant messages)
    elapsed = 0
    response_text = ""
    has_streamed = False

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        # Check for transient retry button
        retry_btn = page.locator("button:has-text('Retry')")
        if retry_btn.count() > 0 and retry_btn.last.is_visible():
            try:
                retry_btn.last.click(timeout=1500)
                time.sleep(1.0)
            except Exception:
                pass

        # Check if currently streaming
        stop_btn = page.locator(
            "button[aria-label*='Stop' i], "
            "button[data-testid='stop-button'], "
            "button[aria-label*='stop' i]"
        )
        is_streaming = stop_btn.count() > 0 and stop_btn.first.is_visible()
        if is_streaming:
            has_streamed = True
            print(f"    ...streaming response ({elapsed}s)")
            continue

        # Check Canvas Writing Blocks
        cur_wbs = page.locator("[data-testid='chatgpt-writing-block'], .group\\/writing-block-surface")
        cur_wb_count = cur_wbs.count()
        if cur_wb_count > 0:
            last_wb = cur_wbs.last
            try:
                cur_wb_text = last_wb.inner_text().strip()
            except Exception:
                cur_wb_text = ""

            is_wb_updated = (cur_wb_count > initial_wb_count) or (has_streamed and cur_wb_text != initial_wb_text) or (cur_wb_text != initial_wb_text and len(cur_wb_text) > 40)
            if is_wb_updated and len(cur_wb_text) > 40:
                pm = last_wb.locator(".ProseMirror")
                if pm.count() > 0:
                    pm_text = pm.inner_text().strip()
                    header = last_wb.locator("header, div[class*='header']").first
                    header_text = header.inner_text().strip() if header.count() > 0 else ""
                    if header_text and header_text not in pm_text:
                        response_text = f"{header_text}\n\n{pm_text}"
                    else:
                        response_text = pm_text
                else:
                    response_text = cur_wb_text

                if response_text and response_text != initial_wb_text:
                    print(f"    ✓ Received writing block response ({elapsed}s, {len(response_text)} chars)")
                    break

        # Check Standard & Modern Assistant Chat Messages
        current_msgs = page.locator(ASSISTANT_MSG_SELECTOR)
        current_count = current_msgs.count()
        if current_count > 0:
            last_msg = current_msgs.last
            try:
                new_last_id = last_msg.evaluate(
                    "el => el.getAttribute('data-dil-message-id') || el.getAttribute('data-message-id') || el.closest('[data-dil-message-id]')?.getAttribute('data-dil-message-id') || ''"
                )
            except Exception:
                new_last_id = ""

            try:
                current_last_text = last_msg.inner_text().strip()
            except Exception:
                current_last_text = ""

            is_new_message = (
                (new_last_id and last_msg_id and new_last_id != last_msg_id)
                or current_count > initial_count
                or (has_streamed and current_last_text != initial_last_text)
                or (current_last_text and current_last_text != initial_last_text and len(current_last_text) > 40)
            )

            if is_new_message:
                md_el = last_msg.locator(".markdown, [class*='MarkdownRoot']")
                if md_el.count() > 0:
                    response_text = md_el.first.inner_text().strip()
                else:
                    response_text = current_last_text

                if response_text and response_text != initial_last_text:
                    print(f"    ✓ Received assistant response ({elapsed}s, {len(response_text)} chars)")
                    break

    if not response_text:
        # Fallback inspection of latest writing block or assistant message
        cur_wbs = page.locator("[data-testid='chatgpt-writing-block'], .group\\/writing-block-surface")
        if cur_wbs.count() > 0:
            last_wb = cur_wbs.last
            pm = last_wb.locator(".ProseMirror")
            response_text = pm.inner_text().strip() if pm.count() > 0 else last_wb.inner_text().strip()

        if not response_text:
            current_msgs = page.locator(ASSISTANT_MSG_SELECTOR)
            if current_msgs.count() > initial_count:
                last_msg = current_msgs.last
                md_el = last_msg.locator(".markdown, [class*='MarkdownRoot']")
                response_text = md_el.first.inner_text().strip() if md_el.count() > 0 else last_msg.inner_text().strip()

    if not response_text:
        raise TimeoutError("Timed out waiting for ChatGPT response (no new assistant reply or writing block was generated).")

    subject, body = parse_email_response(response_text)

    # Copy to system clipboard via pbcopy on macOS
    try:
        import subprocess
        full_clipboard_text = f"Subject: {subject}\n\n{body}" if (subject and subject != "UNSUITABLE_JD") else response_text
        subprocess.run(["pbcopy"], input=full_clipboard_text, text=True, check=False)
        print("    📋 Copied generated response to system clipboard (pbcopy)")
    except Exception:
        pass

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


def send_question_and_get_answer(
    page: Page,
    question_text: str,
    options: Optional[List[str]] = None,
    max_wait: int = 45,
    poll_interval: float = 1.0,
    logger=print,
) -> Tuple[Optional[str], bool]:
    """
    Submit a raw question to the custom GPT chat and wait for the single clean answer.
    No extra system prompts are appended, adhering strictly to pre-configured chat behavior.
    Returns:
        (answer_string, is_user_response_needed)
    """
    if not question_text or not question_text.strip():
        return None, False

    prompt_to_send = question_text.strip()
    if options and len(options) > 0:
        clean_opts = [str(o).strip() for o in options if str(o).strip()]
        if clean_opts:
            prompt_to_send += f"\nOptions: {', '.join(clean_opts)}"

    ASSISTANT_MSG_SELECTOR = (
        "[data-message-author-role='assistant'], "
        "[data-markdown-text-style='assistant-message'], "
        "div[data-dil-message-id]:not([data-message-author-role='user'])"
    )

    existing_msgs = page.locator(ASSISTANT_MSG_SELECTOR)
    initial_count = existing_msgs.count()
    last_msg_id = ""
    initial_last_text = ""
    if initial_count > 0:
        try:
            last_msg = existing_msgs.last
            last_msg_id = last_msg.evaluate(
                "el => el.getAttribute('data-dil-message-id') || el.getAttribute('data-message-id') || el.closest('[data-dil-message-id]')?.getAttribute('data-dil-message-id') || ''"
            )
        except Exception:
            pass
        try:
            initial_last_text = existing_msgs.last.inner_text().strip()
        except Exception:
            pass

    try:
        dismiss_chatgpt_overlays(page)
        page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=12000)
    except Exception:
        logger(f"  ⚠️ Prompt box not found on ChatGPT page (url: {page.url}, title: {page.title()})")
        return None, "FAILED"

    prompt_box = page.locator(PROMPT_BOX_SELECTOR).last
    try:
        prompt_box.click(force=True, timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(250)

    # Insert into ProseMirror composer
    inserted = False
    try:
        inserted = page.evaluate("""({sel, text}) => {
            const els = document.querySelectorAll(sel);
            if (!els.length) return false;
            const el = els[els.length - 1];
            el.focus();
            document.execCommand('selectAll', false, null);
            const ok = document.execCommand('insertText', false, text);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return ok;
        }""", {"sel": PROMPT_BOX_SELECTOR, "text": prompt_to_send})
    except Exception:
        inserted = False

    current_prompt_text = ""
    try:
        current_prompt_text = prompt_box.inner_text().strip()
    except Exception:
        pass

    if not inserted or not current_prompt_text:
        try:
            prompt_box.click()
            lines = prompt_to_send.split("\n")
            for i, line in enumerate(lines):
                if i > 0:
                    page.keyboard.press("Shift+Enter")
                    page.wait_for_timeout(20)
                if line:
                    page.keyboard.insert_text(line)
            current_prompt_text = prompt_box.inner_text().strip()
        except Exception:
            pass

    page.wait_for_timeout(400)

    # Click send button or press Enter
    sent = False
    start_btn = time.time()
    while time.time() - start_btn < 3:
        btn = page.locator(SEND_BTN_SELECTOR).first
        if btn.count() > 0 and btn.is_visible():
            try:
                is_disabled = btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true' || el.classList.contains('opacity-50')")
            except Exception:
                is_disabled = False
            if not is_disabled:
                try:
                    btn.click(timeout=2000)
                    sent = True
                    break
                except Exception:
                    pass
        time.sleep(0.3)

    if not sent:
        try:
            prompt_box.focus()
            page.keyboard.press("Enter")
            sent = True
        except Exception:
            pass

    page.wait_for_timeout(800)

    # Wait for completion
    elapsed = 0.0
    has_streamed = False
    response_text = ""

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        if page.is_closed():
            logger("  ⚠️ ChatGPT page was closed.")
            return None, "FAILED"

        try:
            # Check transient retry button
            retry_btn = page.locator("button:has-text('Retry')")
            if retry_btn.count() > 0 and retry_btn.last.is_visible():
                try:
                    retry_btn.last.click(timeout=1000)
                    time.sleep(1.0)
                except Exception:
                    pass

            # Check streaming
            stop_btn = page.locator(
                "button[aria-label*='Stop' i], button[data-testid='stop-button'], button[aria-label*='stop' i]"
            )
            is_streaming = stop_btn.count() > 0 and stop_btn.first.is_visible()
            if is_streaming:
                has_streamed = True
                continue

            current_msgs = page.locator(ASSISTANT_MSG_SELECTOR)
            current_count = current_msgs.count()
            if current_count > 0:
                last_msg = current_msgs.last
                try:
                    new_last_id = last_msg.evaluate(
                        "el => el.getAttribute('data-dil-message-id') || el.getAttribute('data-message-id') || el.closest('[data-dil-message-id]')?.getAttribute('data-dil-message-id') || ''"
                    )
                except Exception:
                    new_last_id = ""

                try:
                    current_last_text = last_msg.inner_text().strip()
                except Exception:
                    current_last_text = ""

                is_new = (
                    (new_last_id and last_msg_id and new_last_id != last_msg_id)
                    or current_count > initial_count
                    or (has_streamed and current_last_text != initial_last_text)
                    or (current_last_text and current_last_text != initial_last_text and not is_streaming)
                )

                if is_new and current_last_text and not is_streaming:
                    md_el = last_msg.locator(".markdown, [class*='MarkdownRoot']")
                    if md_el.count() > 0:
                        response_text = md_el.first.inner_text().strip()
                    else:
                        response_text = current_last_text

                    if response_text:
                        if current_count > initial_count or (new_last_id and new_last_id != last_msg_id) or response_text != initial_last_text:
                            break
        except Exception as e:
            if "closed" in str(e).lower() or page.is_closed():
                logger(f"  ⚠️ Browser/Page closed during wait: {e}")
                return None, "FAILED"

    if not response_text:
        current_msgs = page.locator(ASSISTANT_MSG_SELECTOR)
        if current_msgs.count() > initial_count:
            last_msg = current_msgs.last
            md_el = last_msg.locator(".markdown, [class*='MarkdownRoot']")
            response_text = md_el.first.inner_text().strip() if md_el.count() > 0 else last_msg.inner_text().strip()

    clean_ans = clean_chatgpt_answer(response_text)
    if is_chatgpt_error_response(clean_ans):
        logger(f"  ⚠️ ChatGPT returned an error message ('{clean_ans}'). Left as PENDING.")
        return None, "FAILED"

    if is_unreasonable_response(clean_ans):
        logger(f"  🚫 ChatGPT classified question as unreasonable ('WTF'): {clean_ans}")
        return None, "WTF"

    if is_dont_know_response(clean_ans):
        logger(f"  ⚠️ ChatGPT responded 'DONT_KNOW': {clean_ans}")
        return None, "DONT_KNOW"

    if clean_ans:
        return clean_ans, "OK"

    return None, "FAILED"


def ask_chatgpt_for_question_answer(
    context,
    question_text: str,
    options: Optional[List[str]] = None,
    logger=print,
) -> Tuple[Optional[str], str]:
    """
    High-level automation helper to query the dedicated ChatGPT question answering conversation.
    Reuses an open ChatGPT tab or creates one in the current Playwright Firefox context.
    Returns:
        (answer_string, status_code) where status_code in ('OK', 'DONT_KNOW', 'WTF', 'FAILED')
    """
    if not context:
        logger("  ⚠️ No browser context provided for ChatGPT question answering.")
        return None, "FAILED"

    target_url = get_chatgpt_question_url()
    chat_page = None

    try:
        # Extract unique chat ID from question URL (e.g. 6a8fb276-b04c-83ee-92e1-89ef66d86bcd)
        chat_id = ""
        if "/c/" in target_url:
            chat_id = target_url.split("/c/")[-1].split("?")[0].strip("/")

        # 1. Reuse existing ChatGPT question page if open in context
        for p in context.pages:
            try:
                p_url = p.url or ""
                if chat_id and chat_id in p_url:
                    chat_page = p
                    break
                elif "6a8fb276-b04c-83ee-92e1-89ef66d86bcd" in p_url:
                    chat_page = p
                    break
            except Exception:
                pass

        if not chat_page:
            logger("  Opening dedicated ChatGPT question answering chat...")
            chat_page = context.new_page()
            navigate_to_conversation(chat_page, url=target_url)
        else:
            try:
                dismiss_chatgpt_overlays(chat_page)
                # Ensure the page is ready and prompt box is available
                chat_page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=4000)
            except Exception:
                try:
                    chat_page.goto(target_url, wait_until="commit", timeout=20000)
                    chat_page.wait_for_timeout(3000)
                    dismiss_chatgpt_overlays(chat_page)
                    chat_page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=15000)
                except Exception:
                    pass

        return send_question_and_get_answer(
            chat_page,
            question_text=question_text,
            options=options,
            logger=logger,
        )
    except Exception as e:
        logger(f"  Notice querying ChatGPT for question: {e}")
        return None, "FAILED"


def ask_chatgpt_for_reason_for_applying(
    context,
    jd_text: str,
    logger=print,
) -> str:
    """
    Query ChatGPT to generate a concise, tailored reason for applying based on the JD.
    Directive format: {jd_text}\n\nNeed reason for applying
    Copies the result to the macOS system clipboard (pbcopy) and returns the generated text.
    """
    clean_jd = (jd_text or "").strip()
    if not clean_jd:
        clean_jd = "Software engineering and full-stack development role."

    prompt_to_send = f"{clean_jd}\n\nNeed reason for applying"
    logger("  🤖 Requesting tailored 'Reason for applying' from ChatGPT...")

    chat_page = None
    target_url = get_chatgpt_question_url()

    try:
        if context:
            for p in context.pages:
                try:
                    p_url = p.url or ""
                    if "chatgpt.com" in p_url:
                        chat_page = p
                        break
                except Exception:
                    pass

            if not chat_page:
                chat_page = context.new_page()
                navigate_to_conversation(chat_page, url=target_url)
            else:
                try:
                    dismiss_chatgpt_overlays(chat_page)
                    chat_page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=4000)
                except Exception:
                    try:
                        chat_page.goto(target_url, wait_until="commit", timeout=20000)
                        chat_page.wait_for_timeout(3000)
                        dismiss_chatgpt_overlays(chat_page)
                        chat_page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=15000)
                    except Exception:
                        pass

        if chat_page:
            ans, status = send_question_and_get_answer(
                chat_page,
                question_text=prompt_to_send,
                logger=logger,
            )
            if ans and status == "OK":
                clean_reason = ans.strip().strip('"\'')
                # Copy to pbcopy on macOS
                try:
                    import subprocess
                    subprocess.run(["pbcopy"], input=clean_reason, text=True, check=False)
                    logger("    📋 Copied generated reason to system clipboard (pbcopy)")
                except Exception:
                    pass
                return clean_reason
    except Exception as e:
        logger(f"  Notice querying ChatGPT for reason: {e}")

    # Fallback tailored paragraph if ChatGPT is unreachable
    fallback = (
        "With hands-on experience building full-stack web applications, robust RESTful APIs, and scalable "
        "cloud infrastructure, I possess the direct technical background and problem-solving skills required "
        "to deliver immediate value to your engineering team."
    )
    try:
        import subprocess
        subprocess.run(["pbcopy"], input=fallback, text=True, check=False)
    except Exception:
        pass
    return fallback
