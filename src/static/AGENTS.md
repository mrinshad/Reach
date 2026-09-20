# Frontend Architecture & Component Router (`src/static/AGENTS.md`)

This guide directs AI agents working on Reach's frontend interface.

## Quick Lookup: DOM Elements, Styles & Methods

| Target UI Element | Element ID / Class | HTML Partial (`partials/`) | CSS Module (`css/`) | JS Handler (`app.js`) |
|---|---|---|---|---|
| Sidebar Root | `#appSidebar` | `sidebar.html` | `sidebar.css` | `toggleSidebarCollapse()` |
| Sidebar Nav Buttons | `.nav-item`, `#btnTabAnalytics`, etc. | `sidebar.html` | `sidebar.css` | `switchTab(tabId)` |
| Sidebar Unsquashed Buttons | `.app-sidebar.collapsed .nav-item` | `sidebar.html` | `sidebar.css` | `44px × 44px` layout |
| Sidebar Pending Badges | `.badge-count`, `#navCountDiscovered` | `sidebar.html` | `sidebar.css` | `updateSidebarBadgeCounts()` |
| Crawler Selector | `#crawlerSourceSelect`, `#crawlerLocationSelect` | `sidebar.html` | `sidebar.css` | `handleCrawlerSourceChange()` |
| Start Crawl Button | `#btnStartCrawl` | `sidebar.html` | `sidebar.css` | `triggerSelectedCrawl()` |
| App Main Scroll Area | `#appMain`, `.app-main` | `index_layout.html` | `layout.css` | 100vh stationary container |
| Sticky Header Bar | `.app-topbar` | `topbar.html` | `layout.css` | Header breadcrumb & actions |
| Notification Bell | `#btnNotifBell`, `.notification-badge` | `topbar.html` | `layout.css` | `toggleNotificationDropdown()` |
| Notification Dropdown | `#notifDropdown` | `topbar.html` | `layout.css` | `renderNotifications()` |
| Notification Help Modal | `#notifHelpModal` | `modals.html` | `modals.css` | `openNotificationHelpModal()` |
| Headless Browser Switch | `#headlessModeSwitch` | `tab_analytics.html` | `dashboard.css` | `toggleHeadlessMode()` |
| Dashboard KPI Cards | `.kpi-card`, `.clickable-kpi` | `tab_analytics.html` | `dashboard.css` | `fetchAnalyticsSummary()` |
| Analytics Charts | `#chartTrends`, `#chartFunnel` | `tab_analytics.html` | `dashboard.css` | `renderCharts()` |
| Discovered Search Bar | `#searchPostsInput` | `tab_discovered.html` | `discovered.css` | `filterPosts()` |
| Discovered Posts Table | `#postsTable`, `#postsTableBody` | `tab_discovered.html` | `discovered.css` | `renderPostsTable()` |
| Discovered Pagination | `#paginationControls` | `tab_discovered.html` | `discovered.css` | `changePage(newPage)` |
| Review Queue Sidebar | `.review-queue`, `#reviewQueueList` | `tab_review.html` | `review.css` | `loadReviewQueue()` |
| Review Queue Batch Bar | `#reviewBatchBar` | `tab_review.html` | `review.css` | `toggleBatchSelection()` |
| Candidate Profile Card | `#reviewCandidateCard` | `tab_review.html` | `review.css` | `renderReviewItem()` |
| Post Scroll Natural Area | `.post-scroll` | `tab_review.html` | `review.css` | Auto-expanding scroll container |
| Generate Mail from JD | `#btnGenerateMailJd` | `tab_review.html` | `review.css` | `generateEmailFromJd(postId)` |
| Email Draft Editor | `#reviewEmailSubject`, `#reviewEmailBody`| `tab_review.html` | `review.css` | `handleDraftInput()` |
| Outreach History Table | `#sentTableBody` | `tab_sent.html` | `history.css` | `loadSentPosts()` |
| Task Drawer & Live Console | `.task-queue-section`, `#taskQueueList` | `task_drawer.html` | `tasks.css` | `pollActiveTasks()` |
| Modals (All 7 Dialogs) | `.modal-overlay` | `modals.html` | `modals.css` | `openModal(id)`, `closeModal(id)` |
| Toast Snackbars | `#toastContainer`, `.toast` | `index_layout.html` | `modals.css` | `showToast(msg, type)` |
| Mobile Backdrop & Drawer | `#sidebarBackdrop`, `.app-sidebar` | `index_layout.html` | `responsive.css` | `toggleMobileSidebar()` |

## Best Practices
1. **Never edit `style.css` directly**: All style rules are segregated in `css/*.css`.
2. **Never edit `index.html` directly**: Modify `partials/*.html` or `index_layout.html`.
3. **Always preserve IDs**: The JavaScript application logic relies on exact element IDs.
