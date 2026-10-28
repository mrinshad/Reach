# Changelog

All notable changes to the Reach project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- Fixed ChatGPT DOM composer locator in `chatgpt_service.py` to target `div.ProseMirror[role='textbox']` directly and use forced dispatch, preventing pointer intercept errors from child placeholder paragraphs.
- Fixed file leak in Easy Apply screening question extraction where resume file radio buttons (`rinshad__._.pdf`) were captured as questions; added file extension filters across `inspect_easy_apply_modal`, `handle_screening_form_step`, and `normalize_question_key`.

### Security
