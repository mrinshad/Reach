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
) -> Dict[str, Any]:
    """Retrieve screening questions from persistent PostgreSQL table with optional filters."""
    return db_get_aggregated_question_bank(category=category, search=search, status=status, sort_by=sort_by)


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
    try:
        paused_until = int(paused_until_raw)
    except Exception:
        paused_until = 0

    now = int(time.time())
    is_paused = paused_until > now
    seconds_remaining = max(0, paused_until - now) if is_paused else 0

    return {
        "is_paused": is_paused,
        "paused_until": paused_until,
        "seconds_remaining": seconds_remaining,
        "safeguard_reason": reason if is_paused else None,
    }


def reset_rate_limit_safeguard() -> Dict[str, Any]:
    """Clear safeguard cooldown in settings to resume Easy Apply immediately."""
    set_setting("easy_apply_paused_until", "0")
    set_setting("easy_apply_safeguard_reason", "")
    return {"success": True, "message": "Safeguard pause cleared. Easy Apply resumed."}
