"""
Screening Question & Answer Bank Database Module
(src/db/question_bank.py)

Manages persistent database storage, migrations, seeders, answer lookups,
and fuzzy/alias matching for LinkedIn Easy Apply screening automation.
"""

import os
import re
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from src.db.connection import get_connection, DEFAULT_DB_URL
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
    cleaned = (text or "").strip().lower()
    cleaned = re.sub(r'[^a-z0-9]', '', cleaned)
    return cleaned


def infer_question_category(question_text: str) -> str:
    """Categorize a question based on keywords in its text."""
    low = (question_text or "").lower()
    if any(k in low for k in ["ctc", "salary", "lpa", "compensation", "inr", "usd", "hourly", "rate", "in-hand"]):
        return "compensation"
    if any(k in low for k in ["notice", "days", "immediate", "joiner", "months"]):
        return "notice"
    if any(k in low for k in ["phone", "mobile", "email", "city", "location", "address", "country", "postal"]):
        return "contact"
    if any(k in low for k in ["year", "experience", "python", "react", "sql", "fastapi", "typescript", "llm", "ai", "javascript", "full-stack", "data", "engineering", "mentor"]):
        return "experience"
    return "profile"


def init_question_bank(db_url: str = DEFAULT_DB_URL):
    """
    Seed standard questions, migrate legacy answers from settings,
    and backfill questions from historical posts into PostgreSQL screening_questions table.
    """
    conn = get_connection(db_url)
    cur = conn.cursor()

    # 1. Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS screening_questions (
            id VARCHAR(64) PRIMARY KEY,
            question_key VARCHAR(128) UNIQUE NOT NULL,
            question_text TEXT NOT NULL,
            category VARCHAR(64) DEFAULT 'profile',
            answer TEXT,
            is_standard BOOLEAN DEFAULT FALSE,
            default_placeholder TEXT,
            occurrences INT DEFAULT 1,
            sample_jobs TEXT[] DEFAULT '{}',
            status VARCHAR(32) DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_screening_questions_key ON screening_questions(question_key);
        CREATE INDEX IF NOT EXISTS idx_screening_questions_status ON screening_questions(status);
    """)

    # 2. Read legacy saved answers from settings table if present
    legacy_answers = {}
    try:
        cur.execute("SELECT value FROM settings WHERE key = 'screening_question_bank';")
        row = cur.fetchone()
        if row and row[0]:
            legacy_answers = json.loads(row[0])
            if not isinstance(legacy_answers, dict):
                legacy_answers = {}
    except Exception:
        legacy_answers = {}

    # 3. Seed standard basic questions
    for std in STANDARD_BASIC_QUESTIONS:
        norm_key = normalize_question_key(std["question"])
        ans = (
            legacy_answers.get(std["id"])
            or legacy_answers.get(norm_key)
            or ""
        ).strip()
        status = "ANSWERED" if ans else "PENDING"

        cur.execute("""
            INSERT INTO screening_questions (
                id, question_key, question_text, category, answer,
                is_standard, default_placeholder, occurrences, sample_jobs, status, updated_at
            ) VALUES (%s, %s, %s, %s, %s, TRUE, %s, 1, ARRAY['Standard Candidate Profile Question'], %s, CURRENT_TIMESTAMP)
            ON CONFLICT (question_key) DO UPDATE SET
                is_standard = TRUE,
                default_placeholder = EXCLUDED.default_placeholder,
                answer = CASE 
                    WHEN (screening_questions.answer IS NULL OR screening_questions.answer = '') 
                         AND EXCLUDED.answer != '' THEN EXCLUDED.answer
                    ELSE screening_questions.answer 
                END,
                status = CASE
                    WHEN (screening_questions.answer IS NOT NULL AND screening_questions.answer != '')
                         OR (EXCLUDED.answer IS NOT NULL AND EXCLUDED.answer != '') THEN 'ANSWERED'
                    ELSE 'PENDING'
                END;
        """, (
            std["id"],
            norm_key,
            std["question"],
            std["category"],
            ans,
            std.get("default_placeholder", ""),
            status
        ))

    # 4. Migrate any remaining legacy answers that don't match standard IDs
    for k, v in legacy_answers.items():
        if not v or not str(v).strip():
            continue
        val = str(v).strip()
        norm_key = normalize_question_key(k)
        if not norm_key:
            continue
        cur.execute("""
            UPDATE screening_questions
            SET answer = %s, status = 'ANSWERED', updated_at = CURRENT_TIMESTAMP
            WHERE question_key = %s OR id = %s;
        """, (val, norm_key, k))

    # 5. Backfill historical questions from posts with status = 'REQUIRES_QUESTIONNAIRE'
    cur.execute("""
        SELECT author_headline, author_name, rejection_reason 
        FROM posts 
        WHERE status = 'REQUIRES_QUESTIONNAIRE' AND rejection_reason IS NOT NULL;
    """)
    screened_posts = cur.fetchall()

    ignored_generic = {
        "requires screening questions",
        "multi-step questionnaire (saved for screening)",
        "multi-step form required manual input",
        "exceeded step limit, saved for screening",
    }

    for headline, company, reason in screened_posts:
        if not reason:
            continue
        raw = reason.strip()
        if raw.lower().startswith("questions:"):
            raw = raw[len("questions:"):].strip()

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

            ans = legacy_answers.get(norm_key, "").strip()
            status = "ANSWERED" if ans else "PENDING"
            qid = f"q_{hashlib.sha256(norm_key.encode()).hexdigest()[:20]}"
            cat = infer_question_category(cleaned)

            cur.execute("""
                INSERT INTO screening_questions (
                    id, question_key, question_text, category, answer,
                    is_standard, default_placeholder, occurrences, sample_jobs, status, updated_at
                ) VALUES (%s, %s, %s, %s, %s, FALSE, 'Enter your answer...', 1, ARRAY[%s], %s, CURRENT_TIMESTAMP)
                ON CONFLICT (question_key) DO UPDATE SET
                    occurrences = screening_questions.occurrences + 1,
                    sample_jobs = CASE 
                        WHEN NOT (%s = ANY(screening_questions.sample_jobs)) AND array_length(screening_questions.sample_jobs, 1) < 5
                        THEN array_append(screening_questions.sample_jobs, %s)
                        ELSE screening_questions.sample_jobs 
                    END;
            """, (
                qid, norm_key, cleaned, cat, ans, job_label, status,
                job_label, job_label
            ))

    conn.commit()
    cur.close()
    conn.close()


def upsert_screening_question(
    question_text: str,
    category: Optional[str] = None,
    answer: Optional[str] = None,
    is_standard: bool = False,
    default_placeholder: Optional[str] = None,
    sample_job: Optional[str] = None,
    conn=None,
) -> Dict[str, Any]:
    """
    Insert or update a screening question.
    If the question is new, saves it with status='PENDING' (or 'ANSWERED' if answer given).
    If it exists, increments occurrence counter and appends sample job.
    """
    cleaned = (question_text or "").rstrip("*").strip()
    norm_key = normalize_question_key(cleaned)
    if not norm_key:
        return {}

    cat = category or infer_question_category(cleaned)
    ans = (answer or "").strip()
    status = "ANSWERED" if ans else "PENDING"
    qid = f"q_{hashlib.sha256(norm_key.encode()).hexdigest()[:20]}"
    placeholder = default_placeholder or "Enter your answer..."
    jobs_array = [sample_job] if sample_job else ["Direct Application Flow"]

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        cur = conn.cursor()
        if ans:
            cur.execute("""
                INSERT INTO screening_questions (
                    id, question_key, question_text, category, answer,
                    is_standard, default_placeholder, occurrences, sample_jobs, status, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (question_key) DO UPDATE SET
                    answer = EXCLUDED.answer,
                    status = 'ANSWERED',
                    occurrences = screening_questions.occurrences + 1,
                    sample_jobs = CASE 
                        WHEN %s IS NOT NULL AND NOT (%s = ANY(screening_questions.sample_jobs)) AND array_length(screening_questions.sample_jobs, 1) < 5
                        THEN array_append(screening_questions.sample_jobs, %s)
                        ELSE screening_questions.sample_jobs 
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, question_key, question_text, category, answer, is_standard, occurrences, sample_jobs, status;
            """, (
                qid, norm_key, cleaned, cat, ans, is_standard, placeholder, jobs_array, status,
                sample_job, sample_job, sample_job
            ))
        else:
            cur.execute("""
                INSERT INTO screening_questions (
                    id, question_key, question_text, category, answer,
                    is_standard, default_placeholder, occurrences, sample_jobs, status, updated_at
                ) VALUES (%s, %s, %s, %s, NULL, %s, %s, 1, %s, 'PENDING', CURRENT_TIMESTAMP)
                ON CONFLICT (question_key) DO UPDATE SET
                    occurrences = screening_questions.occurrences + 1,
                    sample_jobs = CASE 
                        WHEN %s IS NOT NULL AND NOT (%s = ANY(screening_questions.sample_jobs)) AND array_length(screening_questions.sample_jobs, 1) < 5
                        THEN array_append(screening_questions.sample_jobs, %s)
                        ELSE screening_questions.sample_jobs 
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, question_key, question_text, category, answer, is_standard, occurrences, sample_jobs, status;
            """, (
                qid, norm_key, cleaned, cat, is_standard, placeholder, jobs_array,
                sample_job, sample_job, sample_job
            ))
        row = cur.fetchone()
        conn.commit()
        cur.close()

        if row:
            return {
                "id": row[0],
                "key": row[1],
                "question": row[2],
                "category": row[3],
                "answer": row[4] or "",
                "is_standard": row[5],
                "occurrences": row[6],
                "sample_jobs": row[7] or [],
                "status": row[8],
            }
        return {}
    finally:
        if should_close and conn:
            conn.close()


def save_screening_answers(answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Persist user answers into PostgreSQL screening_questions table.
    Updates status to 'ANSWERED' when an answer is provided, or 'PENDING' when empty.
    Synchronizes with settings.screening_question_bank for backward compatibility.
    """
    if not isinstance(answers, dict):
        return {"saved_count": 0, "total_saved": 0}

    conn = get_connection()
    cur = conn.cursor()

    saved_count = 0
    for key, val in answers.items():
        if key is None:
            continue
        k_clean = str(key).strip()
        norm_key = normalize_question_key(k_clean)
        ans_clean = str(val).strip() if val is not None else ""
        status = "ANSWERED" if ans_clean else "PENDING"

        cur.execute("""
            UPDATE screening_questions
            SET answer = %s,
                status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE question_key = %s OR id = %s;
        """, (ans_clean, status, norm_key, k_clean))

        if cur.rowcount > 0:
            saved_count += 1
        elif ans_clean:
            # If not in table yet, insert it as a dynamic question
            upsert_screening_question(
                question_text=k_clean,
                answer=ans_clean,
                conn=conn
            )
            saved_count += 1

    conn.commit()

    # Query all answered questions to synchronize settings table
    cur.execute("""
        SELECT question_key, id, answer 
        FROM screening_questions 
        WHERE answer IS NOT NULL AND answer != '';
    """)
    answered_rows = cur.fetchall()

    sync_dict = {}
    for qkey, qid, qans in answered_rows:
        if qkey:
            sync_dict[qkey] = qans
        if qid:
            sync_dict[qid] = qans
    set_setting("screening_question_bank", json.dumps(sync_dict))

    # Query updated stats
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'ANSWERED' AND answer IS NOT NULL AND answer != '' THEN 1 END) as answered,
            COUNT(CASE WHEN status = 'PENDING' OR answer IS NULL OR answer = '' THEN 1 END) as pending
        FROM screening_questions;
    """)
    stat_row = cur.fetchone()
    total_cnt = stat_row[0] if stat_row else 0
    ans_cnt = stat_row[1] if stat_row else 0
    pending_cnt = stat_row[2] if stat_row else 0

    cur.close()
    conn.close()

    return {
        "saved_count": saved_count,
        "total_count": total_cnt,
        "answered_count": ans_cnt,
        "pending_count": pending_cnt,
    }


def get_aggregated_question_bank(
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve all screening questions from PostgreSQL screening_questions table.
    Sorts standard questions first, then by occurrence count descending, then question text.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            id, question_key, question_text, category, answer,
            is_standard, default_placeholder, occurrences, sample_jobs, status, updated_at
        FROM screening_questions
        ORDER BY is_standard DESC, occurrences DESC, question_text ASC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    questions = []
    total_count = len(rows)
    answered_count = 0
    pending_count = 0

    for r in rows:
        ans = (r[4] or "").strip()
        is_ans = bool(ans)
        if is_ans:
            answered_count += 1
        else:
            pending_count += 1

        q_item = {
            "id": r[0],
            "key": r[1],
            "question": r[2],
            "category": r[3] or "profile",
            "answer": ans,
            "is_standard": bool(r[5]),
            "default_placeholder": r[6] or "Enter your answer...",
            "occurrences": r[7] or 1,
            "sample_jobs": r[8] or [],
            "status": "ANSWERED" if is_ans else "PENDING",
            "updated_at": r[10].isoformat() if r[10] else None,
        }

        # Apply category filter if requested
        if category and isinstance(category, str):
            cat_low = category.lower().strip()
            if cat_low == "unanswered" and is_ans:
                continue
            elif cat_low != "all" and cat_low != "unanswered" and q_item["category"] != cat_low:
                continue

        # Apply search filter if requested
        if search and isinstance(search, str):
            s_low = search.lower().strip()
            if s_low not in q_item["question"].lower() and s_low not in q_item["answer"].lower():
                continue

        questions.append(q_item)

    return {
        "total_count": total_count,
        "answered_count": answered_count,
        "pending_count": pending_count,
        "questions": questions,
    }


def get_unanswered_screening_questions_count() -> int:
    """Return count of screening questions currently missing answers in DB."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM screening_questions 
        WHERE status = 'PENDING' OR answer IS NULL OR answer = '';
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return int(row[0]) if row else 0


def lookup_answer_for_question(question_text: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Search DB Question Bank for an answer to a given question label/prompt.
    Uses multi-tier matching:
    1. Exact normalized alphanumeric key match.
    2. Smart aliases for standard fields (phone, email, CTC, notice period, experience, English, remote/hybrid).
    3. Keyword heuristic match.
    Returns (answer_string_or_None, question_dict_or_None).
    """
    if not question_text:
        return None, None

    cleaned = question_text.strip().rstrip("*")
    norm_key = normalize_question_key(cleaned)
    if not norm_key:
        return None, None

    conn = get_connection()
    cur = conn.cursor()

    # 1. Exact key match
    cur.execute("""
        SELECT id, question_key, question_text, category, answer, is_standard, status
        FROM screening_questions
        WHERE question_key = %s;
    """, (norm_key,))
    row = cur.fetchone()

    if row and row[4] and row[4].strip():
        cur.close()
        conn.close()
        return row[4].strip(), {
            "id": row[0],
            "key": row[1],
            "question": row[2],
            "category": row[3],
            "answer": row[4].strip(),
            "is_standard": row[5],
        }

    # Fetch all standard and answered questions for smart alias matching
    cur.execute("""
        SELECT id, question_key, question_text, category, answer, is_standard
        FROM screening_questions
        WHERE answer IS NOT NULL AND answer != '';
    """)
    answered_pool = cur.fetchall()
    cur.close()
    conn.close()

    answers_by_id = {r[0]: (r[4].strip(), r) for r in answered_pool}
    answers_by_key = {r[1]: (r[4].strip(), r) for r in answered_pool}

    q_low = cleaned.lower()

    # Helper alias checks
    def check_alias(target_id: str, default_ans: Optional[str] = None):
        if target_id in answers_by_id:
            return answers_by_id[target_id][0], answers_by_id[target_id][1]
        norm = normalize_question_key(target_id)
        if norm in answers_by_key:
            return answers_by_key[norm][0], answers_by_key[norm][1]
        return default_ans, None

    # 2. Smart aliases
    if any(k in q_low for k in ["phone", "mobile", "contact number"]):
        ans, r = check_alias("std_phone")
        if ans:
            return ans, {"id": "std_phone", "answer": ans}

    if "email" in q_low and not any(k in q_low for k in ["send", "subject"]):
        ans, r = check_alias("std_email")
        if ans:
            return ans, {"id": "std_email", "answer": ans}

    if any(k in q_low for k in ["city", "current location", "present location", "residing in"]) and "relocat" not in q_low:
        ans, r = check_alias("std_location")
        if ans:
            return ans, {"id": "std_location", "answer": ans}

    if any(k in q_low for k in ["current ctc", "current salary", "fixed ctc", "fix ctc", "in-hand salary", "current compensation"]):
        ans, r = check_alias("std_current_ctc")
        if ans:
            return ans, {"id": "std_current_ctc", "answer": ans}

    if any(k in q_low for k in ["expected ctc", "expected salary", "desired compensation", "expectation fix ctc", "ectc"]):
        ans, r = check_alias("std_expected_ctc")
        if ans:
            return ans, {"id": "std_expected_ctc", "answer": ans}

    if any(k in q_low for k in ["notice period", "notice days", "days left in your notice", "how many days is your notice", "joining time"]):
        ans, r = check_alias("std_notice_period")
        if ans:
            return ans, {"id": "std_notice_period", "answer": ans}

    if any(k in q_low for k in ["total years", "total experience", "overall experience", "years of professional experience"]):
        ans, r = check_alias("std_experience_total")
        if ans:
            return ans, {"id": "std_experience_total", "answer": ans}

    if any(k in q_low for k in ["full stack", "fullstack", "web development"]):
        ans, r = check_alias("std_experience_fullstack")
        if ans:
            return ans, {"id": "std_experience_fullstack", "answer": ans}

    if any(k in q_low for k in ["react", "next.js", "nextjs", "typescript"]):
        ans, r = check_alias("std_experience_react")
        if ans:
            return ans, {"id": "std_experience_react", "answer": ans}

    if any(k in q_low for k in ["python", "node", "fastapi", "django", "backend"]):
        ans, r = check_alias("std_experience_backend")
        if ans:
            return ans, {"id": "std_experience_backend", "answer": ans}

    if "english" in q_low:
        ans, r = check_alias("std_english")
        if ans:
            return ans, {"id": "std_english", "answer": ans}

    if any(k in q_low for k in ["remote", "hybrid", "on-site", "work from home", "wfh"]):
        ans, r = check_alias("std_work_mode")
        if ans:
            return ans, {"id": "std_work_mode", "answer": ans}

    # 3. Fuzzy substring match on question_text of already answered questions
    for r in answered_pool:
        known_q = r[2].lower()
        if (len(known_q) > 10 and known_q in q_low) or (len(q_low) > 10 and q_low in known_q):
            return r[4].strip(), {
                "id": r[0],
                "key": r[1],
                "question": r[2],
                "category": r[3],
                "answer": r[4].strip(),
                "is_standard": r[5],
            }

    # If row was found in exact key match but answer was empty:
    if row:
        return None, {
            "id": row[0],
            "key": row[1],
            "question": row[2],
            "category": row[3],
            "answer": "",
            "is_standard": row[5],
        }

    return None, None
