# CSS Stylesheet Architecture & Selector Index (`src/static/css/AGENTS.md`)

This directory contains the modular styling system for the Reach web application.

## Stylesheet Directory

### 1. [`variables.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/variables.css)
- **Scope**: CSS Custom Properties (`:root`), Design Tokens.
- **Key Tokens**:
  - Surfaces: `--bg-body` (`#090d16`), `--bg-surface` (`#131b2e`), `--bg-card` (`#182238`), `--bg-input` (`#0c1220`).
  - Borders: `--border-subtle`, `--border-medium`, `--border-focus`.
  - Accents: `--accent-indigo` (`#6366f1`), `--accent-cyan` (`#06b6d4`), `--accent-emerald` (`#10b981`), `--accent-amber` (`#f59e0b`), `--accent-rose` (`#f43f5e`).
  - Typography: `--font-logo` (`Space Grotesk`), `--font-sans` (`Plus Jakarta Sans`), `--font-mono` (`JetBrains Mono`).
  - Geometry: `--radius-xs` (4px), `--radius-sm` (8px), `--radius-md` (12px), `--radius-lg` (16px).

### 2. [`base.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/base.css)
- **Scope**: Resets, typography, base buttons, badges, skeleton shimmer.
- **Key Classes**: `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-outline`, `.btn-icon`, `.badge`, `.badge-emerald`, `.badge-amber`, `.badge-rose`, `.skeleton`.

### 3. [`layout.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/layout.css)
- **Scope**: App shell, 100vh stationary layout, header topbar, notification dropdown.
- **Key Classes**:
  - Layout: `html, body { height: 100%; overflow: hidden; }`, `.app-layout`, `.app-main`.
  - Topbar: `.app-topbar`, `.topbar-left`, `.topbar-page-title`, `.topbar-right`, `.sidebar-topbar-toggle`.
  - Notification Center: `.notification-center-wrapper`, `.notification-bell-btn`, `.notification-badge`, `.notification-dropdown`, `.notification-item`.

### 4. [`sidebar.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/sidebar.css)
- **Scope**: Collapsible navigation sidebar, 44x44 unsquashed buttons, crawler launch card, health indicators.
- **Key Classes**:
  - Expanded: `.app-sidebar` (270px width), `.sidebar-brand`, `.sidebar-section`, `.sidebar-nav`, `.nav-item`.
  - Collapsed: `.app-sidebar.collapsed` (68px width), `.nav-item` (`44px × 44px` rounded squares), `.btn-crawl-sidebar` (`44px × 44px`), `.resume-pill-sidebar` (`44px × 44px`), `.sidebar-sys-btn` (`44px × 44px`).
  - Navigation Counts: `.badge-count` (`#navCountDiscovered`, `#navCountReview`).
  - Crawler Trigger: `.crawler-sidebar-card`, `.crawler-source-select`, `.crawler-location-select`, `.btn-crawl-sidebar`.

### 5. [`dashboard.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/dashboard.css)
- **Scope**: Overview dashboard tab (`#tabAnalytics`), KPI summary cards, Chart.js layouts, Headless browser mode switch.
- **Key Classes**:
  - KPI Cards: `.kpi-card`, `.kpi-val`, `.kpi-label`, `.clickable-kpi`, `.kpi-jump-action`.
  - Charts: `.chart-card`, `.chart-wrapper`, `.chart-grid`.
  - Headless Switch: `.headless-toggle-card`, `.toggle-switch-ios`, `.toggle-slider-ios`.
  - Health: `.health-grid`, `.health-card`, `.health-status-dot`.

### 6. [`discovered.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/discovered.css)
- **Scope**: Discovered jobs tab (`#tabDiscovered`), 2-tier search/filter toolbar, data tables, pagination.
- **Key Classes**:
  - Toolbar: `.toolbar-2tier`, `.search-input-group`, `.filter-select-group`, `.btn-filter-pill`.
  - Table: `.data-table`, `th`, `td`, `.row-actions`, `.sortable-header`.
  - Pagination: `.table-footer`, `.pagination-controls`, `.page-btn`.

### 7. [`review.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/review.css)
- **Scope**: Review & drafts workspace (`#tabReview`), queue sidebar, natural post scrolling, email editor, JD mail generator.
- **Key Classes**:
  - Queue: `.review-split`, `.review-queue`, `.review-queue-item`, `.review-batch-bar`.
  - Workspace: `.review-main`, `.review-candidate-card`, `.post-scroll` (natural expander without nested scroll lock).
  - Mail Generator: `.btn-generate-mail-jd` (accent indigo button beside email body header).
  - Draft Editor: `.email-draft-container`, `.email-subject-input`, `.email-body-textarea`, `.review-actions-bar`.

### 8. [`history.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/history.css)
- **Scope**: Sent and cancelled history tab (`#tabSent`), status filter tabs, sent emails data table.
- **Key Classes**: `.history-filter-bar`, `.history-table`, `.status-badge-sent`, `.status-badge-cancelled`, `.reason-pill`.

### 9. [`tasks.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/tasks.css)
- **Scope**: Background automation tasks, live task drawer, terminal log monitor, alert banner.
- **Key Classes**: `.task-queue-section`, `.task-queue-card`, `.queue-pos-badge`, `.btn-cancel-queue-item`, `.terminal-logs`.

### 10. [`modals.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/modals.css)
- **Scope**: Modal overlays, dialog boxes, settings, add JD, direct outreach, notification unblock help, toasts.
- **Key Classes**: `.modal-overlay`, `.modal-box`, `.modal-top`, `.modal-body`, `.modal-bottom`, `.notif-modal-box`, `.notif-status-grid`, `.toast-container`, `.toast`.

### 11. [`easy_apply.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/easy_apply.css)
- **Scope**: LinkedIn Easy Apply & Direct Jobs workspace (`#tabEasyApply`), crawler header, KPI ribbon, floating batch banner, fixed table layout, interactive status dropdowns, and details modal.
- **Key Classes**:
  - Header & Form: `.easy-apply-header`, `.easy-crawler-form`, `.easy-input`, `.btn-easy-crawl`.
  - KPI Metrics: `.easy-kpi-ribbon`, `.easy-kpi-card`, `.kpi-num`, `.kpi-lbl`.
  - Filters & Search: `.easy-filter-bar`, `.status-pill-group`, `.filter-pill`, `.easy-search-box`.
  - Batch Actions: `.easy-batch-banner`, `.batch-info`, `.batch-banner-right`, `.batch-select-badge`, `.batch-transition-lbl`, `.batch-divider`, `.btn-batch-close`.
  - Table: `#tabEasyApply .reach-table`, `.easy-role-cell`, `.easy-job-title-link`, `.easy-actions-cell`.
  - Status Menu: `.easy-status-wrap`, `.tag-easy-status-btn`, `.status-caret`, `.easy-status-menu`, `.status-menu-opt`.
  - Details Modal: `.easy-modal-meta-grid`, `.easy-jd-box`, `.modal-status-toggle-wrap`, `.btn-modal-status-chip`.

### 12. [`responsive.css`](file:///Users/apple/Byten/linkedInScrapper/src/static/css/responsive.css)
- **Scope**: Media queries (`<= 1024px`, `<= 768px`, `<= 480px`), off-canvas mobile drawer, compact headers, mobile cards.
- **Key Breakpoints**:
  - `@media (max-width: 1024px)`: Compact sidebar (240px) and tablet grid adjustments.
  - `@media (max-width: 768px)`: Off-canvas sliding drawer (`.app-sidebar.mobile-open`), `.sidebar-backdrop`, mobile topbar, stacked 2x2 cards, responsive table cards.
  - `@media (max-width: 480px)`: Small smartphone adjustments, full-width modals, touch target padding.
