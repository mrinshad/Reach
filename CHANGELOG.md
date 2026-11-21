# Changelog

All notable changes to the Reach project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Dual-Option Dismissal System Across All Workflows** (`src/api/models.py`, `src/api/posts.py`, `src/static/partials/modals.html`, `src/static/js/review.js`, `src/static/js/discovered.js`, `src/static/js/easy_apply.js`, `src/static/js/indeed_apply.js`):
  - Implemented dual-option dismissal across all 4 workflows (Discovered Jobs, Review & Drafts, LinkedIn Easy Apply, Indeed Apply) for both individual rows and bulk selections.
  - Users can choose either **Dismiss Only** (dismisses the post/application without adding the title to the blacklist) or **Dismiss & Add to Dismissed Roles** (dismisses the item and permanently adds the headline to `dismissed_roles` so all future crawlers skip it).
  - Updated Pydantic schemas (`RejectPostPayload`, `BatchPostActionPayload`, `UpdateStatusPayload`, `BatchStatusPayload`) and REST routes (`/api/posts/{id}/reject`, `/api/posts/reject-batch`, `/api/posts/{id}/status`, `/api/posts/status-batch`) to support `add_to_dismissed_roles: Optional[bool] = False`.
  - Enhanced `#cancelReasonModal` with an explicit toggle checkbox (`#checkAddToDismissedRoles`) and two dedicated action buttons (`#btnDismissPostOnly` and `#btnDismissAndBlacklist`).
  - Added dual dismissal actions in row status dropdown menus across LinkedIn Easy Apply and Indeed Apply (`✕ Dismiss Job Only` and `🚫 Dismiss & Add Role`).
  - Wired batch toolbars across all workspaces to route through the dual-option modal, ensuring smooth undo toasts and live table re-fetching.

### Added
- **3-Layer Dismissal Audit & Core Tech Restoration** (`src/db/dismissed_roles.py`, `src/db/posts.py`):
  - Completed an exhaustive 3-layer audit across all 1,818 entries in `dismissed_roles` (Layer 1: Core Software Development & Engineering, Layer 2: Modern Tech Stack / Cloud / AI / DevOps / QA, Layer 3: Tech Internships / Trainees / Freshers).
  - Restored **523 verified software engineering and developer roles** by removing them from `dismissed_roles`.
  - Reinstated **102 candidate job posts** that had been blocked by past accidental role blacklists back into active `DISCOVERED` status with zero dismissal flags.
- **Anti-Blacklisting Safeguards & Circumstantial Filters** (`src/db/dismissed_roles.py`, `src/db/posts.py`):
  - Stopped automatic insertion of `author_headline` into `dismissed_roles` on post status updates (`REJECTED` / `CANCELLED`). Individual application rejections (due to experience ceilings, location/onsite requirements, multi-step questionnaires, or user cancellations) now stay isolated to that specific post and never blacklist the title globally.
  - Implemented `is_protected_tech_role()` and `is_circumstantial_reason()` in `src/db/dismissed_roles.py` to prevent future attempts to blacklist core developer titles or post-level circumstantial conditions.
- **Zero-Strain Scraper Dismissal Architecture**:
  - Verified and streamlined title dismissal across all 5 crawlers (`linkedin_posts_search.py`, `linkedin_job_search.py`, `easy_apply_service.py`, `indeed_apply_service.py`, `infopark_jobs_search.py`) and `upsert_post`.
  - Scrapers query ONLY the clean, indexed `dismissed_roles` table via in-memory preloaded sets (`get_dismissed_role_titles()`), eliminating heavy queries against the `posts` table history for fast, low-strain discovery.

### Added
- Prominent Batch Actions Bar for Dismissed Roles (`src/static/partials/tab_dismissed_roles.html`, `src/static/css/dismissed_roles.css`, `src/static/js/dismissed_roles.js`):
  - Added a dedicated, vibrant `.batch-actions-bar#dismissedBatchBanner` positioned directly above the table that automatically activates when multiple roles are checked.
  - Displays dynamic selection count (`X roles selected`), a primary 1-click **Restore / Un-dismiss** button to reinstate roles in bulk, and a **Clear Selection** button.
  - Kept the toolbar batch restore button in continuous synchronization with the dedicated banner.
- Universal Top Pagination Bar with Rows Selector & Next/Prev Across All Tables (`src/static/partials/`, `src/static/css/discovered.css`, `src/static/css/responsive.css`, `src/static/js/`):
  - Standardized `.table-header-bar` pagination atop every data table in the system:
    1. **Discovered Posts** (`tabDiscovered`)
    2. **Review & Drafts** (`tabReview`)
    3. **Sent & Cancelled Outreach** (`tabSent` - Applications)
    4. **Activity & Run Logs** (`tabSent` - Logs)
    5. **Dismissed Roles Registry** (`tabDismissedRoles`)
    6. **LinkedIn Easy Apply** (`tabEasyApply`)
    7. **Indeed Apply Portal** (`tabIndeedApply`)
  - Provides instant access to the rows-per-page selector (`Rows: 10/25/50/100/All`) and previous/next navigation buttons at the top of tables without requiring users to scroll to the bottom.
  - Kept top and bottom rows selectors, page info indicators, and page button states in two-way synchronization.
- Dismissed Roles Registry & Management Workspace (`src/db/dismissed_roles.py`, `src/api/dismissed_roles.py`, `src/static/partials/tab_dismissed_roles.html`, `src/static/js/dismissed_roles.js`, `src/static/css/dismissed_roles.css`):
  - Created a dedicated PostgreSQL database table `dismissed_roles` to persist excluded roles across all crawler channels (LinkedIn Posts, LinkedIn Easy Apply, Indeed Apply, Infopark, Manual) with `id`, `role_title`, `normalized_title`, `source`, `reason`, `occurrences`, `created_at`, and `updated_at`.
  - Auto-seeded historical rejected roles (1,830 unique roles) from the `posts` table into `dismissed_roles` while safeguarding core developer titles (Full Stack, Backend, Frontend, Python, React).
  - Built a dedicated UI section and navigation item (`#tabDismissedRoles` / `#btnTabDismissedRoles`) with real-time KPI ribbon counts per source channel, search, source filtering, and sorting (`order by name` A-Z by default, with date and occurrence toggles).
  - Displays when each role was last added/updated along with its origin source channel and occurrence count.
  - Added single and batch restore/delete actions so users can easily un-dismiss any accidentally excluded roles, as well as an "Add Dismissed Role" modal for manual exclusion entries.
  - Integrated with all scrapers (`linkedin_posts_search.py`, `linkedin_job_search.py`, `easy_apply_service.py`, `indeed_apply_service.py`, `infopark_jobs_search.py`) so background crawls skip matching dismissed roles automatically.

### Changed
- UI & Responsiveness Overhaul for Dismissed Roles (`src/static/partials/tab_dismissed_roles.html`, `src/static/css/dismissed_roles.css`, `src/static/css/responsive.css`, `src/static/js/dismissed_roles.js`):
  - Completely aligned the Dismissed Roles workspace with the authentic Reach design system (`docs/DESIGN.md`), removing non-standard oversized headers and multi-color card ribbons.
  - Replaced custom layout with Reach's canonical `.toolbar` structure: interactive source filter pills on the left (`All Sources`, `LinkedIn`, `Easy Apply`, `Indeed`, `Infopark`, `Manual`) and clean controls on the right (batch restore, add role, sync history, order dropdown, search input, and clear filters).
  - Adopted standard `.table-card` and `table.reach-table` architecture with uniform font scales (`0.82rem` body, `var(--font-mono)` for dates/occurrences, uppercase muted headers), subtle row hover, and selection highlighting.
  - Added full mobile/tablet responsive styling under `@media (max-width: 768px)` in `responsive.css`, transforming tabular rows into native stacked cards with top-right anchored checkboxes, title emphasis, contextual reason card snippets, and bottom action bars.
  - Standardized table footer pagination with `.page-btn` controls, rows-per-page selector, and dynamic page calculations.
- Default Filter to Generated in Review & Drafts (`src/static/partials/tab_review.html`, `src/static/js/state.js`, `src/static/js/review.js`, `src/static/js/sidebar.js`):
  - Set `✨ Generated` as the active default filter pill upon loading the Review & Drafts workspace (`state.reviewFilter: 'GENERATED'`).
  - Aligned table results and default view directly with the sidebar badge count (`draftsReady`), presenting generated emails ready for review and dispatch immediately.
  - Updated filter clearing (`clearReviewFilters`) and jump link (`jumpToReviewDrafts`) behaviors to preserve `GENERATED` as the baseline view.

### Fixed
- Re-exported Missing Dismissed Role Filter Functions in `src/db/__init__.py`:
  - Resolved `ImportError: cannot import name 'get_dismissed_role_titles' from 'src.db'` in `scripts/linkedin_posts_search.py` and `scripts/infopark_jobs_search.py`.
  - Added `get_dismissed_role_titles`, `check_title_previously_dismissed`, and `normalize_job_title` to `src/db/__init__.py` imports and `__all__`.
- Automated ChatGPT Email Draft Artifact Stripping & Signature Trimming (`src/services/chatgpt_service.py`, `src/api/posts.py`, `src/static/js/utils.js`, `src/static/js/review.js`, `src/static/partials/tab_review.html`):
  - Automatically strip leading ChatGPT / Canvas UI artifacts (such as solitary "Send", "Send email", "Connect email", "Recipients", "Email Draft:", "To:", "From:") from the beginning of generated or pasted email drafts.
  - Automatically detect the candidate's closing signature block (sign-off like "Regards," + candidate name "Mohammed Rinshad P" + optional title, phone, email, and LinkedIn/GitHub links) and cleanly trim away all trailing assistant commentary ("Let me know if you need changes", "Hope this helps", "Note:", etc.) and Canvas artifact buttons ("Copy", "Edit", "Regenerate").
  - Added smart clipboard paste handlers in Review & Drafts workspace on both Email Body (`#draftBody`) and Subject (`#draftSubject`) fields to detect ChatGPT outputs, extract the subject line, clean the body, and format fields automatically on copy-paste.
  - Added a dedicated "Clean" micro button in the Review & Drafts workspace drawer header for 1-click manual sanitization.

### Fixed
- ChatGPT Auto-Cancellation Rejection Reason Preservation (`src/services/chatgpt_service.py`):
  - Restored saving the authentic reason directly returned by ChatGPT (e.g., "Java Specialized", "SEO role", "US onsite role", ".NET Specialized", "Salesforce Specialized") when posts are auto-cancelled during email generation, instead of overriding them into generic taxonomy buckets.
  - Upgraded `clean_and_truncate_reason` and `extract_unsuitable_reason` to cleanly strip boilerplate prefixes (`UNSUITABLE_JD`, `❌`, `Not suitable —`, `Reason:`) and handle multiline assistant responses.
  - Backfilled and updated all 446 existing auto-cancelled posts in the database with their respective reasons directly from ChatGPT's response bodies.

### Fixed
- Detail Drawer Navbar Overlap & Internal Table Scroll (`src/static/partials/tab_discovered.html`, `src/static/partials/tab_review.html`, `src/static/css/discovered.css`, `src/static/css/review.css`, `src/static/css/layout.css`):
  - Corrected sticky clearance for `.discovered-detail-drawer` and `.review-email-drawer` to `top: calc(73px + 1rem)` with `z-index: 35`, stopping cleanly below the 73px topbar (`z-index: 50`) without overlapping during vertical scrolling.
  - Wrapped Discovered Jobs and Review & Drafts tables inside `.table-scroll-container` with sticky `thead th` headers (`z-index: 10`), isolating mousewheel scrolling to the table rows until boundaries are reached and keeping the outer layout stationary.

### Added
- Dismissal UX Enhancements & Drawer Advance to Next Row (`src/static/partials/modals.html`, `src/static/partials/tab_discovered.html`, `src/static/js/review.js`, `src/static/js/discovered.js`, `src/static/js/crawler.js`):
  - Standardized Dismiss Button & Default Reason: renamed modal title to "Dismiss Post" and confirm button to "✕ Dismiss" (removing "Dismiss as Scam"), while selecting "Irrelevant tech stack" as the default active chip and input value. Scam and Potential Scam remain accessible as secondary chips in the quick reasons grid.
  - Added Dismiss Action to Side Detail Drawer: integrated a dedicated `[✕ Dismiss]` button directly into the drawer action bar (`#btnDrawerDismissDiscovered`), allowing one-click dismissal while reviewing job details.
  - Automatic Advance to Next Row: captured post row index prior to rejection and database re-fetch. Upon dismissing a post that was open in the window (either in Discovered Jobs or Review & Drafts), the drawer immediately advances to the next row in the list with active row highlighting and updated recruiter details, rather than continuing to display the dismissed post. Closes smoothly if the queue becomes empty.
- Discovered Toolbar Layout Re-architecture & Active Filter Chips Bar (`src/static/partials/tab_discovered.html`, `src/static/css/discovered.css`, `src/static/js/discovered.js`, `src/static/js/history.js`):
  - Fixed Reasons Dropdown Overflow: restricted `#selectReasonFilterDiscovered` to a clean compact width (`max-width: 140px`) with CSS text-overflow ellipsis, preventing long dismissal reason strings from expanding or overflowing outside the toolbar card.
  - Aligned Row 3 Controls with Vertical Separator: consolidated `Reason` dropdown, a vertical divider (`.toolbar-separator`), `Dates`, `From - To` date range pickers, `Sort`, `Results Badge`, and `✕ Clear Filters` onto a unified horizontal row.
  - Sneak Peek Truncation & Hover Title: selected reasons display a clean preview inside the dropdown (`..`), while hover tooltips and title attributes provide the full reason name.
  - Active Filter Chips Bar (`#discoveredActiveFiltersBar`): introduced a dedicated active filters bar beneath the toolbar that dynamically renders badges for all active criteria (`Reason`, `Location`, `Experience`, `Source`, `Status`, `Date`, `Search`) with individual `✕` close buttons and a "Clear all" shortcut to remove active filters instantly.
- Manual Auto-Dismiss Database Transaction:
  - Evaluated and classified all 511 active Discovered outreach posts, automatically dismissing 63 out-of-scope non-developer roles (DevOps, QA, Civil/Mechanical, HR/Sales, ERP, and Bench Sales/Hotlists) with `status = 'REJECTED'`, `is_dismissed = TRUE`, and categorized reasons.
  - Strictly safeguarded all core software engineering roles (Full Stack, Backend, Frontend, Python, Java, React, Node, AI/LLM), leaving exactly 448 curated developer jobs in the active queue.

### Fixed
- ChatGPT Premature Message Dispatch Bug (`src/services/chatgpt_service.py`):
  - Resolved issue where ChatGPT submitted prompts before the Job Description was completely entered: `page.keyboard.type(prompt_text)` was converting newline characters (`\n`) into unshifted `Enter` keydown events, triggering ChatGPT's composer submit listener after only the first line/heading was typed.
  - Upgraded prompt insertion to use ProseMirror-native synthetic `DataTransfer` paste event and `page.keyboard.insert_text()` (which sends input events without bare `Enter` keypresses).
  - Guaranteed that any line-by-line fallback utilizes `Shift+Enter` exclusively, adding clean paragraph linebreaks in ChatGPT without triggering premature message dispatch.

### Added
- Discovered Jobs Docked Side Detail Drawer (`src/static/partials/tab_discovered.html`, `src/static/css/discovered.css`, `src/static/js/discovered.js`):
  - Added docked right-side detail drawer matching the Review & Drafts workspace: clicking any row in the Discovered table smoothly opens a clean, focused window displaying exclusively the Job Description (JD), Contact Email, Contact Number, "Generate Mail" button, and "Review" button.
  - Integrated 1-click clipboard copy triggers for Email, Phone, and full JD text, active row highlighting (`.active-row`), sticky positioning beside table rows, and seamless dismissal via the close button (`✕`) or `Escape` key.
- Discovery Table Contact Phone & Recruiter Preview Modal Trigger (`src/static/partials/tab_discovered.html`, `src/static/css/discovered.css`, `src/static/js/discovered.js`, `src/static/js/utils.js`):
  - Added dedicated `Contact Number` (Phone) column to the Discovered Jobs table, replacing the old text snippet column.
  - Implemented `.phone-copy-pill` with phone icon, high-contrast cyan/sky-blue badge styling, and one-click clipboard copying via `copyPhoneToClipboard()`.
  - Converted Recruiter / Author names into interactive preview triggers (`.recruiter-name.clickable-preview` with subtle cursor pointer, underline, and indigo hover state) that open the complete job details dialog modal (`openPostModal`) upon clicking.
- Auto-Dismissed Roles Filtering in Discovery Crawlers & Ingestion (`scripts/infopark_jobs_search.py`, `scripts/linkedin_posts_search.py`, `src/db/posts.py`, `src/services/experience_extractor.py`, `src/db/connection.py`):
  - Integrated the dismissed-role pre-check filter used in LinkedIn Easy Apply into the discovery scrapers (Infopark Kochi and LinkedIn hiring posts crawler).
  - Preloads all previously dismissed / rejected role titles from the database (`get_dismissed_role_titles`) and evaluates each candidate role with `check_title_previously_dismissed()`.
  - Roles matching dismissed patterns are automatically marked as `is_dismissed = TRUE`, `status = 'REJECTED'`, and `rejection_reason = "Auto-dismissed: Matches previously dismissed role '{title}'"`, preventing rejected titles from cluttering the active Discovered feed.
  - Implemented regex phone number extraction (`extract_phone_numbers`) in `src/services/experience_extractor.py`, extracting labeled WhatsApp/mobile numbers and international digits with deduplication, persisted in `posts.contact_phones TEXT[]`.

### Fixed
- LinkedIn Easy Apply Button Click Timeout & Multi-Tab Isolation (`src/services/easy_apply_service.py`):
  - Fixed recurring `Locator.click: Timeout 4000ms exceeded` error when opening LinkedIn Easy Apply modals by introducing `safe_click_button()`: center-scrolls elements into view with `{ block: 'center', inline: 'nearest' }` to prevent occlusion by LinkedIn's sticky `.global-nav` header.
  - Added `no_wait_after=True` to prevent Playwright from stalling/timing out on trailing background GraphQL/telemetry network activity initiated by LinkedIn's React app.
  - Implemented automatic fallback to direct JavaScript DOM click (`el.scrollIntoView()`, `el.dispatchEvent(new MouseEvent(...))`, `el.click()`) whenever Playwright coordinate hit-testing or focus stalls.
  - Added multi-tab isolation and foregrounding in `apply_to_batch_easy_apply_posts`: automatically closes auxiliary tabs/popups opened during prior job submissions and brings the main page to front via `page.bring_to_front()` before processing each queued job.
  - Updated dialog detection in `execute_easy_apply` to recognize LinkedIn's modern component layout (`button[aria-label='Dismiss']`, `button:has-text('Next')`, `h2:has-text('Apply to')`).

### Added
- Review & Drafts Section Redesign (`src/static/partials/tab_review.html`, `src/static/css/review.css`, `src/static/js/review.js`, `src/db/posts.py`):
  - Unified Outreach History & Drafts Table: replaced the cramped split layout with a full-width paginated data table showing the complete history of generated emails, pending outreach roles, and sent emails with dedicated status badges (`✓ Generated`, `⏳ Yet to Generate`, `✉ Sent`, `🚫 Cancelled`).
  - Status Filter Pills: added quick toggle pills for `All Outreach`, `✨ Generated`, `⏳ Yet to Generate`, and `✉ Sent History` with live post counts, date range filters, and source filters.
  - Docked Right-Side Email Window: clicking any row in the table smoothly opens a dedicated, docked side drawer on the right displaying exclusively the generated outreach email, recipient email, subject line, body editor with auto-save, resume attachment indicator, and action triggers (`Save`, `Send Directly`, `Open Gmail`, `Mark Sent`, `Discard`). Calibrated to a comfortable, proportional 630px window height (`max-height: calc(100vh - 12rem)`) with compact `0.74rem` typography and explicit high-contrast button styling (`.btn-primary`, `.btn-outline`, `.btn-success`, `.btn-cancel-app`, `.btn-copy-micro`, `.btn-generate-mail-jd`) so the entire email and all footer action buttons are immediately visible without vertical cut-off or scrolling.
  - Closeable Side Drawer: added a prominent `✕` close button (and `Escape` keyboard shortcut) to dismiss the side window and restore the table to full width.
  - Independent Scrolling Behavior: enabled natural vertical scrolling for the outer page and table list, while keeping the docked right-side email window sticky and in viewport view with its own internal scrollable body.
  - One-Click In-Table & In-Drawer AI Generation: posts pending generation can be generated with a single click directly from the table action button or inside the side drawer via ChatGPT.
- Discovered Jobs Bulk Removal & Dismissal Action (`src/static/partials/tab_discovered.html`, `src/static/js/discovered.js`, `src/static/js/review.js`, `src/static/js/crawler.js`): added batch Dismiss button (`#btnBatchDismiss`) with selection counter badge, header select-all synchronization, reason modal integration, and 14-second Undo notification to batch delete/dismiss posts from the active Discovered feed.
- Exact Job Opening Multi-Check Deduplication & Canonicalization (`src/db/posts.py`, `src/services/easy_apply_service.py`, `src/services/indeed_apply_service.py`): added `canonicalize_job_url` and `compute_exact_opening_signature` stripping tracking query params (`refId`, `trackingId`, `from`, `vjs`, `tk`, `fccid`, `eBP`, etc.) to produce clean canonical URLs (`https://www.linkedin.com/jobs/view/{job_id}/`, `https://in.indeed.com/viewjob?jk={jk}`) and deterministic IDs. Implemented multi-check database queries checking ID, canonical URL, platform job ID, and composite signature `(company, title, location, snippet)` to prevent repeated crawl runs from duplicating exact job openings.
- Dismissed Roles Pre-Check & Monitoring Badge: incoming jobs matching previously dismissed roles/titles or prior rejections are recorded under `status = 'REJECTED'` with `is_dismissed = TRUE` and tagged with a small, clean UI badge (`🚫 Dismissed`) across Discovered, Easy Apply, Indeed Apply, and History views.
- Already Applied Pre-Check & Cancellation Workflow: detects live "Applied" badges on LinkedIn and Indeed search cards/panes and DB application history, automatically saving them as `CANCELLED` (`status = 'REJECTED'`, `rejection_reason = 'Already applied'`) with a clean `✓ Already Applied` badge, preventing already applied roles from cluttering the active discovery queue.
- Indeed Cloudflare "Additional Verification Required" Manual Approval Handler (`src/services/indeed_apply_service.py`): added `detect_cloudflare_challenge` and `handle_cloudflare_or_captcha_pause` to detect Cloudflare Turnstile, Ray ID challenges, and "Additional Verification Required" pages. Pauses automation cleanly, issues terminal alerts, provides periodic 15-second heartbeat logs to keep background task watchdogs active, and automatically resumes execution as soon as the user completes manual approval in the browser.
- Indeed Job Portal & Apply Workspace (`src/services/indeed_apply_service.py`, `src/static/partials/tab_indeed_apply.html`, `src/static/css/indeed_apply.css`, `src/static/js/indeed_apply.js`): autonomous Indeed job discovery crawler with "Easily apply" (DSQF7) filtering, bidirectional cross-platform rejection synchronization with LinkedIn, and multi-step smartapply wizard automation.
- In-Stream Recruiter Email Harvesting: extracts recruiter contact emails directly from Job Description text during crawler discovery and smartapply passes, auto-populating `contact_emails` in PostgreSQL.
- Recruiter Email Filter & Sorting on Indeed workspace: added dedicated filter pill `With Recruiter Email` (`#pillIndeedHasEmail`) with live badge counters and `Sort by Email` button (`#btnSortIndeedByEmail`), allowing users to instantly surface roles with direct recruiter outreach channels.
- 1-Click AI Outreach Draft & Gmail Dispatch: added `✉️ Draft Email` action button on Indeed rows and email chips that trigger ChatGPT cover letter generation via `/api/generate-email/{id}` and transition directly to `Review & Drafts` for review and one-click dispatch.
- Dynamic Question Bank Options & Selection: enriched Question Bank schema and screening modals with option arrays (`options TEXT[]`), enabling clickable option pills and auto-filling for multi-choice dropdowns, radio groups, and custom Mosaic select lists.
- Anti-Bot & reCAPTCHA Detection Safeguard: strictly adheres to bot safety policies by gracefully detecting Indeed's review-step reCAPTCHA challenge ("I'm not a robot") and pausing for manual user verification instead of stalling or setting generic errors.
- Added LinkedIn Daily Easy Apply Limit detection and dedicated popup modal (`modalDailyLimit`): detects "You reached today’s Easy Apply limit" across modal dialogs, submission confirmations, and page loads.
- Differentiates between short 1-hour fast-pace cooldowns and official next-day daily application limits, automatically setting resume timestamps for tomorrow morning while safely preserving all remaining queue applications in `DISCOVERED` (Ready to Apply) status.
- Added pre-checks to `triggerSingleEasyApply`, `batchApplySelectedEasyJobs`, and `triggerRerunScreenedApplications` to display the Daily Limit popup modal directly with remaining time countdown and details.
- Integrated dedicated ChatGPT custom GPT automation (`chatgpt_question_url`) for answering uncataloged Easy Apply screening questions on the fly during job applications.
- Enforced strict "DB First" resolution protocol: answers are resolved from PostgreSQL `screening_question_bank` first before consulting ChatGPT.
- Implemented zero-prompt passthrough: raw questions and options are passed directly to ChatGPT without wrapper meta-prompts, adhering to pre-configured custom GPT instructions.
- Added automatic question-and-answer persistence to PostgreSQL with `status='ANSWERED'` upon receiving valid answers from ChatGPT.
- Added automatic manual screening safeguard: when ChatGPT returns `user_response_needed` or `DONT_KNOW`, the question is cataloged as `PENDING` and the application is safely preserved under `REQUIRES_QUESTIONNAIRE` without submitting dummy values.
- Added instant application abort on `WTF` / `UNREASONABLE`: when ChatGPT classifies a screening question as unreasonable or bogus (`WTF`), the application is halted immediately, the modal is discarded, and the post is saved as `REJECTED` (`Unreasonable screening question`).
- Added standalone batch processing tool `scripts/batch_answer_questions_via_chatgpt.py` to resolve cataloged pending questions directly through the ChatGPT custom GPT in Firefox with `--limit`, `--delay`, `--headless`, and `--dry-run` options.
- Added UI setting `#settingChatGptQuestionUrl` in System Settings modal with full PostgreSQL persistence.
- Automated spam/scam detection for LinkedIn post cards containing comment-bait and engagement farming ("comment below ...", "please comment interested", "drop email in comments") during crawler execution and database ingestion, saving them directly as `REJECTED` (`Scam: Comment bait`).
- Integrated Byten Agentic Engineering & Design System governance framework.
- Installed Impeccable, Intent, Ponytail, and Graphify agent skills in `.agents/skills/`.
- Configured agent governance rules in `.agents/rules/` (`ui-craft.md`, `code-discipline.md`, `change-tracking.md`, `graphify.md`).
- Added custom change tracking skill in `.agents/skills/track-changes/SKILL.md` and workflow in `.agents/workflows/graphify.md`.
- Configured automated UI inspection hooks in `.codex/hooks.json`.
- Established architecture documentation in `docs/` (`ORCHESTRATION.md`, `DESIGN.md`, `PRODUCT.md`, `adr/README.md`, `adr/0001-agent-skillset-and-change-tracking.md`).
- Created living repository ledger `PROJECT_STATE.md`.
- Initialized AST codebase knowledge graph in `graphify-out/`.

### Changed
- Integrated Byten Engineering & Design System Guidelines into root `AGENTS.md` while preserving existing Reach routing matrices and critical agent directives.
- Updated `.gitignore` to ignore graphify cache and local native binaries.

### Deprecated

### Removed

### Fixed
- Fixed Easy Apply Screening Questionnaire Infinite Loop & Radio Option Matching (`src/services/easy_apply_service.py`, `src/services/question_bank_service.py`, `src/services/indeed_apply_service.py`): resolved a core architectural bug where applications requiring questionnaires entered an infinite loop of `REQUIRES_QUESTIONNAIRE` dismissals without submitting. Modern LinkedIn Easy Apply formats radio buttons with empty `<label>` tags and places text in sibling `<p class="gvylje">` containers, causing legacy label queries to extract empty strings and fall back to dummy placeholders. Implemented robust container-based DOM extraction (`{ index, id, text }`).
- Semantic Option Matching Algorithm (`src/services/question_bank_service.py`): created `match_option_to_answer` supporting exact matching, numeric experience ranges (e.g. `'3 years'` matching `'3–4 years'`, `'0 years'` matching `'No professional experience'`), notice period affirmative mapping (`'Serving Notice Period...'` matching `'Yes'`), affirmative/negative semantics, and substring/token overlap for both LinkedIn and Indeed Apply workflows.
- Fixed Elasticsearch `is_skip` Substring False Positive: resolved a critical bug where `"search"` in `standard_skip` matched `"Elasticsearch"` as a substring, causing questions mentioning Elasticsearch to be silently ignored and never evaluated, asked to ChatGPT, or cataloged. Replaced naive substring checks with whole-word regex boundaries (`\bsearch\b`).
- Fieldset Prompt Resolution & Multi-Select Checkboxes: enhanced prompt extraction to traverse previous sibling nodes (`previousElementSibling`) and parent group headers, resolving prompts for checkbox and radio fieldsets that lacked explicit legends or aria-labels. Added full support for multi-select checkbox fieldsets in `handle_screening_form_step`.
- Viewport-Safe Option Dispatch: replaced Playwright `.check(force=True)` with native DOM dispatch (`el.click()` and change events) for radio buttons and checkboxes, eliminating `Locator.check: Element is outside of the viewport` exceptions on long scrolling modal dialogs.
- Automated City / Location Typeahead Selection: broadened location selectors in `fill_contact_info` and added automated dropdown suggestion selection in `handle_screening_form_step` to prevent Step 1 validation stalls when location fields require selecting from LinkedIn's typeahead popover.
- Fixed Question Bank Status Demotion Conflict (`src/db/question_bank.py`): resolved a concurrent race condition where active background apply tasks or crawlers scanning modal forms demoted `ANSWERED` and `AI_SUGGESTED` questions back to `PENDING` due to an unconstrained `ON CONFLICT (question_key) DO UPDATE SET status = EXCLUDED.status` clause. Added status precedence rules in PostgreSQL (`ANSWERED` > `AI_SUGGESTED` > `PENDING`), preserving approved answers and AI suggestions against background clobbering.
- Restored 190 AI-suggested screening questions in PostgreSQL back to `AI_SUGGESTED` status, making them instantly visible and permanently approvable in the Question Bank workspace.
- Indeed 404 & Expired Job Detection (`src/services/indeed_apply_service.py`): added tri-layered detection (HTTP 404/410 network status, `Not Found | Indeed` document title, and DOM heading/body indicators e.g. "We can’t find this page", "page doesn't exist", "This job has expired on Indeed").
- Graceful 404 Bypass & Accurate Statusing: when a job page returns 404 or expired notice, automatically sets post status to `NOT_FOUND` with rejection reason `"Job expired or removed (404 Page Not Found)"`. Bypasses instantly during batch apply with a 2–3s pause instead of stalling for a 45–75s pacing delay. Crawler discovery now skips expired preview panes, preventing dead jobs from entering the Ready queue.
- Frontend UI Status Badge (`src/static/js/indeed_apply.js`): jobs with `NOT_FOUND` status now display a dedicated `🚫 Closed` tag in the actions column rather than an active `⚡ Apply` button.
- Fixed confusing "Incomplete wizard steps" rejection reason on Indeed screening jobs: prevented the wizard failure fallback from overwriting real screening questions or review completion reasons with generic text. Existing posts updated with clear diagnostic statuses (reCAPTCHA verification required or review reached).
- Enhanced Screening Modal diagnostics in `easy_apply.js`: when a job has reached review or requires human CAPTCHA verification, the modal now displays a clear context card with "↗ Open on Indeed" and "⚡ Rerun" action buttons instead of a blank question list.
- Fixed Easy Apply button selector on standalone job view pages: broadened `apply_btn_selector` in `src/services/easy_apply_service.py` to match `<a>` anchor links, roles, and classes (`[aria-label*='Easy Apply']`, `a.jobs-apply-button`) instead of restricting to `<button>` elements, preventing applications from failing with false "No Easy Apply button available" errors.
- Prevented unverified `NOT_FOUND` dismissals: non-visible buttons on valid pages now return `FAILED` rather than permanently moving jobs to `NOT_FOUND` dismissals unless explicit closed indicators or external apply links are detected.
- Restored 51 erroneously dismissed Easy Apply job applications back to `DISCOVERED` (Ready to Apply) status in the PostgreSQL database.
- Fixed LinkedIn crawler cycles clamp and fixed 20-job report: removed `min(cycles, 15)` clamp and `max_jobs = 20` hardcoding in `easy_apply_service.py` and `scripts/linkedin_job_search.py`, allowing custom cycles (up to 1,000) and target job limits to execute without being truncated at 20 jobs.
- Implemented real multi-page pagination navigation (`&start={page * 25}`) for LinkedIn search result cards, overcoming the 25-card single-page DOM limit so discovery continues across multiple search pages.
- Fixed ChatGPT DOM composer locator in `chatgpt_service.py` to target `div.ProseMirror[role='textbox']` directly and use forced dispatch, preventing pointer intercept errors from child placeholder paragraphs.
- Fixed file leak in Easy Apply screening question extraction where resume file radio buttons (`rinshad__._.pdf`) were captured as questions; added file extension filters across `inspect_easy_apply_modal`, `handle_screening_form_step`, and `normalize_question_key`.

### Security
