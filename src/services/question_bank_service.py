"""
Question & Answer Bank Service Module
(src/services/question_bank_service.py)

Manages centralized screening questions collection, deduplication, categorization,
and persistent answers for LinkedIn Easy Apply screening automation.
"""

import re
import json
import time
from typing import Dict, Any, List, Optional
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting


STANDARD_BASIC_QUESTIONS = [
    {
        "id": "std_phone",
        "question": "Phone / Mobile number",
        "category": "contact",
        "default_placeholder": "+91 98956 12423",
        "is_standard": True,
    },
    {
        "id": "std_email",
        "question": "Email address",
        "category": "contact",
        "default_placeholder": "rinshadmorayur09@gmail.com",
        "is_standard": True,
    },
    {
        "id": "std_location",
        "question": "Current City / Location",
        "category": "contact",
        "default_placeholder": "Malappuram, Kerala, India",
        "is_standard": True,
    },
    {
        "id": "std_experience_total",
        "question": "Total years of professional software engineering experience",
        "category": "experience",
        "default_placeholder": "3+",
        "is_standard": True,
    },
    {
        "id": "std_experience_fullstack",
        "question": "Years of Full Stack / Web Application Development experience",
        "category": "experience",
        "default_placeholder": "3+",
        "is_standard": True,
    },
    {
        "id": "std_experience_react",
        "question": "Years of experience with React / Next.js / TypeScript",
        "category": "experience",
        "default_placeholder": "3",
        "is_standard": True,
    },
    {
        "id": "std_experience_backend",
        "question": "Years of experience with Python / Node.js / FastAPI / APIs",
        "category": "experience",
        "default_placeholder": "3",
        "is_standard": True,
    },
    {
        "id": "std_current_ctc",
        "question": "Current CTC / Salary (in LPA or INR)",
        "category": "compensation",
        "default_placeholder": "e.g. 6 LPA",
        "is_standard": True,
    },
    {
        "id": "std_expected_ctc",
        "question": "Expected CTC / Salary (in LPA or INR)",
        "category": "compensation",
        "default_placeholder": "Negotiable / As per company standards",
        "is_standard": True,
    },
    {
        "id": "std_notice_period",
        "question": "Notice Period (in Days)",
        "category": "notice",
        "default_placeholder": "Immediate / 15-30 days",
        "is_standard": True,
    },
    {
        "id": "std_english",
        "question": "Level of proficiency in English (1-10 or Fluent/Professional)",
        "category": "profile",
        "default_placeholder": "Professional / Fluent (8/10)",
        "is_standard": True,
    },
    {
        "id": "std_work_mode",
        "question": "Comfortable with Remote / Hybrid / On-site roles?",
        "category": "profile",
        "default_placeholder": "Yes, open to Remote and Hybrid roles",
        "is_standard": True,
    },
]


def normalize_question_key(text: str) -> str:
    """Produce a deterministic, lowercase alphanumeric slug for deduplication."""
    cleaned = text.strip().lower()
    cleaned = re.sub(r'[^a-z0-9]', '', cleaned)
    return cleaned


def infer_question_category(question_text: str) -> str:
    """Categorize a question based on keywords in its text."""
    low = question_text.lower()
    if any(k in low for k in ["ctc", "salary", "lpa", "compensation", "inr", "usd", "hourly", "rate", "in-hand"]):
        return "compensation"
    if any(k in low for k in ["notice", "days", "immediate", "joiner", "months"]):
        return "notice"
    if any(k in low for k in ["phone", "mobile", "email", "city", "location", "address", "country", "postal"]):
        return "contact"
    if any(k in low for k in ["year", "experience", "python", "react", "sql", "fastapi", "typescript", "llm", "ai", "javascript", "full-stack", "data", "engineering", "mentor"]):
        return "experience"
    return "profile"


def match_option_to_answer(answer: str, options: List[str], prompt: str = "") -> Optional[str]:
    """
    Intelligently match a stored Question Bank answer or candidate profile value
    to one of the available multiple-choice radio or dropdown options.
    Supports exact match, numeric experience ranges, notice period, yes/no semantics,
    and substring/token containment.
    """
    if not answer or not options:
        return None
    ans_clean = str(answer).strip()
    if not ans_clean:
        return None
    ans_low = ans_clean.lower()
    prompt_low = (prompt or "").lower()

    # Clean option map: list of (original, cleaned_lower)
    opt_map = [(opt, str(opt).strip().lower()) for opt in options if str(opt).strip()]
    if not opt_map:
        return None

    # 1. Exact match (case-insensitive)
    for orig, low in opt_map:
        if low == ans_low:
            return orig

    # 2. Number / Experience Range matching
    is_exp_q = any(k in prompt_low for k in ["experience", "year", "ctc", "salary"]) or any(k in ans_low for k in ["year", "exp", "lpa"])
    num_val = None
    m_ans = re.search(r'(\d+(?:\.\d+)?)', ans_clean)
    if m_ans:
        try:
            num_val = float(m_ans.group(1))
        except Exception:
            pass
    elif ans_low in ["0", "none", "no experience", "nil", "zero", "no", "nope"] and is_exp_q:
        num_val = 0.0

    if num_val is not None:
        # Zero experience check
        if num_val == 0:
            for orig, low in opt_map:
                if any(k in low for k in ["no professional", "no experience", "none", "0 year", "0-", "zero"]):
                    return orig
            for orig, low in opt_map:
                if low in ["no", "none"]:
                    return orig

        # Range check: '3–4 years', '1 - 2 years', '2 to 4'
        for orig, low in opt_map:
            m_range = re.search(r'(\d+(?:\.\d+)?)\s*(?:[-–—]|to)\s*(\d+(?:\.\d+)?)', low)
            if m_range:
                try:
                    r_low = float(m_range.group(1))
                    r_high = float(m_range.group(2))
                    if r_low <= num_val <= r_high:
                        return orig
                except Exception:
                    pass

        # Less than check: 'Less than 3 years', '< 1 year'
        for orig, low in opt_map:
            m_less = re.search(r'(?:less than|<|under)\s*(\d+(?:\.\d+)?)', low)
            if m_less:
                try:
                    max_v = float(m_less.group(1))
                    if num_val < max_v and (num_val > 0 or not any("no" in o[1] or "none" in o[1] for o in opt_map)):
                        return orig
                except Exception:
                    pass

        # Greater than / Plus check: '6+ years', '5+ years', '> 5 years'
        for orig, low in opt_map:
            m_plus = re.search(r'(?:(\d+(?:\.\d+)?)\s*\+|\b(?:more than|>)\s*(\d+(?:\.\d+)?))', low)
            if m_plus:
                try:
                    min_v = float(m_plus.group(1) or m_plus.group(2))
                    if num_val >= min_v:
                        return orig
                except Exception:
                    pass

    # 3. Notice Period / Immediate Joiner handling
    is_notice_q = any(k in prompt_low for k in ["notice", "joiner", "immediate", "serving"])
    if is_notice_q:
        is_immediate = any(k in ans_low for k in ["immediate", "serving", "lwd", "15 days", "30 days", "0 days", "yes", "true"])
        if is_immediate:
            for orig, low in opt_map:
                if low in ["yes", "immediate", "serving notice period", "yes, immediate", "15-30 days", "< 15 days", "1- 15 days", "1-15 days"]:
                    return orig
                if "yes" in low:
                    return orig

    # 4. Affirmative / Negative matching
    is_affirmative = (
        ans_low in ["yes", "true", "y", "i do", "i have", "definitely", "open", "comfortable", "agreed", "sure"]
        or ans_low.startswith("yes,")
        or ans_low.startswith("yes ")
    )
    is_negative = (
        ans_low in ["no", "false", "n", "nope", "i have not", "none", "not yet", "not comfortable", "nil"]
        or ans_low.startswith("no,")
        or ans_low.startswith("no ")
    )

    if is_affirmative:
        for orig, low in opt_map:
            if low == "yes":
                return orig
        yes_starts = [orig for orig, low in opt_map if low.startswith("yes")]
        if yes_starts:
            return yes_starts[0]
        for orig, low in opt_map:
            if "yes" in low:
                return orig

    if is_negative:
        for orig, low in opt_map:
            if low == "no":
                return orig
        no_starts = [orig for orig, low in opt_map if low.startswith("no")]
        if no_starts:
            return no_starts[0]
        for orig, low in opt_map:
            if "no" in low or "none" in low:
                return orig

    # 5. Substring / Prefix match
    for orig, low in opt_map:
        if len(low) >= 3 and low in ans_low:
            return orig
        if len(ans_low) >= 3 and ans_low in low:
            return orig

    # 6. Fallback word overlap
    ans_words = set(re.findall(r'\b\w{3,}\b', ans_low))
    if ans_words:
        best_opt = None
        best_score = 0
        for orig, low in opt_map:
            opt_words = set(re.findall(r'\b\w{3,}\b', low))
            if opt_words:
                overlap = len(ans_words.intersection(opt_words)) / max(len(ans_words), len(opt_words))
                if overlap > 0.6 and overlap > best_score:
                    best_score = overlap
                    best_opt = orig
        if best_opt:
            return best_opt

    return None



from src.db.question_bank import (
    STANDARD_BASIC_QUESTIONS,
    normalize_question_key,
    infer_question_category,
    save_screening_answers as db_save_screening_answers,
    get_aggregated_question_bank as db_get_aggregated_question_bank,
    get_unanswered_screening_questions_count,
    lookup_answer_for_question,
    upsert_screening_question,
    delete_screening_question as db_delete_screening_question,
    delete_screening_questions_batch as db_delete_screening_questions_batch,
)


def get_stored_answers() -> Dict[str, str]:
    """Retrieve saved answers from PostgreSQL settings."""
    raw = get_setting("screening_question_bank", "{}")
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_stored_answers(answers: Dict[str, str]) -> Dict[str, Any]:
    """Persist updated answers into PostgreSQL screening_questions table and settings."""
    return db_save_screening_answers(answers)


def get_aggregated_question_bank(
    category: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve screening questions from persistent PostgreSQL table with optional filters."""
    return db_get_aggregated_question_bank(
        category=category,
        search=search,
        status=status,
        sort_by=sort_by,
        from_date=from_date,
        to_date=to_date,
    )


def delete_question(key_or_id: str) -> bool:
    """Delete a single screening question by id or normalized key."""
    return db_delete_screening_question(key_or_id)


def delete_questions_batch(keys: List[str]) -> int:
    """Delete multiple screening questions by their keys or ids."""
    return db_delete_screening_questions_batch(keys)


def create_or_update_question(
    question_text: str,
    category: Optional[str] = None,
    answer: Optional[str] = None,
    default_placeholder: Optional[str] = None,
    options: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Manually insert or update a custom question into the Question Bank."""
    return upsert_screening_question(
        question_text=question_text,
        category=category,
        answer=answer,
        default_placeholder=default_placeholder,
        sample_job="Manual User Ingestion",
        options=options,
    )



def get_rate_limit_safeguard_status() -> Dict[str, Any]:
    """Check if LinkedIn safeguard cooldown is currently active."""
    paused_until_raw = get_setting("easy_apply_paused_until", "0")
    reason = get_setting(
        "easy_apply_safeguard_reason",
        "LinkedIn safeguard: Easy Apply temporarily paused due to fast pace to protect account.",
    )
    limit_type = get_setting("easy_apply_limit_type", "fast_pace")
    try:
        paused_until = int(paused_until_raw)
    except Exception:
        paused_until = 0

    now = int(time.time())
    is_paused = paused_until > now
    seconds_remaining = max(0, paused_until - now) if is_paused else 0
    is_daily = (limit_type == "daily_limit") or (
        "today" in (reason or "").lower() and "limit" in (reason or "").lower()
    ) or ("continue applying tomorrow" in (reason or "").lower())

    return {
        "is_paused": is_paused,
        "paused_until": paused_until,
        "seconds_remaining": seconds_remaining,
        "safeguard_reason": reason if is_paused else None,
        "limit_type": "daily_limit" if is_daily else "fast_pace",
        "is_daily_limit": is_daily,
    }


def reset_rate_limit_safeguard() -> Dict[str, Any]:
    """Clear safeguard cooldown in settings to resume Easy Apply immediately."""
    set_setting("easy_apply_paused_until", "0")
    set_setting("easy_apply_safeguard_reason", "")
    set_setting("easy_apply_limit_type", "fast_pace")
    return {"success": True, "message": "Safeguard pause cleared. Easy Apply resumed."}
