# Reach CLI & Scraper Scripts Agent Guide (`scripts/`)

This directory contains standalone CLI scripts for crawling job boards, running batch tests, and verifying individual pipeline stages outside the web dashboard.

---

## Scripts Directory Matrix

| Script | Purpose & Description | Typical Execution Command |
|---|---|---|
| [`linkedin_posts_search.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/linkedin_posts_search.py) | Playwright scraper extracting hiring posts from LinkedIn's feed. Visits individual posts, extracts author details, experience, emails, and full post text. | `python3 scripts/linkedin_posts_search.py --query "Full stack developer"` |
| [`infopark_jobs_search.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/infopark_jobs_search.py) | Standalone crawler for Infopark Kochi (`infopark.in/companies-job`). Visits each details page, extracts full JDs, recruiter emails, and saves directly to PostgreSQL. | `python3 scripts/infopark_jobs_search.py` |
| [`process_posts_with_chatgpt.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/process_posts_with_chatgpt.py) | CLI runner that queries pending email outreach posts and automates ChatGPT generation via headed Firefox browser session. | `python3 scripts/process_posts_with_chatgpt.py` |
| [`prepare_gmail_draft.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/prepare_gmail_draft.py) | Automates Gmail compose drafting for approved posts, attaching the active resume PDF. | `python3 scripts/prepare_gmail_draft.py` |
| [`demo_pipeline_single_post.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/demo_pipeline_single_post.py) | End-to-end dry-run test processing a single post through JD ingestion, AI generation, and draft preparation. | `python3 scripts/demo_pipeline_single_post.py` |
| [`test_firefox_chatgpt.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/test_firefox_chatgpt.py) | Diagnostic probe testing persistent Firefox context connection and ChatGPT session cookies. | `python3 scripts/test_firefox_chatgpt.py` |
| [`test_chatgpt_conversation.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/test_chatgpt_conversation.py) | Diagnostic test verifying ProseMirror typing and streaming completion listener in ChatGPT Custom GPT. | `python3 scripts/test_chatgpt_conversation.py` |
| [`test_cdp_connection.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/test_cdp_connection.py) | Diagnostic test verifying Chrome DevTools Protocol (CDP) connectivity on port 9222. | `python3 scripts/test_cdp_connection.py` |
| [`linkedin_job_search.py`](file:///Users/apple/Byten/linkedInScrapper/scripts/linkedin_job_search.py) | Alternate scraper targeting LinkedIn structured Job search tab rather than feed posts. | `python3 scripts/linkedin_job_search.py` |

---

## Agent Directives for Scripts

1. **Shared Package Imports**: All scripts import database operations via `from src.db import ...` and services via `from src.services import ...` directly. No legacy shims are used.
2. **Profile Directory Safety**: Ensure no concurrent script execution shares the persistent Firefox profile (`~/.playwright_firefox_profile`) while the web dashboard task queue is actively running a browser session.
