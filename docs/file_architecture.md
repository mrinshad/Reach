# Project File Architecture & Reference Guide

This document describes the exact role, inputs, outputs, and status of every file in the project. It serves as the single source of truth for the codebase architecture and will be continuously maintained and updated as new modules are developed.

---

## High-Level Vision & Data Flow

```text
[ LinkedIn Global Posts Search ]
            │ (Playwright Firefox - Headed, Human Pacing)
            ▼
[ Raw Post Extraction & Parsing ]
            │
            ├── Experience Extractor (Min/Max YOE, Fresher, Seniority)
            ├── Email & URL Extraction (Direct recruiters vs External portals)
            └── Job-Seeker & Comment-Bait Filtering
            │
            ▼
[ PostgreSQL Database (Storage & State Management) ]
   - Table: posts (URL, Author, Text, Experience, Emails, Status)
            │
            ▼
[ Next.js Dashboard UI (Future Frontend) ]
   - Review and filter extracted posts (by Experience, Date, Tech)
   - Select posts for outreach
            │
            ▼
[ ChatGPT Service (Playwright - Headed) ]
   - Send selected JD to dedicated custom GPT conversation
   - Extract tailored cold outreach email
            │
            ▼
[ Review & Human Approval ]
   - Review generated email & subject on the UI
   - One-click send with resume attached via Gmail/browser
```

---

## Detailed File Registry

### 1. Core Source Modules (`src/`)

| File Path | Description & Core Responsibility | Key Functions / Classes | Inputs & Outputs | Status |
| :--- | :--- | :--- | :--- | :---: |
| [`src/firefox_connector.py`](file:///Users/apple/Byten/linkedInScrapper/src/firefox_connector.py) | Manages Playwright Firefox persistent browser context (`~/.playwright_firefox_profile`). Preserves login sessions for LinkedIn and ChatGPT across runs, terminates orphaned/stale processes using the profile directory, and prevents profile collision errors. | `launch_firefox_context`, `extract_desktop_cookies`, `cleanup_stale_profile_locks` | **Input:** User profile dir, headless flag.<br>**Output:** Active Playwright `BrowserContext`. | **Active & Verified** |
| [`src/chrome_connector.py`](file:///Users/apple/Byten/linkedInScrapper/src/chrome_connector.py) | Connects to an existing Google Chrome instance over Chrome DevTools Protocol (CDP port 9222). Note: Cloudflare Turnstile actively blocks ChatGPT under Chrome CDP, so Firefox persistent context is preferred. | `connect_to_chrome`, `verify_chrome_connection` | **Input:** CDP endpoint URL.<br>**Output:** Chromium `BrowserContext`. | **Reference / Fallback** |
| [`src/experience_extractor.py`](file:///Users/apple/Byten/linkedInScrapper/src/experience_extractor.py) | NLP and Regex parser for extracting Years of Experience (YOE) requirements from unstructured LinkedIn post text. Handles ranges, plus patterns, freshers, and seniority categorization. | `extract_experience` | **Input:** Raw post text.<br>**Output:** Dict: `min_years`, `max_years`, `raw_text`, `is_fresher`, `seniority_level`. | **Active & Verified** |
| [`src/db.py`](file:///Users/apple/Byten/linkedInScrapper/src/db.py) | PostgreSQL database client for local database `linkedin_scrapper`. Manages `posts` and `settings` tables. Provides table initialization, deduplication/upsert, status updates, dynamic DB URL fallback, spam detection queries, key-value configuration (`get_setting`, `set_setting`, `get_all_settings`, `seed_default_settings`), and reverting sent posts (`revert_post_to_draft`). | `init_db`, `upsert_post`, `get_posts`, `update_post_status`, `revert_post_to_draft`, `save_chatgpt_response`, `get_setting`, `set_setting`, `get_all_settings`, `seed_default_settings` | **Input:** Post dictionaries, configuration key-values.<br>**Output:** Persisted records in PostgreSQL. | **Active & Verified** |
| [`src/chatgpt_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/chatgpt_service.py) | Modular service to send a job description to the dedicated ChatGPT custom GPT conversation, wait for streaming completion, and extract the generated outreach email. Loads custom GPT URL dynamically from DB `settings` table. | `navigate_to_conversation`, `send_jd_and_get_email`, `parse_email_response`, `get_default_chatgpt_url` | **Input:** Raw JD text, DB-backed URL.<br>**Output:** Generated cold outreach email tuple (Subject, Body). | **Active & Verified** |
| [`src/gmail_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/gmail_service.py) | Gmail automation service to open compose modal, populate recipient, subject, body, attach resume PDF, and stop for human approval. | `navigate_to_gmail`, `populate_email_draft` | **Input:** Recipient, subject, body, attachment path.<br>**Output:** Populated compose window in Gmail. | **Active & Verified** |
| [`src/health_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/health_service.py) | Inspects persistent Firefox session cookies and PostgreSQL connectivity to provide live health indicators for LinkedIn, ChatGPT, Gmail, and DB. | `check_firefox_session_cookies`, `check_database_health`, `get_system_health` | **Input:** Profile cookies.<br>**Output:** Health status JSON. | **Active & Verified** |
| [`src/app.py`](file:///Users/apple/Byten/linkedInScrapper/src/app.py) | FastAPI backend serving REST API endpoints (`/api/posts`, `/api/posts/{id}/revert`, `/api/posts/{id}/spam`, `/api/scrapers`, `/api/stats`, `/api/health`, `/api/resume/upload`, `/api/generate-batch`, `/api/open-gmail`, `/api/scrape`, `/api/tasks/status`, `/api/settings`) and static dashboard assets. | `serve_index`, `api_get_stats`, `api_get_health`, `api_revert_post`, `api_mark_spam`, `api_get_scrapers`, `api_upload_resume`, `api_get_posts` | **Input:** HTTP Requests from frontend.<br>**Output:** JSON responses & static HTML. | **Active & Verified** |
| [`src/automation_tasks.py`](file:///Users/apple/Byten/linkedInScrapper/src/automation_tasks.py) | Asynchronous task manager running long-running Playwright jobs with a unified extensible `SCRAPER_REGISTRY` (LinkedIn Posts, Infopark, etc.), 90s inactivity timeout enforcement, ChatGPT batch generation, and Gmail draft preparation in strictly headed Firefox (`headless=False`) with live progress and logs. | `TaskManager`, `SCRAPER_REGISTRY`, `get_registered_scrapers`, `run_scraper_by_source`, `run_chatgpt_batch`, `run_open_gmail_draft` | **Input:** Scraper source ID, post IDs, parameters.<br>**Output:** Real-time task logs & browser automation. | **Active & Verified** |
| [`src/config.py`](file:///Users/apple/Byten/linkedInScrapper/src/config.py) | Application configuration manager handling global resume path, search queries, custom GPT URLs, and human pacing limits. Automatically synchronizes `chatgpt_url` and `search_query` bidirectionally with PostgreSQL `settings` table. | `load_config`, `save_config` | **Input:** `config.json` & PostgreSQL `settings`.<br>**Output:** Config dictionary. | **Active & Verified** |
| [`src/static/index.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/index.html) | Modern, minimalist "Reach" dashboard. Features live session health indicators, unified scraper dropdown selector, 3-stage lifecycle tabs (Discovered, Ready to Send, Others), 1-click spam buttons, side-by-side draft editor, spacious post details modal with rejection reason banner, and resume upload. | UI HTML structure | **Input:** User browser interactions.<br>**Output:** Rendered UI. | **Active & Verified** |
| [`src/static/style.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/style.css) | Clean design tokens, Space Grotesk typography, crawler source selector styling, 1-click quick action buttons (`.btn-spam-quick`, `.btn-cancel-quick`), spacious modal padding, stacked expandable snackbar cards, and responsive dark-mode styling. | CSS styling rules | **Output:** Visual presentation. | **Active & Verified** |
| [`src/static/app.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/app.js) | Frontend client application. Unified crawler controller (`#crawlerSourceSelect`), 3-stage tab manager, stacked expandable snackbar notification engine (`showSnackbar`), 1-click spam reporting (`markPostSpam`), quick cancellation dialog with preset suggestions, post restoration, and live task progress. | `initCrawlerSourceSelect`, `triggerUnifiedCrawl`, `markPostSpam`, `promptCancelPost`, `restorePostFromModal`, `openPostModal`, `fetchHealth` | **Input:** User clicks, REST responses.<br>**Output:** Dynamic DOM updates. | **Active & Verified** |

---

### 2. Application Entry Point & Scripts (`/` and `scripts/`)

| File Path | Description & Core Responsibility | Inputs & Outputs | Status |
| :--- | :--- | :--- | :---: |
| [`run.py`](file:///Users/apple/Byten/linkedInScrapper/run.py) | Main entry point script. Starts the FastAPI server on `http://localhost:8000` via Uvicorn. | **Command:** `python3 run.py`.<br>**Output:** Running web application. | **Active & Verified** |
| [`scripts/prepare_gmail_draft.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/prepare_gmail_draft.py) | Retrieves generated email from PostgreSQL, launches headed Gmail, populates draft with resume attached, and stops for mandatory human review before sending. | **Input:** Post from PostgreSQL (`status='EMAIL_GENERATED'`), resume path.<br>**Output:** Ready-to-send draft in Gmail. | **Active & Verified** |
| [`scripts/process_posts_with_chatgpt.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/process_posts_with_chatgpt.py) | Batch processor that queries pending posts from PostgreSQL, sequentially feeds them into ChatGPT in headed Firefox with human delays, and saves generated email drafts back to the database. | **Input:** Pending posts in PostgreSQL (`--limit N` or `--all`).<br>**Output:** Updated database records with `status='EMAIL_GENERATED'`. | **Active & Verified** |
| [`scripts/linkedin_posts_search.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/linkedin_posts_search.py) | The primary LinkedIn scraper script. Navigates to LinkedIn Global Search -> Posts for the past 24 hours in headed mode (`headless=False`). Simulates human scrolling, extracts posts, detects contact emails, parses experience, categorizes into Email Outreach vs Drafts, and saves directly to PostgreSQL. | **Input:** Search query (`"Full stack developer "`).<br>**Output:** Records inserted/updated in PostgreSQL. | **Active & Verified** |
| [`scripts/test_chatgpt_conversation.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/test_chatgpt_conversation.py) | Verified test script that opens the user's specific custom GPT conversation (`Job Application Follow-up`), types a sample JD into the ProseMirror editor, waits for streaming to complete, and captures the email response. | **Input:** Sample JD text.<br>**Output:** Extracted outreach email saved to artifact. | **Verified Working** |
| [`scripts/linkedin_job_search.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/linkedin_job_search.py) | Initial exploration script that navigated to LinkedIn's formal `/jobs/search/` section. Replaced by `linkedin_posts_search.py` because the user explicitly requested job opportunities posted as personal feed posts. | **Input:** Keywords.<br>**Output:** Jobs section listings. | **Deprecated** |
| [`scripts/test_firefox_chatgpt.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/test_firefox_chatgpt.py) | Minimal diagnostic script to test navigating to ChatGPT under Firefox persistent context and verifying session cookies. | **Input:** None.<br>**Output:** Console status & page title. | **Utility** |
| [`scripts/test_cdp_connection.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/test_cdp_connection.py) | Initial diagnostic script to test connecting to Chrome over port 9222. | **Input:** CDP endpoint.<br>**Output:** Open tab list. | **Utility** |

---

### 3. Documentation (`docs/`)

| File Path | Description | Contents | Status |
| :--- | :--- | :--- | :---: |
| [`docs/file_architecture.md`](file:///Users/apple/Byten/linkedInScrapper/docs/file_architecture.md) | **This file.** Comprehensive registry of all files, their purpose, architecture, and evolution. | File table, data flow diagram, and architectural roadmap. | **Maintained Live** |
| [`docs/workflows.md`](file:///Users/apple/Byten/linkedInScrapper/docs/workflows.md) | Technical log of all discovered workflows, URL parameters, and DOM selectors. | Chrome CDP limitations, Firefox persistent context setup, ChatGPT ProseMirror selectors, LinkedIn `LazyColumn` DOM elements. | **Maintained Live** |
| [`docs/implementation_plan.md`](file:///Users/apple/Byten/linkedInScrapper/docs/implementation_plan.md) | Implementation roadmap and account safety guidelines (human pacing, rate-limiting, CAPTCHA handling). | Step-by-step development sequence, account risk analysis. | **Maintained Live** |

---

### 4. Database & Configuration

| File Path | Description | Status |
| :--- | :--- | :---: |
| `requirements.txt` | Python dependency specifications (`playwright`, `psycopg2-binary`, `fastapi`, `uvicorn`). | **Active** |
| `config.json` | JSON store for user settings (global resume path, search query, pacing delays). | **Active** |
