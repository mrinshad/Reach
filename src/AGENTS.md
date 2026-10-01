# Reach Backend & Automation Architecture (`src/AGENTS.md`)

This directory contains the FastAPI server, background Playwright automation, database abstraction, and web presentation layer.

---

## Subsystem Navigation Matrix

| Subsystem / Directory | Responsibility | Primary Entrypoints & Modules | Designated Agent Guide |
|---|---|---|---|
| [`src/api/`](file:///Users/apple/Byten/linkedInScrapper/src/api/) | FastAPI REST API routers decomposed by domain (posts, tasks, stats, settings). | `posts.py`, `tasks.py`, `stats.py`, `settings.py`, `models.py` | [`src/api/AGENTS.md`](file:///Users/apple/Byten/linkedInScrapper/src/api/AGENTS.md) |
| [`src/services/`](file:///Users/apple/Byten/linkedInScrapper/src/services/) | Sequential FIFO task queue engine, Playwright browser connectors, ChatGPT Custom GPT generator, Gmail automation, LinkedIn Easy Apply crawler, and health probes. | `automation_tasks.py`, `easy_apply_service.py`, `chatgpt_service.py`, `gmail_service.py`, `firefox_connector.py`, `health_service.py`, `experience_extractor.py` | [`src/services/AGENTS.md`](file:///Users/apple/Byten/linkedInScrapper/src/services/AGENTS.md) |
| [`src/db/`](file:///Users/apple/Byten/linkedInScrapper/src/db/) | PostgreSQL database models, connection pooling, migrations, post queries, settings, and analytics. | `connection.py`, `posts.py`, `settings.py`, `analytics.py` | [`src/db/AGENTS.md`](file:///Users/apple/Byten/linkedInScrapper/src/db/AGENTS.md) |
| [`src/static/`](file:///Users/apple/Byten/linkedInScrapper/src/static/) | Frontend UI assets: modular stylesheets (`css/`), client scripts (`js/`), component partials (`partials/`), and Service Worker (`sw.js`). | `index_layout.html`, `app.js`, `style.css`, `sw.js` | [`src/static/AGENTS.md`](file:///Users/apple/Byten/linkedInScrapper/src/static/AGENTS.md) |
| [`src/app.py`](file:///Users/apple/Byten/linkedInScrapper/src/app.py) | Master FastAPI application root. Configures CORS, development no-cache middleware, dynamic template compiler, and mounts `api_router`. | `app`, `serve_index`, `get_rendered_index_html` | Root Entrypoint |
| [`src/config.py`](file:///Users/apple/Byten/linkedInScrapper/src/config.py) | Configuration manager for persistent database settings and local fallback defaults. | `load_config`, `save_config`, `is_headless` | Global Config |

---

## Agent Directives for Backend

1. **Sequential Task Execution**: Automation operations must be enqueued via `task_manager.enqueue_task(...)`. Never launch concurrent Playwright browser sessions on the persistent Firefox profile.
2. **Clean Modular Imports**: All subsystems and CLI scripts in `scripts/` import directly from designated packages (`src.services.*`, `src.db.*`, `src.api.*`). No legacy shims are used.
3. **Database-First Data Operations**: Multi-parameter search, pagination, and sorting must be executed in PostgreSQL queries (`src/db/posts.py`), never filtered in-memory in Python.
