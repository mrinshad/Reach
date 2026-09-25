# Reach Client JavaScript Agent Guide (`src/static/js/`)

This directory contains the modular frontend client architecture decomposed from the monolithic 4,060-line `app.js`.

---

## JavaScript Modules Directory Matrix

| Script Module | Global Scope / Objects | Primary Domain Responsibilities |
|---|---|---|
| [`state.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/state.js) | `window.state`, `window.DEFAULT_OPPORTUNITY_*` | Global state variables, filters, active review post, selected IDs, configuration cache. |
| [`utils.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/utils.js) | `showConfirm`, `showSnackbar`, `showToast`, `showAlert`, `formatDateTime`, `escapeHtml`, `copyEmailToClipboard`, `copyJobDescription`, `copyEmailDraft` | Custom non-blocking modal dialogs, stacked expandable snackbar toasts, string escape, date formatters. |
| [`notifications.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/notifications.js) | `initNotificationSystem`, `playNotificationSound`, `triggerHapticVibration`, `sendAppNotification`, `toggleNotificationCenter` | Service Worker push listener, Web Audio harmonic double chime, navigator vibration, in-app notification center. |
| [`sidebar.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/sidebar.js) | `switchTab`, `toggleSidebarCollapse`, `initSidebarCollapse`, `jumpTo*` | Top-level tab switcher, responsive sidebar collapse/expand, mobile drawer, KPI card jump helpers. |
| [`api.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/api.js) | `fetchHealth`, `updateHealthPill`, `loadDashboardData`, `fetchStats`, `fetchSettings`, `handleResumeUpload` | REST API communication, live session health probes, KPI metrics updates, resume PDF uploader. |
| [`discovered.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/discovered.js) | `fetchDiscoveredPosts`, `renderPostsTable`, `renderPagination`, `applyFilters`, `clearDiscoveredFilters`, `toggleSort` | Discovered job table rendering, 2-tier search/experience filters, pagination, batch generation selection. |
| [`review.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/review.js) | `fetchReviewPosts`, `selectReviewPost`, `saveActiveDraftEdits`, `generateEmailForActiveDraft`, `sendActiveDraftDirectly`, `openActivePostInGmail`, `confirmCancelWithReason` | Review & drafts queue, AI draft editor, 1-click JD mail generation, direct Gmail dispatch, cancellation reasons. |
| [`easy_apply.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/easy_apply.js) | `fetchEasyApplyPosts`, `filterEasyApplyStatus`, `handleEasyTableSearch`, `triggerEasyApplyCrawl`, `triggerSingleEasyApply`, `toggleEasyStatusMenu`, `setEasyPostStatus`, `batchSetEasyStatus`, `setModalPostStatus`, `openEasyDetailsModal`, `closeEasyDetailsModal`, `openScreeningModal`, `closeScreeningModal`, `parseScreeningQuestions`, `triggerScreeningRescan`, `markScreeningAsReady`, `copyScreeningLink`, `copyEasyJobLink`, `batchCopyEasyLinks`, `batchDismissEasyJobs`, `batchApplySelectedEasyJobs`, `clearEasySelection` | LinkedIn Easy Apply & Direct Jobs workspace: crawling trigger, client-side filtering, fixed-position smart status dropdowns, batch status transitions, selection reset, details modal, dedicated Screening Questionnaire modal, and automated application dispatch. |
| [`history.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/history.js) | `fetchSentPosts`, `setOthersFilter`, `loadRejectionReasonsFilter`, `revertPostToDraft` | Sent & cancelled history table, dynamic rejection reason chips, history pagination, post draft restoration. |
| [`crawler.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/crawler.js) | `triggerSelectedCrawl`, `fetchScrapers`, `fetchLocations`, `generateSingleChatGPT`, `generateBatchChatGPT`, `markPostAsSpam` | Extensible crawler trigger, source selection (LinkedIn, Infopark), location hubs, spam reporting. |
| [`tasks.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/tasks.js) | `startTaskPolling`, `stopTaskPolling`, `pollTaskStatus`, `cancelQueuedTask`, `clearTaskQueue`, `showCrawlSummaryModal` | Sequential FIFO task queue drawer, live terminal log streaming, queue cancellation, crawl summary modal. |
| [`modals.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/modals.js) | `openPostModal`, `openAddJdModal`, `submitManualJd`, `openDirectOutreachModal`, `openSettingsModal`, `updateHeadlessUI`, `toggleQuickHeadless` | Dialog overlays (Job Details, Manual JD ingestion, Direct Recruiter Outreach, Settings, Headless switch). |
| [`analytics.js`](file:///Users/apple/Byten/linkedInScrapper/src/static/js/analytics.js) | `loadAnalytics`, `renderDailyAppliedChart`, `renderDailyScrapedChart`, `renderStatusBreakdownChart`, `setAnalyticsTimeframe` | Chart.js visualizer (application velocity, scraping inflow, status breakdown, reason distribution). |

---

## Agent Directives for Client JavaScript

1. **Global Scope Binding**: Every user-facing function invoked via inline HTML attributes (`onclick`, `onchange`, `onkeyup`) must be assigned to `window` (e.g. `window.switchTab = switchTab;`).
2. **Apply Link Directives**: The user explicitly rolled back the apply link button. Do NOT re-add application link buttons to tables or review views.
3. **No External Bundlers**: Reach uses clean, standard vanilla ES6 JavaScript natively in the browser without node build steps or webpack/vite compilation.
