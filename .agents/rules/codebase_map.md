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
- `history.css`    ➔ Outreach history tab (`#tabSent`), sent/cancelled tables, status tags, cancellation pills.
- `tasks.css`      ➔ Background task drawer, progress bar, live terminal logs.
- `modals.css`     ➔ All 7 dialog modals (`#postModal`, `#settingsModal`, `#modalAddJd`, `#modalDirectOutreach`, `#cancelReasonModal`, `#crawlSummaryModal`, `#notifHelpModal`), toasts.
- `responsive.css` ➔ Mobile drawer, media queries (`<= 1024px`, `<= 768px`, `<= 480px`), touch UI.

## 2. Frontend HTML Partials Routing (`src/static/partials/`)
- `sidebar.html`        ➔ Sidebar DOM (`#appSidebar`, crawler trigger, nav buttons).
- `topbar.html`         ➔ Top header DOM (`.app-topbar`, page title, action buttons, bell).
- `task_drawer.html`    ➔ Live task queue & alert banner DOM.
- `tab_analytics.html`  ➔ Dashboard metrics cards, charts, and headless toggle.
- `tab_discovered.html` ➔ Search input, filters, batch trigger, posts table.
- `tab_review.html`     ➔ Candidate details, post scroll container, email draft editor, JD mail button.
- `tab_sent.html`       ➔ Sent & cancelled history table.
- `modals.html`         ➔ All modal overlays and notification diagnostic dialog.

## 3. Backend Routing (`src/`)
- `app.py`                ➔ FastAPI routes, API endpoints, static file serving, index HTML dynamic assembly.
- `automation_tasks.py`   ➔ Playwright crawler automation, batch email generation, outreach execution.
- `db.py`                 ➔ PostgreSQL connection, queries, post status updates, analytics calculations.
- `chrome_connector.py`   ➔ Chrome CDP connector for headed & headless browser automation.
- `chatgpt_service.py`    ➔ OpenAI API prompts, email generation, tech stack analysis.
- `gmail_service.py`      ➔ Gmail SMTP & OAuth email delivery.
- `health_service.py`     ➔ Health checks for external services and database.
