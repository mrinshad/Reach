# Discovered Workflows

This document records the workflows discovered during interactive development.
No credentials, session tokens, or authentication data are stored here.

---

## 1. Chrome + CDP Connection

**Discovered:** Step 1

### Prerequisites
- macOS
- Chrome 152.0.7977.84 at `/Applications/Google Chrome.app`
- Python 3.13 with Playwright 1.63.0
- Existing Chrome profile: `Default`

### Workflow

1. **Quit Chrome** if it's currently running (Cmd+Q)
2. **Relaunch with CDP**:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   ```
   - All tabs and sessions are restored from the existing profile
   - CDP endpoint becomes available at `http://localhost:9222`
3. **Login** to LinkedIn, ChatGPT, Gmail (done manually by the user)
4. **Connect Playwright**:
   ```python
   browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
   ```
5. **Verify** by listing open tabs
6. **Disconnect** cleanly — Chrome remains running

### Key Notes & Limitations
- Chrome must NOT be already running when launched with `--remote-debugging-port`.
- The existing `Default` profile is used automatically.
- No credentials are stored or transmitted.
- **Limitation**: Cloudflare Turnstile actively blocks/drops connections on `chatgpt.com` when Chrome is running with `--remote-debugging-port`.

---

## 2. Playwright Firefox (Persistent Context)

**Discovered:** Step 2

### Prerequisites
- Python 3.13 with Playwright 1.63.0 (`playwright install firefox`)
- Persistent profile directory: `~/.playwright_firefox_profile`

### Workflow

1. **Launch Firefox persistent context**:
   ```python
   context = playwright.firefox.launch_persistent_context(
       user_data_dir=os.path.expanduser("~/.playwright_firefox_profile"),
       headless=False,
   )
   ```
2. **Navigate to ChatGPT / LinkedIn**:
   ```python
   page = context.pages[0] if context.pages else context.new_page()
   page.goto("https://chatgpt.com")
   ```
3. **One-time Login**: The user logs in manually directly in the opened browser window.
4. **Persistence**: Cookies and storage remain saved in `~/.playwright_firefox_profile` across automation runs.
5. **Clean Exit**: `context.close()` persists the session without killing background user data.

### Key Notes
- Avoids Cloudflare Turnstile blocks encountered under Chrome CDP.
- Credentials and 2FA are handled securely by the user in the browser window.

---

## 3. ChatGPT Dedicated Conversation

**Discovered:** Step 3

### Workflow
1. **Target URL**: Direct link to the dedicated custom GPT conversation.
2. **Input Method**: `#prompt-textarea` is a ProseMirror `div[contenteditable]`.
   - Must use `page.keyboard.type(line, delay=5)` with `page.keyboard.press("Shift+Enter")` for newlines (standard `fill()` does not work).
3. **Send**: `button[data-testid='send-button']` (becomes visible and enabled once text is typed).
4. **Streaming Completion**: Wait until `button[aria-label='Stop generating']` disappears.
5. **Response Extraction**: Locate `[data-message-author-role='assistant']` and read `.markdown` content from the newest message ID.

---

## 4. LinkedIn Global Posts Search

**Discovered:** Step 4

### Workflow
1. **Target URL**:
   `https://www.linkedin.com/search/results/content/?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER&sortBy=%22date_posted%22`
2. **Container**:
   `div[data-testid="lazy-column"]` containing direct feed card children.
3. **Field Extraction**:
   - **Author**: First `a[href*="/in/"]` with non-empty text, stripping degree badges.
   - **Headline**: Header lines below author name.
   - **Date**: Matches `^\d+[hdmy]\b` (e.g. `6m`, `20h`, `1d`).
   - **Post Direct URL**: Click card's control button (`button[aria-label*="control menu"]`), click `"Copy link to post"`, and read from clipboard (`pbpaste`).
   - **Full Text**: Extracted from card body, excluding header and engagement counts.
   - **Emails**: Regex pattern `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`.
   - **External Links**: Extracted external application links.
4. **Filtering & Categorization**:
   - **Date Filter**: Search URL includes `&datePosted=%22past-24h%22` and verifies timestamp (`^\d+[hm]$` or `just now`). Older posts are excluded.
   - **Job Seeker Exclusion**: Discards posts matching `#opentowork`, `looking for a new role`, `seeking opportunities`, etc.
   - **Email Outreach List**: Posts with detected contact emails (excluding comment-bait schemes).
   - **Draft / Other Posts List**: Preserves posts with external portal links, application URLs, or comment-to-apply prompts for alternative workflows.

---

## 5. Gmail Draft Preparation & Formatting

**Discovered:** Step 5

### Workflow
1. **Target URL**: `https://mail.google.com/mail/u/0/#inbox` (reusing existing session in Firefox persistent profile).
2. **Compose Button**: `div[gh="cm"], div[role="button"]:has-text("Compose")`.
3. **Recipient Field**: `input[aria-label*="To"], input.agP`. Type email and press `Enter` to create recipient chip.
4. **Subject Field**: `input[name="subjectbox"]`.
5. **Message Body Formatting**:
   - **Critical Gotcha**: Gmail's `div[role="textbox"][aria-label*="Message Body"]` is a rich-text contenteditable element. Calling Playwright's `locator.fill()` collapses all line breaks into spaces.
   - **Solution**: Split text into lines and type each line with `page.keyboard.type(line)` followed by `page.keyboard.press("Enter")`. This creates native `<div>`/paragraph blocks with clean, professional spacing.
6. **Attachment**: `input[type="file"][name="Filedata"]`. Global resume path attached via `set_input_files`.
7. **Strict Human Safety**: Automation stops at draft preparation and never sends automatically during development.

---

## 6. Unified Scraper Source Registry

**Discovered:** Step 6

### Architecture & Registration Pattern
Instead of hardcoding disparate buttons in the UI for every scraping source, the backend manages an extensible dictionary in [`src/services/automation_tasks.py`](file:///Users/apple/Byten/linkedInScrapper/src/services/automation_tasks.py):
```python
SCRAPER_REGISTRY = {
    "linkedin_posts": {
        "id": "linkedin_posts",
        "name": "LinkedIn Posts (Feed)",
        "icon": "💼",
        "handler": run_linkedin_scraper,
    },
    "infopark": {
        "id": "infopark",
        "name": "Infopark Jobs Portal",
        "icon": "🏢",
        "handler": run_infopark_scraper,
    },
}
```
- **Discovery**: The frontend calls `GET /api/scrapers` on load to dynamically populate the crawler `<select>` dropdown.
- **Trigger**: Single `POST /api/scrape` endpoint accepts `{"source": "<source_id>"}` and dispatches to the corresponding handler.
- **Extensibility**: Adding new scrapers (e.g. Technopark, Indeed, YC Work at a Startup) only requires registering 1 entry in `SCRAPER_REGISTRY`.

---

## 7. 90-Second Inactivity Timeout & Clean Process Termination

**Discovered:** Step 7

### Problem & Solution
Network stalls or dynamic infinite scroll locks can cause scrapers to hang indefinitely without throwing exceptions.
- **Inactivity Tracker**: The runner tracks `last_progress_time = time.time()`. Whenever a new post is parsed or a valid scroll completes, `last_progress_time` resets.
- **Auto-Termination**: If `time.time() - last_progress_time > 90`, the task logs a warning, persists all gathered items up to that timestamp to PostgreSQL, cleanly closes browser contexts, and marks the task as completed.

---

## 8. Spam / Scam Intelligence & 1-Click Marking

**Discovered:** Step 8

### Workflow & Ingestion Heuristic
1. **1-Click Spam Action**:
   - Available on feed cards (`.btn-spam-quick`) and inside the Review workspace (`#btnWorkspaceSpam`).
   - Dispatches `POST /api/posts/{post_id}/spam`.
   - Immediately sets `status = 'REJECTED'` and `rejection_reason = 'Spam / Scam'`.
2. **Auto-Reject Ingestion Rule**:
   - When new posts are scraped, their contact emails and domains are checked against rejected spam/scam records.
   - If a custom corporate domain was previously reported as scam/spam, the post is automatically rejected upon ingestion with the prior reason and matched recruiter.
   - If an exact email was reported as scam/spam (including on mainstream providers), it is auto-rejected.
3. **Scam & Potential Scam Tooltip & Modal Display**:
   - Recruiters labeled as `🛑 Scam` or `⚠️ Potential Scam` display actionable hover tooltips explaining the reason why.
   - Clicking "View" opens the application modal featuring dedicated Scam or Potential Scam banner alerts with full explanations.
   - Mainstream public providers (`gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `proton.me`, `icloud.com`) are excluded from domain-level blocking to prevent false positives.

---

## 9. Dynamic PostgreSQL Settings & Environmental Fallback

**Discovered:** Step 9

### Storage & Synchronization
- **Table `settings`**: Key-value store (`key VARCHAR PRIMARY KEY, value TEXT, updated_at TIMESTAMP`).
- **Synchronized Keys**:
  - `chatgpt_url`: Dedicated custom GPT conversation URL.
  - `search_query`: LinkedIn search keyword string.
  - `headless_mode`: Browser automation visibility (`"true"` / `"false"`).
- **Fallback**:
  - If `DATABASE_URL` environment variable is not defined, connection dynamically resolves to `postgresql://{USER}@localhost:5432/linkedin_scrapper`.
  - Zero hardcoded personal URLs or user credentials are stored in code.

---

## 10. Sequential FIFO Task Queue & Live Task Drawer

**Discovered:** Task Engine Architecture

### Mechanics
- **Thread-Safe Queue (`TaskManager`)**: Prevents `409 Conflict` errors during parallel triggers. Enqueues background jobs in FIFO sequence and executes them one at a time.
- **Queue Controls**: 
  - `GET /api/tasks/status`: Returns current active task, status, terminal log stream, and array of pending queue items.
  - `POST /api/tasks/queue/cancel/{id}`: Cancels a specific pending queued task.
  - `POST /api/tasks/queue/clear`: Empties all queued background operations.
- **UI Task Drawer**: Real-time terminal log drawer at the bottom of the screen (`#taskDrawer`), polling status at 1.5s intervals and displaying animated progress indicators.

---

## 11. Headless Browser Mode On/Off Switch

**Discovered:** Background Automation Engine

### Implementation
- **Configuration Persistence**: Stored in PostgreSQL `settings.headless_mode` (`"true"` or `"false"`).
- **Toggle API**: `POST /api/settings/headless` flips the mode and returns the updated state.
- **Browser Contexts**: `get_headless_mode()` in `src/firefox_connector.py` passes the mode to `playwright.firefox.launch_persistent_context(headless=mode)`.
- **UI Switch**: Toggle button in the sidebar footer and switch in the analytics overview, updating dynamically across all connected devices.

---

## 12. Direct AI Email Generation from JD with Force Override

**Discovered:** Review & Drafts Workflow

### Implementation
- **Button in UI**: `[ ✨ Generate Mail from JD ]` (`#btnGenerateMailJd`) placed in the Review & Drafts workspace next to the Email Body label.
- **Endpoint**: `POST /api/generate-email/{post_id}?force=true`.
- **Behavior**: Bypasses the existing draft check, queues a single-post ChatGPT generation task, and updates the email body live on completion without moving the post between tabs.

---

## 13. Full Codebase Restructuring & Subsystem Modularization

**Discovered:** Architectural Scaling

### Architecture
1. **Database Decoupling (`src/db/`)**:
   - `connection.py`: Thread-safe connection pooling with context-managed cursors and auto-migrations.
   - `settings.py`: PostgreSQL-backed key-value settings store.
   - `posts.py`: Deduplicated post ingestion, anti-spam heuristics, and paginated searches.
   - `analytics.py`: KPI counts, daily outreach velocity, and cancellation reason aggregations.
   - `__init__.py`: Backward-compatible symbol re-exports.
2. **Services & Workers Layer (`src/services/`)**:
   - `automation_tasks.py`: Sequential FIFO `TaskManager` and `SCRAPER_REGISTRY`.
   - `chatgpt_service.py`, `firefox_connector.py`, `gmail_service.py`, `health_service.py`, `experience_extractor.py`.
   - All CLI scripts in `scripts/` import directly from `src.services.*` with zero legacy shims needed.
3. **Modular API Routers (`src/api/`)**:
   - Decomposed monolithic API into domain routers: `posts.py`, `tasks.py`, `stats.py`, `settings.py`, and Pydantic schemas in `models.py`.
   - Assembled under `api_router` in `src/api/__init__.py`.
   - Lightweight `src/app.py` root server (~140 lines) focused on startup, CORS, and template assembly.

---

## 14. Mobile Web Push Notifications & Web Audio Alerts

**Discovered:** Multi-Device Accessibility

### Architecture
- **Root-Scoped Service Worker (`/sw.js`)**: Proxied by `src/app.py` directly from root URL with `Service-Worker-Allowed: /` header to support full-app notification scope on mobile browsers.
- **Audio Chime**: Uses Web Audio API oscillator synthesis (`440Hz` → `880Hz` dual-tone chime) on task completion. Includes user-interaction audio unlock.
- **Haptic Feedback**: Triggers `navigator.vibrate([100, 50, 100])` on supported smartphones.
- **Diagnostics Help Modal (`#notifHelpModal`)**: Step-by-step instructions for unblocking notifications on Safari iOS, Chrome Android, and macOS.

---

## 15. Modular Static Architecture & Dynamic Layout Assembly

**Discovered:** Codebase Maintainability & Agent Routing

### Architecture
- **CSS Modularity (`src/static/css/`)**: 11 focused stylesheets (`variables.css`, `base.css`, `layout.css`, `sidebar.css`, `dashboard.css`, `discovered.css`, `review.css`, `history.css`, `tasks.css`, `modals.css`, `responsive.css`).
- **HTML Partials (`src/static/partials/`)**: 8 component partials included dynamically via `<!-- INCLUDE: partials/filename.html -->` in `index_layout.html`.
- **Client JavaScript Modularity (`src/static/js/`)**: Deconstructed 4,060-line monolith into 12 domain ES modules (`state.js`, `utils.js`, `notifications.js`, `sidebar.js`, `api.js`, `discovered.js`, `review.js`, `history.js`, `crawler.js`, `tasks.js`, `modals.js`, `analytics.js`) orchestrated by a ~60-line `app.js` bootstrapper.
- **Dynamic Server Assembly**: `get_rendered_index_html()` in `src/app.py` compiles the layout on each server response and keeps `src/static/index.html` synchronized on disk.
- **Hierarchical Agent Guides**: Dedicated `AGENTS.md` files in every folder across the workspace guide AI coding assistants directly to responsible files without broad directory scans.
