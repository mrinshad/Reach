"""
Reach — Activity & Automation Run Logs Database Queries.
(src/db/activity_logs.py)

Tracks and persists execution history for automated background tasks:
- Scrapers (LinkedIn Posts, Easy Apply, Infopark)
- Batch & Single Easy Apply applications
- ChatGPT email draft generation

Excludes manual user clicks / actions.
"""

import json
import time
from typing import Any, Dict, List, Optional
import psycopg2.extras
from src.db.connection import DEFAULT_DB_URL, get_connection


def create_activity_log(
    log_id: str,
    task_type: str,
    task_name: str,
    short_name: str = "",
    parameters: Optional[Dict[str, Any]] = None,
    total_items: int = 0,
    db_url: str = DEFAULT_DB_URL,
) -> str:
    """Create a new activity run log in 'running' status."""
    query = """
    INSERT INTO activity_logs (
        id, task_type, task_name, short_name, parameters,
        status, total_items, completed_items, started_at, created_at
    ) VALUES (
        %s, %s, %s, %s, %s,
        'running', %s, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    ON CONFLICT (id) DO UPDATE SET
        task_name = EXCLUDED.task_name,
        parameters = EXCLUDED.parameters,
        status = 'running'
    RETURNING id;
    """
    params_json = json.dumps(parameters or {})
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (log_id, task_type, task_name, short_name or task_name, params_json, total_items),
                )
                conn.commit()
                return log_id
    except Exception as e:
        print(f"Error creating activity log {log_id}: {e}")
        return log_id


def update_activity_log_progress(
    log_id: str,
    completed_items: int = 0,
    logs: Optional[List[str]] = None,
    db_url: str = DEFAULT_DB_URL,
):
    """Update progress items and append recent logs."""
    query = """
    UPDATE activity_logs
    SET completed_items = %s,
        logs = %s
    WHERE id = %s;
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (completed_items, logs or [], log_id))
                conn.commit()
    except Exception as e:
        print(f"Error updating progress for activity log {log_id}: {e}")


def finish_activity_log(
    log_id: str,
    status: str = "completed",
    result_summary: str = "",
    crawl_stats: Optional[Dict[str, Any]] = None,
    logs: Optional[List[str]] = None,
    duration_seconds: float = 0.0,
    db_url: str = DEFAULT_DB_URL,
):
    """Mark an activity log as finished ('completed', 'error', or 'stopped')."""
    query = """
    UPDATE activity_logs
    SET status = %s,
        result_summary = %s,
        crawl_stats = %s,
        logs = %s,
        finished_at = CURRENT_TIMESTAMP,
        duration_seconds = %s
    WHERE id = %s;
    """
    stats_json = json.dumps(crawl_stats or {})
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        status,
                        result_summary,
                        stats_json,
                        logs or [],
                        round(float(duration_seconds), 2),
                        log_id,
                    ),
                )
                conn.commit()
    except Exception as e:
        print(f"Error finishing activity log {log_id}: {e}")


def get_activity_logs(
    limit: int = 25,
    offset: int = 0,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    db_url: str = DEFAULT_DB_URL,
) -> Dict[str, Any]:
    """
    Retrieve paginated activity logs (excluding heavy logs array for list performance).
    Returns {"total": int, "runs": List[Dict]}.
    """
    where_clauses = []
    params = []

    if task_type and task_type != "ALL":
        where_clauses.append("task_type = %s")
        params.append(task_type)

    if status and status != "ALL":
        where_clauses.append("status = %s")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"SELECT COUNT(*) FROM activity_logs {where_sql};"
    select_sql = f"""
    SELECT
        id, task_type, task_name, short_name, parameters,
        status, result_summary, crawl_stats,
        total_items, completed_items,
        started_at, finished_at, duration_seconds, created_at,
        cardinality(logs) AS log_count
    FROM activity_logs
    {where_sql}
    ORDER BY created_at DESC
    LIMIT %s OFFSET %s;
    """

    try:
        with get_connection(db_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(count_sql, tuple(params))
                total = cur.fetchone()["count"]

                query_params = list(params) + [limit, offset]
                cur.execute(select_sql, tuple(query_params))
                rows = [dict(r) for r in cur.fetchall()]

                # Serialize timestamps for JSON
                for r in rows:
                    if r.get("started_at"):
                        r["started_at"] = r["started_at"].isoformat()
                    if r.get("finished_at"):
                        r["finished_at"] = r["finished_at"].isoformat()
                    if r.get("created_at"):
                        r["created_at"] = r["created_at"].isoformat()

                return {"total": total, "runs": rows}
    except Exception as e:
        print(f"Error fetching activity logs: {e}")
        return {"total": 0, "runs": []}


def get_activity_log_by_id(log_id: str, db_url: str = DEFAULT_DB_URL) -> Optional[Dict[str, Any]]:
    """Retrieve full activity log record including all console terminal logs."""
    query = """
    SELECT
        id, task_type, task_name, short_name, parameters,
        status, result_summary, crawl_stats, logs,
        total_items, completed_items,
        started_at, finished_at, duration_seconds, created_at
    FROM activity_logs
    WHERE id = %s
    LIMIT 1;
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (log_id,))
                row = cur.fetchone()
                if not row:
                    return None
                data = dict(row)
                if data.get("started_at"):
                    data["started_at"] = data["started_at"].isoformat()
                if data.get("finished_at"):
                    data["finished_at"] = data["finished_at"].isoformat()
                if data.get("created_at"):
                    data["created_at"] = data["created_at"].isoformat()
                return data
    except Exception as e:
        print(f"Error fetching activity log {log_id}: {e}")
        return None


def clear_activity_logs(db_url: str = DEFAULT_DB_URL) -> int:
    """Clear all activity logs (maintenance helper)."""
    query = "DELETE FROM activity_logs;"
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                count = cur.rowcount
                conn.commit()
                return count
    except Exception as e:
        print(f"Error clearing activity logs: {e}")
        return 0
