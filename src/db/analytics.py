"""
PostgreSQL Analytics, KPI Aggregations & Rejection Analysis.
"""

from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from src.db.connection import get_connection, DEFAULT_DB_URL


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
        COUNT(*) FILTER (WHERE category = 'DRAFT_PORTAL') AS draft_portal_total,
        COUNT(*) FILTER (WHERE category = 'EASY_APPLY') AS easy_apply_total,
        COUNT(*) FILTER (WHERE category = 'EASY_APPLY' AND status = 'DISCOVERED') AS easy_apply_pending,
        COUNT(*) FILTER (WHERE category = 'EASY_APPLY' AND status = 'REQUIRES_QUESTIONNAIRE') AS easy_apply_questionnaire,
        COUNT(*) FILTER (WHERE category = 'EASY_APPLY' AND status = 'APPLIED') AS easy_apply_applied,
        COUNT(*) FILTER (WHERE is_potential_spam = TRUE) AS potential_spam_total,
        COUNT(*) FILTER (WHERE array_length(contact_emails, 1) > 0) AS with_emails
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
                "easy_apply_total": 0,
                "easy_apply_pending": 0,
                "easy_apply_questionnaire": 0,
                "easy_apply_applied": 0,
                "potential_spam_total": 0,
                "with_emails": 0,
            }
            if "others_total" not in stats:
                stats["others_total"] = (stats.get("applications_sent") or 0) + (stats.get("rejected_total") or 0)
            if "potential_spam_total" not in stats:
                stats["potential_spam_total"] = 0
            if "with_emails" not in stats:
                stats["with_emails"] = stats.get("email_outreach_total") or 0
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
                    WHERE created_at >= %s::date
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

            # 6. Rejection / Spam Reasons Breakdown
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
