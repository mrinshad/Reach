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
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS potential_spam_reason TEXT;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS location VARCHAR(128);
    CREATE INDEX IF NOT EXISTS idx_posts_location ON posts(location);
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


def check_email_spam(emails: List[str], cur) -> Tuple[bool, bool, Optional[str], Optional[str]]:
    """
    Check contact emails against known scam/spam reports:
    1. For non-mainstream corporate/custom domains:
       If the domain was previously reported as scam/spam in the database (status = 'REJECTED'
       and rejection_reason contains 'scam' or 'spam', excluding legacy duplicate email logs),
       then auto-reject the incoming post with the matched reason.
    2. For any email (including mainstream domains like gmail.com, yahoo.com):
       If the exact email was previously reported as scam/spam, auto-reject with the matched reason.
    3. Potential scam check:
       If another post from that corporate domain was flagged as potential scam, flag as potential scam.
    
    Returns: (is_scam, is_potential_scam, scam_reason, potential_scam_reason)
    """
    if not emails:
        return False, False, None, None

    clean_emails = [e.strip().lower() for e in emails if e and "@" in e]
    if not clean_emails:
        return False, False, None, None

    for em in clean_emails:
        parts = em.split("@", 1)
        if len(parts) != 2:
            continue
        prefix, domain = parts[0].strip(), parts[1].strip()
        if not domain:
            continue

        # Check 1: Non-mainstream domain reported as scam/spam
        if domain not in PUBLIC_EMAIL_DOMAINS:
            cur.execute("""
                SELECT author_name, rejection_reason
                FROM posts, unnest(contact_emails) as other_em
                WHERE status = 'REJECTED'
                  AND (rejection_reason ILIKE '%%scam%%' OR rejection_reason ILIKE '%%spam%%')
                  AND rejection_reason NOT ILIKE '%%duplicate email%%'
                  AND split_part(lower(other_em), '@', 2) = %s
                LIMIT 1;
            """, (domain,))
            row = cur.fetchone()
            if row:
                author_match = row[0] or "Unknown"
                orig_reason = row[1] or "Scam"
                return True, False, f"Scam: Domain '{domain}' reported as scam/spam ({orig_reason})", None

        # Check 2: Exact email reported as scam/spam (applies to ALL domains including gmail, yahoo, etc.)
        cur.execute("""
            SELECT author_name, rejection_reason
            FROM posts
            WHERE status = 'REJECTED'
              AND (rejection_reason ILIKE '%%scam%%' OR rejection_reason ILIKE '%%spam%%')
              AND rejection_reason NOT ILIKE '%%duplicate email%%'
              AND (%s = ANY(contact_emails) OR %s ILIKE ANY(contact_emails))
            LIMIT 1;
        """, (em, em))
        row = cur.fetchone()
        if row:
            author_match = row[0] or "Unknown"
            orig_reason = row[1] or "Scam"
            return True, False, f"Scam: Email '{em}' reported as scam/spam ({orig_reason})", None

        # Check 3: Check if domain was previously marked as potential scam
        if domain not in PUBLIC_EMAIL_DOMAINS:
            cur.execute("""
                SELECT author_name, potential_spam_reason
                FROM posts, unnest(contact_emails) as other_em
                WHERE is_potential_spam = TRUE
                  AND split_part(lower(other_em), '@', 2) = %s
                LIMIT 1;
            """, (domain,))
            row = cur.fetchone()
            if row:
                prior_reason = row[1] or "Suspicious domain activity"
                return False, True, None, f"Potential Scam: Domain '{domain}' flagged ({prior_reason})"

    return False, False, None, None


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
            is_scam, is_potential_spam, scam_reason, potential_spam_reason = check_email_spam(emails, cur)
            initial_status = "REJECTED" if is_scam else "DISCOVERED"
            initial_reason = scam_reason if is_scam else None
            location = (post_data.get("location") or "").strip() or None

            insert_sql = """
            INSERT INTO posts (
                id, post_url, author_name, author_headline, author_profile,
                posted_date_raw, full_text, contact_emails, external_links,
                min_experience, max_experience, raw_experience, seniority_level,
                is_fresher, category, status, rejection_reason, is_potential_spam, potential_spam_reason,
                location, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
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
                potential_spam_reason,
                location,
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
    reason: Optional[str] = None,
    date_filter: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db_url: str = DEFAULT_DB_URL
) -> List[Dict[str, Any]]:
    """Retrieve posts with optional filtering, sorting, and search for UI dashboard and automation."""
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
        elif src_upper == "DIRECT":
            where_clauses.append("(COALESCE(post_url, '') LIKE %s OR COALESCE(post_url, '') LIKE %s)")
            params.extend(["direct://%", "%direct%"])
        elif src_upper == "LINKEDIN":
            where_clauses.append("(COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s)")
            params.extend(["%infopark.in%", "manual://%", "%manual%", "direct://%", "%direct%"])

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

    if reason and reason != "ALL":
        where_clauses.append("rejection_reason ILIKE %s")
        params.append(f"%{reason}%")

    if location and location != "ALL":
        where_clauses.append("location ILIKE %s")
        params.append(f"%{location}%")

    if date_filter:
        df_upper = date_filter.upper()
        if df_upper == "TODAY":
            where_clauses.append("created_at >= CURRENT_DATE")
        elif df_upper == "YESTERDAY":
            where_clauses.append("created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE")
        elif df_upper == "WEEK":
            where_clauses.append("created_at >= CURRENT_DATE - INTERVAL '7 days'")

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
                OR COALESCE(posted_date_raw, '') ILIKE %s
                OR COALESCE(location, '') ILIKE %s
                OR COALESCE(array_to_string(contact_emails, ' '), '') ILIKE %s
            )
        """)
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param, s_param, s_param, s_param, s_param, s_param])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    if order_by == "exp_asc":
        order_sql = "ORDER BY CASE WHEN is_fresher = TRUE THEN 0 WHEN min_experience IS NOT NULL THEN min_experience ELSE 99 END ASC, created_at DESC"
    elif order_by == "exp_desc":
        order_sql = "ORDER BY COALESCE(max_experience, min_experience, 0) DESC, is_fresher ASC, created_at DESC"
    elif order_by == "date_desc":
        order_sql = "ORDER BY created_at DESC"
    elif order_by == "date_asc":
        order_sql = "ORDER BY created_at ASC"
    elif order_by == "author_asc":
        order_sql = "ORDER BY author_name ASC, created_at DESC"
    elif order_by == "author_desc":
        order_sql = "ORDER BY author_name DESC, created_at DESC"
    elif status in ("OTHERS", "HISTORY", "ARCHIVE") or gen_status in ("OTHERS", "HISTORY", "ARCHIVE") or order_by == "updated_at":
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
    reason: Optional[str] = None,
    date_filter: Optional[str] = None,
    location: Optional[str] = None,
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
        elif src_upper == "DIRECT":
            where_clauses.append("(COALESCE(post_url, '') LIKE %s OR COALESCE(post_url, '') LIKE %s)")
            params.extend(["direct://%", "%direct%"])
        elif src_upper == "LINKEDIN":
            where_clauses.append("(COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s AND COALESCE(post_url, '') NOT LIKE %s)")
            params.extend(["%infopark.in%", "manual://%", "%manual%", "direct://%", "%direct%"])

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

    if reason and reason != "ALL":
        where_clauses.append("rejection_reason ILIKE %s")
        params.append(f"%{reason}%")

    if location and location != "ALL":
        where_clauses.append("location ILIKE %s")
        params.append(f"%{location}%")

    if date_filter:
        df_upper = date_filter.upper()
        if df_upper == "TODAY":
            where_clauses.append("created_at >= CURRENT_DATE")
        elif df_upper == "YESTERDAY":
            where_clauses.append("created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE")
        elif df_upper == "WEEK":
            where_clauses.append("created_at >= CURRENT_DATE - INTERVAL '7 days'")

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
                OR COALESCE(posted_date_raw, '') ILIKE %s
                OR COALESCE(location, '') ILIKE %s
                OR COALESCE(array_to_string(contact_emails, ' '), '') ILIKE %s
            )
        """)
        s_param = f"%{search}%"
        params.extend([s_param, s_param, s_param, s_param, s_param, s_param, s_param, s_param])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    count_sql = f"SELECT COUNT(*) FROM posts {where_sql};"

    if order_by == "exp_asc":
        order_sql = "ORDER BY CASE WHEN is_fresher = TRUE THEN 0 WHEN min_experience IS NOT NULL THEN min_experience ELSE 99 END ASC, created_at DESC"
    elif order_by == "exp_desc":
        order_sql = "ORDER BY COALESCE(max_experience, min_experience, 0) DESC, is_fresher ASC, created_at DESC"
    elif order_by == "date_desc":
        order_sql = "ORDER BY created_at DESC"
    elif order_by == "date_asc":
        order_sql = "ORDER BY created_at ASC"
    elif order_by == "author_asc":
        order_sql = "ORDER BY author_name ASC, created_at DESC"
    elif order_by == "author_desc":
        order_sql = "ORDER BY author_name DESC, created_at DESC"
    elif status in ("OTHERS", "HISTORY", "ARCHIVE") or gen_status in ("OTHERS", "HISTORY", "ARCHIVE") or order_by == "updated_at":
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


def get_rejection_reasons_with_counts(db_url: str = DEFAULT_DB_URL) -> List[Dict[str, Any]]:
    """Retrieve distinct cancellation/rejection reasons with their post counts for dropdown filtering in UI."""
    sql = """
        SELECT TRIM(rejection_reason) AS reason, COUNT(*) AS count
        FROM posts
        WHERE status = 'REJECTED'
          AND rejection_reason IS NOT NULL
          AND TRIM(rejection_reason) != ''
        GROUP BY TRIM(rejection_reason)
        ORDER BY count DESC, reason ASC;
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                return [{"reason": r[0], "count": int(r[1])} for r in rows if r[0]]
    except Exception as e:
        print(f"Error fetching rejection reasons with counts: {e}")
        return []


def get_distinct_rejection_reasons(db_url: str = DEFAULT_DB_URL) -> List[str]:
    """Retrieve list of distinct cancellation/rejection reasons for dropdown filtering in UI."""
    items = get_rejection_reasons_with_counts(db_url)
    return [item["reason"] for item in items]


def get_distinct_locations(db_url: str = DEFAULT_DB_URL) -> List[str]:
    """Retrieve list of distinct job locations saved in the database."""
    sql = """
        SELECT DISTINCT TRIM(location) AS loc
        FROM posts
        WHERE location IS NOT NULL AND TRIM(location) != ''
        ORDER BY loc ASC;
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                return [r[0] for r in rows if r[0]]
    except Exception as e:
        print(f"Error fetching distinct locations: {e}")
        return []


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
    rejection_reason: Optional[str] = None,  # will be sanitized/truncated before saving
    is_potential_spam: Optional[bool] = None,
    potential_spam_reason: Optional[str] = None,
    db_url: str = DEFAULT_DB_URL
):
    """Update post workflow status with optional cancellation/rejection reason and potential scam flags."""
    set_clauses = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
    params = [new_status]

    if rejection_reason is not None:
        from src.chatgpt_service import clean_and_truncate_reason
        cleaned_reason = clean_and_truncate_reason(rejection_reason)
        set_clauses.append("rejection_reason = %s")
        params.append(cleaned_reason)

        if is_potential_spam is None and ("potential scam" in rejection_reason.lower() or "potential spam" in rejection_reason.lower()):
            is_potential_spam = True
            if potential_spam_reason is None:
                potential_spam_reason = rejection_reason

    if is_potential_spam is not None:
        set_clauses.append("is_potential_spam = %s")
        params.append(is_potential_spam)

    if potential_spam_reason is not None:
        set_clauses.append("potential_spam_reason = %s")
        params.append(potential_spam_reason)

    params.append(post_id)
    sql = f"UPDATE posts SET {', '.join(set_clauses)} WHERE id = %s;"
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
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
        is_potential_spam = FALSE,
        potential_spam_reason = NULL,
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
        COUNT(*) FILTER (WHERE category = 'EMAIL_OUTREACH' AND status IN ('DISCOVERED', 'SELECTED') AND (generated_body IS NULL OR generated_body = '')) AS pending_generation,
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


def get_analytics_summary(days: Optional[int] = 30, db_url: str = DEFAULT_DB_URL) -> Dict[str, Any]:
    """
    Retrieve aggregated analytics for dashboard metrics:
    - Daily applications sent timeline (for line graph)
    - Daily scraping activity timeline (for bar chart)
    - Application status distribution (Donut chart)
    - Scraper source breakdown (LinkedIn vs Infopark vs Manual)
    - Rejection / Spam reasons breakdown
    - Experience level tiers
    - High-level KPIs & conversion rates
    """
    from datetime import datetime, timedelta

    cutoff_date = None
    date_labels = []
    
    effective_days = days if (days and days > 0) else None
    if effective_days:
        today = datetime.now().date()
        cutoff_date = (today - timedelta(days=effective_days - 1)).strftime('%Y-%m-%d')
        date_labels = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(effective_days - 1, -1, -1)]

    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Summary KPIs
            cur.execute("""
                SELECT
                    COUNT(*) AS total_scraped,
                    COUNT(*) FILTER (WHERE array_length(contact_emails, 1) > 0) AS with_emails,
                    COUNT(*) FILTER (WHERE status = 'SENT') AS total_sent,
                    COUNT(*) FILTER (WHERE status = 'EMAIL_GENERATED') AS total_drafted,
                    COUNT(*) FILTER (WHERE status = 'REJECTED') AS total_rejected,
                    COUNT(*) FILTER (WHERE is_potential_spam = TRUE) AS potential_spam_total,
                    COUNT(*) FILTER (WHERE status IN ('DISCOVERED', 'SELECTED')) AS pending_review
                FROM posts;
            """)
            kpi_row = dict(cur.fetchone() or {})
            total_scraped = kpi_row.get("total_scraped") or 0
            with_emails = kpi_row.get("with_emails") or 0
            total_sent = kpi_row.get("total_sent") or 0
            total_drafted = kpi_row.get("total_drafted") or 0
            total_rejected = kpi_row.get("total_rejected") or 0

            email_rate = round((with_emails / total_scraped * 100), 1) if total_scraped > 0 else 0.0
            sent_conversion = round((total_sent / total_scraped * 100), 1) if total_scraped > 0 else 0.0

            # 2. Daily Applied Timeline
            if cutoff_date:
                cur.execute("""
                    SELECT TO_CHAR(sent_at, 'YYYY-MM-DD') AS day, COUNT(*) AS count
                    FROM posts
                    WHERE status = 'SENT' AND sent_at >= %s::date
                    GROUP BY day
                    ORDER BY day ASC;
                """, (cutoff_date,))
            else:
                cur.execute("""
                    SELECT TO_CHAR(sent_at, 'YYYY-MM-DD') AS day, COUNT(*) AS count
                    FROM posts
                    WHERE status = 'SENT' AND sent_at IS NOT NULL
                    GROUP BY day
                    ORDER BY day ASC;
                """)
            applied_map = {r["day"]: int(r["count"]) for r in cur.fetchall()}

            # 3. Daily Scraped Timeline
            if cutoff_date:
                cur.execute("""
                    SELECT TO_CHAR(created_at, 'YYYY-MM-DD') AS day, COUNT(*) AS count
                    FROM posts
                    WHERE created_at >= %s::date
                    GROUP BY day
                    ORDER BY day ASC;
                """, (cutoff_date,))
            else:
                cur.execute("""
                    SELECT TO_CHAR(created_at, 'YYYY-MM-DD') AS day, COUNT(*) AS count
                    FROM posts
                    GROUP BY day
                    ORDER BY day ASC;
                """)
            scraped_map = {r["day"]: int(r["count"]) for r in cur.fetchall()}

            if not date_labels:
                all_dates = sorted(set(list(applied_map.keys()) + list(scraped_map.keys())))
                if not all_dates:
                    all_dates = [datetime.now().strftime('%Y-%m-%d')]
                date_labels = all_dates

            timeline_applied = []
            timeline_scraped = []
            for d in date_labels:
                try:
                    dt_obj = datetime.strptime(d, '%Y-%m-%d')
                    lbl = dt_obj.strftime('%b %d')
                except Exception:
                    lbl = d
                timeline_applied.append({"date": d, "label": lbl, "count": applied_map.get(d, 0)})
                timeline_scraped.append({"date": d, "label": lbl, "count": scraped_map.get(d, 0)})

            # 4. Application Status Breakdown
            cur.execute("""
                SELECT status, COUNT(*) AS count
                FROM posts
                GROUP BY status
                ORDER BY count DESC;
            """)
            status_colors = {
                "SENT": "#10b981",            # Emerald
                "EMAIL_GENERATED": "#6366f1", # Indigo
                "DISCOVERED": "#0ea5e9",      # Sky blue
                "GENERATING_EMAIL": "#f59e0b",# Amber
                "REJECTED": "#f43f5e",        # Rose
                "SELECTED": "#8b5cf6",        # Purple
            }
            status_labels = {
                "SENT": "Applied / Sent",
                "EMAIL_GENERATED": "Drafts Ready",
                "DISCOVERED": "Discovered",
                "GENERATING_EMAIL": "Generating Draft",
                "REJECTED": "Cancelled / Discarded",
                "SELECTED": "Selected",
            }
            raw_statuses = cur.fetchall()
            status_breakdown = []
            for r in raw_statuses:
                st = r["status"]
                status_breakdown.append({
                    "status": st,
                    "label": status_labels.get(st, st),
                    "count": int(r["count"]),
                    "color": status_colors.get(st, "#64748b")
                })

            # 5. Scraper Sources Breakdown
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN post_url LIKE 'https://infopark.in%' THEN 'Infopark Kochi'
                        WHEN post_url LIKE 'manual://%' THEN 'Manual Input'
                        WHEN post_url LIKE 'direct://%' THEN 'Direct Outreach'
                        ELSE 'LinkedIn'
                    END AS source,
                    COUNT(*) AS total_scraped,
                    COUNT(*) FILTER (WHERE array_length(contact_emails, 1) > 0) AS with_emails,
                    COUNT(*) FILTER (WHERE status = 'SENT') AS total_sent,
                    COUNT(*) FILTER (WHERE status = 'REJECTED') AS total_rejected
                FROM posts
                GROUP BY 1
                ORDER BY total_scraped DESC;
            """)
            source_breakdown = [dict(r) for r in cur.fetchall()]

            # 6. Rejection / Spam Reasons Breakdown (no LIMIT — show all reasons)
            cur.execute("""
                SELECT 
                    COALESCE(NULLIF(TRIM(rejection_reason), ''), 'Not Specified') AS reason,
                    COUNT(*) AS count
                FROM posts
                WHERE status = 'REJECTED'
                GROUP BY 1
                ORDER BY count DESC;
            """)
            rejection_reasons = [dict(r) for r in cur.fetchall()]

            # 7. Experience Distribution
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN is_fresher = TRUE OR (max_experience IS NOT NULL AND max_experience <= 1) THEN 'Fresher (0–1 yr)'
                        WHEN min_experience >= 3 OR max_experience >= 4 THEN 'Senior (3–5+ yrs)'
                        WHEN min_experience >= 1 OR max_experience > 1 THEN 'Mid-Level (1–3 yrs)'
                        ELSE 'Flexible / Unspecified'
                    END AS exp_tier,
                    COUNT(*) AS count
                FROM posts
                GROUP BY 1
                ORDER BY count DESC;
            """)
            experience_breakdown = [dict(r) for r in cur.fetchall()]

            return {
                "timeframe_days": effective_days,
                "summary": {
                    "total_scraped": total_scraped,
                    "with_emails": with_emails,
                    "total_sent": total_sent,
                    "total_drafted": total_drafted,
                    "total_rejected": total_rejected,
                    "potential_spam_total": kpi_row.get("potential_spam_total") or 0,
                    "pending_review": kpi_row.get("pending_review") or 0,
                    "email_rate_pct": email_rate,
                    "sent_conversion_pct": sent_conversion,
                },
                "timeline_applied": timeline_applied,
                "timeline_scraped": timeline_scraped,
                "status_breakdown": status_breakdown,
                "source_breakdown": source_breakdown,
                "rejection_reasons": rejection_reasons,
                "experience_breakdown": experience_breakdown,
            }


