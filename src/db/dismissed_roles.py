"""
Dismissed Roles Database Module
(src/db/dismissed_roles.py)

Manages persistent database storage, deduplication, search, and seeding of
dismissed/excluded job roles across LinkedIn, Indeed, Easy Apply, and Infopark.
"""

import os
import re
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
from psycopg2.extras import RealDictCursor

from src.db.connection import get_connection, DEFAULT_DB_URL
from src.db.posts import normalize_job_title

# Strict non-software / non-IT physical engineering & non-tech domains
NON_TECH_PATTERNS = [
    r'\b(civil engineer|mechanical engineer|electrical engineer|sheet metal|piping engineer|welder|plant sales|marine engineer|petroleum engineer|chemical engineer|mining engineer|hvac|hardware applications engineer|camera optics|cable design|digital power controllers|electromechanical)\b',
    r'\b(architectural designer|interior designer|landscape architect|bachelor of architecture)\b',
    r'\b(real estate developer|property developer|land developer)\b',
    r'\b(sales engineer|field sales|technical sales engineer|sales executive|sales manager|sales representative|business development executive|bde\b|bda\b|door ironmongery)\b',
    r'\b(telecaller|telesales|telesale|tele-sales|bpo\b|cold call|inside sales|customer support executive|calling executive)\b',
    r'\b(recruiter|recruitment|talent acquisition|headhunter|staffing specialist|bench sales|technical recruiter|hr executive|hr intern|hr generalist|hr manager|hrd\b|hrm student|hr operations|placement manager)\b',
    r'\b(accountant|accounting|audit|taxation|payroll|billing executive|accounts receivable|accounts payable)\b',
    r'\b(graphic designer|video editor|animator|social media manager|content writer|copywriter|seo executive|digital marketer|digital marketing|affiliate marketing)\b',
    r'\b(nurse|doctor|pharmacist|medical officer|store manager|cook|chef|waiter|cashier|delivery driver|logistics coordinator)\b',
    r'\b(receptionist|front desk|office assistant|data entry operator|back office executive)\b',
]

TECH_RESTORE_PATTERNS = [
    r'\b(developer|programmer|coder|software\s+engineer|software\s+development|sde\b|swe\b|web\s+developer)\b',
    r'\b(full[- ]?stack|front[- ]?end|back[- ]?end|web\s+dev)\b',
    r'\b(mobile|android|ios|flutter|react\s+native|app\s+developer|application\s+developer)\b',
    r'\b(founding\s+engineer|staff\s+engineer|principal\s+engineer|lead\s+engineer|product\s+engineer)\b',
    r'\b(python|react|node|next\.js|nextjs|typescript|javascript|django|fastapi|flask|express|golang|rust|java(?!\s+script)|c\+\+|\.net|c#|laravel|php|ruby|rails|shopify|wordpress|sap\s+abap|appian|oracle|oic|salesforce|mulesoft)\b',
    r'\b(ai\b|artificial\s+intelligence|ml\b|machine\s+learning|genai|generative\s+ai|llm|deep\s+learning|data\s+scientist|data\s+science|data\s+engineer|nlp|computer\s+vision|agentic)\b',
    r'\b(devops|devsecops|cloud|platform\s+engineer|site\s+reliability|sre\b|systems?\s+engineer|infrastructure\s+engineer|network\s+engineer)\b',
    r'\b(qa\b|sdet\b|test\s+engineer|automation\s+engineer|quality\s+assurance|tester)\b',
    r'\b(solution\s+architect|solutions\s+architect|cloud\s+architect|software\s+architect|enterprise\s+architect|technical\s+architect|ai\s+architect|data\s+architect|aks\s+platform\s+architect|aem\s+architect|servicenow\s+architect|ccaas\s+architect|digital\s+workspace\s+architect|iot\s+architect)\b',
    r'\b(integration\s+engineer|integrations\s+engineer|api\b|webhooks?|inference\s+engineer|finops\s+engineer|database\s+reliability|application\s+security\s+engineer)\b',
    r'\b(website\s+engineer|website\s+developer)\b',
    r'\b(tech\s+lead|engineering\s+lead|engineering\s+manager)\b',
]

CIRCUMSTANTIAL_REJECTION_PATTERNS = [
    r'years?\s+of\s+experience', r'\b(?:5\+|6\+|7\+|8\+|10\+)\s*(?:years?|yrs?)\b',
    r'\bexperience\s+required\b', r'\bexperience\s+exceeds?\b',
    r'\blocation\b', r'\bonsite\b', r'\bon-site\b', r'\bvisa\b', r'\bsponsorship\b',
    r'\bquestionnaire\b', r'\bquestions?:\b', r'\bscreening\b',
    r'\bcomment\s+bait\b', r'\bscam\b', r'\bspam\b', r'\balready\s+applied\b',
    r'\bexpired\b', r'\bcancelled\s+by\s+user\b', r'\buser\s+cancelled\b',
    r'\bemail\s+could\s+not\s+be\s+generated\b', r'\bmatches\s+previously\s+dismissed\b',
]

def is_strictly_non_tech(text: str) -> bool:
    t = text.lower()
    for pat in NON_TECH_PATTERNS:
        if re.search(pat, t):
            return True
    return False

def is_protected_tech_role(title: str) -> bool:
    t = title.lower()
    if is_strictly_non_tech(t):
        return False
    for pat in TECH_RESTORE_PATTERNS:
        if re.search(pat, t):
            return True
    if any(k in t for k in ['intern', 'trainee', 'fresher', 'junior', 'graduate']):
        if any(tk in t for tk in ['tech', 'software', 'web', 'dev', 'code', 'data', 'python', 'cloud', 'qa']):
            return True
    return False

def is_circumstantial_reason(reason: Optional[str]) -> bool:
    if not reason:
        return False
    reas = reason.lower()
    for pat in CIRCUMSTANTIAL_REJECTION_PATTERNS:
        if re.search(pat, reas):
            return True
    return False

# Legacy set for backward compatibility
PROTECTED_CORE_TITLES = {
    "full stack developer", "full stack engineer", "full stack",
    "software engineer", "software developer", "software development engineer", "sde",
    "backend developer", "backend engineer", "backend",
    "frontend developer", "frontend engineer", "frontend",
    "web developer", "react developer", "node js developer", "python developer"
}


def init_dismissed_roles(db_url: str = DEFAULT_DB_URL):
    """Create the dismissed_roles table and indexes if they do not exist."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS dismissed_roles (
        id VARCHAR(64) PRIMARY KEY,
        role_title TEXT NOT NULL,
        normalized_title VARCHAR(256) UNIQUE NOT NULL,
        source VARCHAR(64) NOT NULL DEFAULT 'LinkedIn Posts',
        reason TEXT,
        occurrences INT DEFAULT 1,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_dismissed_roles_norm ON dismissed_roles(normalized_title);
    CREATE INDEX IF NOT EXISTS idx_dismissed_roles_title ON dismissed_roles(role_title);
    CREATE INDEX IF NOT EXISTS idx_dismissed_roles_source ON dismissed_roles(source);
    CREATE INDEX IF NOT EXISTS idx_dismissed_roles_updated_at ON dismissed_roles(updated_at DESC);
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
        conn.commit()

    # Automatically seed from existing historical posts if table is empty
    seed_dismissed_roles_from_posts(db_url)


def detect_post_source(category: Optional[str], post_url: Optional[str]) -> str:
    """Classify the origin source channel of a post."""
    cat = (category or "").upper()
    url = (post_url or "").lower()

    if cat == "EASY_APPLY":
        return "LinkedIn Easy Apply"
    if cat == "INDEED_APPLY" or "indeed.com" in url:
        return "Indeed Apply"
    if "infopark.in" in url:
        return "Infopark"
    if "manual://" in url or "direct://" in url:
        return "Manual"
    return "LinkedIn Posts"


def seed_dismissed_roles_from_posts(db_url: str = DEFAULT_DB_URL) -> int:
    """
    Import previously rejected or dismissed posts from the posts table into
    the dismissed_roles registry. Skips core developer titles to safeguard search.
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dismissed_roles;")
            existing_count = cur.fetchone()[0]
            if existing_count > 0:
                return 0

            # Fetch candidate dismissed posts
            query = """
            SELECT 
                author_headline, 
                category, 
                post_url, 
                rejection_reason,
                created_at,
                updated_at
            FROM posts 
            WHERE (status = 'REJECTED' OR is_dismissed = TRUE) 
              AND author_headline IS NOT NULL 
              AND trim(author_headline) != '';
            """
            cur.execute(query)
            rows = cur.fetchall()

            aggregated = {}
            for headline, cat, url, reason, created, updated in rows:
                norm = normalize_job_title(headline)
                if not norm or len(norm) < 2 or norm in PROTECTED_CORE_TITLES or is_protected_tech_role(headline) or is_circumstantial_reason(reason):
                    continue

                source = detect_post_source(cat, url)
                last_dt = updated or created or datetime.now()

                if norm not in aggregated:
                    role_id = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
                    aggregated[norm] = {
                        "id": role_id,
                        "role_title": headline.strip(),
                        "normalized_title": norm,
                        "source": source,
                        "reason": reason or "Previously dismissed role",
                        "occurrences": 1,
                        "created_at": created or datetime.now(),
                        "updated_at": last_dt,
                    }
                else:
                    aggregated[norm]["occurrences"] += 1
                    if last_dt and aggregated[norm]["updated_at"] and last_dt > aggregated[norm]["updated_at"]:
                        aggregated[norm]["updated_at"] = last_dt
                        aggregated[norm]["source"] = source
                        if reason:
                            aggregated[norm]["reason"] = reason

            if not aggregated:
                return 0

            insert_sql = """
            INSERT INTO dismissed_roles (
                id, role_title, normalized_title, source, reason, occurrences, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (normalized_title) DO UPDATE SET
                occurrences = dismissed_roles.occurrences + EXCLUDED.occurrences,
                updated_at = GREATEST(dismissed_roles.updated_at, EXCLUDED.updated_at),
                reason = COALESCE(EXCLUDED.reason, dismissed_roles.reason);
            """
            data = [
                (
                    v["id"],
                    v["role_title"],
                    v["normalized_title"],
                    v["source"],
                    v["reason"],
                    v["occurrences"],
                    v["created_at"],
                    v["updated_at"],
                )
                for v in aggregated.values()
            ]
            cur.executemany(insert_sql, data)
        conn.commit()

    print(f"✓ Seeded {len(aggregated)} historical dismissed roles into dismissed_roles table.")
    return len(aggregated)


def sync_dismissed_roles_from_posts(db_url: str = DEFAULT_DB_URL) -> int:
    """
    Incremental sync: inspects posts for newly rejected/dismissed items not yet registered.
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            query = """
            SELECT 
                author_headline, 
                category, 
                post_url, 
                rejection_reason,
                created_at,
                updated_at
            FROM posts 
            WHERE (status = 'REJECTED' OR is_dismissed = TRUE) 
              AND author_headline IS NOT NULL 
              AND trim(author_headline) != '';
            """
            cur.execute(query)
            rows = cur.fetchall()

            upserted = 0
            for headline, cat, url, reason, created, updated in rows:
                norm = normalize_job_title(headline)
                if not norm or len(norm) < 2 or norm in PROTECTED_CORE_TITLES or is_protected_tech_role(headline) or is_circumstantial_reason(reason):
                    continue

                source = detect_post_source(cat, url)
                last_dt = updated or created or datetime.now()
                role_id = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]

                insert_sql = """
                INSERT INTO dismissed_roles (
                    id, role_title, normalized_title, source, reason, occurrences, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
                ON CONFLICT (normalized_title) DO UPDATE SET
                    occurrences = dismissed_roles.occurrences + 1,
                    updated_at = GREATEST(dismissed_roles.updated_at, EXCLUDED.updated_at),
                    reason = COALESCE(EXCLUDED.reason, dismissed_roles.reason);
                """
                cur.execute(insert_sql, (role_id, headline.strip(), norm, source, reason or "Dismissed role", created or datetime.now(), last_dt))
                upserted += 1
        conn.commit()
    return upserted


def get_dismissed_roles(
    search: Optional[str] = None,
    source: Optional[str] = None,
    order_by: str = "name_asc",
    limit: int = 50,
    offset: int = 0,
    db_url: str = DEFAULT_DB_URL,
) -> Dict[str, Any]:
    """
    Retrieve paginated dismissed roles, ordered by name by default.
    """
    where_clauses = []
    params = []

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        where_clauses.append("(LOWER(role_title) LIKE %s OR LOWER(COALESCE(reason, '')) LIKE %s)")
        params.extend([term, term])

    if source and source != "ALL":
        where_clauses.append("source = %s")
        params.append(source)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Ordering logic
    if order_by == "name_desc":
        order_sql = "ORDER BY LOWER(role_title) DESC, updated_at DESC"
    elif order_by in ("recent", "updated_desc", "date_desc"):
        order_sql = "ORDER BY updated_at DESC, LOWER(role_title) ASC"
    elif order_by in ("oldest", "updated_asc", "date_asc"):
        order_sql = "ORDER BY updated_at ASC, LOWER(role_title) ASC"
    elif order_by == "occurrences_desc":
        order_sql = "ORDER BY occurrences DESC, LOWER(role_title) ASC"
    else:  # name_asc (default)
        order_sql = "ORDER BY LOWER(role_title) ASC, updated_at DESC"

    count_sql = f"SELECT COUNT(*) FROM dismissed_roles {where_sql};"
    select_sql = f"""
    SELECT 
        id, 
        role_title, 
        normalized_title, 
        source, 
        reason, 
        occurrences, 
        created_at, 
        updated_at
    FROM dismissed_roles
    {where_sql}
    {order_sql}
    LIMIT %s OFFSET %s;
    """

    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(count_sql, tuple(params))
            total = cur.fetchone()["count"]

            fetch_params = params + [limit, offset]
            cur.execute(select_sql, tuple(fetch_params))
            rows = [dict(r) for r in cur.fetchall()]

    return {"roles": rows, "total": total}


def get_dismissed_roles_stats(db_url: str = DEFAULT_DB_URL) -> Dict[str, Any]:
    """Get total count and breakdown by source channel."""
    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM dismissed_roles;")
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT source, COUNT(*) as count 
                FROM dismissed_roles 
                GROUP BY source 
                ORDER BY count DESC;
            """)
            source_rows = cur.fetchall()

    sources = {r["source"]: r["count"] for r in source_rows}
    return {
        "total": total,
        "sources": sources,
    }


def add_dismissed_role(
    role_title: str,
    source: str = "LinkedIn Posts",
    reason: Optional[str] = None,
    db_url: str = DEFAULT_DB_URL,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Add or update a dismissed role in the registry.
    Safeguards prevent accidental blacklisting of core tech/developer roles.
    """
    clean_title = (role_title or "").strip()
    if not clean_title:
        raise ValueError("Role title cannot be empty.")

    norm = normalize_job_title(clean_title)
    if not norm:
        raise ValueError("Invalid role title.")

    if not force:
        if is_protected_tech_role(clean_title):
            raise ValueError(f"Cannot dismiss core tech role '{clean_title}'. Relatable software engineering and developer roles must remain discoverable.")
        if is_circumstantial_reason(reason):
            raise ValueError(f"Circumstantial reason ('{reason}') applies only to an individual post, not the global role title.")

    role_id = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]

    sql = """
    INSERT INTO dismissed_roles (
        id, role_title, normalized_title, source, reason, occurrences, updated_at
    ) VALUES (%s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP)
    ON CONFLICT (normalized_title) DO UPDATE SET
        occurrences = dismissed_roles.occurrences + 1,
        updated_at = CURRENT_TIMESTAMP,
        source = COALESCE(EXCLUDED.source, dismissed_roles.source),
        reason = COALESCE(EXCLUDED.reason, dismissed_roles.reason)
    RETURNING *;
    """
    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (role_id, clean_title, norm, source or "Manual", reason or "Dismissed role"))
            row = cur.fetchone()
        conn.commit()

    return dict(row) if row else {}


def delete_dismissed_role(role_id: str, db_url: str = DEFAULT_DB_URL) -> bool:
    """Delete a single dismissed role from the registry by id or normalized title."""
    sql = "DELETE FROM dismissed_roles WHERE id = %s OR normalized_title = %s;"
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (role_id, role_id))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def delete_dismissed_roles_batch(role_ids: List[str], db_url: str = DEFAULT_DB_URL) -> int:
    """Batch delete dismissed roles from the registry."""
    if not role_ids:
        return 0
    sql = "DELETE FROM dismissed_roles WHERE id = ANY(%s) OR normalized_title = ANY(%s);"
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (role_ids, role_ids))
            count = cur.rowcount
        conn.commit()
    return count


def get_dismissed_role_titles(db_url: str = DEFAULT_DB_URL) -> Set[str]:
    """
    Fetch all unique normalized job titles from dismissed_roles table.
    Used by scrapers across LinkedIn, Indeed, and Infopark to skip dismissed roles.
    """
    dismissed = set()
    query = "SELECT normalized_title FROM dismissed_roles;"
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                for (norm,) in cur.fetchall():
                    if norm:
                        dismissed.add(norm)
    except Exception as e:
        print(f"Notice fetching dismissed role titles: {e}")
    return dismissed


def check_title_previously_dismissed(
    title: str,
    dismissed_set: Optional[Set[str]] = None,
    db_url: str = DEFAULT_DB_URL,
) -> Tuple[bool, Optional[str]]:
    """Check if title matches any previously dismissed role in the registry."""
    if not title:
        return False, None
    if dismissed_set is None:
        dismissed_set = get_dismissed_role_titles(db_url)
    norm = normalize_job_title(title)
    if norm in dismissed_set:
        return True, f"Auto-dismissed: Matches previously dismissed role '{title}'"
    return False, None
