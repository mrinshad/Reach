# Reach — System Implementation Plan & Milestone Roadmap

## Account Safety & Automation Guidelines

1. **Flexible Browser Visibility**:
   - Configurable between **Headed Mode** (visible Playwright window for live review) and **Headless Mode** (silent background automation) using persistent Firefox profile (`~/.playwright_firefox_profile`).
2. **Keystroke & Human Pacing Delays**:
   - Random delays between 2.0s and 4.5s before taking navigation actions.
   - Smooth, incremental scrolling (300–600px at a time) with brief pauses to mimic reading behavior.
   - 90-second inactivity watchdog terminates stuck sessions safely while saving all collected leads.
3. **Session Volume & Reputation Protection**:
   - Polite sequential FIFO queuing for all operations, eliminating concurrency collisions.
   - Batch operations space dispatches with randomized 4–8s cooldown intervals.
   - Immediate pause and user alert if CAPTCHAs, security challenges, or bot blocks occur.
4. **No Credential Storage**:
   - Uses pre-authenticated browser sessions stored locally in Firefox user profile. No passwords, tokens, or private secrets are tracked in code or database.

---

## High-Level System Workflow

```text
[ Multi-Platform Crawling (LinkedIn, Infopark Kochi, Manual JD, Direct Outreach) ]
                    │
                    ▼
[ Extensible Scraper Registry & 90s Inactivity Watchdog ]
                    │
                    ▼
[ PostgreSQL Storage & Deduplication (posts, settings) ]
                    │
                    ▼
[ Sequential FIFO Task Queue Manager ]
                    │
                    ├── AI Email Generation (Web ChatGPT / Custom GPT)
                    ├── Anti-Spam & Fraud Rejection Filtering
                    └── Experience & Seniority Extraction
                    │
                    ▼
[ Review & Human Oversight Workspace ]
                    ├── Natural-scroll Job Details & Quick Actions
                    ├── AI Application Draft Live Editing
                    ├── On-Demand "Generate Mail from JD" Override
                    └── Resume Attachment Validation
                    │
                    ▼
[ Gmail Outreach Dispatch ]
                    ├── Interactive Headed Review & Compose
                    └── Automated Silent Direct Dispatch
```

---

## Completed Architectural Milestones

### Milestone 1: Core Automation & Session Persistence ✅
- Configured persistent Playwright Firefox context (`~/.playwright_firefox_profile`).
- Developed `scripts/linkedin_posts_search.py` and `scripts/infopark_jobs_search.py`.
- Built regex experience extractor (`src/experience_extractor.py`) parsing years of experience, ranges, and freshers.
- Implemented PostgreSQL schema (`posts`, `settings`) with deduplication and indexes.

### Milestone 2: AI Screening & Gmail Dispatch ✅
- Orchestrated web ChatGPT Custom GPT integration (`src/chatgpt_service.py`) via ProseMirror editor typing and streaming completion listeners.
- Integrated automated suitability screening (`UNSUITABLE_JD - ❌ Not suitable — {reason}`) into PostgreSQL status.
- Implemented Gmail compose automation with automatic resume PDF attachment (`src/gmail_service.py`).
- Implemented 1-click Spam/Scam reporting with domain-level blacklist filtering.

### Milestone 3: Sequential FIFO Task Queue & Real-Time Analytics ✅
- Replaced concurrent task collisions with thread-safe sequential FIFO task queue engine (`TaskManager`).
- Built real-time task drawer terminal with cancel and clear controls.
- Created real-time Analytics overview tab with daily application velocity and conversion stages.

### Milestone 4: Headless Mode Switch & Multi-Channel Notifications ✅
- Built 1-click Headless Mode on/off switch persisted in PostgreSQL.
- Implemented root-scoped Service Worker (`/sw.js`) for Mobile Web Push alerts.
- Added Web Audio API dual-tone chime and haptic feedback on task completion.

### Milestone 5: Layout Ergonomics & Review Scrolling ✅
- Stationary 100vh app shell preventing sidebar movement during content scrolling.
- Natural scroll view for candidate cards and email drafts without nested scroll traps.
- Collapsible sidebar with unsquashed 44x44 icon buttons and live badges.
- `[ ✨ Generate Mail from JD ]` override button with `POST /api/generate-email/{id}?force=true`.

### Milestone 6: Modular Static Asset Architecture & Agent Maps ✅
- Deconstructed monolithic 4,800-line stylesheet into 11 modular CSS files under `src/static/css/`.
- Deconstructed monolithic HTML into 8 component partials under `src/static/partials/`.
- Implemented dynamic server-side template compiler in `src/app.py` keeping `src/static/index.html` synchronized.
- Created hierarchical `AGENTS.md` codebase routing guides for rapid AI agent navigation.

### Milestone 7: Pinned Modal Layout & Safe Viewports ✅
- Constrained modal dialog containers (`max-height: calc(100vh - 3rem)`) preventing vertical clipping across displays.
- Pinned modal headers and action footers with independently scrollable body containers.
- Enhanced touch viewports and clean responsive cards across mobile devices.

### Milestone 8: Full Codebase Restructuring & Hierarchical AGENTS.md Architecture ✅
- **Modular Database Layer (`src/db/`)**: Decomposed monolithic database logic into `connection.py`, `settings.py`, `posts.py`, `analytics.py`, and `__init__.py` with 100% symbol parity.
- **Decoupled Automation Services (`src/services/`)**: Moved background workers, FIFO queue manager, and browser connectors to `src/services/` with transparent backward-compatibility shims in `src/*.py`.
- **Modular REST API Routers (`src/api/`)**: Split endpoints into dedicated domain routers (`posts.py`, `tasks.py`, `stats.py`, `settings.py`, `models.py`) mounted via unified `api_router`. Refactored `src/app.py` into a clean root app (~140 lines).
- **Modular Client JavaScript (`src/static/js/`)**: Deconstructed 4,060-line monolithic `app.js` into 12 domain ES modules orchestrated by a ~60-line master bootstrapper.
- **Hierarchical AGENTS.md Network**: Created specialized routing guides in every repository directory (`/`, `src/`, `src/api/`, `src/db/`, `src/services/`, `src/static/`, `src/static/js/`, `src/static/css/`, `src/static/partials/`, `scripts/`, `docs/`).
- **Comprehensive Documentation Synchronization**: Synchronized `README.md`, `docs/file_architecture.md`, `docs/workflows.md`, and `docs/implementation_plan.md`.
