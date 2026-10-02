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
        "options": [],
    },
    {
        "id": "std_email",
        "question": "Email address",
        "category": "contact",
        "default_placeholder": "rinshadmorayur09@gmail.com",
        "is_standard": True,
        "options": [],
    },
    {
        "id": "std_middle_name",
        "question": "Middle Name",
        "category": "contact",
        "answer": "__EMPTY__",
        "default_placeholder": "(Intentionally left blank / N/A)",
        "is_standard": True,
        "options": [],
    },
    {
        "id": "std_location",
        "question": "Current City / Location",
        "category": "contact",
        "default_placeholder": "Malappuram, Kerala, India",
        "is_standard": True,
        "options": [],
    },
    {
        "id": "std_experience_total",
        "question": "Total years of professional software engineering experience",
        "category": "experience",
        "default_placeholder": "3+",
        "is_standard": True,
        "options": ["1", "2", "3", "4", "5", "6", "7", "8+"],
    },
    {
        "id": "std_experience_fullstack",
        "question": "Years of Full Stack / Web Application Development experience",
        "category": "experience",
        "default_placeholder": "3+",
        "is_standard": True,
        "options": ["1", "2", "3", "4", "5", "6", "7", "8+"],
    },
    {
        "id": "std_experience_react",
        "question": "Years of experience with React / Next.js / TypeScript",
        "category": "experience",
        "default_placeholder": "3",
        "is_standard": True,
        "options": ["1", "2", "3", "4", "5", "6", "7", "8+"],
    },
    {
        "id": "std_experience_backend",
        "question": "Years of experience with Python / Node.js / FastAPI / APIs",
        "category": "experience",
        "default_placeholder": "3",
        "is_standard": True,
        "options": ["1", "2", "3", "4", "5", "6", "7", "8+"],
    },
    {
        "id": "std_current_ctc",
        "question": "Current CTC / Salary (in LPA or INR)",
        "category": "compensation",
        "default_placeholder": "e.g. 6 LPA",
        "is_standard": True,
        "options": [],
    },
    {
        "id": "std_expected_ctc",
        "question": "Expected CTC / Salary (in LPA or INR)",
        "category": "compensation",
        "default_placeholder": "Negotiable / As per company standards",
        "is_standard": True,
        "options": [],
    },
    {
        "id": "std_notice_period",
        "question": "Notice Period (in Days)",
        "category": "notice",
        "default_placeholder": "Immediate / 15-30 days",
        "is_standard": True,
        "options": ["Immediate", "15 Days", "30 Days", "45 Days", "60 Days", "90 Days"],
    },
    {
        "id": "std_english",
        "question": "Level of proficiency in English (1-10 or Fluent/Professional)",
        "category": "profile",
        "default_placeholder": "Professional / Fluent (8/10)",
        "is_standard": True,
        "options": ["Fluent", "Professional", "Conversational", "Basic"],
    },
    {
        "id": "std_work_mode",
        "question": "Comfortable with Remote / Hybrid / On-site roles?",
        "category": "profile",
        "default_placeholder": "Yes, open to Remote and Hybrid roles",
        "is_standard": True,
        "options": ["Yes", "No", "Remote", "Hybrid", "On-site"],
    },
]

TOMBSTONE_SETTING_KEY = "deleted_screening_questions"


def get_deleted_question_keys() -> set:
    """Retrieve set of soft-deleted / dismissed question keys from settings."""
    raw = get_setting(TOMBSTONE_SETTING_KEY, "[]")
    try:
        data = json.loads(raw)
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()


def add_to_deleted_question_keys(keys: List[str]):
    """Add question keys to tombstone list to prevent resurrection on crawler backfill."""
    cur_keys = get_deleted_question_keys()
    for k in keys:
        if k:
            cur_keys.add(str(k).strip())
            norm = normalize_question_key(k)
            if norm:
                cur_keys.add(norm)
    set_setting(TOMBSTONE_SETTING_KEY, json.dumps(list(cur_keys)))


def remove_from_deleted_question_keys(keys: List[str]):
    """Remove keys from tombstone list when user explicitly creates/re-adds question."""
    cur_keys = get_deleted_question_keys()
    changed = False
    for k in keys:
        if not k:
            continue
        ks = str(k).strip()
        norm = normalize_question_key(ks)
        if ks in cur_keys:
            cur_keys.remove(ks)
            changed = True
        if norm in cur_keys:
            cur_keys.remove(norm)
            changed = True
    if changed:
        set_setting(TOMBSTONE_SETTING_KEY, json.dumps(list(cur_keys)))


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
    if any(k in low for k in ["phone", "mobile", "email", "city", "location", "address", "country", "postal", "middle name"]):
        return "contact"
    if any(k in low for k in ["year", "experience", "python", "react", "sql", "fastapi", "typescript", "llm", "ai", "javascript", "full-stack", "data", "engineering", "mentor"]):
        return "experience"
    return "profile"


def init_question_bank(db_url: str = DEFAULT_DB_URL):
    """
    Seed standard questions, migrate legacy answers from settings,
    and backfill questions from historical posts into PostgreSQL screening_questions table.
    Guards against resurrecting deleted questions using the tombstone blacklist.
    """
    conn = get_connection(db_url)
    cur = conn.cursor()

    # 1. Ensure table exists with options column
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
            options TEXT[] DEFAULT '{}',
            status VARCHAR(32) DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_screening_questions_key ON screening_questions(question_key);
        CREATE INDEX IF NOT EXISTS idx_screening_questions_status ON screening_questions(status);
        ALTER TABLE screening_questions ADD COLUMN IF NOT EXISTS options TEXT[] DEFAULT '{}';
    """)

    # 2. Read legacy saved answers and tombstone set
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

    deleted_keys = get_deleted_question_keys()

    # 3. Seed standard basic questions (skipping tombstoned keys)
    for std in STANDARD_BASIC_QUESTIONS:
        norm_key = normalize_question_key(std["question"])
        if std["id"] in deleted_keys or norm_key in deleted_keys:
            continue

        std_ans = std.get("answer", "")
        ans = (
            legacy_answers.get(std["id"])
            or legacy_answers.get(norm_key)
            or std_ans
            or ""
        ).strip()
        status = "ANSWERED" if (ans or ans == "__EMPTY__") else "PENDING"
        std_options = std.get("options", [])

        cur.execute("""
            INSERT INTO screening_questions (
                id, question_key, question_text, category, answer,
                is_standard, default_placeholder, occurrences, sample_jobs, options, status, updated_at
            ) VALUES (%s, %s, %s, %s, %s, TRUE, %s, 1, ARRAY['Standard Candidate Profile Question'], %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (question_key) DO UPDATE SET
                is_standard = TRUE,
                default_placeholder = EXCLUDED.default_placeholder,
                options = CASE 
                    WHEN array_length(EXCLUDED.options, 1) > 0 AND (screening_questions.options IS NULL OR array_length(screening_questions.options, 1) = 0)
                    THEN EXCLUDED.options
                    ELSE screening_questions.options
                END,
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
            std_options,
            status
        ))

    # 4. Migrate any remaining legacy answers that don't match standard IDs
    for k, v in legacy_answers.items():
        if not v or not str(v).strip():
            continue
        val = str(v).strip()
        norm_key = normalize_question_key(k)
        if not norm_key or norm_key in deleted_keys or k in deleted_keys:
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
            if not norm_key or norm_key in deleted_keys:
                continue

            ans = legacy_answers.get(norm_key, "").strip()
            status = "ANSWERED" if (ans or ans == "__EMPTY__") else "PENDING"
            qid = f"q_{hashlib.sha256(norm_key.encode()).hexdigest()[:20]}"
            cat = infer_question_category(cleaned)

            cur.execute("""
                INSERT INTO screening_questions (
                    id, question_key, question_text, category, answer,
                    is_standard, default_placeholder, occurrences, sample_jobs, options, status, updated_at
                ) VALUES (%s, %s, %s, %s, %s, FALSE, 'Enter your answer...', 1, ARRAY[%s], '{}', %s, CURRENT_TIMESTAMP)
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
    options: Optional[List[str]] = None,
    conn=None,
) -> Dict[str, Any]:
    """
    Insert or update a screening question.
    If the question is new, saves it with status='PENDING' (or 'ANSWERED' if answer/empty given).
    If it exists, increments occurrence counter, updates options, and appends sample job.
    Removes key from tombstone blacklist if user sets an answer.
    """
    cleaned = (question_text or "").rstrip("*").strip()
    norm_key = normalize_question_key(cleaned)
    if not norm_key:
        return {}

    cat = category or infer_question_category(cleaned)
    ans = (answer or "").strip() if answer is not None else ""
    is_empty_spec = (ans == "__EMPTY__")
    status = "ANSWERED" if (ans or is_empty_spec) else "PENDING"
    qid = f"q_{hashlib.sha256(norm_key.encode()).hexdigest()[:20]}"
    placeholder = default_placeholder or ("(Intentionally left blank / N/A)" if is_empty_spec else "Enter your answer...")
    jobs_array = [sample_job] if sample_job else ["Direct Application Flow"]

    # Filter and sanitize options
    clean_options = []
    if options and isinstance(options, list):
        for opt in options:
            if opt and str(opt).strip():
                clean_options.append(str(opt).strip())

    # If saving with an answer or empty setting, remove from tombstone blacklist
    if status == "ANSWERED":
        remove_from_deleted_question_keys([norm_key, qid, cleaned])

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        cur = conn.cursor()
        if status == "ANSWERED":
            cur.execute("""
                INSERT INTO screening_questions (
                    id, question_key, question_text, category, answer,
                    is_standard, default_placeholder, occurrences, sample_jobs, options, status, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (question_key) DO UPDATE SET
                    answer = EXCLUDED.answer,
                    status = 'ANSWERED',
                    options = CASE 
                        WHEN array_length(EXCLUDED.options, 1) > 0 THEN EXCLUDED.options
                        ELSE screening_questions.options
                    END,
                    occurrences = screening_questions.occurrences + 1,
                    sample_jobs = CASE 
                        WHEN %s IS NOT NULL AND NOT (%s = ANY(screening_questions.sample_jobs)) AND array_length(screening_questions.sample_jobs, 1) < 5
                        THEN array_append(screening_questions.sample_jobs, %s)
                        ELSE screening_questions.sample_jobs 
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, question_key, question_text, category, answer, is_standard, occurrences, sample_jobs, options, status;
            """, (
                qid, norm_key, cleaned, cat, ans, is_standard, placeholder, jobs_array, clean_options, status,
                sample_job, sample_job, sample_job
            ))
        else:
            cur.execute("""
                INSERT INTO screening_questions (
                    id, question_key, question_text, category, answer,
                    is_standard, default_placeholder, occurrences, sample_jobs, options, status, updated_at
                ) VALUES (%s, %s, %s, %s, NULL, %s, %s, 1, %s, %s, 'PENDING', CURRENT_TIMESTAMP)
                ON CONFLICT (question_key) DO UPDATE SET
                    options = CASE 
                        WHEN array_length(EXCLUDED.options, 1) > 0 THEN EXCLUDED.options
                        ELSE screening_questions.options
                    END,
                    occurrences = screening_questions.occurrences + 1,
                    sample_jobs = CASE 
                        WHEN %s IS NOT NULL AND NOT (%s = ANY(screening_questions.sample_jobs)) AND array_length(screening_questions.sample_jobs, 1) < 5
                        THEN array_append(screening_questions.sample_jobs, %s)
                        ELSE screening_questions.sample_jobs 
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, question_key, question_text, category, answer, is_standard, occurrences, sample_jobs, options, status;
            """, (
                qid, norm_key, cleaned, cat, is_standard, placeholder, jobs_array, clean_options,
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
                "options": list(row[8]) if row[8] else [],
                "status": row[9],
            }
        return {}
    finally:
        if should_close and conn:
            conn.close()


def save_screening_answers(answers: Dict[str, str]) -> Dict[str, Any]:
    """
    Persist user answers into PostgreSQL screening_questions table.
    Updates status to 'ANSWERED' when an answer or '__EMPTY__' is provided.
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
        ans_raw = str(val).strip() if val is not None else ""
        is_empty_spec = (ans_raw == "__EMPTY__")
        status = "ANSWERED" if (ans_raw != "" or is_empty_spec) else "PENDING"

        # Remove from tombstone blacklist since user explicitly saved it
        remove_from_deleted_question_keys([norm_key, k_clean])

        cur.execute("""
            UPDATE screening_questions
            SET answer = %s,
                status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE question_key = %s OR id = %s;
        """, (ans_raw, status, norm_key, k_clean))

        if cur.rowcount > 0:
            saved_count += 1
        elif ans_raw or is_empty_spec:
            # If not in table yet, insert it as a dynamic question
            upsert_screening_question(
                question_text=k_clean,
                answer=ans_raw,
                conn=conn
            )
            saved_count += 1

    conn.commit()

    # Query all answered questions to synchronize settings table
    cur.execute("""
        SELECT question_key, id, answer 
        FROM screening_questions 
        WHERE status = 'ANSWERED' AND answer IS NOT NULL;
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
            COUNT(CASE WHEN status = 'ANSWERED' THEN 1 END) as answered,
            COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending
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
    status: Optional[str] = None,
    sort_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve all screening questions from PostgreSQL screening_questions table.
    Supports filtering by category, search text, answering status, and flexible sorting.
    Includes multi-choice options for dropdowns and radios.
    """
    order_clause = "ORDER BY is_standard DESC, occurrences DESC, question_text ASC"
    if sort_by and isinstance(sort_by, str):
        sb = sort_by.lower().strip()
        if sb in ("recent", "updated"):
            order_clause = "ORDER BY updated_at DESC, occurrences DESC"
        elif sb in ("alpha", "alphabetical", "title"):
            order_clause = "ORDER BY question_text ASC"
        elif sb in ("occurrences", "popular", "frequent"):
            order_clause = "ORDER BY occurrences DESC, question_text ASC"
        elif sb in ("standard", "std"):
            order_clause = "ORDER BY is_standard DESC, question_text ASC"
        elif sb in ("status", "pending_first"):
            order_clause = "ORDER BY (CASE WHEN status = 'ANSWERED' THEN 1 ELSE 0 END) ASC, occurrences DESC"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT 
            id, question_key, question_text, category, answer,
            is_standard, default_placeholder, occurrences, sample_jobs, status, updated_at, options
        FROM screening_questions
        {order_clause};
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
        status_val = (r[9] or "PENDING").upper()
        is_ans = (status_val == "ANSWERED") or bool(ans) or (ans == "__EMPTY__")
        opts = list(r[11]) if (len(r) > 11 and r[11]) else []

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
            "options": opts,
        }

        # Apply status filter if requested
        if status and isinstance(status, str):
            stat_low = status.lower().strip()
            if stat_low in ("pending", "unanswered") and is_ans:
                continue
            elif stat_low in ("answered", "completed") and not is_ans:
                continue

        # Apply category filter if requested
        if category and isinstance(category, str):
            cat_low = category.lower().strip()
            if cat_low in ("unanswered", "pending") and is_ans:
                continue
            elif cat_low not in ("all", "unanswered", "pending") and q_item["category"] != cat_low:
                continue

        # Apply search filter if requested
        if search and isinstance(search, str):
            s_low = search.lower().strip()
            text_match = s_low in q_item["question"].lower()
            ans_match = s_low in q_item["answer"].lower()
            cat_match = s_low in q_item["category"].lower()
            jobs_match = any(s_low in str(j).lower() for j in q_item["sample_jobs"])
            opts_match = any(s_low in str(o).lower() for o in opts)
            if not (text_match or ans_match or cat_match or jobs_match or opts_match):
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
        WHERE status = 'PENDING' AND (answer IS NULL OR (answer = '' AND status != 'ANSWERED'));
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
    2. Smart aliases for standard fields (phone, email, middle name, CTC, notice period, experience, English, remote/hybrid).
    3. Keyword heuristic match.
    Returns (answer_string_or_None, question_dict_or_None).
    Supports explicit empty response ('__EMPTY__').
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
        SELECT id, question_key, question_text, category, answer, is_standard, status, options
        FROM screening_questions
        WHERE question_key = %s;
    """, (norm_key,))
    row = cur.fetchone()

    if row and ((row[4] is not None and row[4] != "") or row[6] == "ANSWERED"):
        ans_val = (row[4] or "").strip()
        cur.close()
        conn.close()
        return ans_val, {
            "id": row[0],
            "key": row[1],
            "question": row[2],
            "category": row[3],
            "answer": ans_val,
            "is_standard": row[5],
            "status": row[6],
            "options": list(row[7]) if (len(row) > 7 and row[7]) else [],
        }

    # Fetch all standard and answered questions for smart alias matching
    cur.execute("""
        SELECT id, question_key, question_text, category, answer, is_standard, status, options
        FROM screening_questions
        WHERE status = 'ANSWERED' OR (answer IS NOT NULL AND answer != '');
    """)
    answered_pool = cur.fetchall()
    cur.close()
    conn.close()

    answers_by_id = {r[0]: ((r[4] or "").strip(), r) for r in answered_pool}
    answers_by_key = {r[1]: ((r[4] or "").strip(), r) for r in answered_pool}

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
    if "middle name" in q_low or q_low in ["middle_name", "middlename"]:
        ans, r = check_alias("std_middle_name", "__EMPTY__")
        return ans, {"id": "std_middle_name", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["phone", "mobile", "contact number"]):
        ans, r = check_alias("std_phone")
        if ans:
            return ans, {"id": "std_phone", "answer": ans, "status": "ANSWERED"}

    if "email" in q_low and not any(k in q_low for k in ["send", "subject"]):
        ans, r = check_alias("std_email")
        if ans:
            return ans, {"id": "std_email", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["city", "current location", "present location", "residing in"]) and "relocat" not in q_low:
        ans, r = check_alias("std_location")
        if ans:
            return ans, {"id": "std_location", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["current ctc", "current salary", "fixed ctc", "fix ctc", "in-hand salary", "current compensation"]):
        ans, r = check_alias("std_current_ctc")
        if ans:
            return ans, {"id": "std_current_ctc", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["expected ctc", "expected salary", "desired compensation", "expectation fix ctc", "ectc"]):
        ans, r = check_alias("std_expected_ctc")
        if ans:
            return ans, {"id": "std_expected_ctc", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["notice period", "notice days", "days left in your notice", "how many days is your notice", "joining time"]):
        ans, r = check_alias("std_notice_period")
        if ans:
            return ans, {"id": "std_notice_period", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["total years", "total experience", "overall experience", "years of professional experience"]):
        ans, r = check_alias("std_experience_total")
        if ans:
            return ans, {"id": "std_experience_total", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["full stack", "fullstack", "web development"]):
        ans, r = check_alias("std_experience_fullstack")
        if ans:
            return ans, {"id": "std_experience_fullstack", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["react", "next.js", "nextjs", "typescript"]):
        ans, r = check_alias("std_experience_react")
        if ans:
            return ans, {"id": "std_experience_react", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["python", "node", "fastapi", "django", "backend"]):
        ans, r = check_alias("std_experience_backend")
        if ans:
            return ans, {"id": "std_experience_backend", "answer": ans, "status": "ANSWERED"}

    if "english" in q_low:
        ans, r = check_alias("std_english")
        if ans:
            return ans, {"id": "std_english", "answer": ans, "status": "ANSWERED"}

    if any(k in q_low for k in ["remote", "hybrid", "on-site", "work from home", "wfh"]):
        ans, r = check_alias("std_work_mode")
        if ans:
            return ans, {"id": "std_work_mode", "answer": ans, "status": "ANSWERED"}

    # 3. Fuzzy substring match on question_text of already answered questions
    for r in answered_pool:
        known_q = r[2].lower()
        if (len(known_q) > 10 and known_q in q_low) or (len(q_low) > 10 and q_low in known_q):
            ans_val = (r[4] or "").strip()
            return ans_val, {
                "id": r[0],
                "key": r[1],
                "question": r[2],
                "category": r[3],
                "answer": ans_val,
                "is_standard": r[5],
                "status": r[6],
                "options": list(r[7]) if (len(r) > 7 and r[7]) else [],
            }

    # If row was found in exact key match but answer was pending:
    if row:
        return None, {
            "id": row[0],
            "key": row[1],
            "question": row[2],
            "category": row[3],
            "answer": "",
            "is_standard": row[5],
            "status": row[6],
            "options": list(row[7]) if (len(row) > 7 and row[7]) else [],
        }

    return None, None


def delete_screening_question(key_or_id: str) -> bool:
    """
    Delete a screening question by id or normalized question_key.
    Adds key to tombstone blacklist to prevent resurrection during crawler backfills.
    Cleans reference from historical posts with status='REQUIRES_QUESTIONNAIRE'.
    """
    if not key_or_id:
        return False
    k_clean = str(key_or_id).strip()
    norm_key = normalize_question_key(k_clean)

    conn = get_connection()
    cur = conn.cursor()

    # Fetch question text before deleting to clean post rejection_reasons
    cur.execute("SELECT question_text FROM screening_questions WHERE id = %s OR question_key = %s;", (k_clean, norm_key))
    q_row = cur.fetchone()
    q_text = q_row[0] if q_row else None

    cur.execute("""
        DELETE FROM screening_questions
        WHERE id = %s OR question_key = %s;
    """, (k_clean, norm_key))
    deleted = cur.rowcount > 0

    if deleted:
        # Add to tombstone blacklist
        add_to_deleted_question_keys([k_clean, norm_key, q_text])

        # Clean from legacy settings
        try:
            raw = get_setting("screening_question_bank", "{}")
            cur_dict = json.loads(raw) if raw else {}
            if k_clean in cur_dict:
                del cur_dict[k_clean]
            if norm_key in cur_dict:
                del cur_dict[norm_key]
            set_setting("screening_question_bank", json.dumps(cur_dict))
        except Exception:
            pass

        # Clean from posts with status = 'REQUIRES_QUESTIONNAIRE'
        try:
            cur.execute("""
                SELECT id, rejection_reason FROM posts 
                WHERE status = 'REQUIRES_QUESTIONNAIRE' AND rejection_reason IS NOT NULL;
            """)
            screened_posts = cur.fetchall()
            all_targets = {k_clean.lower(), norm_key.lower()}
            if q_text:
                all_targets.add(q_text.lower())
                all_targets.add(normalize_question_key(q_text).lower())

            for pid, r_reason in screened_posts:
                if not r_reason:
                    continue
                raw_txt = r_reason.strip()
                prefix = "Questions: " if raw_txt.lower().startswith("questions:") else ""
                content = raw_txt[len("questions:"):].strip() if prefix else raw_txt
                parts = [p.strip() for p in content.split(";") if p.strip()]
                new_parts = []
                changed = False
                for p in parts:
                    p_norm = normalize_question_key(p).lower()
                    if p.lower() in all_targets or p_norm in all_targets:
                        changed = True
                    else:
                        new_parts.append(p)
                if changed:
                    new_reason = f"Questions: {'; '.join(new_parts)}" if new_parts else "Screening requirements dismissed"
                    cur.execute("UPDATE posts SET rejection_reason = %s WHERE id = %s;", (new_reason, pid))
        except Exception:
            pass

    conn.commit()
    cur.close()
    conn.close()
    return deleted


def delete_screening_questions_batch(keys_or_ids: List[str]) -> int:
    """
    Delete multiple screening questions by their ids or keys.
    Adds all keys to tombstone blacklist to prevent resurrection during crawler backfills.
    Cleans references from historical posts with status='REQUIRES_QUESTIONNAIRE'.
    """
    if not keys_or_ids:
        return 0

    clean_keys = [str(k).strip() for k in keys_or_ids if k]
    norm_keys = [normalize_question_key(k) for k in clean_keys]
    all_targets = list(set(clean_keys + norm_keys))

    conn = get_connection()
    cur = conn.cursor()

    # Fetch question texts before deleting
    cur.execute("""
        SELECT question_text FROM screening_questions
        WHERE id = ANY(%s) OR question_key = ANY(%s);
    """, (all_targets, all_targets))
    q_texts = [r[0] for r in cur.fetchall() if r[0]]

    cur.execute("""
        DELETE FROM screening_questions
        WHERE id = ANY(%s) OR question_key = ANY(%s);
    """, (all_targets, all_targets))
    deleted_count = cur.rowcount

    if deleted_count > 0:
        # Add to tombstone blacklist
        add_to_deleted_question_keys(all_targets + q_texts)

        try:
            raw = get_setting("screening_question_bank", "{}")
            cur_dict = json.loads(raw) if raw else {}
            for t in all_targets:
                if t in cur_dict:
                    del cur_dict[t]
            set_setting("screening_question_bank", json.dumps(cur_dict))
        except Exception:
            pass

        # Clean from posts with status = 'REQUIRES_QUESTIONNAIRE'
        try:
            cur.execute("""
                SELECT id, rejection_reason FROM posts 
                WHERE status = 'REQUIRES_QUESTIONNAIRE' AND rejection_reason IS NOT NULL;
            """)
            screened_posts = cur.fetchall()
            target_set = {t.lower() for t in all_targets + q_texts}
            for q_t in q_texts:
                target_set.add(normalize_question_key(q_t).lower())

            for pid, r_reason in screened_posts:
                if not r_reason:
                    continue
                raw_txt = r_reason.strip()
                prefix = "Questions: " if raw_txt.lower().startswith("questions:") else ""
                content = raw_txt[len("questions:"):].strip() if prefix else raw_txt
                parts = [p.strip() for p in content.split(";") if p.strip()]
                new_parts = []
                changed = False
                for p in parts:
                    p_norm = normalize_question_key(p).lower()
                    if p.lower() in target_set or p_norm in target_set:
                        changed = True
                    else:
                        new_parts.append(p)
                if changed:
                    new_reason = f"Questions: {'; '.join(new_parts)}" if new_parts else "Screening requirements dismissed"
                    cur.execute("UPDATE posts SET rejection_reason = %s WHERE id = %s;", (new_reason, pid))
        except Exception:
            pass

    conn.commit()
    cur.close()
    conn.close()
    return deleted_count


