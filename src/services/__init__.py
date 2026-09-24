"""
Reach Services Package
Exports background tasks, Playwright connectors, AI generators, and health diagnostics.
"""

from .automation_tasks import (
    task_manager,
    TaskManager,
    SCRAPER_REGISTRY,
    run_chatgpt_batch,
    run_open_gmail_draft,
    run_send_single_draft,
    run_send_batch_drafts,
    run_scraper_subprocess_with_timeout,
    run_infopark_scraper,
    run_linkedin_scraper,
    get_registered_scrapers,
    run_scraper_by_source,
    run_interactive_login,
)

from .chatgpt_service import (
    navigate_to_conversation,
    send_jd_and_get_email,
    parse_email_response,
    extract_unsuitable_reason,
    clean_and_truncate_reason,
    get_default_chatgpt_url,
)

from .gmail_service import (
    navigate_to_gmail,
    populate_email_draft,
    send_email_directly,
    GMAIL_INBOX_URL,
)

from .firefox_connector import (
    DEFAULT_PROFILE_DIR,
    DESKTOP_FIREFOX_PROFILES_DIR,
    get_default_firefox_profile_dir,
    find_desktop_firefox_profile,
    extract_desktop_cookies,
    cleanup_stale_profile_locks,
    launch_firefox_context,
    open_or_get_tab,
)

from .chrome_connector import (
    DEFAULT_CDP_PORT,
    CDP_DATA_DIR,
    is_cdp_available,
    is_chrome_running,
    prepare_cdp_profile,
    launch_chrome_with_cdp,
    connect_to_chrome,
    list_open_tabs,
)

from .health_service import (
    check_database_health,
    check_firefox_session_cookies,
    get_system_health,
)

from .experience_extractor import (
    extract_experience,
)

__all__ = [
    "task_manager",
    "TaskManager",
    "SCRAPER_REGISTRY",
    "run_chatgpt_batch",
    "run_open_gmail_draft",
    "run_send_single_draft",
    "run_send_batch_drafts",
    "run_scraper_subprocess_with_timeout",
    "run_infopark_scraper",
    "run_linkedin_scraper",
    "get_registered_scrapers",
    "run_scraper_by_source",
    "navigate_to_conversation",
    "send_jd_and_get_email",
    "parse_email_response",
    "extract_unsuitable_reason",
    "clean_and_truncate_reason",
    "get_default_chatgpt_url",
    "navigate_to_gmail",
    "populate_email_draft",
    "send_email_directly",
    "GMAIL_INBOX_URL",
    "DEFAULT_PROFILE_DIR",
    "DESKTOP_FIREFOX_PROFILES_DIR",
    "get_default_firefox_profile_dir",
    "find_desktop_firefox_profile",
    "extract_desktop_cookies",
    "cleanup_stale_profile_locks",
    "launch_firefox_context",
    "open_or_get_tab",
    "DEFAULT_CDP_PORT",
    "CDP_DATA_DIR",
    "is_cdp_available",
    "is_chrome_running",
    "prepare_cdp_profile",
    "launch_chrome_with_cdp",
    "connect_to_chrome",
    "list_open_tabs",
    "check_database_health",
    "check_firefox_session_cookies",
    "get_system_health",
    "extract_experience",
]
