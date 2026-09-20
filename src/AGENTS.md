# Backend & Automation Architecture Guide (`src/AGENTS.md`)

This guide directs AI agents working on Reach's backend, data operations, and automation services.

## Module Directory

### 1. [`app.py`](file:///Users/apple/Byten/linkedInScrapper/src/app.py)
- **Role**: FastAPI application, REST endpoints, static asset mounting, dynamic template assembly.
- **Key Functions / Routes**:
  - `serve_index()`: Assembles `src/static/index_layout.html` with `src/static/partials/*.html` on the fly.
  - `/api/stats/summary`: Returns KPI totals, pending counts, and sidebar badge numbers.
  - `/api/posts`: Paginated, filtered discovered job posts.
  - `/api/review/queue`: Posts awaiting draft generation or human review.
  - `POST /api/generate-email/{post_id}`: Generates an AI email draft (supports `?force=true` override).
  - `POST /api/approve/{post_id}`: Approves and queues email sending.
  - `POST /api/crawl`: Launches Playwright background job scraping task.
  - `/api/settings/headless`: Gets/sets headless browser mode in `config.json`.
  - `/api/health`: Probes LinkedIn, ChatGPT, Gmail, and DB connectivity.

### 2. [`automation_tasks.py`](file:///Users/apple/Byten/linkedInScrapper/src/automation_tasks.py)
- **Role**: Background task manager, Playwright browser workers, batch processing.
- **Key Functions**:
  - `TaskManager`: Thread-safe active task tracking, logging stream, and cancellation.
  - `run_crawler_task(source, location)`: Scrapes LinkedIn/Infopark posts.
  - `run_email_generation_task(post_ids, force)`: Batch AI email generation via ChatGPT service.
  - `run_batch_send_task(post_ids, mode)`: Automated or manual outreach delivery.

### 3. [`db.py`](file:///Users/apple/Byten/linkedInScrapper/src/db.py)
- **Role**: PostgreSQL database connection pool, queries, schema setup, analytics calculations.
- **Key Functions**:
  - `get_analytics_summary()`: Aggregates metrics (discovered, pending review, sent, conversion rates).
  - `get_posts_paginated()`: Server-side search, filtering, and pagination.
  - `update_post_email()`: Saves generated or edited email subject and body.
  - `mark_post_sent()`: Updates post state to sent with timestamp.

### 4. [`chrome_connector.py`](file:///Users/apple/Byten/linkedInScrapper/src/chrome_connector.py) & [`firefox_connector.py`](file:///Users/apple/Byten/linkedInScrapper/src/firefox_connector.py)
- **Role**: Browser connection layer (Playwright CDP session attachment, headless/headed launch).

### 5. [`chatgpt_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/chatgpt_service.py)
- **Role**: OpenAI API prompt engineering, resume-to-JD matching, personalized cold email generation.

### 6. [`gmail_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/gmail_service.py)
- **Role**: Gmail API / SMTP delivery, OAuth token refresh, message drafting.

### 7. [`health_service.py`](file:///Users/apple/Byten/linkedInScrapper/src/health_service.py)
- **Role**: Real-time integration health probes for all connected subsystems.
