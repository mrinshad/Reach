"""
PostgreSQL Database Package.
Re-exports all connection, posts, settings, and analytics functions.
"""

from src.db.connection import (
    DEFAULT_DB_URL,
    get_connection,
    get_db_connection,
    init_db,
)

from src.db.settings import (
    get_setting,
    set_setting,
    get_all_settings,
    seed_default_settings,
)

from src.db.posts import (
    PUBLIC_EMAIL_DOMAINS,
    check_email_spam,
    get_existing_post_identifiers,
    is_post_already_saved,
    upsert_post,
    get_posts,
    get_posts_paginated,
    get_post_by_id,
    update_post_status,
    update_post_email,
    mark_post_sent,
    mark_post_spam,
    revert_post_to_draft,
    revert_posts_batch,
    reject_posts_batch,
    move_post_to_review,
    save_chatgpt_response,
    cleanup_stuck_generating_posts,
    get_pending_email_posts,
    get_recently_sent_recipients,
    SEND_COOLDOWN_DAYS,
)

from src.db.analytics import (
    get_rejection_reasons_with_counts,
    get_distinct_rejection_reasons,
    get_distinct_locations,
    get_stats,
    get_analytics_summary,
)

from src.db.activity_logs import (
    create_activity_log,
    update_activity_log_progress,
    finish_activity_log,
    get_activity_logs,
    get_activity_log_by_id,
    clear_activity_logs,
)

__all__ = [
    "DEFAULT_DB_URL",
    "get_connection",
    "get_db_connection",
    "init_db",
    "get_setting",
    "set_setting",
    "get_all_settings",
    "seed_default_settings",
    "PUBLIC_EMAIL_DOMAINS",
    "check_email_spam",
    "get_existing_post_identifiers",
    "is_post_already_saved",
    "upsert_post",
    "get_posts",
    "get_posts_paginated",
    "get_post_by_id",
    "update_post_status",
    "update_post_email",
    "mark_post_sent",
    "mark_post_spam",
    "revert_post_to_draft",
    "revert_posts_batch",
    "reject_posts_batch",
    "move_post_to_review",
    "save_chatgpt_response",
    "cleanup_stuck_generating_posts",
    "get_pending_email_posts",
    "get_rejection_reasons_with_counts",
    "get_distinct_rejection_reasons",
    "get_distinct_locations",
    "get_stats",
    "get_analytics_summary",
    "create_activity_log",
    "update_activity_log_progress",
    "finish_activity_log",
    "get_activity_logs",
    "get_activity_log_by_id",
    "clear_activity_logs",
]
