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


def get_stored_answers() -> Dict[str, str]:
    """Retrieve saved answers from PostgreSQL settings."""
    raw = get_setting("screening_question_bank", "{}")
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_stored_answers(answers: Dict[str, str]) -> Dict[str, Any]:
    """Merge and persist updated answers into PostgreSQL settings."""
    current = get_stored_answers()
    current.update(answers)
    set_setting("screening_question_bank", json.dumps(current))
    return {
        "saved_count": len(answers),
        "total_saved": len(current),
    }


def get_aggregated_question_bank() -> Dict[str, Any]:
    """
    Aggregate all unique screening questions across:
    1. Standard profile questions (contact, compensation, notice, experience).
    2. Dynamically extracted questions from all REQUIRES_QUESTIONNAIRE posts.
    Merges with persistent answers from database settings.
    """
    saved_answers = get_stored_answers()
    questions_map: Dict[str, Dict[str, Any]] = {}

    # 1. Seed standard profile questions
    for std in STANDARD_BASIC_QUESTIONS:
        norm_key = normalize_question_key(std["question"])
        # Also check if user answered by id or norm_key
        ans = saved_answers.get(std["id"]) or saved_answers.get(norm_key) or ""
        questions_map[norm_key] = {
            "id": std["id"],
            "key": norm_key,
            "question": std["question"],
            "category": std["category"],
            "default_placeholder": std.get("default_placeholder", ""),
            "is_standard": True,
            "occurrences": 1,
            "sample_jobs": ["Standard Profile Question"],
            "answer": ans,
        }

    # 2. Extract dynamic questions from database posts
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, author_headline, author_name, rejection_reason 
        FROM posts 
        WHERE status = 'REQUIRES_QUESTIONNAIRE' 
          AND (category = 'EASY_APPLY' OR category IS NULL);
    """)
    screened_posts = cur.fetchall()
    cur.close()
    conn.close()

    ignored_generic = {
        "requires screening questions",
        "multi-step questionnaire (saved for screening)",
        "multi-step form required manual input",
        "exceeded step limit, saved for screening",
    }

    for pid, headline, company, reason in screened_posts:
        if not reason:
            continue
        raw = reason
        if raw.startswith("Questions:"):
            raw = raw[len("Questions:"):].strip()

        # Split multiple questions by semicolon
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        job_label = f"{headline or 'Job'} @ {company or 'Company'}"

        for p in parts:
            cleaned = p.rstrip("*").strip()
            if not cleaned or len(cleaned) < 3 or cleaned.lower() in ignored_generic:
                continue

            norm_key = normalize_question_key(cleaned)
            if not norm_key:
                continue

            if norm_key in questions_map:
                questions_map[norm_key]["occurrences"] += 1
                if job_label not in questions_map[norm_key]["sample_jobs"] and len(questions_map[norm_key]["sample_jobs"]) < 4:
                    questions_map[norm_key]["sample_jobs"].append(job_label)
            else:
                ans = saved_answers.get(norm_key) or ""
                cat = infer_question_category(cleaned)
                questions_map[norm_key] = {
                    "id": f"q_{norm_key[:24]}",
                    "key": norm_key,
                    "question": cleaned,
                    "category": cat,
                    "default_placeholder": "Enter your answer...",
                    "is_standard": False,
                    "occurrences": 1,
                    "sample_jobs": [job_label],
                    "answer": ans,
                }

    # Sort questions: standard first, then by occurrences descending, then by question label
    question_list = list(questions_map.values())
    question_list.sort(key=lambda q: (not q["is_standard"], -q["occurrences"], q["question"]))

    total_count = len(question_list)
    answered_count = sum(1 for q in question_list if bool(q.get("answer", "").strip()))

    return {
        "total_count": total_count,
        "answered_count": answered_count,
        "questions": question_list,
    }


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
