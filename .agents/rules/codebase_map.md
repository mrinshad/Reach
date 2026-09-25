---
description: Codebase Architecture Directory and Fast Component Routing Map
always_on: true
---

# Codebase Fast Routing Map

Before reading large files or grepping through the repository, use this directory map to identify the exact files to inspect and edit:

## 1. Frontend CSS Routing (`src/static/css/`)
- `variables.css`  ➔ Color tokens, typography, CSS variables (`:root`).
- `base.css`       ➔ Resets, typography, standard buttons (`.btn`), badges, skeleton loader.
- `layout.css`     ➔ App shell (`.app-layout`, `.app-main`), header topbar (`.app-topbar`), notifications.
- `sidebar.css`    ➔ Left navigation (`.app-sidebar`), 44x44 icons, badge counts, crawler source/location selector.
- `dashboard.css`  ➔ Overview tab (`#tabAnalytics`), KPI summary cards, Chart.js grid, headless mode switch.
- `discovered.css` ➔ Discovered tab (`#tabDiscovered`), 2-tier search/filter toolbar, data table, pagination.
- `review.css`     ➔ Review tab (`#tabReview`), queue sidebar, candidate card, natural post scroll, email editor, `[ ✨ Generate Mail from JD ]` button.
- `history.css`    ➔ Outreach history tab (`#tabSent`), view switcher, sent/cancelled tables, status tags, cancellation pills, activity & run log history table, terminal log dialog.
- `tasks.css`      ➔ Background task drawer, progress bar, live terminal logs, run history shortcut button.
- `easy_apply.css` ➔ LinkedIn Easy Apply table, KPI ribbon, fixed status dropdown, screening modal, bulk search modal.
- `modals.css`     ➔ All dialog modals (`#postModal`, `#settingsModal`, `#modalAddJd`, `#modalDirectOutreach`, `#cancelReasonModal`, `#crawlSummaryModal`, `#notifHelpModal`, `#modalRunTerminalLogs`), toasts.
- `responsive.css` ➔ Mobile drawer, media queries (`<= 1024px`, `<= 768px`, `<= 480px`), touch UI.

## 2. Frontend HTML Partials Routing (`src/static/partials/`)
- `sidebar.html`        ➔ Sidebar DOM (`#appSidebar`, crawler trigger, nav buttons).
- `topbar.html`         ➔ Top header DOM (`.app-topbar`, page title, action buttons, bell).
- `task_drawer.html`    ➔ Live task queue, alert banner DOM, and `[ 📜 Run History ]` shortcut.
- `tab_analytics.html`  ➔ Dashboard metrics cards, charts, and headless toggle.
- `tab_discovered.html` ➔ Search input, filters, batch trigger, posts table.
- `tab_review.html`     ➔ Candidate details, post scroll container, email draft editor, JD mail button.
- `tab_easy_apply.html` ➔ LinkedIn Easy Apply workspace, 5-KPI ribbon, responsive table, screening modal (`#modalScreeningQuestions`), bulk search modal (`#modalBulkEasySearch`).
- `tab_sent.html`       ➔ Sent & cancelled history table, segmented view switcher, automated activity & run logs table.
- `modals.html`         ➔ All modal overlays, notification diagnostic dialog, and terminal output viewer (`#modalRunTerminalLogs`).

## 3. Backend Routing (`src/`)
- `app.py`                ➔ FastAPI root application, template compiler, static file mounting.
- `api/tasks.py`          ➔ Task execution triggers, status polling, FIFO queue, and `/api/activity-logs` endpoints.
- `services/automation_tasks.py` ➔ Sequential FIFO TaskManager, crawler runners, run activity logging.
- `services/easy_apply_service.py` ➔ LinkedIn Easy Apply crawler, multi-step questionnaire detection & form handling.
- `db/activity_logs.py`   ➔ Persistent database logging for automated task runs (crawls, Easy Apply, batch AI).
- `db/posts.py`           ➔ Post upsert, filtering, pagination, and status updates.
- `db/connection.py`      ➔ PostgreSQL connection pooling and table migrations (`posts`, `settings`, `activity_logs`).
- `chrome_connector.py`   ➔ Chrome CDP connector for headed & headless browser automation.
- `chatgpt_service.py`    ➔ Web ChatGPT orchestrator, email generation, tech stack analysis.
- `gmail_service.py`      ➔ Gmail compose automation & direct dispatch.
- `health_service.py`     ➔ Health checks for external services and database.

