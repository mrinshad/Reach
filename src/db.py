"""
PostgreSQL Database Client for LinkedIn Job Automation

Connects to local PostgreSQL (database: linkedin_scrapper),
matching schema.prisma. Provides idempotency / deduplication,
batch storage, status updates, and query filters.
"""

import os
import json
import uuid
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional, Set, Tuple

def _load_env_file():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_file = os.path.join(root_dir, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

_current_user = os.getenv("USER", "postgres")
DEFAULT_DB_URL = os.getenv("DATABASE_URL", f"postgresql://{_current_user}@localhost:5432/linkedin_scrapper")


def get_connection(db_url: str = DEFAULT_DB_URL):
    """Return a psycopg2 connection to PostgreSQL."""
    return psycopg2.connect(db_url)


def init_db(db_url: str = DEFAULT_DB_URL):
    """Create the posts and settings tables if they do not exist, matching schema.prisma."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS posts (
        id VARCHAR(64) PRIMARY KEY,
        post_url VARCHAR(512) UNIQUE,
        author_name VARCHAR(256) NOT NULL,
        author_headline TEXT,
        author_profile VARCHAR(512),
        posted_date_raw VARCHAR(64),
        full_text TEXT NOT NULL,
        contact_emails TEXT[] DEFAULT '{}',
        external_links TEXT[] DEFAULT '{}',
        min_experience REAL,
        max_experience REAL,
        raw_experience TEXT,
        seniority_level VARCHAR(64),
        is_fresher BOOLEAN DEFAULT FALSE,
        category VARCHAR(64) DEFAULT 'EMAIL_OUTREACH',
        status VARCHAR(64) DEFAULT 'DISCOVERED',
        generated_subject TEXT,
        generated_body TEXT,
        approved_at TIMESTAMP,
        sent_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
    CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
    CREATE INDEX IF NOT EXISTS idx_posts_exp ON posts(min_experience, max_experience);
    CREATE INDEX IF NOT EXISTS idx_posts_status_created ON posts(status, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);

    CREATE TABLE IF NOT EXISTS settings (
        key VARCHAR(128) PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    alter_sql = """
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_potential_spam BOOLEAN DEFAULT FALSE;
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            cur.execute(alter_sql)
        conn.commit()

    seed_default_settings(db_url)
    print("✓ PostgreSQL database initialized (tables: posts, settings).")


def get_setting(key: str, default: Optional[str] = None, db_url: str = DEFAULT_DB_URL) -> Optional[str]:
    """Retrieve a configuration value by key from the database settings table."""
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM settings WHERE key = %s LIMIT 1;", (key,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    return str(row[0])
    except Exception as e:
        print(f"Warning: Could not get db setting '{key}': {e}")
    return default


def set_setting(key: str, value: str, db_url: str = DEFAULT_DB_URL) -> None:
    """Insert or update a configuration key-value in the database settings table."""
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP;
            """, (key, str(value)))
        conn.commit()


def get_all_settings(db_url: str = DEFAULT_DB_URL) -> Dict[str, str]:
    """Retrieve all configuration key-values from the database settings table."""
    results = {}
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT key, value FROM settings;")
                for k, v in cur.fetchall():
                    results[k] = v
    except Exception as e:
        print(f"Warning: Could not fetch all db settings: {e}")
    return results


def seed_default_settings(db_url: str = DEFAULT_DB_URL) -> None:
    """Seed initial settings into database from config.json if not present."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_file = os.path.join(root_dir, "config.json")
    chatgpt_val = ""
    search_val = "Full stack developer"

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("chatgpt_url"):
                    chatgpt_val = cfg["chatgpt_url"]
                if cfg.get("search_query"):
                    search_val = cfg["search_query"]
        except Exception:
            pass

    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                if search_val:
                    cur.execute(
                        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING;",
                        ("search_query", search_val)
                    )
                if chatgpt_val:
                    cur.execute(
                        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING;",
                        ("chatgpt_url", chatgpt_val)
                    )
            conn.commit()
    except Exception as e:
        print(f"Warning: Could not seed settings: {e}")


PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com",
    "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.com.br",
    "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "aol.com", "zoho.com",
    "mail.com", "yandex.com", "gmx.com", "rediffmail.com",
}


def check_email_spam(emails: List[str], cur) -> Tuple[bool, bool, Optional[str]]:
    """
    Check extracted contact emails against database for duplicate/spam:
    1. Exact Email Match -> is_exact_spam = True, auto-reject with comment.
    2. Same Corporate/Custom Domain with Different Prefix -> is_potential_spam = True.
       Exempts public email providers (gmail, hotmail, yahoo, etc.).
    Returns: (is_exact_spam, is_potential_spam, spam_reason)
    """
    if not emails:
        return False, False, None

    clean_emails = [e.strip().lower() for e in emails if e and "@" in e]
    if not clean_emails:
        return False, False, None

    # Check 1: Exact email duplicate in database
    for em in clean_emails:
        cur.execute(
            "SELECT 1 FROM posts WHERE %s = ANY(contact_emails) OR %s ILIKE ANY(contact_emails) LIMIT 1;",
            (em, em)
        )
        if cur.fetchone():
            return True, False, f"Spam: Duplicate email ({em}) already in database"

    # Check 2: Potential spam - same custom domain with different prefix
    is_potential = False
    for em in clean_emails:
        parts = em.split("@", 1)
        if len(parts) == 2:
            prefix, domain = parts[0].strip(), parts[1].strip()
            if domain and domain not in PUBLIC_EMAIL_DOMAINS:
                cur.execute("""
                    SELECT 1 FROM posts, unnest(contact_emails) as other_em
                    WHERE split_part(lower(other_em), '@', 2) = %s
                      AND split_part(lower(other_em), '@', 1) != %s
                    LIMIT 1;
                """, (domain, prefix))
                if cur.fetchone():
                    is_potential = True
                    break

    return False, is_potential, None


def get_existing_post_identifiers(db_url: str = DEFAULT_DB_URL) -> Set[str]:
    """
    Retrieve all existing post identifiers (URLs, IDs, content signatures)
    into an in-memory set for rapid O(1) duplicate checks during scraping.
    """
    identifiers = set()
    sql = "SELECT id, post_url, author_name, substring(full_text, 1, 100) AS snippet FROM posts;"
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                pid, url, author, snippet = row[0], row[1], row[2], row[3]
                if pid:
                    identifiers.add(str(pid))
                if url:
                    clean_url = url.split("?")[0].rstrip("/")
                    identifiers.add(clean_url)
                    identifiers.add(url.rstrip("/"))
                if author and snippet:
                    sig = f"{author.strip().lower()}:{snippet.strip()[:60]}"
                    identifiers.add(sig)
    return identifiers


def is_post_already_saved(
    post_url: Optional[str] = None,
    author_name: str = "",
    full_text: str = "",
    db_url: str = DEFAULT_DB_URL
) -> bool:
    """Check whether a post already exists in the database by URL or content signature."""
    if post_url:
        clean_url = post_url.split("?")[0].rstrip("/")
        sql = "SELECT 1 FROM posts WHERE post_url ILIKE %s OR post_url = %s LIMIT 1;"
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (f"%{clean_url}%", post_url))
                if cur.fetchone():
                    return True

    if author_name and full_text:
        sql = "SELECT 1 FROM posts WHERE author_name = %s AND substring(full_text, 1, 80) = %s LIMIT 1;"
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (author_name.strip(), full_text.strip()[:80]))
                if cur.fetchone():
                    return True

    return False


def upsert_post(
    post_data: Dict[str, Any],
    skip_if_exists: bool = True,
    db_url: str = DEFAULT_DB_URL
) -> Tuple[str, bool]:
    """
    Insert or update a post in the database.
    If skip_if_exists is True, existing posts are untouched to preserve workflow status.
    Returns (post_id, was_created).
    """
    post_url = post_data.get("post_url", "").strip() or None
    author_name = post_data.get("author_name", "Unknown").strip()
    full_text = post_data.get("full_text", "").strip()

    # Deterministic ID if URL is present, otherwise hash content
    if post_url:
        record_id = hashlib.sha256(post_url.encode()).hexdigest()[:32]
    else:
        sig = f"{author_name}:{full_text[:100]}"
        record_id = hashlib.sha256(sig.encode()).hexdigest()[:32]

    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            # Check if post already exists
            if post_url:
                cur.execute("SELECT id FROM posts WHERE id = %s OR post_url = %s LIMIT 1;", (record_id, post_url))
            else:
                cur.execute(
                    "SELECT id FROM posts WHERE id = %s OR (author_name = %s AND substring(full_text, 1, 80) = %s) LIMIT 1;",
                    (record_id, author_name, full_text[:80])
                )
            existing = cur.fetchone()
            if existing:
                if skip_if_exists:
                    return (existing[0], False)

            emails = post_data.get("detected_emails", []) or []
            links = post_data.get("detected_links", []) or []

            # Experience details
            exp = post_data.get("experience", {})
            min_exp = exp.get("min_years")
            max_exp = exp.get("max_years")
            raw_exp = exp.get("raw_text")
            seniority = exp.get("seniority_level", "Unspecified")
            is_fresher = exp.get("is_fresher", False)
            category = post_data.get("category", "EMAIL_OUTREACH")

            # Email duplicate and spam check
            is_exact_spam, is_potential_spam, spam_reason = check_email_spam(emails, cur)
            initial_status = "REJECTED" if is_exact_spam else "DISCOVERED"
            initial_reason = spam_reason if is_exact_spam else None

            insert_sql = """
            INSERT INTO posts (
                id, post_url, author_name, author_headline, author_profile,
                posted_date_raw, full_text, contact_emails, external_links,
                min_experience, max_experience, raw_experience, seniority_level,
                is_fresher, category, status, rejection_reason, is_potential_spam, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (post_url) DO NOTHING
            RETURNING id;
            """
            cur.execute(insert_sql, (
                record_id,
                post_url,
                author_name,
                post_data.get("author_headline", ""),
                post_data.get("author_profile", ""),
                post_data.get("post_date", ""),
                full_text,
                emails,
                links,
                min_exp,
                max_exp,
                raw_exp,
                seniority,
                is_fresher,
                category,
                initial_status,
                initial_reason,
                is_potential_spam,
            ))
            res = cur.fetchone()
            conn.commit()
            created_id = res[0] if res else record_id
            return (created_id, res is not None)


def get_posts(
    category: Optional[str] = None,
    status: Optional[str] = None,
    gen_status: Optional[str] = None,
    source: Optional[str] = None,
    min_exp: Optional[float] = None,
    max_exp: Optional[float] = None,
    search: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db_url: str = DEFAULT_DB_URL
) -> List[Dict[str, Any]]:
    """Retrieve posts with optional filtering and search for UI dashboard and automation."""
    where_clauses = []
    params = []

    if category and category != "ALL":
        where_clauses.append("category = %s")
        params.append(category)

    if source and source != "ALL":
        src_upper = source.upper()
        if src_upper == "INFOPARK":
            where_clauses.append("COALESCE(post_url, '') LIKE %s")
            params.append("%infopark.in%")
        elif src_upper == "MANUAL":
            where_clauses.append("(COALESCE(post_url, '') LIKE %s OR COALESCE(post_url, '') LIKE %s)")
            params.extend(["manual://%", "%manual%"])
        elif src_upper == "LINKEDIN":
            where_clauses.append("(COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s)")
            params.extend(["%infopark.in%", "manual://%", "%manual%"])

    if status and status != "ALL":
        if status in ("OTHERS", "HISTORY", "ARCHIVE"):
            where_clauses.append("status IN ('SENT', 'REJECTED')")
        else:
            where_clauses.append("status = %s")
            params.append(status)
    elif gen_status and gen_status not in ("ALL", "ALL_INCL_GENERATED"):
        if gen_status in ("PENDING", "YET_TO_GENERATE", "DISCOVERED"):
            where_clauses.append("(status IN ('DISCOVERED', 'SELECTED') AND (generated_body IS NULL OR generated_body = ''))")
        elif gen_status == "GENERATED":
            where_clauses.append("status = 'EMAIL_GENERATED'")
        elif gen_status == "SENT":
            where_clauses.append("status = 'SENT'")
        elif gen_status in ("OTHERS", "HISTORY", "ARCHIVE"):
            where_clauses.append("status IN ('SENT', 'REJECTED')")
        elif gen_status == "REJECTED":
            where_clauses.append("status = 'REJECTED'")
        elif gen_status == "EVERYTHING":
            pass
    elif gen_status in ("ALL", "ALL_INCL_GENERATED"):
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED', 'EMAIL_GENERATED')")
    elif gen_status is None and status is None:
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED')")

    if min_exp is not None and max_exp is not None:
        where_clauses.append("""
            (
                (min_experience >= %s AND min_experience <= %s)
                OR (max_experience >= %s AND max_experience <= %s)
                OR (min_experience <= %s AND max_experience >= %s)
            )
        """)
        params.extend([min_exp, max_exp, min_exp, max_exp, min_exp, max_exp])
    elif max_exp is not None:
        where_clauses.append("""
            (
                is_fresher = TRUE
                OR (min_experience IS NOT NULL AND min_experience <= %s)
                OR (max_experience IS NOT NULL AND max_experience <= %s)
            )
        """)
        params.extend([max_exp, max_exp])
    elif min_exp is not None:
        where_clauses.append("""
            (
                min_experience >= %s
                OR max_experience >= %s
            )
        """)
        params.extend([min_exp, min_exp])

    if search:
        where_clauses.append("""
            (
                author_name ILIKE %s 
                OR full_text ILIKE %s 
                OR COALESCE(author_headline, '') ILIKE %s 
                OR COALESCE(generated_subject, '') ILIKE %s 
                OR COALESCE(rejection_reason, '') ILIKE %s
                OR COALESCE(array_to_string(contact_emails, ' '), '') ILIKE %s
            )
        """)
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param, s_param, s_param, s_param])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    if status in ("OTHERS", "HISTORY", "ARCHIVE") or gen_status in ("OTHERS", "HISTORY", "ARCHIVE") or order_by == "updated_at":
        order_sql = "ORDER BY updated_at DESC"
    else:
        order_sql = """
        ORDER BY 
          CASE 
            WHEN status IN ('DISCOVERED', 'SELECTED') AND (generated_body IS NULL OR generated_body = '') THEN 0
            WHEN status = 'EMAIL_GENERATED' THEN 1
            WHEN status = 'SENT' THEN 2
            ELSE 3
          END ASC,
          created_at DESC
        """
    sql = f"""
    SELECT * FROM posts
    {where_sql}
    {order_sql}
    LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])

    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            return [dict(row) for row in cur.fetchall()]


def get_posts_paginated(
    category: Optional[str] = None,
    status: Optional[str] = None,
    gen_status: Optional[str] = None,
    source: Optional[str] = None,
    min_exp: Optional[float] = None,
    max_exp: Optional[float] = None,
    search: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    db_url: str = DEFAULT_DB_URL
) -> Dict[str, Any]:
    """Retrieve posts with total count for clean UI table pagination."""
    where_clauses = []
    params = []

    if category and category != "ALL":
        where_clauses.append("category = %s")
        params.append(category)

    if source and source != "ALL":
        src_upper = source.upper()
        if src_upper == "INFOPARK":
            where_clauses.append("COALESCE(post_url, '') LIKE %s")
            params.append("%infopark.in%")
        elif src_upper == "MANUAL":
            where_clauses.append("(COALESCE(post_url, '') LIKE %s OR COALESCE(post_url, '') LIKE %s)")
            params.extend(["manual://%", "%manual%"])
        elif src_upper == "LINKEDIN":
            where_clauses.append("(COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s)")
            params.extend(["%infopark.in%", "manual://%", "%manual%"])

    if status and status != "ALL":
        if status in ("OTHERS", "HISTORY", "ARCHIVE"):
            where_clauses.append("status IN ('SENT', 'REJECTED')")
        else:
            where_clauses.append("status = %s")
            params.append(status)
    elif gen_status and gen_status not in ("ALL", "ALL_INCL_GENERATED"):
        if gen_status in ("PENDING", "YET_TO_GENERATE", "DISCOVERED"):
            where_clauses.append("(status IN ('DISCOVERED', 'SELECTED') AND (generated_body IS NULL OR generated_body = ''))")
        elif gen_status == "GENERATED":
            where_clauses.append("status = 'EMAIL_GENERATED'")
        elif gen_status == "SENT":
            where_clauses.append("status = 'SENT'")
        elif gen_status in ("OTHERS", "HISTORY", "ARCHIVE"):
            where_clauses.append("status IN ('SENT', 'REJECTED')")
        elif gen_status == "REJECTED":
            where_clauses.append("status = 'REJECTED'")
        elif gen_status == "EVERYTHING":
            pass
    elif gen_status in ("ALL", "ALL_INCL_GENERATED"):
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED', 'EMAIL_GENERATED')")
    elif gen_status is None and status is None:
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED')")

    if min_exp is not None and max_exp is not None:
        where_clauses.append("""
            (
                (min_experience >= %s AND min_experience <= %s)
                OR (max_experience >= %s AND max_experience <= %s)
                OR (min_experience <= %s AND max_experience >= %s)
            )
        """)
        params.extend([min_exp, max_exp, min_exp, max_exp, min_exp, max_exp])
    elif max_exp is not None:
        where_clauses.append("""
            (
                is_fresher = TRUE
                OR (min_experience IS NOT NULL AND min_experience <= %s)
                OR (max_experience IS NOT NULL AND max_experience <= %s)
            )
        """)
        params.extend([max_exp, max_exp])
    elif min_exp is not None:
        where_clauses.append("""
            (
                min_experience >= %s
                OR max_experience >= %s
            )
        """)
        params.extend([min_exp, min_exp])

    if search:
        where_clauses.append("""
            (
                author_name ILIKE %s 
                OR full_text ILIKE %s 
                OR COALESCE(author_headline, '') ILIKE %s 
                OR COALESCE(generated_subject, '') ILIKE %s 
                OR COALESCE(rejection_reason, '') ILIKE %s
                OR COALESCE(array_to_string(contact_emails, ' '), '') ILIKE %s
            )
        """)
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param, s_param, s_param, s_param])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    count_sql = f"SELECT COUNT(*) FROM posts {where_sql};"

    if status in ("OTHERS", "HISTORY", "ARCHIVE") or gen_status in ("OTHERS", "HISTORY", "ARCHIVE") or order_by == "updated_at":
        order_sql = "ORDER BY updated_at DESC"
    else:
        order_sql = """
        ORDER BY 
          CASE 
            WHEN status IN ('DISCOVERED', 'SELECTED') AND (generated_body IS NULL OR generated_body = '') THEN 0
            WHEN status = 'EMAIL_GENERATED' THEN 1
            WHEN status = 'SENT' THEN 2
            ELSE 3
          END ASC,
          created_at DESC
        """

    select_sql = f"""
    SELECT * FROM posts
    {where_sql}
    {order_sql}
    LIMIT %s OFFSET %s;
    """

    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, tuple(params))
            total_count = cur.fetchone()[0]

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            select_params = list(params) + [limit, offset]
            cur.execute(select_sql, tuple(select_params))
            rows = [dict(row) for row in cur.fetchall()]

    return {
        "posts": rows,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


def get_post_by_id(post_id: str, db_url: str = DEFAULT_DB_URL) -> Optional[Dict[str, Any]]:
    """Retrieve a single post record by its ID."""
    sql = "SELECT * FROM posts WHERE id = %s;"
    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (post_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def update_post_status(
    post_id: str,
    new_status: str,
    rejection_reason: Optional[str] = None,
    db_url: str = DEFAULT_DB_URL
):
    """Update post workflow status with optional cancellation/rejection reason."""
    if rejection_reason is not None:
        sql = "UPDATE posts SET status = %s, rejection_reason = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;"
        params = (new_status, rejection_reason, post_id)
    else:
        sql = "UPDATE posts SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;"
        params = (new_status, post_id)
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def update_post_email(
    post_id: str,
    subject: str,
    body: str,
    db_url: str = DEFAULT_DB_URL
):
    """Update the generated/edited email subject and body for a post."""
    sql = """
    UPDATE posts SET
        generated_subject = %s,
        generated_body = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (subject, body, post_id))
        conn.commit()


def mark_post_sent(post_id: str, db_url: str = DEFAULT_DB_URL):
    """Mark a post outreach email as sent with timestamp."""
    sql = """
    UPDATE posts SET
        status = 'SENT',
        sent_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (post_id,))
        conn.commit()


def revert_post_to_draft(post_id: str, db_url: str = DEFAULT_DB_URL):
    """Revert a sent or rejected post back to active status (EMAIL_GENERATED if draft exists, else DISCOVERED)."""
    sql = """
    UPDATE posts SET
        status = CASE 
            WHEN generated_body IS NOT NULL AND generated_body != '' THEN 'EMAIL_GENERATED'
            ELSE 'DISCOVERED'
        END,
        rejection_reason = NULL,
        sent_at = NULL,
        approved_at = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (post_id,))
        conn.commit()


def move_post_to_review(post_id: str, db_url: str = DEFAULT_DB_URL) -> Optional[Dict[str, Any]]:
    """Move a discovered post directly to EMAIL_GENERATED status for review/drafting."""
    sql = """
    UPDATE posts SET
        status = 'EMAIL_GENERATED',
        generated_subject = COALESCE(NULLIF(generated_subject, ''), CONCAT('Application: Job Opportunity - ', author_name)),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    RETURNING *;
    """
    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (post_id,))
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def save_chatgpt_response(
    post_id: str,
    subject: str,
    body: str,
    db_url: str = DEFAULT_DB_URL
):
    """Save the ChatGPT generated email draft to the post record."""
    sql = """
    UPDATE posts SET
        generated_subject = %s,
        generated_body = %s,
        status = 'EMAIL_GENERATED',
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (subject, body, post_id))
        conn.commit()


def get_pending_email_posts(
    limit: Optional[int] = None,
    db_url: str = DEFAULT_DB_URL
) -> List[Dict[str, Any]]:
    """Retrieve posts with contact emails that haven't had an outreach email generated yet."""
    sql = """
    SELECT * FROM posts
    WHERE category = 'EMAIL_OUTREACH'
      AND (status = 'DISCOVERED' OR status = 'SELECTED')
      AND generated_body IS NULL
    ORDER BY created_at ASC
    """
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    sql += ";"

    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]


def get_stats(db_url: str = DEFAULT_DB_URL) -> Dict[str, int]:
    """Retrieve aggregate status counts for dashboard display."""
    sql = """
    SELECT
        COUNT(*) AS total_posts,
        COUNT(*) FILTER (WHERE category = 'EMAIL_OUTREACH') AS email_outreach_total,
        COUNT(*) FILTER (WHERE (generated_body IS NULL OR generated_body = '') AND status IN ('DISCOVERED', 'SELECTED')) AS pending_generation,
        COUNT(*) FILTER (WHERE status = 'EMAIL_GENERATED') AS emails_generated,
        COUNT(*) FILTER (WHERE status = 'SENT') AS applications_sent,
        COUNT(*) FILTER (WHERE status IN ('DISCOVERED', 'SELECTED')) AS discovered_total,
        COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected_total,
        COUNT(*) FILTER (WHERE status IN ('SENT', 'REJECTED')) AS others_total,
        COUNT(*) FILTER (WHERE category = 'DRAFT_PORTAL') AS draft_portal_total
    FROM posts;
    """
    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            row = cur.fetchone()
            stats = dict(row) if row else {
                "total_posts": 0,
                "email_outreach_total": 0,
                "pending_generation": 0,
                "emails_generated": 0,
                "applications_sent": 0,
                "discovered_total": 0,
                "rejected_total": 0,
                "others_total": 0,
                "draft_portal_total": 0,
            }
            if "others_total" not in stats:
                stats["others_total"] = (stats.get("applications_sent") or 0) + (stats.get("rejected_total") or 0)
            return stats

