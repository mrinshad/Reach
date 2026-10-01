"""
Reach — Real-Time Dynamic Task Duration & ETA Estimation Service.
(src/services/timing_service.py)

Calculates estimated time to complete (ETA) for automation tasks using:
1. Continuous learning from historical execution data in PostgreSQL activity_logs.
2. Dynamic live progress rates as batch items complete in real-time.
3. Pre-calibrated baseline fallbacks for new or low-sample task types.
"""

import time
from typing import Any, Dict, List, Optional
from src.db.activity_logs import get_task_timing_benchmarks

# Pre-calibrated default baselines (seconds per unit or total seconds)
DEFAULT_TASK_BASELINES: Dict[str, float] = {
    "easy_apply_crawler": 128.0,
    "linkedin_posts_crawler": 490.0,
    "infopark_crawler": 30.0,
    "crawler": 180.0,
    "chatgpt": 35.0,               # ~35s per generated email draft
    "chatgpt_batch": 35.0,
    "gmail_send_batch": 24.0,       # ~24s per dispatched Gmail application
    "gmail_send": 20.0,
    "easy_apply": 35.0,             # ~35s per Easy Apply submission
    "easy_apply_batch": 35.0,
    "easy_apply_scraper": 128.0,
    "service_login": 120.0,
    "default": 45.0,
}

# In-memory benchmark cache with 60-second TTL
_BENCHMARK_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_CACHE_FETCH: float = 0.0
_CACHE_TTL_SECONDS: float = 60.0


def get_cached_benchmarks(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """Return in-memory cached timing benchmarks, refreshed every 60 seconds from PostgreSQL."""
    global _BENCHMARK_CACHE, _LAST_CACHE_FETCH
    now = time.time()
    if force_refresh or (now - _LAST_CACHE_FETCH > _CACHE_TTL_SECONDS) or not _BENCHMARK_CACHE:
        try:
            _BENCHMARK_CACHE = get_task_timing_benchmarks()
            _LAST_CACHE_FETCH = now
        except Exception as e:
            print(f"Error refreshing timing benchmarks cache: {e}")
            if not _BENCHMARK_CACHE:
                _BENCHMARK_CACHE = {}
    return _BENCHMARK_CACHE


def resolve_task_benchmark_key(task_type: str, task_name: str = "", metadata: Optional[Dict[str, Any]] = None) -> str:
    """Classify task into specific benchmark bucket based on type, name, and parameters."""
    t_type = (task_type or "").lower().strip()
    t_name = (task_name or "").lower().strip()
    meta = metadata or {}

    if ("easy" in t_name and "apply" in t_name) or "easy_apply" in t_type:
        if any(w in t_name for w in ("crawl", "scraper", "search", "bot")) or t_type in ("crawler", "scraper"):
            return "easy_apply_crawler"
    if "infopark" in t_name or "infopark" in t_type:
        return "infopark_crawler"
    if "linkedin" in t_name and ("scraper" in t_name or "posts" in t_name or "crawl" in t_name):
        return "linkedin_posts_crawler"

    if t_type in ("crawler", "scraper"):
        source = str(meta.get("source", "")).lower()
        if "easy" in source or "job" in source:
            return "easy_apply_crawler"
        if "infopark" in source:
            return "infopark_crawler"
        return "linkedin_posts_crawler"

    if "chatgpt" in t_type or "chatgpt" in t_name or "draft" in t_name:
        return "chatgpt"

    if "gmail" in t_type or "gmail" in t_name or "send" in t_name:
        return "gmail_send_batch"

    if "easy_apply" in t_type or "easy apply" in t_name:
        return "easy_apply_batch"

    if "login" in t_type or "login" in t_name:
        return "service_login"

    return t_type or "default"


def format_time_estimate(remaining_seconds: float) -> str:
    """Format remaining seconds into clean, human-friendly ETA text."""
    if remaining_seconds <= 10.0:
        return "Finalizing..."
    if remaining_seconds < 60.0:
        return f"~{max(5, int(round(remaining_seconds)))}s remaining"

    total_secs = int(round(remaining_seconds))
    if total_secs < 3600:
        mins = total_secs // 60
        secs = total_secs % 60
        if secs >= 10:
            return f"~{mins}m {secs}s remaining"
        return f"~{mins}m remaining"

    hrs = total_secs // 3600
    mins = (total_secs % 3600) // 60
    if mins > 0:
        return f"~{hrs}h {mins}m remaining"
    return f"~{hrs}h remaining"


def format_duration_short(seconds: float) -> str:
    """Format duration into concise representation for queue chips (e.g. '~1m 30s')."""
    total = max(5, int(round(seconds)))
    if total < 60:
        return f"~{total}s"
    if total < 3600:
        mins = total // 60
        secs = total % 60
        return f"~{mins}m {secs}s" if secs >= 10 else f"~{mins}m"
    hrs = total // 3600
    mins = (total % 3600) // 60
    return f"~{hrs}h {mins}m" if mins > 0 else f"~{hrs}h"


def compute_task_timing_estimate(
    task_type: str,
    task_name: str = "",
    total_items: int = 1,
    completed_items: int = 0,
    started_at: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute real-time dynamic duration and ETA estimates for an automation task.
    Blends real-time live performance with historical PostgreSQL benchmarks.
    """
    now = time.time()
    elapsed = max(0.0, now - started_at) if started_at else 0.0

    key = resolve_task_benchmark_key(task_type, task_name, metadata)
    benchmarks = get_cached_benchmarks()
    bench = benchmarks.get(key) or benchmarks.get(task_type) or {}

    sample_count = int(bench.get("sample_count", 0))
    hist_per_item = float(bench.get("avg_per_item", 0.0))
    hist_total_duration = float(bench.get("avg_duration", 0.0))

    fallback_rate = DEFAULT_TASK_BASELINES.get(key, DEFAULT_TASK_BASELINES.get(task_type, DEFAULT_TASK_BASELINES["default"]))
    benchmark_rate = hist_per_item if (sample_count >= 1 and hist_per_item > 0) else fallback_rate
    benchmark_total = hist_total_duration if (sample_count >= 1 and hist_total_duration > 0) else fallback_rate

    effective_total = max(1, total_items)
    effective_done = max(0, completed_items)
    remaining_items = max(0, effective_total - effective_done)

    confidence = "baseline"
    if sample_count >= 1:
        confidence = "historical"

    # Multi-item batch tasks
    if effective_total > 1 or effective_done > 0:
        if effective_done > 0 and elapsed > 0:
            live_rate = elapsed / effective_done
            # Dynamic weighting: when 1 item done, 50% live + 50% benchmark; when >= 2 items, 85% live
            if effective_done == 1:
                blended_rate = (0.50 * live_rate) + (0.50 * benchmark_rate)
            else:
                blended_rate = (0.85 * live_rate) + (0.15 * benchmark_rate)

            confidence = "live_adaptive"
            estimated_remaining = remaining_items * blended_rate
            effective_unit_rate = blended_rate
        else:
            effective_unit_rate = benchmark_rate
            estimated_total_initial = effective_total * benchmark_rate
            estimated_remaining = max(5.0, estimated_total_initial - elapsed)

        estimated_total = elapsed + estimated_remaining
    else:
        # Single unit or continuous crawl tasks (e.g. search scraper)
        expected_duration = benchmark_total
        effective_unit_rate = expected_duration

        if elapsed < expected_duration:
            estimated_remaining = max(5.0, expected_duration - elapsed)
            estimated_total = expected_duration
        else:
            # Running longer than historical average: gracefully signal final stages
            estimated_remaining = 8.0
            estimated_total = elapsed + 8.0

    eta_display = format_time_estimate(estimated_remaining)
    eta_short = format_duration_short(estimated_remaining)

    return {
        "elapsed_seconds": round(elapsed, 1),
        "estimated_remaining_seconds": round(estimated_remaining, 1),
        "estimated_total_seconds": round(estimated_total, 1),
        "eta_display": eta_display,
        "eta_short": eta_short,
        "confidence": confidence,
        "unit_rate_seconds": round(effective_unit_rate, 1),
        "sample_count": sample_count,
        "benchmark_key": key,
    }


def estimate_queued_task(item: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate total duration for a pending task in the queue."""
    t_type = item.get("type", "")
    t_name = item.get("name", "")
    meta = item.get("metadata") or {}

    count = int(meta.get("count") or meta.get("max_jobs") or meta.get("total_items") or 1)
    key = resolve_task_benchmark_key(t_type, t_name, meta)

    benchmarks = get_cached_benchmarks()
    bench = benchmarks.get(key) or benchmarks.get(t_type) or {}
    sample_count = int(bench.get("sample_count", 0))

    fallback_rate = DEFAULT_TASK_BASELINES.get(key, DEFAULT_TASK_BASELINES.get(t_type, DEFAULT_TASK_BASELINES["default"]))
    hist_rate = float(bench.get("avg_per_item", 0.0))
    rate = hist_rate if (sample_count >= 1 and hist_rate > 0) else fallback_rate

    if count > 1:
        est_duration = count * rate
    else:
        hist_total = float(bench.get("avg_duration", 0.0))
        est_duration = hist_total if (sample_count >= 1 and hist_total > 0) else fallback_rate

    return {
        "estimated_duration_seconds": round(est_duration, 1),
        "eta_display": f"Est. {format_duration_short(est_duration)}",
        "sample_count": sample_count,
        "benchmark_key": key,
    }
