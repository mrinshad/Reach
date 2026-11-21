"""
PostgreSQL Posts Data Access & Workflow State Operations.
"""

import re
import hashlib
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional, Set, Tuple
from src.db.connection import get_connection, DEFAULT_DB_URL

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
    
    Returns: (is_scam, is_potential_scam, scam_reason, potential_spam_reason)
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


def canonicalize_job_url(url: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Sanitize and canonicalize a job URL, extracting platform name and native job ID.
    Returns: (canonical_url, platform, platform_job_id)
    """
    if not url or not url.strip():
        return None, None, None

    u = url.strip()

    # Manual or direct schemes
    if u.startswith("manual://") or u.startswith("direct://"):
        return u, ("manual" if u.startswith("manual://") else "direct"), None

    # 1. LinkedIn Job View or currentJobId
    li_job_m = re.search(r"(?:jobs/view/|currentJobId=)(\d{8,16})", u)
    if li_job_m:
        jid = li_job_m.group(1)
        return f"https://www.linkedin.com/jobs/view/{jid}/", "linkedin", jid

    # 2. LinkedIn Feed / Activity Post
    li_post_m = re.search(r"(?:feed/update/urn:li:activity:|posts/.*?activity-)(\d{15,22})", u)
    if li_post_m:
        pid = li_post_m.group(1)
        return f"https://www.linkedin.com/feed/update/urn:li:activity:{pid}/", "linkedin_post", pid

    # 3. Indeed Job View / rc / clk
    ind_m = re.search(r"(?:jk=|viewjob\?jk=)([a-f0-9]{12,24})", u, re.I)
    if ind_m:
        jk = ind_m.group(1)
        domain = "in.indeed.com" if "in.indeed.com" in u else "www.indeed.com"
        return f"https://{domain}/viewjob?jk={jk}", "indeed", jk

    # 4. Infopark Kochi
    info_m = re.search(r"/companies/job-search/detail/(\d+)", u)
    if info_m:
        ijid = info_m.group(1)
        return f"https://infopark.in/companies/job-search/detail/{ijid}", "infopark", ijid

    # 5. Generic URLs: strip tracking query params
    clean_u = re.sub(
        r"([?&])(refId|trackingId|tracking_id|utm_[a-z]+|eBP|from|vjs|tk|fccid|session_redirect|midToken|trk|trkInfo|refMarker|dest_url)=[^&#]*",
        r"\1",
        u,
        flags=re.I,
    )
    clean_u = re.sub(r"[?&]+$", "", clean_u)
    clean_u = clean_u.rstrip("/")
    return clean_u, "generic", None


def compute_exact_opening_signature(
    author_name: str,
    author_headline: str,
    location: Optional[str] = None,
    full_text: Optional[str] = None,
) -> str:
    """
    Generate a normalized composite signature uniquely identifying an exact job opening.
    (Company + Normalized Title + Location + Text snippet).
    """
    c_author = (author_name or "").strip().lower()
    c_title = normalize_job_title(author_headline or "")
    c_loc = (location or "").strip().lower()
    c_snippet = re.sub(r"\s+", " ", (full_text or "").strip().lower())[:80]
    return f"{c_author}|{c_title}|{c_loc}|{c_snippet}"


def get_existing_post_identifiers(db_url: str = DEFAULT_DB_URL) -> Set[str]:
    """
    Retrieve all existing post identifiers (URLs, IDs, platform IDs, content signatures)
    into an in-memory set for rapid O(1) duplicate checks during scraping.
    """
    identifiers = set()
    sql = "SELECT id, post_url, author_name, author_headline, location, substring(full_text, 1, 100) AS snippet, platform_job_id FROM posts;"
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                pid, url, author, headline, loc, snippet, plat_id = (
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6]
                )
                if pid:
                    identifiers.add(str(pid))
                if plat_id:
                    identifiers.add(str(plat_id))
                    identifiers.add(f"easy_apply_{plat_id}")
                    identifiers.add(f"ind_{plat_id}")
                if url:
                    canonical_u, _, u_plat_id = canonicalize_job_url(url)
                    if canonical_u:
                        identifiers.add(canonical_u)
                        identifiers.add(canonical_u.rstrip("/"))
                    if u_plat_id:
                        identifiers.add(u_plat_id)
                    identifiers.add(url.split("?")[0].rstrip("/"))
                    identifiers.add(url.rstrip("/"))
                if author and snippet:
                    sig = f"{(author or '').strip().lower()}:{(snippet or '').strip()[:60]}"
                    identifiers.add(sig)
                if author and headline:
                    exact_sig = compute_exact_opening_signature(author, headline, loc, snippet)
                    identifiers.add(exact_sig)
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


def normalize_job_title(title: Optional[str]) -> str:
    """Normalize job title for consistent matching against dismissed roles."""
    if not title:
        return ""
    t = title.strip().lower()
    # Strip common LinkedIn tag patterns like (Verified job), (Hybrid), (Remote), etc.
    t = re.sub(r"\((verified job|hybrid|remote|on-site|onsite|wfh|full-time|part-time|contract|entry level|immediate joiner[s]?)\)", "", t, flags=re.I)
    # Strip common noise symbols and punctuation
    t = re.sub(r"[\(\)\[\]\{\}\-\–\—\•\|\:\,\/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def get_dismissed_role_titles(db_url: str = DEFAULT_DB_URL) -> Set[str]:
    """
    Fetch all unique normalized job titles from dismissed_roles table.
    Used by scrapers to automatically dismiss matching newly discovered roles.
    """
    try:
        from src.db.dismissed_roles import get_dismissed_role_titles as _get_titles
        return _get_titles(db_url)
    except Exception as e:
        print(f"Notice fetching dismissed role titles: {e}")
        return set()


def check_title_previously_dismissed(
    title: str,
    dismissed_set: Optional[Set[str]] = None,
    db_url: str = DEFAULT_DB_URL,
) -> Tuple[bool, Optional[str]]:
    """Check if title matches any previously dismissed role."""
    from src.db.dismissed_roles import check_title_previously_dismissed as _check_title
    return _check_title(title, dismissed_set=dismissed_set, db_url=db_url)


# Patterns indicating comment-bait / comment to get link / engagement farming
COMMENT_BAIT_PATTERNS = [
    # Comment below / down below / in comments
    r"comment\s+(down\s+)?below",
    r"(drop|leave|put|post)\s+(a\s+)?comment\s+(down\s+)?below",
    r"comment\s+in\s+(the\s+)?comments?",
    r"comment\s+(your\s+)?(email|resume|cv|details|contact|id|portfolio|profile)\s+(down\s+)?below",
    # Comment interested / yes / info / etc.
    r"comment\s+['\"]?(interested|yes|apply|ready|send|link|details|info|email|here|cfbr|fsd)['\"]?",
    r"comment\s+(if\s+|when\s+)?['\"]?interested['\"]?",
    r"please\s+comment\s+['\"]?interested['\"]?",
    r"interested\s*[,.]?\s*(please\s+)?comment\b",
    # Drop/share email or resume in comments
    r"(drop|share|leave|put|post)\s+(your\s+)?(email|resume|cv|contact|details|id)\s+(in\s+)?(the\s+)?comments?",
    # Type interested in comments
    r"type\s+['\"]?interested['\"]?",
    r"type\s+['\"]?(interested|yes|apply|info)['\"]?\s+(in\s+)?(the\s+)?comments?",
    r"write\s+['\"]?interested[\'\"]?\s+(in\s+)?(the\s+)?comments?",
    # Comment to / for apply / link / details
    r"comment\s+(to\s+|for\s+)(apply|get\s+link|receive|details|referral|the\s+link|link|info)",
    r"leave\s+(a\s+)?comment\s+(below|with|to|for)",
]


def check_comment_bait(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Detect if the post text contains comment-to-apply bait ('comment below', 'comment interested', etc.).
    Returns: (is_bait, bait_reason)
    """
    if not text:
        return False, None
    lower_text = text.lower()
    for p in COMMENT_BAIT_PATTERNS:
        if re.search(p, lower_text):
            return True, "Scam: Comment bait ('comment below' / 'comment interested')"
    return False, None


def upsert_post(
    post_data: Dict[str, Any],
    skip_if_exists: bool = True,
    db_url: str = DEFAULT_DB_URL
) -> Tuple[str, bool]:
    """
    Insert or update a post in the database with multi-layer exact job opening
    deduplication, dismissed roles monitoring, and already-applied cancellation.
    Returns (post_id, was_created).
    """
    raw_url = post_data.get("post_url", "").strip() or None
    canonical_url, platform, platform_job_id = canonicalize_job_url(raw_url)
    post_url = canonical_url or raw_url

    author_name = post_data.get("author_name", "Unknown").strip()
    author_headline = (post_data.get("author_headline") or "").strip()
    full_text = post_data.get("full_text", "").strip()
    location = (post_data.get("location") or "").strip() or None
    incoming_id = (post_data.get("id") or "").strip()

    # Deterministic ID resolution
    if incoming_id and (incoming_id.startswith("easy_apply_") or incoming_id.startswith("ind_") or incoming_id.startswith("infopark_")):
        record_id = incoming_id
    elif platform == "linkedin" and platform_job_id:
        record_id = f"easy_apply_{platform_job_id}"
    elif platform == "indeed" and platform_job_id:
        record_id = f"ind_{platform_job_id}"
    elif platform == "infopark" and platform_job_id:
        record_id = f"infopark_{platform_job_id}"
    elif post_url:
        record_id = hashlib.sha256(post_url.encode()).hexdigest()[:32]
    else:
        sig = f"{author_name}:{full_text[:100]}"
        record_id = hashlib.sha256(sig.encode()).hexdigest()[:32]

    snippet_80 = full_text[:80]

    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            # Multi-layer Exact Job Opening Duplicate Check
            # Check 1: Record ID or incoming ID
            # Check 2: Canonical or raw post_url
            # Check 3: Platform Job ID
            # Check 4: Exact composite opening signature (company, title, location, snippet)
            dup_query = """
                SELECT id, status, rejection_reason, is_dismissed, platform_job_id
                FROM posts
                WHERE id = %s
                   OR id = %s
                   OR (post_url IS NOT NULL AND post_url IN (%s, %s))
                   OR (%s IS NOT NULL AND platform_job_id = %s)
                   OR (
                       LOWER(TRIM(author_name)) = LOWER(TRIM(%s))
                       AND LOWER(TRIM(COALESCE(author_headline, ''))) = LOWER(TRIM(%s))
                       AND LOWER(TRIM(COALESCE(location, ''))) = LOWER(TRIM(%s))
                       AND substring(full_text, 1, 80) = %s
                   )
                LIMIT 1;
            """
            cur.execute(
                dup_query,
                (
                    record_id,
                    incoming_id or record_id,
                    post_url,
                    raw_url or post_url,
                    platform_job_id,
                    platform_job_id or "",
                    author_name,
                    author_headline,
                    location or "",
                    snippet_80,
                ),
            )
            existing = cur.fetchone()

            is_already_applied = bool(post_data.get("is_already_applied", False))

            if existing:
                existing_id, existing_status, existing_reason, existing_is_dismissed, existing_plat_id = existing

                # If existing is already applied or sent, preserve it
                if existing_status in ("APPLIED", "SENT"):
                    return (existing_id, False)

                # If new pass detects it has been applied on the platform, mark as CANCELLED
                if is_already_applied:
                    cur.execute(
                        "UPDATE posts SET status = 'REJECTED', rejection_reason = 'Already applied', updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                        (existing_id,)
                    )
                    conn.commit()
                    return (existing_id, False)

                # If already rejected / cancelled, preserve
                if existing_status in ("REJECTED", "CANCELLED"):
                    return (existing_id, False)

                # If skip_if_exists is True, return existing record without duplicating
                if skip_if_exists:
                    return (existing_id, False)

            emails = post_data.get("detected_emails", []) or []
            phones = post_data.get("contact_phones")
            if phones is None:
                from src.services.experience_extractor import extract_phone_numbers
                phones = extract_phone_numbers(full_text)
            links = post_data.get("detected_links", []) or []

            exp = post_data.get("experience", {})
            min_exp = exp.get("min_years")
            max_exp = exp.get("max_years")
            raw_exp = exp.get("raw_text")
            seniority = exp.get("seniority_level", "Unspecified")
            is_fresher = exp.get("is_fresher", False)
            category = post_data.get("category", "EMAIL_OUTREACH")

            is_scam, is_potential_spam, scam_reason, potential_spam_reason = check_email_spam(emails, cur)

            # Check comment bait spam
            is_bait, bait_reason = check_comment_bait(full_text)
            if is_bait and not is_scam:
                is_scam = True
                scam_reason = bait_reason

            # CHECK 1: Auto-dismiss check if role headline matches a previously dismissed role
            is_dismissed = bool(post_data.get("is_dismissed", False))
            dismissed_reason = post_data.get("rejection_reason") if is_dismissed else None
            if not is_dismissed and author_headline and post_data.get("status") in (None, "DISCOVERED"):
                is_prev_dismissed, prev_reason = check_title_previously_dismissed(author_headline, db_url=db_url)
                if is_prev_dismissed:
                    is_dismissed = True
                    dismissed_reason = prev_reason

            # CHECK 2: Already Applied Check -> mark as CANCELLED (status = 'REJECTED', reason = 'Already applied')
            if is_already_applied:
                initial_status = "REJECTED"
                initial_reason = "Already applied"
            elif is_scam:
                initial_status = "REJECTED"
                initial_reason = scam_reason
            elif is_dismissed:
                initial_status = "REJECTED"
                initial_reason = dismissed_reason
            elif post_data.get("status"):
                initial_status = "REJECTED" if post_data["status"] == "CANCELLED" else post_data["status"]
                initial_reason = post_data.get("rejection_reason")
            else:
                initial_status = "DISCOVERED"
                initial_reason = None

            if post_data.get("is_potential_spam") is not None:
                is_potential_spam = bool(post_data["is_potential_spam"])
            if post_data.get("potential_spam_reason") is not None:
                potential_spam_reason = post_data["potential_spam_reason"]

            insert_sql = """
            INSERT INTO posts (
                id, post_url, author_name, author_headline, author_profile,
                posted_date_raw, full_text, contact_emails, contact_phones, external_links,
                min_experience, max_experience, raw_experience, seniority_level,
                is_fresher, category, status, rejection_reason, is_potential_spam, potential_spam_reason,
                location, platform_job_id, is_dismissed, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (post_url) DO UPDATE SET
                contact_phones = CASE WHEN cardinality(posts.contact_phones) = 0 THEN EXCLUDED.contact_phones ELSE posts.contact_phones END
            RETURNING id;
            """
            cur.execute(insert_sql, (
                record_id,
                post_url,
                author_name,
                author_headline,
                post_data.get("author_profile", ""),
                post_data.get("post_date", ""),
                full_text,
                emails,
                phones,
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
                platform_job_id,
                is_dismissed,
            ))
            res = cur.fetchone()
            conn.commit()
            created_id = res[0] if res else record_id
            return (created_id, res is not None)


def backfill_comment_bait_spam(db_url: str = DEFAULT_DB_URL) -> int:
    """
    Find existing DISCOVERED posts whose full_text matches comment bait patterns
    and update them to status = 'REJECTED' with rejection_reason = "Scam: Comment bait ('comment below' / 'comment interested')".
    Returns the count of updated posts.
    """
    count = 0
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, full_text FROM posts WHERE status = 'DISCOVERED';")
            rows = cur.fetchall()
            ids_to_update = []
            for post_id, full_text in rows:
                is_bait, _ = check_comment_bait(full_text)
                if is_bait:
                    ids_to_update.append(post_id)
            if ids_to_update:
                cur.execute(
                    "UPDATE posts SET status = 'REJECTED', "
                    "rejection_reason = 'Scam: Comment bait (''comment below'' / ''comment interested'')', "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ANY(%s);",
                    (ids_to_update,)
                )
                count = len(ids_to_update)
            conn.commit()
    return count


def _apply_date_filter(
    date_filter: Optional[str],
    where_clauses: list,
    params: list,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    gen_status: Optional[str] = None,
):
    """Safely append SQL where clauses for custom from/to date ranges and predefined filters."""
    is_history = (
        (status and status.upper() in ("SENT", "REJECTED", "OTHERS", "HISTORY", "ARCHIVE"))
        or (gen_status and gen_status.upper() in ("SENT", "REJECTED", "OTHERS", "HISTORY", "ARCHIVE"))
    )
    ts_col = "COALESCE(sent_at, updated_at, created_at)" if is_history else "created_at"

    # Custom from/to date boundaries (e.g. '2026-09-01')
    has_custom = False
    clean_from = from_date.strip() if isinstance(from_date, str) and from_date.strip() and not from_date.strip().lower().startswith("query") else None
    clean_to = to_date.strip() if isinstance(to_date, str) and to_date.strip() and not to_date.strip().lower().startswith("query") else None

    if clean_from:
        where_clauses.append(f"DATE({ts_col}) >= %s::date")
        params.append(clean_from)
        has_custom = True
    if clean_to:
        where_clauses.append(f"DATE({ts_col}) <= %s::date")
        params.append(clean_to)
        has_custom = True

    if has_custom or not date_filter:
        return

    df = date_filter.strip().upper()
    if df == "ALL":
        return
    if df in ("24H", "LAST_24H", "PAST_24H"):
        where_clauses.append(f"{ts_col} >= NOW() - INTERVAL '24 hours'")
    elif df == "TODAY":
        where_clauses.append(f"{ts_col} >= CURRENT_DATE")
    elif df == "YESTERDAY":
        where_clauses.append(f"{ts_col} >= CURRENT_DATE - INTERVAL '1 day' AND {ts_col} < CURRENT_DATE")
    elif df in ("2D", "LAST_2_DAYS", "2DAYS", "48H"):
        where_clauses.append(f"{ts_col} >= NOW() - INTERVAL '2 days'")
    elif df in ("3D", "LAST_3_DAYS", "3DAYS", "72H"):
        where_clauses.append(f"{ts_col} >= NOW() - INTERVAL '3 days'")
    elif df in ("WEEK", "PAST_WEEK", "7D"):
        where_clauses.append(f"{ts_col} >= NOW() - INTERVAL '7 days'")
    elif df.startswith("CUSTOM_HOURS:") or df.startswith("HOURS:"):
        try:
            hrs = int(df.split(":")[1])
            if hrs > 0:
                where_clauses.append(f"{ts_col} >= NOW() - make_interval(hours => %s)")
                params.append(hrs)
        except (ValueError, IndexError):
            pass
    elif df.startswith("CUSTOM_DAYS:") or df.startswith("DAYS:"):
        try:
            dys = int(df.split(":")[1])
            if dys > 0:
                where_clauses.append(f"{ts_col} >= NOW() - make_interval(days => %s)")
                params.append(dys)
        except (ValueError, IndexError):
            pass


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
    experience_only: bool = False,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    has_email: Optional[bool] = None,
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
            where_clauses.append("status IN ('SENT', 'REJECTED', 'CANCELLED')")
        elif status in ("REJECTED", "CANCELLED"):
            where_clauses.append("status IN ('REJECTED', 'CANCELLED')")
        elif status == "REVIEW_ALL":
            where_clauses.append("(status IN ('EMAIL_GENERATED', 'DISCOVERED', 'SELECTED') OR (status = 'SENT' AND generated_body IS NOT NULL AND length(trim(generated_body)) > 0))")
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
        elif gen_status == "REVIEW_ALL":
            where_clauses.append("(status IN ('EMAIL_GENERATED', 'DISCOVERED', 'SELECTED') OR (status = 'SENT' AND generated_body IS NOT NULL AND length(trim(generated_body)) > 0))")
        elif gen_status == "EVERYTHING":
            pass
    elif gen_status in ("ALL", "ALL_INCL_GENERATED"):
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED', 'EMAIL_GENERATED')")
    elif gen_status is None and status is None:
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED')")

    if experience_only:
        where_clauses.append("(rejection_reason = 'Experience Requirement Mismatch' OR rejection_reason ILIKE %s)")
        params.append("%experience%")
    elif reason and reason != "ALL":
        where_clauses.append("rejection_reason ILIKE %s")
        params.append(f"%{reason}%")

    if location and location != "ALL":
        where_clauses.append("location ILIKE %s")
        params.append(f"%{location}%")

    _apply_date_filter(date_filter, where_clauses, params, from_date=from_date, to_date=to_date, status=status, gen_status=gen_status)

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

    if has_email is True:
        where_clauses.append("(contact_emails IS NOT NULL AND cardinality(contact_emails) > 0)")
    elif has_email is False:
        where_clauses.append("(contact_emails IS NULL OR cardinality(contact_emails) = 0)")

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
    elif order_by in ("email_desc", "has_email", "email"):
        order_sql = "ORDER BY CASE WHEN contact_emails IS NOT NULL AND cardinality(contact_emails) > 0 THEN 0 ELSE 1 END ASC, created_at DESC"
    elif order_by == "generated_first":
        order_sql = """
        ORDER BY 
          CASE 
            WHEN status = 'EMAIL_GENERATED' THEN 0
            WHEN status IN ('DISCOVERED', 'SELECTED') AND (generated_body IS NOT NULL AND generated_body != '') THEN 1
            WHEN status IN ('DISCOVERED', 'SELECTED') THEN 2
            WHEN status = 'SENT' THEN 3
            ELSE 4
          END ASC,
          created_at DESC
        """
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
    experience_only: bool = False,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    has_email: Optional[bool] = None,
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
            where_clauses.append("status IN ('SENT', 'REJECTED', 'CANCELLED')")
        elif status in ("REJECTED", "CANCELLED"):
            where_clauses.append("status IN ('REJECTED', 'CANCELLED')")
        elif status == "REVIEW_ALL":
            where_clauses.append("(status IN ('EMAIL_GENERATED', 'DISCOVERED', 'SELECTED') OR (status = 'SENT' AND generated_body IS NOT NULL AND length(trim(generated_body)) > 0))")
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
        elif gen_status == "REVIEW_ALL":
            where_clauses.append("(status IN ('EMAIL_GENERATED', 'DISCOVERED', 'SELECTED') OR (status = 'SENT' AND generated_body IS NOT NULL AND length(trim(generated_body)) > 0))")
        elif gen_status == "EVERYTHING":
            pass
    elif gen_status in ("ALL", "ALL_INCL_GENERATED"):
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED', 'EMAIL_GENERATED')")
    elif gen_status is None and status is None:
        where_clauses.append("status IN ('DISCOVERED', 'SELECTED')")

    if experience_only:
        where_clauses.append("(rejection_reason = 'Experience Requirement Mismatch' OR rejection_reason ILIKE %s)")
        params.append("%experience%")
    elif reason and reason != "ALL":
        where_clauses.append("rejection_reason ILIKE %s")
        params.append(f"%{reason}%")

    if location and location != "ALL":
        where_clauses.append("location ILIKE %s")
        params.append(f"%{location}%")

    _apply_date_filter(date_filter, where_clauses, params, from_date=from_date, to_date=to_date, status=status, gen_status=gen_status)

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

    if has_email is True:
        where_clauses.append("(contact_emails IS NOT NULL AND cardinality(contact_emails) > 0)")
    elif has_email is False:
        where_clauses.append("(contact_emails IS NULL OR cardinality(contact_emails) = 0)")

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
    elif order_by in ("email_desc", "has_email", "email"):
        order_sql = "ORDER BY CASE WHEN contact_emails IS NOT NULL AND cardinality(contact_emails) > 0 THEN 0 ELSE 1 END ASC, created_at DESC"
    elif order_by == "generated_first":
        order_sql = """
        ORDER BY 
          CASE 
            WHEN status = 'EMAIL_GENERATED' THEN 0
            WHEN status IN ('DISCOVERED', 'SELECTED') AND (generated_body IS NOT NULL AND generated_body != '') THEN 1
            WHEN status IN ('DISCOVERED', 'SELECTED') THEN 2
            WHEN status = 'SENT' THEN 3
            ELSE 4
          END ASC,
          created_at DESC
        """
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


def get_post_by_id(post_id: str, db_url: str = DEFAULT_DB_URL) -> Optional[Dict[str, Any]]:
    """Retrieve a single post record by its ID."""
    sql = "SELECT * FROM posts WHERE id = %s;"
    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (post_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_posts_by_ids(post_ids: List[str], db_url: str = DEFAULT_DB_URL) -> List[Dict[str, Any]]:
    """Retrieve multiple post records by their IDs in a single batch query."""
    if not post_ids:
        return []
    sql = "SELECT * FROM posts WHERE id = ANY(%s);"
    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (list(post_ids),))
            return [dict(row) for row in cur.fetchall()]


def update_post_status(
    post_id: str,
    new_status: str,
    rejection_reason: Optional[str] = None,
    is_potential_spam: Optional[bool] = None,
    potential_spam_reason: Optional[str] = None,
    db_url: str = DEFAULT_DB_URL
):
    """Update post workflow status with optional cancellation/rejection reason and potential scam flags."""
    set_clauses = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
    params = [new_status]

    if rejection_reason is not None:
        if new_status == "REQUIRES_QUESTIONNAIRE":
            # Preserve raw screening questions intact — do not truncate or normalize
            set_clauses.append("rejection_reason = %s")
            params.append(rejection_reason)
        else:
            from src.services.chatgpt_service import clean_and_truncate_reason
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

    if new_status in ("REJECTED", "CANCELLED"):
        if rejection_reason and "dismiss" in rejection_reason.lower():
            set_clauses.append("is_dismissed = TRUE")
    elif new_status in ("DISCOVERED", "APPLIED", "EMAIL_GENERATED", "REQUIRES_QUESTIONNAIRE", "SENT"):
        set_clauses.append("is_dismissed = FALSE")

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


SEND_COOLDOWN_DAYS = 3


def get_recently_sent_recipients(
    emails: List[str],
    cooldown_days: int = SEND_COOLDOWN_DAYS,
    db_url: str = DEFAULT_DB_URL
) -> Dict[str, Dict[str, Any]]:
    """
    Check which recipient emails have already received an outreach email
    within the cooldown window. Returns a mapping of email -> info with
    the last sent timestamp, the post that was sent, and seconds remaining
    before sending again is allowed.
    """
    cleaned = [e.strip().lower() for e in (emails or []) if e and e.strip()]
    if not cleaned:
        return {}

    sql = """
    SELECT lower(recipient) AS email,
           MAX(p.sent_at) AS last_sent_at,
           (ARRAY_AGG(p.id ORDER BY p.sent_at DESC))[1] AS post_id,
           (ARRAY_AGG(p.author_name ORDER BY p.sent_at DESC))[1] AS author_name
    FROM posts p, unnest(p.contact_emails) AS recipient
    WHERE p.status = 'SENT'
      AND p.sent_at IS NOT NULL
      AND lower(recipient) = ANY(%s)
      AND p.sent_at >= NOW() - make_interval(days => %s)
    GROUP BY lower(recipient);
    """
    from datetime import datetime, timezone

    with get_connection(db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (cleaned, cooldown_days))
            rows = cur.fetchall()

    now = datetime.now(timezone.utc)
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        last_sent = row["last_sent_at"]
        if last_sent is not None and last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        elapsed = (now - last_sent).total_seconds() if last_sent else 0
        wait_seconds = max(0, int(cooldown_days * 86400 - elapsed))
        result[row["email"]] = {
            "email": row["email"],
            "post_id": row["post_id"],
            "author_name": row["author_name"],
            "last_sent_at": last_sent.isoformat() if last_sent else None,
            "wait_seconds": wait_seconds,
        }
    return result


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


def revert_posts_batch(post_ids: List[str], db_url: str = DEFAULT_DB_URL) -> int:
    """Revert multiple sent or rejected posts back to active status (EMAIL_GENERATED if draft exists, else DISCOVERED)."""
    if not post_ids:
        return 0
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
    WHERE id = ANY(%s);
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (list(post_ids),))
            count = cur.rowcount
        conn.commit()
    return count


def reject_posts_batch(
    post_ids: List[str],
    rejection_reason: Optional[str] = None,
    db_url: str = DEFAULT_DB_URL
) -> int:
    """Reject/cancel multiple posts with optional cancellation reason."""
    if not post_ids:
        return 0
    set_clauses = ["status = 'REJECTED'", "updated_at = CURRENT_TIMESTAMP"]
    params = []

    if rejection_reason is not None:
        from src.services.chatgpt_service import clean_and_truncate_reason
        cleaned_reason = clean_and_truncate_reason(rejection_reason)
        set_clauses.append("rejection_reason = %s")
        params.append(cleaned_reason)

        is_potential_spam = "potential scam" in rejection_reason.lower() or "potential spam" in rejection_reason.lower() or "scam" in rejection_reason.lower()
        if is_potential_spam:
            set_clauses.append("is_potential_spam = TRUE")
            set_clauses.append("potential_spam_reason = %s")
            params.append(cleaned_reason)

    params.append(list(post_ids))
    sql = f"UPDATE posts SET {', '.join(set_clauses)} WHERE id = ANY(%s);"
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            count = cur.rowcount
        conn.commit()
    return count


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


def mark_post_spam(post_id: str, reason: str = "Spam / Scam", db_url: str = DEFAULT_DB_URL):
    """Mark a post as rejected due to spam/scam."""
    return update_post_status(post_id, "REJECTED", rejection_reason=reason, db_url=db_url)


def cleanup_stuck_generating_posts(db_url: str = DEFAULT_DB_URL) -> int:
    """Recover posts stuck in GENERATING_EMAIL status back to their appropriate active state."""
    sql = """
    UPDATE posts SET
        status = CASE
            WHEN generated_body IS NOT NULL AND generated_body != '' AND (generated_subject IS NULL OR generated_subject != 'UNSUITABLE_JD') THEN 'EMAIL_GENERATED'
            ELSE 'DISCOVERED'
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE status = 'GENERATING_EMAIL';
    """
    with get_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            count = cur.rowcount
        conn.commit()
    return count

