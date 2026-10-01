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
        status = 'running',
        result_summary = 'Re-running task...',
        started_at = CURRENT_TIMESTAMP,
        finished_at = NULL,
        duration_seconds = 0,
        completed_items = 0
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
    completed_items: Optional[int] = None,
    total_items: Optional[int] = None,
    db_url: str = DEFAULT_DB_URL,
):
    """Mark an activity log as finished ('completed', 'error', or 'stopped') and persist final item counts."""
    set_clauses = [
        "status = %s",
        "result_summary = %s",
        "crawl_stats = %s",
        "logs = %s",
        "finished_at = CURRENT_TIMESTAMP",
        "duration_seconds = %s",
    ]
    stats_json = json.dumps(crawl_stats or {})
    params: list = [
        status,
        result_summary,
        stats_json,
        logs or [],
        round(float(duration_seconds), 2),
    ]

    if completed_items is not None:
        set_clauses.append("completed_items = %s")
        params.append(max(0, int(completed_items)))

    if total_items is not None and int(total_items) > 0:
        set_clauses.append("total_items = %s")
        params.append(int(total_items))

    params.append(log_id)
    query = f"""
    UPDATE activity_logs
    SET {', '.join(set_clauses)}
    WHERE id = %s;
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                conn.commit()
    except Exception as e:
        print(f"Error finishing activity log {log_id}: {e}")


def get_activity_logs(
    limit: int = 25,
    offset: int = 0,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
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
        s_clean = status.strip().lower()
        if s_clean in ("uncompleted", "incomplete", "failed_or_stopped"):
            where_clauses.append("status IN ('error', 'stopped')")
        else:
            where_clauses.append("status = %s")
            params.append(status)

    clean_from = from_date.strip() if isinstance(from_date, str) and from_date.strip() and not from_date.strip().lower().startswith("query") else None
    clean_to = to_date.strip() if isinstance(to_date, str) and to_date.strip() and not to_date.strip().lower().startswith("query") else None

    if clean_from:
        where_clauses.append("DATE(created_at) >= %s::date")
        params.append(clean_from)

    if clean_to:
        where_clauses.append("DATE(created_at) <= %s::date")
        params.append(clean_to)

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


def delete_activity_log(log_id: str, db_url: str = DEFAULT_DB_URL) -> bool:
    """Delete a single activity log by id."""
    query = "DELETE FROM activity_logs WHERE id = %s;"
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (log_id,))
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
    except Exception as e:
        print(f"Error deleting activity log {log_id}: {e}")
        return False


def delete_activity_logs_batch(log_ids: List[str], db_url: str = DEFAULT_DB_URL) -> int:
    """Delete multiple activity logs by list of ids."""
    if not log_ids:
        return 0
    query = "DELETE FROM activity_logs WHERE id = ANY(%s);"
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (list(log_ids),))
                deleted_count = cur.rowcount
                conn.commit()
                return deleted_count
    except Exception as e:
        print(f"Error batch deleting activity logs: {e}")
        return 0


def reset_activity_log_for_retry(
    log_id: str,
    queue_pos: int = 0,
    db_url: str = DEFAULT_DB_URL,
) -> bool:
    """
    Reset an existing activity log in-place when re-executed.
    Updates status to 'running', resets timers and logs, so no duplicate row is created.
    """
    initial_log = f"[{time.strftime('%H:%M:%S')}] Task re-queued in FIFO queue (Position #{queue_pos})." if queue_pos > 0 else f"[{time.strftime('%H:%M:%S')}] Task re-execution started."
    summary = f"Re-queued in FIFO queue (Position #{queue_pos})" if queue_pos > 0 else "Re-running task..."
    query = """
    UPDATE activity_logs
    SET status = 'running',
        result_summary = %s,
        started_at = CURRENT_TIMESTAMP,
        finished_at = NULL,
        duration_seconds = 0,
        completed_items = 0,
        logs = ARRAY[%s]
    WHERE id = %s;
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (summary, initial_log, log_id))
                updated = cur.rowcount > 0
                conn.commit()
                return updated
    except Exception as e:
        print(f"Error resetting activity log for retry {log_id}: {e}")
        return False


def cleanup_orphaned_running_logs(older_than_minutes: int = 5, db_url: str = DEFAULT_DB_URL) -> int:
    """
    Mark lingering 'running' logs from dead/previous sessions as 'stopped'.
    Avoids false 'running' indicators after server restarts.
    """
    query = """
    UPDATE activity_logs
    SET status = 'stopped',
        result_summary = 'Interrupted: Process stopped before completion.',
        finished_at = CURRENT_TIMESTAMP
    WHERE status = 'running'
      AND started_at < NOW() - (INTERVAL '1 minute' * %s);
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (older_than_minutes,))
                count = cur.rowcount
                conn.commit()
                return count
    except Exception as e:
        print(f"Error cleaning up orphaned activity logs: {e}")
        return 0


def get_activity_log_counts(db_url: str = DEFAULT_DB_URL) -> Dict[str, int]:
    """Return counts of activity runs by status (all, completed, uncompleted, error, stopped)."""
    query = """
    SELECT
        COUNT(*) AS total_all,
        COUNT(*) FILTER (WHERE status = 'completed') AS total_completed,
        COUNT(*) FILTER (WHERE status IN ('error', 'stopped')) AS total_uncompleted,
        COUNT(*) FILTER (WHERE status = 'error') AS total_error,
        COUNT(*) FILTER (WHERE status = 'stopped') AS total_stopped,
        COUNT(*) FILTER (WHERE status = 'running') AS total_running
    FROM activity_logs;
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                row = cur.fetchone()
                if not row:
                    return {"all": 0, "completed": 0, "uncompleted": 0, "error": 0, "stopped": 0, "running": 0}
                return {
                    "all": int(row["total_all"] or 0),
                    "completed": int(row["total_completed"] or 0),
                    "uncompleted": int(row["total_uncompleted"] or 0),
                    "error": int(row["total_error"] or 0),
                    "stopped": int(row["total_stopped"] or 0),
                    "running": int(row["total_running"] or 0),
                }
    except Exception as e:
        print(f"Error fetching activity log counts: {e}")
        return {"all": 0, "completed": 0, "uncompleted": 0, "error": 0, "stopped": 0, "running": 0}


def get_task_timing_benchmarks(db_url: str = DEFAULT_DB_URL) -> Dict[str, Dict[str, Any]]:
    """
    Compute real aggregated execution time benchmarks from historical activity_logs in PostgreSQL.
    Groups by task_type and subtype (e.g. easy_apply_crawler vs linkedin_posts_crawler).
    Returns dict mapping subtype/type -> {
        "avg_duration": float,
        "avg_per_item": float,
        "sample_count": int,
        "min_duration": float,
        "max_duration": float
    }
    """
    query = """
    SELECT 
        task_type,
        CASE 
            WHEN task_name ILIKE '%Easy Apply Crawler%' OR task_name ILIKE '%easy_apply%' THEN 'easy_apply_crawler'
            WHEN task_name ILIKE '%Infopark%' THEN 'infopark_crawler'
            WHEN (task_name ILIKE '%LinkedIn%' OR task_name ILIKE '%Scraper%') AND task_type = 'crawler' THEN 'linkedin_posts_crawler'
            ELSE task_type 
        END AS sub_type,
        COUNT(*) AS sample_count,
        ROUND(AVG(duration_seconds)::numeric, 1) AS avg_duration,
        ROUND(MIN(duration_seconds)::numeric, 1) AS min_duration,
        ROUND(MAX(duration_seconds)::numeric, 1) AS max_duration,
        ROUND(AVG(
            CASE 
                WHEN completed_items > 0 THEN duration_seconds / completed_items
                WHEN parameters->>'count' IS NOT NULL AND (parameters->>'count')::int > 0 
                    THEN duration_seconds / (parameters->>'count')::int 
                WHEN total_items > 1 THEN duration_seconds / total_items
                ELSE duration_seconds 
            END
        )::numeric, 1) AS avg_per_unit
    FROM activity_logs 
    WHERE status = 'completed' AND duration_seconds > 0
    GROUP BY 1, 2;
    """
    benchmarks: Dict[str, Dict[str, Any]] = {}
    try:
        with get_connection(db_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                for r in cur.fetchall():
                    key = r["sub_type"] or r["task_type"]
                    benchmarks[key] = {
                        "task_type": r["task_type"],
                        "sub_type": r["sub_type"],
                        "sample_count": int(r["sample_count"]),
                        "avg_duration": float(r["avg_duration"] or 0.0),
                        "min_duration": float(r["min_duration"] or 0.0),
                        "max_duration": float(r["max_duration"] or 0.0),
                        "avg_per_item": float(r["avg_per_unit"] or r["avg_duration"] or 0.0),
                    }
                    if r["task_type"] not in benchmarks:
                        benchmarks[r["task_type"]] = benchmarks[key]
    except Exception as e:
        print(f"Error fetching task timing benchmarks: {e}")
    return benchmarks


def backfill_historical_task_counts(db_url: str = DEFAULT_DB_URL) -> int:
    """
    One-time remediation: backfill completed_items and total_items from parameters->>'count'
    for past batch runs where completed_items was not persisted.
    """
    query = """
    UPDATE activity_logs
    SET completed_items = (parameters->>'count')::int,
        total_items = GREATEST(total_items, (parameters->>'count')::int)
    WHERE (completed_items = 0 OR completed_items IS NULL)
      AND parameters->>'count' IS NOT NULL
      AND (parameters->>'count')::int > 0
      AND status = 'completed';
    """
    try:
        with get_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                updated = cur.rowcount
                conn.commit()
                return updated
    except Exception as e:
        print(f"Error backfilling historical task counts: {e}")
        return 0
