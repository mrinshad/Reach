# Reach API Router Agent Guide (`src/api/`)

This directory contains the modular FastAPI endpoint routers decomposed from the monolithic `src/app.py`.

---

## API Router Directory Matrix

| Router Module | Route Prefix | Endpoints | Domain Responsibility |
|---|---|---|---|
| [`posts.py`](file:///Users/apple/Byten/linkedInScrapper/src/api/posts.py) | `/api` | `POST /api/posts/manual`, `GET /api/posts`, `GET /api/locations`, `GET /api/reasons`, `GET /api/posts/{id}`, `PUT /api/posts/{id}`, `POST /api/posts/{id}/status`, `POST /api/posts/status-batch`, `POST /api/posts/{id}/move-to-review`, `POST /api/posts/{id}/mark-sent`, `POST /api/posts/{id}/revert`, `POST /api/posts/{id}/reject`, `POST /api/posts/{id}/spam` | Discovered job listings, filtering, pagination, manual JD input, post status lifecycle transitions (Ready, Screening, Applied, Failed, Not Found). |
| [`tasks.py`](file:///Users/apple/Byten/linkedInScrapper/src/api/tasks.py) | `/api` | `POST /api/generate-email/{id}`, `POST /api/generate-batch`, `POST /api/open-gmail/{id}`, `POST /api/send-direct/{id}`, `POST /api/send-batch`, `POST /api/direct-outreach`, `POST /api/scrape/infopark`, `POST /api/scrape/linkedin`, `POST /api/scrape/easy-apply`, `POST /api/scrape/easy-apply/batch`, `POST /api/easy-apply/{id}`, `GET /api/scrapers`, `POST /api/scrape`, `GET /api/tasks/status`, `POST /api/tasks/clear`, `POST /api/tasks/queue/cancel/{id}`, `POST /api/tasks/queue/clear` | Sequential FIFO task queue submission, active queue polling, log terminal streaming, cancellation. |
| [`stats.py`](file:///Users/apple/Byten/linkedInScrapper/src/api/stats.py) | `/api` | `GET /api/health`, `GET /api/stats`, `GET /api/analytics` | Live session health checks (LinkedIn, ChatGPT, Gmail, DB), KPI counters, historical chart data. |
| [`settings.py`](file:///Users/apple/Byten/linkedInScrapper/src/api/settings.py) | `/api` | `POST /api/resume/upload`, `GET /api/settings`, `POST /api/settings`, `POST /api/settings/headless` | Configuration retrieval, pacing adjustments, Headless on/off switch, resume document uploads. |
| [`models.py`](file:///Users/apple/Byten/linkedInScrapper/src/api/models.py) | N/A | Pydantic Request Models: `ManualPostPayload`, `UpdateEmailPayload`, `UpdateStatusPayload`, `BatchStatusPayload`, `RejectPostPayload`, `SpamPostPayload`, `GenerateBatchPayload`, `SendBatchPayload`, `DirectOutreachPayload`, `SettingsPayload`, `HeadlessTogglePayload`, `ScrapePayload`, `EasyApplyBatchScrapePayload` | Shared schemas, validation rules, and default constants. |

---

## Agent Directives for API Modifications

1. **Routing Registration**: All new routers must be mounted in [`src/api/__init__.py`](file:///Users/apple/Byten/linkedInScrapper/src/api/__init__.py) into `api_router`.
2. **Backward Contract Compatibility**: Never change the JSON response structure of existing endpoints. Frontend client JavaScript relies strictly on fields like `res.success`, `res.ok`, `res.data`, `res.posts`, `res.total`.
3. **Database-First Operations**: Keep sorting, pagination, and multi-parameter filtering in PostgreSQL via `src/db/posts.py`. Do not fetch all posts to filter in memory.
