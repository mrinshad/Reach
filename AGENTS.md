# Reach Codebase — Agent Navigation & Routing Guide (AGENTS.md)

This file is the primary directory and navigation guide for AI coding agents and pair programmers working in this repository.

> **CRITICAL DIRECTIVE FOR AGENTS**:
> - **DO NOT** read all of `src/static/style.css` (4,800+ lines). Check the **Routing Matrix** below and edit **ONLY** the designated file in `src/static/css/`.
> - **DO NOT** edit `src/static/index.html` directly. Edit the designated partial in `src/static/partials/`. The backend dynamically assembles and synchronizes `index.html`.
> - **DO NOT** commit changes to git unless the user explicitly commands it.

---

## Component-to-File Routing Matrix

When a user asks to modify a feature, UI element, workflow, or API, use this table to navigate directly to the responsible files:

| Feature / UI Component | HTML Partial (`src/static/partials/`) | Modular CSS (`src/static/css/`) | Client JS (`src/static/app.js`) | Backend / API (`src/`) |
|---|---|---|---|---|
| **Left Sidebar & Navigation** | [`sidebar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/sidebar.html) | [`sidebar.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/sidebar.css) | `toggleSidebarCollapse()`, `switchTab()`, `updateSidebarBadgeCounts()` | `app.py` (`/api/stats/summary`, `/api/health`) |
| **Crawler Trigger & Platform Select** | [`sidebar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/sidebar.html) | [`sidebar.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/sidebar.css) | `triggerSelectedCrawl()`, `handleCrawlerSourceChange()` | `app.py` (`/api/crawl`), `automation_tasks.py` |
| **Topbar & Header Actions** | [`topbar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/topbar.html) | [`layout.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/layout.css) | `openSettingsModal()`, `openNotificationHelpModal()` | `app.py` (`/api/stats/summary`) |
| **Notification Center Bell & Dropdown** | [`topbar.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/topbar.html) | [`layout.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/layout.css) | `toggleNotificationDropdown()`, `loadNotifications()` | `app.py` (`/api/notifications`) |
| **Dashboard Overview (Home)** | [`tab_analytics.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_analytics.html) | [`dashboard.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/dashboard.css) | `fetchAnalyticsSummary()`, `renderCharts()`, `initAnalyticsView()` | `app.py` (`/api/stats/summary`), `db.py` |
| **Headless Browser On/Off Switch** | [`tab_analytics.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_analytics.html) | [`dashboard.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/dashboard.css) | `toggleHeadlessMode()`, `updateHeadlessUI()` | `app.py` (`/api/settings/headless`), `config.py` |
| **Discovered Jobs Tab** | [`tab_discovered.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_discovered.html) | [`discovered.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/discovered.css) | `loadDiscoveredPosts()`, `filterPosts()`, `renderPostsTable()` | `app.py` (`/api/posts`), `db.py` |
| **Search & 2-Tier Filter Toolbar** | [`tab_discovered.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_discovered.html) | [`discovered.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/discovered.css) | `handleSearchInput()`, `filterByExperience()`, `filterByPlatform()` | `app.py` (`/api/posts`), `db.py` |
| **Review & Drafts Workspace** | [`tab_review.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_review.html) | [`review.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/review.css) | `loadReviewQueue()`, `renderReviewItem()`, `approvePost()` | `app.py` (`/api/review/queue`), `automation_tasks.py` |
| **Generate Mail from JD Button** | [`tab_review.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_review.html) | [`review.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/review.css) | `generateEmailFromJd(postId)` | `app.py` (`POST /api/generate-email/{post_id}?force=true`) |
| **Post Scrolling & Natural View** | [`tab_review.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_review.html) | [`review.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/review.css) | N/A (`.post-scroll` natural expander) | N/A |
| **Sent & Cancelled History** | [`tab_sent.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/tab_sent.html) | [`history.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/history.css) | `loadSentPosts()`, `filterSentHistory()` | `app.py` (`/api/sent-history`), `db.py` |
| **Task Drawer & Live Logs** | [`task_drawer.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/task_drawer.html) | [`tasks.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/tasks.css) | `pollActiveTasks()`, `renderTaskTerminal()` | `app.py` (`/api/tasks/status`), `automation_tasks.py` |
| **Modal Overlays (All 7 Dialogs)** | [`modals.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/modals.html) | [`modals.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/modals.css) | `openPostModal()`, `openSettingsModal()`, `openAddJdModal()` | `app.py` (`/api/settings`, `/api/add-jd`) |
| **Mobile Drawer & Responsiveness** | [`index_layout.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/index_layout.html) | [`responsive.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/responsive.css) | `toggleMobileSidebar()`, `closeMobileSidebar()` | N/A |
| **Mobile Web Push & Audio Alerts** | [`modals.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/modals.html) | [`modals.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/modals.css) | `initServiceWorker()`, `playNotificationChime()` | `src/static/sw.js`, `app.py` (`/sw.js`) |

---

## Directory Organization

```
linkedInScrapper/
├── AGENTS.md                                # Root Agent Directory & Routing Map (This file)
├── .agents/
│   └── rules/
│       └── codebase_map.md                  # Antigravity Workspace Rule
├── run.py                                   # Server entrypoint (Uvicorn / FastAPI)
├── requirements.txt                         # Python dependencies
├── src/
│   ├── AGENTS.md                            # Backend & Automation Agent Guide
│   ├── app.py                               # FastAPI routes, middleware & dynamic template assembly
│   ├── automation_tasks.py                  # Playwright crawler, email generation & sending workers
│   ├── chrome_connector.py                  # Chrome CDP browser connector
│   ├── firefox_connector.py                 # Firefox browser connector
│   ├── chatgpt_service.py                   # OpenAI / ChatGPT JD extraction & draft generator
│   ├── gmail_service.py                     # Gmail SMTP / OAuth email sender
│   ├── health_service.py                    # Health probe for LinkedIn, ChatGPT, Gmail & DB
│   ├── db.py                                # PostgreSQL database models, queries & migrations
│   ├── config.py                            # Settings configuration loader & serializer
│   ├── experience_extractor.py              # Regex experience parser (years of exp)
│   └── static/
│       ├── AGENTS.md                        # Frontend Component & Partials Router
│       ├── index_layout.html                # Master HTML template with partial include markers
│       ├── index.html                       # Auto-synchronized single-page HTML
│       ├── app.js                           # Dashboard client application logic & state
│       ├── style.css                        # Master stylesheet manifest importing css/ modules
│       ├── sw.js                            # Service worker for push notifications
│       ├── css/
│       │   ├── AGENTS.md                    # CSS Selectors, Tokens & Classes Guide
│       │   ├── variables.css                # Design tokens, color palette, typography
│       │   ├── base.css                     # Resets, generic buttons, badges, skeleton
│       │   ├── layout.css                   # 100vh app shell, topbar, notification dropdown
│       │   ├── sidebar.css                  # Sidebar nav, 44x44 icons, crawler card, badges
│       │   ├── dashboard.css                # KPI metric cards, charts, headless toggle
│       │   ├── discovered.css               # Search toolbar, table, cards, pagination
│       │   ├── review.css                   # Review queue, candidate card, JD mail button
│       │   ├── history.css                  # Sent & cancelled tables, cancellation pills
│       │   ├── tasks.css                    # Task queue drawer, terminal logs
│       │   ├── modals.css                   # Dialog modals & toast notifications
│       │   └── responsive.css               # Media queries (<=1024px, <=768px, <=480px)
│       └── partials/
│           ├── sidebar.html                 # Left sidebar component
│           ├── topbar.html                  # Header topbar component
│           ├── task_drawer.html             # Automation task drawer & alerts
│           ├── tab_analytics.html           # Dashboard overview tab
│           ├── tab_discovered.html          # Discovered jobs table tab
│           ├── tab_review.html              # Review & draft workspace tab
│           ├── tab_sent.html                # Outreach history tab
│           └── modals.html                  # All dialog modals & notification help
```

---

## Agent Rules of Engagement

1. **Precision File Loading**: When tasked with modifying styling or markup, open **ONLY** the relevant file from `src/static/css/` or `src/static/partials/`. Never load `style.css` (4,800+ lines).
2. **Dynamic HTML Assembly**: When updating HTML, edit `src/static/partials/*.html`. `src/app.py` serves the assembled layout automatically and keeps `index.html` synchronized.
3. **No Blind Refactoring**: Keep changes minimal, preserve existing DOM IDs and classes, and avoid adding unrequested dependencies.
4. **Git Safety**: Never execute `git commit` unless explicitly instructed by the user.
