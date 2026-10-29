# Reach — Living Project State & Architecture Ledger (PROJECT_STATE.md)

This living document tracks the active operational state, architectural milestones, system matrix, technical debt ledger, and ongoing maintenance tasks for Reach.

---

## 1. Project Overview

- **Repository**: Reach (`Byten/linkedInScrapper`)
- **System Purpose**: Autonomous multi-platform job crawler, generative AI outreach writer, LinkedIn Easy Apply manager, and automated Gmail dispatcher.
- **Active Branch**: `qstn-bank`
- **Primary Runtime**: Python 3.10+ / FastAPI / Playwright / PostgreSQL / Vanilla ES Modules / CSS Variables

---

## 2. Milestone Roadmap & Status

| Milestone | Title | Status | Details |
| :--- | :--- | :--- | :--- |
| **M1** | Core Automation & Session Persistence | Complete | Playwright Firefox context, crawler scripts, PostgreSQL schema |
| **M2** | AI Screening & Gmail Dispatch | Complete | Web ChatGPT Custom GPT integration, spam filter, Gmail dispatch |
| **M3** | Sequential FIFO Task Queue & Analytics | Complete | Thread-safe `TaskManager`, live drawer terminal, real-time analytics |
| **M4** | Headless Mode Switch & Multi-Channel Alerts| Complete | 1-click headless toggle, root Service Worker push, audio chime |
| **M5** | Layout Ergonomics & Natural Scrolling | Complete | 100vh locked shell, 68px/270px collapsible sidebar, candidate cards |
| **M6** | Modular Static Asset Architecture | Complete | Decomposed 4,800-line CSS into 11 files & HTML into 8 partials |
| **M7** | Pinned Modal Layout & Safe Viewports | Complete | Pinned modal headers/footers with internal scrolling |
| **M8** | Full Codebase Modular Restructuring | Complete | Decoupled `src/api/`, `src/db/`, `src/services/`, `src/static/js/` |
| **M9** | LinkedIn Easy Apply & Screening Extraction | Complete | Multi-step Easy Apply runner, form extractor, 5-KPI ribbon |
| **M10** | Safe Human Pacing & Anti-Abuse Watchdog | Complete | 45-75s pacing, rate-limit banner auto-pause, health probes |
| **M11** | Screening Question & Answer Bank | Complete | Persistent `screening_question_bank` table, modal UI, auto-sync |
| **M12** | Activity Run Logs & Modern Dashboard | Complete | Activity logs table, retry engine, modernized overview cards |
| **M13** | Question Bank Dedicated Page & Enhancements| Complete | Dedicated question bank page, filtering dismissed roles, batch question management, ChatGPT question answering with DB First protocol, WTF abort safeguard, and batch answer automation script |

---

## 3. Subsystem Architecture Matrix

| Layer | Primary Files | Responsibilities |
| :--- | :--- | :--- |
| **REST API** | `src/api/posts.py`, `src/api/tasks.py`, `src/api/stats.py`, `src/api/settings.py` | FastAPI endpoints, FIFO task triggers, status polling, settings |
| **Automation Services** | `src/services/automation_tasks.py`, `src/services/easy_apply_service.py`, `src/services/chatgpt_service.py`, `src/services/gmail_service.py` | Browser automation runners, watchdog monitors, rate limit safeguards |
| **Database** | `src/db/connection.py`, `src/db/posts.py`, `src/db/question_bank.py`, `src/db/activity_logs.py`, `src/db/settings.py`, `src/db/analytics.py` | Connection pooling, table migrations, relational CRUD operations |
| **Client UI (JS)** | `src/static/js/` (`app.js`, `state.js`, `api.js`, `easy_apply.js`, `question_bank.js`, `review.js`, `discovered.js`, `tasks.js`) | Modular ES components, state management, UI rendering, event listeners |
| **Styles (CSS)** | `src/static/css/` (`variables.css`, `base.css`, `layout.css`, `sidebar.css`, `easy_apply.css`, `question_bank.css`, etc.) | Design tokens, component stylesheets, responsive layout |
| **Templates** | `src/static/partials/` (`sidebar.html`, `topbar.html`, `tab_easy_apply.html`, `tab_question_bank.html`, `modals.html`, etc.) | Component partials dynamically compiled into `src/static/index.html` |

---

## 4. Technical Debt Ledger (`ponytail-debt`)

*Record deliberate simplifications marked with `shortcut:` or `ponytail:` comments here.*

| ID | Location | Shortcut Description | Planned Resolution |
| :--- | :--- | :--- | :--- |
| *None* | Workspace | Clean initial ledger established with Byten governance setup | Log newly introduced deliberate shortcuts here |

---

## 5. Maintenance Checklist

- [ ] Run `npx impeccable detect` before presenting major UI changes.
- [ ] Evaluate new features against Ponytail's 7-Step Necessity Ladder.
- [ ] Keep `CHANGELOG.md` updated under `## [Unreleased]`.
- [ ] Record structural architectural changes in `docs/adr/`.
- [ ] Run `graphify update .` after modifying codebase symbols or directory structure.
