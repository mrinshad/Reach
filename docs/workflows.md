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
Instead of hardcoding disparate buttons in the UI for every scraping source, the backend manages an extensible dictionary in [`src/automation_tasks.py`](file:///Users/apple/Byten/linkedInScrapper/src/automation_tasks.py):
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
   - When new posts are scraped, their contact emails are checked against rejected spam records.
   - If an exact email match exists in known spam records, the post is automatically rejected upon ingestion with `rejection_reason = 'Auto-rejected: Email marked as Spam'`.
3. **Potential Spam Heuristic**:
   - If the domain matches a spam record but the prefix differs, the post is flagged as `Potential Spam`.
   - Standard public providers (`gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `proton.me`, `icloud.com`) are excluded from domain matching to prevent false positives.

---

## 9. Dynamic PostgreSQL Settings & Environmental Fallback

**Discovered:** Step 9

### Storage & Synchronization
- **Table `settings`**: Key-value store (`key VARCHAR PRIMARY KEY, value TEXT, updated_at TIMESTAMP`).
- **Synchronized Keys**:
  - `chatgpt_url`: Dedicated custom GPT conversation URL.
  - `search_query`: LinkedIn search keyword string.
- **Fallback**:
  - If `DATABASE_URL` environment variable is not defined, connection dynamically resolves to `postgresql://{USER}@localhost:5432/linkedin_scrapper`.
  - Zero hardcoded personal URLs or user credentials are stored in code.



