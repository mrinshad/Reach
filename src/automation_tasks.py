"""
Background Automation Task Runner

Manages background execution of Playwright automation workflows (LinkedIn Scraper,
ChatGPT Email Generator, Gmail Draft Composer) in strictly headed mode (headless=False)
while providing real-time status and logs to the FastAPI dashboard.
"""

from src.db import update_post_email
import os
import sys
import time
import random
import threading
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright

from src.db import (
    get_post_by_id,
    save_chatgpt_response,
    mark_post_sent,
    update_post_status,
)
from src.firefox_connector import launch_firefox_context
from src.chatgpt_service import (
    navigate_to_conversation,
    send_jd_and_get_email,
    extract_unsuitable_reason,
    get_default_chatgpt_url,
)
from src.gmail_service import (
    navigate_to_gmail,
    populate_email_draft,
    send_email_directly,
)
from src.config import load_config


class TaskManager:
    """Thread-safe task state tracker for the web dashboard."""
    def __init__(self):
        self._lock = threading.Lock()
        self.state: Dict[str, Any] = {
            "status": "idle",       # idle | running | completed | error
            "task_name": "",
            "current_step": "",
            "total_items": 0,
            "completed_items": 0,
            "logs": [],
            "error": None,
            "started_at": None,
            "finished_at": None,
            "crawl_stats": None,
        }

    def start_task(self, task_name: str, total_items: int = 1):
        with self._lock:
            self.state = {
                "status": "running",
                "task_name": task_name,
                "current_step": "Initializing...",
                "total_items": total_items,
                "completed_items": 0,
                "logs": [f"[{time.strftime('%H:%M:%S')}] Started {task_name}"],
                "error": None,
                "started_at": time.time(),
                "finished_at": None,
                "crawl_stats": None,
            }

    def log(self, message: str):
        with self._lock:
            entry = f"[{time.strftime('%H:%M:%S')}] {message}"
            self.state["logs"].append(entry)
            # Keep last 150 log lines
            if len(self.state["logs"]) > 150:
                self.state["logs"] = self.state["logs"][-150:]
            print(entry)

    def set_current_step(self, step: str):
        with self._lock:
            self.state["current_step"] = step

    def update_progress(self, completed: int, current_step: str = ""):
        with self._lock:
            self.state["completed_items"] = completed
            if current_step:
                self.state["current_step"] = current_step

    def finish_task(self, success_message: str = "Task completed successfully.", crawl_stats: Optional[Dict[str, Any]] = None):
        with self._lock:
            self.state["status"] = "completed"
            self.state["current_step"] = success_message
            self.state["finished_at"] = time.time()
            if crawl_stats:
                self.state["crawl_stats"] = crawl_stats
            self.state["logs"].append(f"[{time.strftime('%H:%M:%S')}] ✓ {success_message}")

    def fail_task(self, error_message: str):
        with self._lock:
            self.state["status"] = "error"
            self.state["error"] = error_message
            self.state["current_step"] = f"Failed: {error_message}"
            self.state["finished_at"] = time.time()
            self.state["logs"].append(f"[{time.strftime('%H:%M:%S')}] ✗ Error: {error_message}")

    def clear_task(self):
        with self._lock:
            self.state["status"] = "idle"
            self.state["error"] = None
            self.state["task_name"] = ""
            self.state["current_step"] = ""
            self.state["crawl_stats"] = None

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.state)


# Singleton task manager instance
task_manager = TaskManager()


def run_chatgpt_batch(post_ids: List[str]):
    """
    Generate cold outreach emails using ChatGPT in headed Firefox (headless=False).
    Runs post-by-post with conservative pacing.
    """
    task_manager.start_task("ChatGPT Email Generation", total_items=len(post_ids))
    config = load_config()

    try:
        task_manager.log(f"Launching Firefox in headed mode (headless=False)...")
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=False,
                sync_cookies_domains=["chatgpt.com", "openai.com"],
            )

            page = context.pages[0] if context.pages else context.new_page()
            custom_gpt_url = config.get("chatgpt_url") or get_default_chatgpt_url()

            task_manager.log(f"Navigating to custom GPT conversation...")
            navigate_to_conversation(page, url=custom_gpt_url)

            success_count = 0
            rejected_count = 0
            failed_posts = []

            for idx, post_id in enumerate(post_ids, start=1):
                post = get_post_by_id(post_id)
                if not post:
                    task_manager.log(f"Post {post_id} not found in database, skipping.")
                    continue

                author = post.get("author_name", "Unknown")
                task_manager.update_progress(idx - 1, f"Processing {idx}/{len(post_ids)}: {author}")
                task_manager.log(f"[{idx}/{len(post_ids)}] Submitting JD for {author}...")

                update_post_status(post_id, "GENERATING_EMAIL")

                try:
                    subject, body = send_jd_and_get_email(page, post["full_text"])
                    if subject == "UNSUITABLE_JD" or "UNSUITABLE_JD" in body or "❌ not suitable" in body.lower() or "not suitable —" in body.lower():
                        reason = extract_unsuitable_reason(body)
                        update_post_status(post_id, "REJECTED", rejection_reason=reason)
                        update_post_email(post_id, "UNSUITABLE_JD", body)
                        rejected_count += 1
                        task_manager.log(f"  🚫 [Auto-Cancelled] Unsuitable JD for {author}: {reason}")
                    else:
                        save_chatgpt_response(post_id, subject, body)
                        success_count += 1
                        task_manager.log(f"  ✓ Email generated: '{subject[:60]}...'")
                except Exception as post_err:
                    err_str = str(post_err)
                    task_manager.log(f"  ✗ Failed for post {author}: {err_str}")
                    update_post_status(post_id, "DISCOVERED")
                    failed_posts.append((author, err_str))

                    # If browser context or page was closed or crashed, abort immediately
                    if "closed" in err_str.lower() or "target crash" in err_str.lower() or "disconnected" in err_str.lower():
                        task_manager.fail_task(f"Browser closed or disconnected while generating for {author}: {err_str}")
                        return
                    continue

                task_manager.update_progress(idx)

                # Human pacing pause if more posts remain
                if idx < len(post_ids):
                    pause = random.uniform(
                        config.get("pacing_min_seconds", 6),
                        config.get("pacing_max_seconds", 12)
                    )
                    task_manager.log(f"  Pacing pause: waiting {pause:.1f}s before next post...")
                    time.sleep(pause)

            task_manager.log("Closing browser session...")
            context.close()

            if len(failed_posts) > 0 and success_count == 0 and rejected_count == 0:
                reasons = "; ".join([f"{a}: {m}" for a, m in failed_posts[:3]])
                task_manager.fail_task(f"Generation stopped for all {len(failed_posts)} post(s): {reasons}")
            elif len(failed_posts) > 0:
                reasons = "; ".join([f"{a}: {m}" for a, m in failed_posts[:2]])
                task_manager.fail_task(f"Generated {success_count} email(s), but stopped on {len(failed_posts)} post(s): {reasons}")
            else:
                task_manager.finish_task(
                    f"Processed {len(post_ids)} post(s): {success_count} draft(s) created, {rejected_count} unsuitable auto-rejected."
                )

    except Exception as e:
        task_manager.fail_task(f"ChatGPT Generation Error: {str(e)}")


def run_open_gmail_draft(post_id: str):
    """
    Launch headed Firefox (headless=False), navigate to Gmail, populate the
    compose window with To, Subject, paragraph-formatted body, and resume attachment.
    Leaves the browser window open for user review.
    """
    task_manager.start_task("Gmail Draft Preparation", total_items=1)
    config = load_config()
    resume_path = config.get("resume_path", "")

    post = get_post_by_id(post_id)
    if not post:
        task_manager.fail_task(f"Post {post_id} not found in database.")
        return

    emails = post.get("contact_emails", [])
    if not emails:
        task_manager.fail_task(f"No contact email found for this post.")
        return

    recipient = emails[0]
    subject = post.get("generated_subject") or "Application for Full Stack Developer"
    body = post.get("generated_body") or ""

    if not body:
        task_manager.fail_task(f"No generated email body found. Generate email first.")
        return

    try:
        task_manager.log(f"Launching Firefox in headed mode (headless=False)...")
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=False,
                sync_cookies_domains=["google.com", "gmail.com"],
            )

            page = context.pages[0] if context.pages else context.new_page()

            task_manager.log(f"Navigating to Gmail...")
            navigate_to_gmail(page)

            task_manager.log(f"Populating draft for {recipient}...")
            attachment = resume_path if os.path.exists(resume_path) else None
            if attachment:
                task_manager.log(f"  Attaching resume: {os.path.basename(attachment)}")
            else:
                task_manager.log(f"  Note: No resume found at '{resume_path}'")

            populate_email_draft(
                page=page,
                recipient=recipient,
                subject=subject,
                body=body,
                attachment_path=attachment,
            )

            task_manager.log("✓ Draft ready in Gmail!")
            task_manager.log("Firefox will stay open on screen for you to review or send.")
            task_manager.finish_task("Gmail draft ready on screen for human review.")

            # Keep context open so user can review and edit in Gmail
            # We poll until all pages in this context are closed by the user
            try:
                while len(context.pages) > 0 and not page.is_closed():
                    time.sleep(2)
            except Exception:
                pass

            task_manager.log("Gmail window closed by user.")

    except Exception as e:
        task_manager.fail_task(str(e))


def run_send_single_draft(post_id: str):
    """
    Directly send outreach email for a single post via Gmail without manual interaction,
    attaching the resume, clicking Send, and updating post status in PostgreSQL to SENT.
    """
    task_manager.start_task("Sending Outreach Email", total_items=1)
    config = load_config()
    resume_path = config.get("resume_path", "")

    post = get_post_by_id(post_id)
    if not post:
        task_manager.fail_task(f"Post {post_id} not found.")
        return

    emails = post.get("contact_emails", [])
    if not emails:
        task_manager.fail_task(f"No contact email found for {post.get('author_name')}.")
        return

    recipient = emails[0]
    subject = post.get("generated_subject") or "Application for Full Stack Developer"
    body = post.get("generated_body") or ""
    author = post.get("author_name", "Recruiter")

    if not body:
        task_manager.fail_task("Email draft is empty. Generate draft before sending.")
        return

    try:
        task_manager.log(f"Launching Firefox session for direct sending to {author} ({recipient})...")
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=False,
                sync_cookies_domains=["google.com", "gmail.com"],
            )
            page = context.pages[0] if context.pages else context.new_page()

            task_manager.log("Navigating to Gmail...")
            navigate_to_gmail(page)

            attachment = resume_path if os.path.exists(resume_path) else None
            task_manager.log(f"Composing email to {recipient}...")
            populate_email_draft(
                page=page,
                recipient=recipient,
                subject=subject,
                body=body,
                attachment_path=attachment,
            )

            task_manager.log("Clicking Send directly...")
            send_email_directly(page)

            # Update database
            mark_post_sent(post_id)
            task_manager.log(f"✓ Application to {author} ({recipient}) sent successfully!")
            task_manager.update_progress(1)
            time.sleep(1)

            context.close()
            task_manager.finish_task(f"Successfully sent application to {author} ({recipient})!")
    except Exception as e:
        task_manager.fail_task(f"Send Error: {str(e)}")


def run_send_batch_drafts(post_ids: List[str]):
    """
    Directly send multiple outreach emails in a batch via a single Gmail browser session.
    Iterates through each post, composes, attaches resume, clicks Send directly,
    marks each sent in PostgreSQL, and applies human pacing delays between messages.
    """
    task_manager.start_task("Batch Outreach Sending", total_items=len(post_ids))
    config = load_config()
    resume_path = config.get("resume_path", "")
    attachment = resume_path if os.path.exists(resume_path) else None

    successful = 0
    failed = []

    try:
        task_manager.log(f"Launching Firefox session to send {len(post_ids)} applications...")
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=False,
                sync_cookies_domains=["google.com", "gmail.com"],
            )
            page = context.pages[0] if context.pages else context.new_page()

            task_manager.log("Navigating to Gmail...")
            navigate_to_gmail(page)

            for idx, post_id in enumerate(post_ids, 1):
                post = get_post_by_id(post_id)
                if not post:
                    failed.append((post_id, "Post not found"))
                    continue

                emails = post.get("contact_emails", [])
                if not emails:
                    failed.append((post.get("author_name", post_id), "No email found"))
                    continue

                recipient = emails[0]
                author = post.get("author_name", "Recruiter")
                subject = post.get("generated_subject") or "Application for Full Stack Developer"
                body = post.get("generated_body") or ""

                if not body:
                    failed.append((author, "Empty email body"))
                    continue

                task_manager.log(f"[{idx}/{len(post_ids)}] Composing to {author} ({recipient})...")
                task_manager.set_current_step(f"Sending {idx}/{len(post_ids)}: {author}")

                try:
                    populate_email_draft(
                        page=page,
                        recipient=recipient,
                        subject=subject,
                        body=body,
                        attachment_path=attachment,
                    )
                    send_email_directly(page)
                    mark_post_sent(post_id)
                    successful += 1
                    task_manager.log(f"  ✓ Sent application {idx}/{len(post_ids)} to {author} ({recipient})")
                except Exception as send_err:
                    task_manager.log(f"  ✗ Failed to send to {author}: {send_err}")
                    failed.append((author, str(send_err)))

                task_manager.update_progress(idx)

                if idx < len(post_ids):
                    pause = random.uniform(
                        config.get("pacing_min_seconds", 4),
                        config.get("pacing_max_seconds", 8)
                    )
                    task_manager.log(f"  Waiting {pause:.1f}s before sending next email...")
                    time.sleep(pause)

            task_manager.log("Closing browser session...")
            context.close()

            if failed and successful == 0:
                reasons = "; ".join([f"{a}: {m}" for a, m in failed[:3]])
                task_manager.fail_task(f"Failed to send all {len(failed)} emails: {reasons}")
            elif failed:
                task_manager.finish_task(f"Sent {successful} of {len(post_ids)} applications. ({len(failed)} failed)")
            else:
                task_manager.finish_task(f"Successfully sent all {successful} applications via Gmail!")

    except Exception as e:
        task_manager.fail_task(f"Batch Send Error: {str(e)}")


import subprocess
import threading


def run_scraper_subprocess_with_timeout(
    task_name: str,
    script_path: str,
    inactivity_timeout_seconds: float = 90.0,
    finish_message: str = "Scraping finished successfully."
):
    """
    Run a scraper script subprocess with a 90-second inactivity watchdog.
    If the scraper stops producing output / making progress for 90 seconds,
    the watchdog terminates the subprocess, closes the task cleanly, and
    preserves all jobs saved in the database up to that point.
    """
    task_manager.start_task(task_name, total_items=1)
    try:
        task_manager.log(f"Starting {task_name} (inactivity timeout: {int(inactivity_timeout_seconds)}s)...")

        proc = subprocess.Popen(
            [sys.executable, "-u", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        last_activity = [time.time()]
        timed_out = [False]
        completed = threading.Event()

        def inactivity_watchdog():
            while not completed.is_set():
                time.sleep(1.0)
                if completed.is_set():
                    break
                elapsed = time.time() - last_activity[0]
                if elapsed >= inactivity_timeout_seconds:
                    timed_out[0] = True
                    task_manager.log(
                        f"⏱️ [Inactivity Timeout] No scraping progress for {int(elapsed)}s "
                        f"(limit: {int(inactivity_timeout_seconds)}s)."
                    )
                    task_manager.log("Terminating scraper process and closing task cleanly...")
                    try:
                        proc.terminate()
                        time.sleep(1.5)
                        if proc.poll() is None:
                            proc.kill()
                    except Exception:
                        pass
                    break

        watchdog_thread = threading.Thread(target=inactivity_watchdog, daemon=True)
        watchdog_thread.start()

        parsed_stats = None
        for line in proc.stdout:
            last_activity[0] = time.time()
            cleaned = line.rstrip()
            if cleaned:
                if "__CRAWL_STATS__:" in cleaned:
                    try:
                        import json
                        raw_json = cleaned.split("__CRAWL_STATS__:", 1)[1].strip()
                        parsed_stats = json.loads(raw_json)
                    except Exception:
                        pass
                else:
                    task_manager.log(cleaned)

        completed.set()
        proc.wait()

        if timed_out[0]:
            task_manager.finish_task(
                f"{task_name} closed after 90s inactivity timeout. Scraped posts saved.",
                crawl_stats=parsed_stats
            )
        elif proc.returncode == 0:
            if parsed_stats:
                custom_msg = (
                    f"Crawling complete: {parsed_stats.get('total_crawled', 0)} crawled, "
                    f"{parsed_stats.get('newly_added', 0)} newly added, "
                    f"{parsed_stats.get('skipped_already_added', 0)} skipped (already in DB)."
                )
                task_manager.finish_task(custom_msg, crawl_stats=parsed_stats)
            else:
                task_manager.finish_task(finish_message)
        else:
            task_manager.fail_task(f"{task_name} exited with code {proc.returncode}")
    except Exception as e:
        task_manager.fail_task(str(e))


def run_infopark_scraper():
    """
    Run the Infopark Jobs Scraper via subprocess with 90-second inactivity timeout.
    Scrapes today's opportunities from https://infopark.in/companies-job,
    extracting full JDs and direct recruiter emails.
    """
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts",
        "infopark_jobs_search.py"
    )
    run_scraper_subprocess_with_timeout(
        task_name="Infopark Jobs Scraper",
        script_path=script_path,
        inactivity_timeout_seconds=90.0,
        finish_message="Infopark jobs scraping finished successfully."
    )


def run_linkedin_scraper():
    """
    Run the LinkedIn Posts Scraper in headed Firefox (headless=False) via subprocess
    with 90-second inactivity timeout.
    """
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts",
        "linkedin_posts_search.py"
    )
    run_scraper_subprocess_with_timeout(
        task_name="LinkedIn Posts Scraper",
        script_path=script_path,
        inactivity_timeout_seconds=90.0,
        finish_message="LinkedIn scraping finished successfully."
    )


SCRAPER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "linkedin": {
        "id": "linkedin",
        "name": "LinkedIn Posts",
        "icon": "💼",
        "description": "Scrapes today's hiring posts via search query in headed Firefox",
        "runner": run_linkedin_scraper,
    },
    "infopark": {
        "id": "infopark",
        "name": "Infopark Kochi",
        "icon": "🏢",
        "description": "Scrapes active IT company openings and recruiter emails from infopark.in",
        "runner": run_infopark_scraper,
    },
}


def get_registered_scrapers() -> List[Dict[str, str]]:
    """Return public metadata of all registered website scrapers."""
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "icon": s["icon"],
            "description": s["description"],
        }
        for s in SCRAPER_REGISTRY.values()
    ]


def run_scraper_by_source(source_id: str):
    """Dispatch and run a scraper background task by source ID."""
    source_lower = (source_id or "linkedin").strip().lower()
    scraper = SCRAPER_REGISTRY.get(source_lower)
    if not scraper:
        valid_sources = list(SCRAPER_REGISTRY.keys())
        raise ValueError(f"Unknown scraper source '{source_id}'. Supported sources: {valid_sources}")
    scraper["runner"]()

