# Reach Services & Automation Agent Guide (`src/services/`)

This directory contains the background task queue manager, Playwright browser automation engines, AI text generation orchestrators, and system diagnostic probes.

---

## Service Architecture & Responsibilities

| Service Module | Primary Responsibilities | Key Functions / Classes | Core Dependencies |
|---|---|---|---|
| [`automation_tasks.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/automation_tasks.py) | Sequential FIFO task queue engine, worker thread lifecycle, active cancellation, log capture, crawler registry dispatch. | `TaskManager`, `Task`, `task_manager`, `run_scraper`, `generate_email_for_post`, `send_email_for_post`, `open_gmail_compose` | `src/db/`, `firefox_connector.py`, `chatgpt_service.py`, `gmail_service.py` |
| [`chatgpt_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/chatgpt_service.py) | Web ChatGPT Custom GPT orchestrator. Injects JD into ProseMirror editor with humanized keystrokes, listens for streaming completion, extracts cold outreach drafts or unsuitability reasons. | `navigate_to_conversation`, `send_jd_and_get_email`, `parse_email_response`, `clean_and_truncate_reason` | Playwright, `src/db/settings.py` |
| [`gmail_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/gmail_service.py) | Gmail web interface automation. Fills recipient, subject, body, and automatically attaches resume PDF from local settings. Supports interactive compose or direct dispatch. | `navigate_to_gmail`, `fill_compose_dialog`, `open_gmail_compose_and_leave_open`, `send_gmail_directly` | Playwright, `src/db/settings.py` |
| [`firefox_connector.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/firefox_connector.py) | Playwright Firefox persistent context lifecycle manager. Handles profile locking, lock file cleanup, headless/headed switching, and clean termination. | `launch_firefox_context`, `close_firefox_context`, `get_firefox_profile_dir`, `is_firefox_running`, `kill_firefox_process` | Playwright, `src/db/settings.py` |
| [`chrome_connector.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/chrome_connector.py) | Fallback Chrome CDP (Chrome DevTools Protocol) browser connector. | `connect_to_chrome`, `launch_chrome_with_cdp`, `is_chrome_running` | Playwright CDP |
| [`health_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/health_service.py) | Live diagnostic probe checking PostgreSQL connectivity, Firefox profile existence, and active session cookies (LinkedIn, ChatGPT, Gmail). | `check_database_health`, `check_firefox_session_cookies`, `check_system_health`, `get_health_summary` | `src/db/connection.py`, `config.py` |
| [`experience_extractor.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/experience_extractor.py) | Regex and rule-based parser extracting years of experience, experience ranges, and fresher tags from job descriptions. | `extract_experience` | `re` |

---

## Agent Directives for Services

1. **FIFO Queue Preservation**: Never run browser automation jobs directly outside of `task_manager.add_task(...)`. Concurrent Playwright sessions colliding on the same Firefox profile directory will corrupt locks and fail.
2. **Humanization Delays**: Maintain randomized pacing delays (2.0s–4.5s) between actions in `chatgpt_service.py` and `gmail_service.py`. Do not eliminate delays.
3. **90s Inactivity Watchdog**: Respect the watchdog loop in `automation_tasks.py`. If a task hangs due to an unexpected UI block or CAPTCHA, it must release locks gracefully.
4. **No Plaintext Passwords**: Authentication relies strictly on persistent browser profiles (`~/.playwright_firefox_profile`). Never store or prompt for user passwords.
