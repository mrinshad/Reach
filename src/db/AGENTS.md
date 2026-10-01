# Reach Database Layer — Agent Navigation Guide (src/db/)

This directory contains the PostgreSQL database schema, connection pooling, and data access logic for the Reach platform.

## Module Routing Map

| Module | Responsibilities | Key Functions |
|---|---|---|
| [`connection.py`](file:///Users/apple/Byten/linkedInScrapper/src/db/connection.py) | Connection pool, env parsing, table schemas (`posts`, `settings`), and migrations (`alter_sql`) | `get_connection()`, `init_db()` |
| [`settings.py`](file:///Users/apple/Byten/linkedInScrapper/src/db/settings.py) | Dynamic key-value configuration (`chatgpt_url`, `search_query`, `headless_mode`) | `get_setting()`, `set_setting()`, `get_all_settings()`, `seed_default_settings()` |
| [`posts.py`](file:///Users/apple/Byten/linkedInScrapper/src/db/posts.py) | Post ingestion, deduplication, spam detection, status transitions, and pagination | `upsert_post()`, `get_posts_paginated()`, `get_post_by_id()`, `update_post_status()`, `update_post_email()`, `mark_post_sent()`, `revert_post_to_draft()` |
| [`analytics.py`](file:///Users/apple/Byten/linkedInScrapper/src/db/analytics.py) | KPI aggregation, application velocity timeline, conversion stages, and rejection breakdown | `get_stats()`, `get_analytics_summary()`, `get_rejection_reasons_with_counts()`, `get_distinct_locations()` |
| [`activity_logs.py`](file:///Users/apple/Byten/linkedInScrapper/src/db/activity_logs.py) | Automated background task and crawl execution history persistence | `create_activity_log()`, `update_activity_log_progress()`, `finish_activity_log()`, `get_activity_logs()`, `get_activity_log_by_id()` |
| [`__init__.py`](file:///Users/apple/Byten/linkedInScrapper/src/db/__init__.py) | Package manifest re-exporting all functions for 100% backward-compatible imports | Re-exports all symbols |

## Key Database Models & Tables

### `activity_logs` Table
- `id` (`VARCHAR(64) PRIMARY KEY`): Unique task/run identifier.
- `task_type` (`VARCHAR(64)`): `crawler`, `easy_apply_scraper`, `chatgpt_batch`, `infopark`, `gmail_send`.
- `task_name` (`VARCHAR(256)`): Human-readable activity title.
- `short_name` (`VARCHAR(128)`): Condensed label for UI cards.
- `parameters` (`JSONB`): What was involved (query, location, time window, max jobs, count).
- `status` (`VARCHAR(32)`): `'running'`, `'completed'`, `'error'`, `'stopped'`.
- `result_summary` (`TEXT`): Plain-English outcome message.
- `crawl_stats` (`JSONB`): Structured count metrics.
- `logs` (`TEXT[]`): Real-time terminal console output lines for this run.
- `started_at`, `finished_at`, `duration_seconds`: Performance and execution timing.

### `posts` Table
- `id` (`VARCHAR(64) PRIMARY KEY`): Deterministic SHA-256 hash of URL or content signature.
- `post_url` (`VARCHAR(512) UNIQUE`): Source URL from LinkedIn, Infopark, or manual input.
- `author_name`, `author_headline`, `author_profile`: Recruiter/poster details.
- `full_text`: Raw job description text.
- `contact_emails` (`TEXT[]`): Recruiter contact emails detected during crawling.
- `external_links` (`TEXT[]`): Application links, form URLs, and portal links.
- `min_experience`, `max_experience`, `is_fresher`, `seniority_level`: Parsed experience metrics.
- `category` (`VARCHAR(64)`): `'EMAIL_OUTREACH'` (direct email) vs `'DRAFT_PORTAL'` (portal link).
- `status` (`VARCHAR(64)`): `'DISCOVERED'`, `'SELECTED'`, `'EMAIL_GENERATED'`, `'SENT'`, `'REJECTED'`.
- `rejection_reason`: Pre-screen or manual cancellation reason (sanitized and truncated).
- `is_potential_spam`, `potential_spam_reason`: Anti-spam intelligence flags.
- `location`: Extracted geographic location (e.g. Bangalore, Kochi, Remote).

### `settings` Table
- `key` (`VARCHAR(128) PRIMARY KEY`): Configuration key name.
- `value` (`TEXT`): Serialized configuration value.

## Agent Guidelines
1. **Never use `db push`**: All table adjustments must go through `alter_sql` in `connection.py`.
2. **Backward Compatibility**: Always import via `from src.db import ...`.
3. **Database-First Operations**: Keep sorting, filtering, and pagination backend-first.
