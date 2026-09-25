# Reach Codebase — Agent Navigation & Routing Guide (AGENTS.md)

This file is the primary directory and navigation guide for AI coding agents and pair programmers working in this repository.

> **CRITICAL DIRECTIVES FOR AGENTS**:
> - **DO NOT** edit `src/static/index.html` directly. Edit the designated partial in `src/static/partials/`. The backend dynamically assembles and synchronizes `index.html`.
> - **DO NOT** read all of `src/static/style.css` (4,800+ lines). Check the **Routing Matrix** below and edit **ONLY** the designated file in `src/static/css/`.
> - **DO NOT** commit changes to git unless the user explicitly commands it.
> - **NO APPLY LINK BUTTON**: The user explicitly rolled back the apply link button. Do not add or restore apply link buttons.

---

## Hierarchical AGENTS.md Navigation Network

Every subsystem within Reach features a dedicated `AGENTS.md` guide containing localized maps, schemas, function references, and rules:

1. [**Root System Directory**](file:///Users/apple/Byten/linkedInScrapper/AGENTS.md) (This file)
2. [**Backend Subsystems (`src/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/AGENTS.md)
3. [**FastAPI REST Routers (`src/api/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/api/AGENTS.md)
4. [**Database Queries & Models (`src/db/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/db/AGENTS.md)
5. [**Playwright Workers & Automation (`src/services/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/services/AGENTS.md)
6. [**Frontend UI Architecture (`src/static/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/static/AGENTS.md)
7. [**Client JavaScript Modules (`src/static/js/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/static/js/AGENTS.md)
8. [**Modular CSS Design Tokens & Styles (`src/static/css/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/static/css/AGENTS.md)
9. [**HTML Component Partials (`src/static/partials/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/AGENTS.md)
10. [**CLI Scrapers & Standalone Tools (`scripts/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/scripts/AGENTS.md)
11. [**System Documentation & Workflows (`docs/AGENTS.md`)**](file:///Users/apple/Byten/linkedInScrapper/docs/AGENTS.md)

---

## Component-to-File Routing Matrix

When tasked with modifying a feature, UI element, workflow, or API, use this table to navigate directly to the responsible files:

| Feature / UI Component | HTML Partial (`src/static/partials/`) | Modular CSS (`src/static/css/`) | Client JS (`src/static/js/`) | Backend / API (`src/`) |
|---|---|---|---|---|
| **Left Sidebar & Navigation** | [`sidebar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/sidebar.html) | [`sidebar.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/sidebar.css) | [`sidebar.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/sidebar.js) (`switchTab`, `toggleSidebarCollapse`) | `src/api/stats.py` (`/api/stats`) |
| **Crawler Trigger & Source Select** | [`sidebar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/sidebar.html) | [`sidebar.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/sidebar.css) | [`crawler.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/crawler.js) (`triggerSelectedCrawl`, `fetchScrapers`) | `src/api/tasks.py` (`/api/scrape`), `src/services/automation_tasks.py` |
| **Topbar & Health Status** | [`topbar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/topbar.html) | [`layout.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/layout.css) | [`api.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/api.js) (`fetchHealth`, `updateHealthPill`) | `src/api/stats.py` (`/api/health`), `src/services/health_service.py` |
| **Notification Center & Chimes** | [`topbar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/topbar.html) | [`layout.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/layout.css) | [`notifications.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/notifications.js) (`sendAppNotification`, `playNotificationSound`) | Root `/sw.js` via `src/app.py` |
| **Dashboard Overview (Home)** | [`tab_analytics.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_analytics.html) | [`dashboard.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/dashboard.css) | [`analytics.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/analytics.js) (`loadAnalytics`, `renderDailyAppliedChart`) | `src/api/stats.py` (`/api/analytics`), `src/db/analytics.py` |
| **Headless Browser Mode Switch** | [`tab_analytics.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_analytics.html) | [`dashboard.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/dashboard.css) | [`modals.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/modals.js) (`toggleQuickHeadless`, `updateHeadlessUI`) | `src/api/settings.py` (`POST /api/settings/headless`), `src/config.py` |
| **Discovered Jobs Tab** | [`tab_discovered.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_discovered.html) | [`discovered.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/discovered.css) | [`discovered.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/discovered.js) (`fetchDiscoveredPosts`, `renderPostsTable`) | `src/api/posts.py` (`GET /api/posts`), `src/db/posts.py` |
| **2-Tier Search & Experience Toolbar** | [`tab_discovered.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_discovered.html) | [`discovered.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/discovered.css) | [`discovered.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/discovered.js) (`applyFilters`, `setExpFilter`) | `src/api/posts.py` (`/api/locations`, `/api/reasons`) |
| **Review & Drafts Workspace** | [`tab_review.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_review.html) | [`review.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/review.css) | [`review.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/review.js) (`fetchReviewPosts`, `saveActiveDraftEdits`) | `src/api/posts.py`, `src/api/tasks.py` (`/api/generate-email/{id}`) |
| **Generate Mail from JD Button** | [`tab_review.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_review.html) | [`review.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/review.css) | [`review.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/review.js) (`generateEmailForActiveDraft`) | `src/api/tasks.py` (`POST /api/generate-email/{id}?force=true`) |
| **Direct Gmail Dispatch** | [`tab_review.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_review.html) | [`review.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/review.css) | [`review.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/review.js) (`sendActiveDraftDirectly`, `openActivePostInGmail`) | `src/api/tasks.py` (`/api/send-direct/{id}`, `/api/open-gmail/{id}`) |
| **LinkedIn Easy Apply Workspace** | [`tab_easy_apply.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_easy_apply.html) | [`easy_apply.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/easy_apply.css) | [`easy_apply.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/easy_apply.js) (`fetchEasyApplyPosts`, `setEasyPostStatus`, `batchSetEasyStatus`, `openBulkSearchModal`, `submitBulkEasySearch`, `NOT_FOUND` handling) | `src/api/posts.py` (`POST /api/posts/{id}/status`, `POST /api/posts/status-batch`), `src/api/tasks.py` (`POST /api/scrape/easy-apply`, `POST /api/scrape/easy-apply/batch`, `POST /api/easy-apply/{id}`), `src/services/easy_apply_service.py` |
| **Screening Questionnaire Modal** | [`tab_easy_apply.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_easy_apply.html) (`#modalScreeningQuestions`) | [`easy_apply.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/easy_apply.css) | [`easy_apply.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/easy_apply.js) (`openScreeningModal`, `parseScreeningQuestions`, `triggerScreeningRescan`, `markScreeningAsReady`) | `src/services/easy_apply_service.py` (`REQUIRES_QUESTIONNAIRE` questionnaire parsing & extraction) |
| **Sent & Cancelled History (Others)** | [`tab_sent.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_sent.html) | [`history.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/history.css) | [`history.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/history.js) (`fetchSentPosts`, `revertPostToDraft`) | `src/api/posts.py` (`status=OTHERS`, `revert`) |
| **Task Drawer & Live Logs** | [`task_drawer.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/task_drawer.html) | [`tasks.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/tasks.css) | [`tasks.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/tasks.js) (`pollTaskStatus`, `cancelQueuedTask`) | `src/api/tasks.py` (`/api/tasks/status`, `/api/tasks/queue/*`) |
| **Dialog Modals (All 7 Dialogs)** | [`modals.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/modals.html) | [`modals.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/modals.css) | [`modals.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/modals.js) (`openPostModal`, `submitManualJd`) | `src/api/posts.py`, `src/api/settings.py` |
| **Mobile Sidebar & Drawer** | [`index_layout.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/index_layout.html) | [`responsive.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/responsive.css) | [`sidebar.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/sidebar.js) (`closeMobileSidebar`) | N/A |

---

## Directory Organization

```
linkedInScrapper/
├── AGENTS.md                                # Root Directory & Routing Map (This file)
├── run.py                                   # Server entrypoint (Uvicorn / FastAPI)
├── requirements.txt                         # Python dependencies
├── scripts/
│   ├── AGENTS.md                            # CLI & Scraper Standalone Guide
│   ├── linkedin_posts_search.py             # Playwright LinkedIn hiring post crawler
│   ├── infopark_jobs_search.py              # Infopark Kochi companies-job crawler
│   └── ...                                  # Batch testing & session diagnostic probes
├── docs/
│   ├── AGENTS.md                            # Architecture & Workflows Documentation Guide
│   ├── file_architecture.md                 # Complete system file architecture & directory tree
│   ├── workflows.md                         # End-to-end user workflows & lifecycle diagrams
│   └── implementation_plan.md               # Safety guidelines & completed milestone roadmap
└── src/
    ├── AGENTS.md                            # Backend & Automation Agent Guide
    ├── app.py                               # FastAPI root application & template compiler
    ├── config.py                            # Settings configuration loader & serializer
    ├── api/
    │   ├── AGENTS.md                        # REST API Routers Guide
    │   ├── __init__.py                      # Aggregates modular routers into api_router
    │   ├── models.py                        # Pydantic request models & constants
    │   ├── posts.py                         # Post querying, filtering, manual ingestion & status
    │   ├── tasks.py                         # FIFO task queue management & scraper triggers
    │   ├── stats.py                         # Dashboard counters, analytics & session health
    │   └── settings.py                      # Configuration, resume uploads & Headless toggle
    ├── services/
    │   ├── AGENTS.md                        # Automation & Browser Services Guide
    │   ├── __init__.py                      # Services package re-exports
    │   ├── automation_tasks.py              # Sequential FIFO TaskManager & watchdog runners
    │   ├── easy_apply_service.py            # LinkedIn Easy Apply crawler & modal multi-step questionnaire automation
    │   ├── chatgpt_service.py               # Web ChatGPT Custom GPT orchestrator
    │   ├── gmail_service.py                 # Gmail compose automation & direct dispatch
    │   ├── firefox_connector.py             # Persistent Playwright Firefox context lifecycle
    │   ├── chrome_connector.py              # Fallback Chrome CDP browser connector
    │   ├── health_service.py                # Database & browser session cookie health probes
    │   └── experience_extractor.py          # Regex years of experience & fresher parser
    ├── db/
    │   ├── AGENTS.md                        # Database Queries & Schema Guide
    │   ├── __init__.py                      # Database package re-exports
    │   ├── connection.py                    # Connection pooling & table migrations
    │   ├── posts.py                         # Post upsert, filtering, pagination & status updates
    │   ├── settings.py                      # Persistent settings key-value store
    │   └── analytics.py                     # Aggregated conversion analytics & trend queries
    └── static/
        ├── AGENTS.md                        # Frontend Component & Static Asset Guide
        ├── index_layout.html                # Master HTML layout template with include markers
        ├── index.html                       # Auto-synchronized single-page HTML
        ├── app.js                           # Master client bootstrapper
        ├── style.css                        # Master stylesheet importing css/ modules
        ├── sw.js                            # Service Worker for push notifications
        ├── js/
        │   ├── AGENTS.md                    # Client JavaScript Modules Guide
        │   ├── state.js                     # Global dashboard state & configuration
        │   ├── utils.js                     # Dialogs, snackbar toasts & formatters
        │   ├── notifications.js             # Web Push, audio chimes & notification center
        │   ├── sidebar.js                   # Tab switching & sidebar collapse
        │   ├── api.js                       # API communications & stats polling
        │   ├── discovered.js                # Discovered jobs table & 2-tier filters
        │   ├── review.js                    # Review queue, AI editor & Gmail dispatch
        │   ├── history.js                   # Sent & cancelled history table
        │   ├── crawler.js                   # Scraper triggers & platform selection
        │   ├── tasks.js                     # Live task drawer & log streaming
        │   ├── modals.js                    # Dialog overlays & Headless switch
        │   └── analytics.js                 # Chart.js visualizations
        ├── css/
        │   ├── AGENTS.md                    # CSS Selectors & Tokens Guide
        │   ├── variables.css                # Design tokens & color palette
        │   ├── base.css                     # Resets, buttons, badges & skeleton
        │   ├── layout.css                   # App shell, topbar & notification center
        │   ├── sidebar.css                  # Navigation sidebar & crawler card
        │   ├── dashboard.css                # KPI metric cards & headless toggle
        │   ├── discovered.css               # Discovered jobs table & search toolbar
        │   ├── review.css                   # Candidate review card & natural scroll
        │   ├── history.css                  # Sent & cancelled tables & chips
        │   ├── tasks.css                    # Task queue drawer & terminal logs
        │   ├── modals.css                   # Dialog modals & snackbar alerts
        │   └── responsive.css               # Media queries for mobile & tablet
        └── partials/
            ├── AGENTS.md                    # HTML Partials & DOM Elements Guide
            ├── sidebar.html                 # Navigation sidebar partial
            ├── topbar.html                  # Top header bar partial
            ├── task_drawer.html             # Task queue & log drawer partial
            ├── tab_analytics.html           # Analytics overview tab partial
            ├── tab_discovered.html          # Discovered jobs table tab partial
            ├── tab_review.html              # Review & drafts workspace partial
            ├── tab_sent.html                # Outreach history tab partial
            └── modals.html                  # Modal dialogs partial
```
