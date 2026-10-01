# Reach Frontend Architecture Agent Guide (`src/static/`)

This directory houses the entire client presentation layer for Reach, organized into modular CSS, JavaScript, HTML partials, and Service Worker assets.

---

## Directory Navigation Matrix

| Directory / File | Type | Domain Scope | Designated Agent Guide |
|---|---|---|---|
| [`css/`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/) | Directory | Modular CSS stylesheets (12 modules): tokens, layout, sidebar, tables, review workspace, easy apply, modals, responsive breakpoints. | [`src/static/css/AGENTS.md`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/AGENTS.md) |
| [`js/`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/) | Directory | Modular client JavaScript (13 modules): state, utils, notifications, sidebar, api, discovered, review, easy apply, history, crawler, tasks, modals, analytics. | [`src/static/js/AGENTS.md`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/AGENTS.md) |
| [`partials/`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/) | Directory | HTML component partials (9 components): sidebar, topbar, tabs (analytics, discovered, review, easy apply, sent), task drawer, and modal overlays. | [`src/static/partials/AGENTS.md`](file:///Users/apple/Byten/linkedInScrapper/src/static/partials/AGENTS.md) |
| [`index_layout.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/index_layout.html) | File | Master HTML assembly template containing CSS imports, partial include directives, and script tags. | Edit this template when adding new global assets or partials. |
| [`index.html`](file:///Users/apple/Byten/linkedInScrapper/src/static/index.html) | File | Auto-synchronized standalone HTML generated dynamically by `src/app.py`. | **Do NOT edit directly.** Edit `index_layout.html` or `partials/`. |
| [`app.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/app.js) | File | Master client bootstrapper and event wire-up executing on `DOMContentLoaded`. | Clean coordinator loading modular scripts from `js/`. |
| [`style.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/style.css) | File | Master CSS bundle importing modular stylesheets from `css/`. | **Do NOT edit directly.** Edit files in `css/`. |
| [`sw.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/sw.js) | File | Root-scoped Service Worker handling system push notifications and notification click actions. | Served via root route `/sw.js` with `Service-Worker-Allowed: /`. |

---

## Agent Directives for Frontend

1. **No Monolithic Edits**: Never add code back into large legacy files. Always edit the specialized file in `css/`, `js/`, or `partials/`.
2. **Apply Link Directives**: The user explicitly rolled back the apply link button. Do NOT re-add application link buttons.
3. **Template Synchronization**: When adding or updating HTML markup, modify the files in `src/static/partials/`. The backend server dynamically compiles them into `index.html`.
