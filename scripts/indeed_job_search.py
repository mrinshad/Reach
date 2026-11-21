#!/usr/bin/env python3
"""
Indeed Job Search & Indeed Apply Crawler CLI
(scripts/indeed_job_search.py)

Standalone runner and subprocess worker for autonomous Indeed Job Search with
'Easily apply' (DSQF7) filtering, in-stream recruiter email harvesting from JDs,
and database ingestion into category='INDEED_APPLY'.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.indeed_apply_service import run_indeed_apply_crawler
from src.db.settings import get_setting
from src.config import load_config


def parse_args():
    parser = argparse.ArgumentParser(description="Indeed Job Crawler & Apply Collector")
    parser.add_argument("--query", "-q", default=None, help="Job title or keywords")
    parser.add_argument("--location", "-l", default=None, help="Target location")
    parser.add_argument("--time-filter", "-t", default=None, help="Time filter: 24h, week, month, all")
    parser.add_argument("--max-jobs", "-m", type=int, default=None, help="Max jobs to process")
    parser.add_argument("--cycles", "-c", type=int, default=None, help="Number of scroll/pagination cycles")
    parser.add_argument("--pacing", "-p", default="safe", choices=["safe", "slow", "standard"], help="Delay between job submissions")
    parser.add_argument("--auto-apply", action="store_true", default=False, help="Automatically submit applications during crawl")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()

    raw_query = args.query if args.query is not None else os.environ.get("SCRAPER_SEARCH_QUERY")
    query = (raw_query or "").strip()

    location = (
        args.location
        or os.environ.get("SCRAPER_LOCATION")
        or get_setting("search_location", "India")
        or "India"
    ).strip()

    time_filter = (
        args.time_filter
        or os.environ.get("SCRAPER_TIME_FILTER")
        or "24h"
    ).strip()

    limit_str = os.environ.get("SCRAPER_LIMIT")
    cycles_env = os.environ.get("SCRAPER_CYCLES")

    try:
        max_jobs = args.max_jobs or (int(limit_str) if limit_str else 50)
    except (ValueError, TypeError):
        max_jobs = 50

    try:
        cycles = args.cycles or (int(cycles_env) if cycles_env else 8)
    except (ValueError, TypeError):
        cycles = 8

    pacing = args.pacing or os.environ.get("SCRAPER_PACING") or "safe"

    print("=" * 60)
    print("Indeed Crawler Subprocess Initialized (Job Collection Mode)")
    print("=" * 60)

    summary = run_indeed_apply_crawler(
        keywords=query,
        location=location,
        time_filter=time_filter,
        cycles=cycles,
        max_jobs=max_jobs,
        pacing=pacing,
        auto_apply=args.auto_apply,
    )
    print(f"Result: {summary}")


if __name__ == "__main__":
    main()
