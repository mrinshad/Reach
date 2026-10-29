# Changelog

All notable changes to the Reach project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- Fixed Easy Apply button selector on standalone job view pages: broadened `apply_btn_selector` in `src/services/easy_apply_service.py` to match `<a>` anchor links, roles, and classes (`[aria-label*='Easy Apply']`, `a.jobs-apply-button`) instead of restricting to `<button>` elements, preventing applications from failing with false "No Easy Apply button available" errors.
- Prevented unverified `NOT_FOUND` dismissals: non-visible buttons on valid pages now return `FAILED` rather than permanently moving jobs to `NOT_FOUND` dismissals unless explicit closed indicators or external apply links are detected.
- Restored 51 erroneously dismissed Easy Apply job applications back to `DISCOVERED` (Ready to Apply) status in the PostgreSQL database.
- Fixed LinkedIn crawler cycles clamp and fixed 20-job report: removed `min(cycles, 15)` clamp and `max_jobs = 20` hardcoding in `easy_apply_service.py` and `scripts/linkedin_job_search.py`, allowing custom cycles (up to 1,000) and target job limits to execute without being truncated at 20 jobs.
- Implemented real multi-page pagination navigation (`&start={page * 25}`) for LinkedIn search result cards, overcoming the 25-card single-page DOM limit so discovery continues across multiple search pages.
- Fixed ChatGPT DOM composer locator in `chatgpt_service.py` to target `div.ProseMirror[role='textbox']` directly and use forced dispatch, preventing pointer intercept errors from child placeholder paragraphs.
- Fixed file leak in Easy Apply screening question extraction where resume file radio buttons (`rinshad__._.pdf`) were captured as questions; added file extension filters across `inspect_easy_apply_modal`, `handle_screening_form_step`, and `normalize_question_key`.

### Security
