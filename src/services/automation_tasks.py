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
    get_recently_sent_recipients,
    SEND_COOLDOWN_DAYS,
)
from .firefox_connector import launch_firefox_context
from .chatgpt_service import (
    navigate_to_conversation,
    send_jd_and_get_email,
    extract_unsuitable_reason,
    is_unsuitable_response,
    get_default_chatgpt_url,
)
from .gmail_service import (
    navigate_to_gmail,
    populate_email_draft,
    send_email_directly,
)
from .health_service import check_firefox_session_cookies
from src.config import load_config, is_headless

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TaskManager:
    """Thread-safe task state tracker and centralized sequential execution queue."""
    def __init__(self):
        self._lock = threading.Lock()
        self._queue_lock = threading.Lock()
        self.queue: List[Dict[str, Any]] = []
        self._worker_thread: Optional[threading.Thread] = None
        self._cancel_requested = threading.Event()
        self._active_proc: Optional[Any] = None
        self._active_context: Optional[Any] = None
        self._current_task: Optional[Dict[str, Any]] = None
        self.state: Dict[str, Any] = {
            "status": "idle",       # idle | running | completed | error
            "task_name": "",
            "short_name": "",
            "snippet": "",
            "current_step": "",
            "total_items": 0,
            "completed_items": 0,
            "logs": [],
            "error": None,
            "started_at": None,
            "finished_at": None,
            "crawl_stats": None,
        }

    def set_active_proc(self, proc):
        with self._lock:
            self._active_proc = proc

    def clear_active_proc(self):
        with self._lock:
            self._active_proc = None

    def set_active_context(self, context):
        with self._lock:
            self._active_context = context

    def clear_active_context(self):
        with self._lock:
            self._active_context = None

    def is_cancel_requested(self) -> bool:
        return self._cancel_requested.is_set()

    def cancel_active_task(self) -> bool:
        """Cancel the currently executing automation task and stop underlying processes/browser."""
        with self._lock:
            if self.state["status"] != "running":
                return False
            self._cancel_requested.set()
            task_name = self.state.get("task_name") or "Task"
            entry = f"[{time.strftime('%H:%M:%S')}] 🛑 Stopping ongoing task: {task_name}..."
            self.state["logs"].append(entry)
            print(entry)

            # Terminate active scraper subprocess if running
            if self._active_proc:
                try:
                    self._active_proc.terminate()
                    time.sleep(0.3)
                    if self._active_proc.poll() is None:
                        self._active_proc.kill()
                except Exception:
                    pass

            # Close active Playwright context if running
            if self._active_context:
                try:
                    self._active_context.close()
                except Exception:
                    pass

            self.state["status"] = "error"
            self.state["error"] = "Task stopped by user."
            self.state["current_step"] = "Stopped by user"
            self.state["finished_at"] = time.time()
            self.state["logs"].append(f"[{time.strftime('%H:%M:%S')}] 🛑 {task_name} was stopped by user.")
            return True

    def enqueue_task(
        self,
        task_type: str,
        task_name: str,
        runner_func,
        args: tuple = (),
        kwargs: dict = None,
        metadata: dict = None,
        short_name: str = "",
        snippet: str = "",
    ) -> Dict[str, Any]:
        """
        Thread-safe addition to FIFO queue.
        If worker is idle, starts background sequential processor immediately.
        If another task is active, enqueues item and returns its queue position.
        """
        task_id = f"task_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        item = {
            "id": task_id,
            "type": task_type,
            "name": task_name,
            "short_name": short_name or task_name,
            "snippet": snippet or "",
            "runner": runner_func,
            "args": args or (),
            "kwargs": kwargs or {},
            "metadata": metadata or {},
            "enqueued_at": time.time(),
        }

        with self._queue_lock:
            with self._lock:
                is_currently_running = self.state["status"] == "running"

            if is_currently_running:
                self.queue.append(item)
                pos = len(self.queue)
                disp_desc = f"{item['short_name']} ({snippet})" if snippet else item["short_name"]
                self.log(f"Enqueued task #{pos}: {disp_desc}")
                return {
                    "queued": True,
                    "task_id": task_id,
                    "position": pos,
                    "queue_length": len(self.queue),
                    "task_name": task_name,
                    "short_name": item["short_name"],
                    "snippet": item["snippet"],
                }
            else:
                self.queue.append(item)
                if self._worker_thread is None or not self._worker_thread.is_alive():
                    self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
                    self._worker_thread.start()
                return {
                    "queued": False,
                    "task_id": task_id,
                    "position": 0,
                    "queue_length": len(self.queue),
                    "task_name": task_name,
                    "short_name": item["short_name"],
                    "snippet": item["snippet"],
                }

    def _worker_loop(self):
        """Sequential queue execution worker loop."""
        while True:
            current_item = None
            with self._queue_lock:
                if not self.queue:
                    break
                current_item = self.queue.pop(0)

            if not current_item:
                break

            self._cancel_requested.clear()
            self._current_task = current_item
            runner = current_item["runner"]
            args = current_item.get("args", ())
            kwargs = current_item.get("kwargs", {})

            try:
                runner(*args, **kwargs)
            except Exception as e:
                if not self.is_cancel_requested():
                    self.fail_task(str(e))
            finally:
                self._current_task = None
                self._active_proc = None
                self._active_context = None

            # Pause briefly if more tasks are queued to allow the frontend poller to register completion
            with self._queue_lock:
                has_more = len(self.queue) > 0

            if has_more:
                time.sleep(2.5)

    def cancel_queued_task(self, task_id: str) -> bool:
        """Cancel and remove a pending task from the queue."""
        with self._queue_lock:
            for idx, item in enumerate(self.queue):
                if item["id"] == task_id:
                    del self.queue[idx]
                    self.log(f"Cancelled queued task: {item.get('short_name') or item['name']}")
                    return True
        return False

    def clear_queue(self) -> int:
        """Clear all pending tasks from the queue."""
        with self._queue_lock:
            count = len(self.queue)
            self.queue.clear()
            if count > 0:
                self.log(f"Cleared {count} queued task(s)")
            return count

    def get_queue_summary(self) -> List[Dict[str, Any]]:
        """Return a lightweight, JSON-serializable list of queued tasks with snippet descriptors."""
        with self._queue_lock:
            return [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "short_name": item.get("short_name") or item["name"],
                    "snippet": item.get("snippet") or "",
                    "type": item["type"],
                    "metadata": item.get("metadata", {}),
                    "enqueued_at": item.get("enqueued_at"),
                }
                for item in self.queue
            ]

    def start_task(self, task_name: str, total_items: int = 1, short_name: str = "", snippet: str = ""):
        with self._lock:
            self.state = {
                "status": "running",
                "task_name": task_name,
                "short_name": short_name or task_name,
                "snippet": snippet or "",
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
            self.state["short_name"] = ""
            self.state["snippet"] = ""
            self.state["current_step"] = ""
            self.state["crawl_stats"] = None

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            st = dict(self.state)
        st["queue"] = self.get_queue_summary()
        st["queue_length"] = len(st["queue"])
        return st


# Singleton task manager instance
task_manager = TaskManager()


def run_chatgpt_batch(post_ids: List[str], force: bool = False):
    """
    Generate cold outreach emails using ChatGPT in headed Firefox (headless=False).
    Runs post-by-post with conservative pacing.
    If force=True, instructs ChatGPT to pitch the profile regardless of tech stack differences.
    """
    task_manager.start_task("ChatGPT Email Generation", total_items=len(post_ids))
    config = load_config()
    hl = is_headless()

    try:
        mode_str = "headless mode (silent background)" if hl else "headed mode (visible window)"
        task_manager.log(f"Launching Firefox in {mode_str}...")
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=hl,
                sync_cookies_domains=["chatgpt.com", "openai.com"],
            )
            task_manager.set_active_context(context)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                custom_gpt_url = config.get("chatgpt_url") or get_default_chatgpt_url()

                task_manager.log(f"Navigating to custom GPT conversation...")
                navigate_to_conversation(page, url=custom_gpt_url)

                success_count = 0
                rejected_count = 0
                failed_posts = []

                for idx, post_id in enumerate(post_ids, start=1):
                    if task_manager.is_cancel_requested():
                        task_manager.log("🛑 ChatGPT generation stopped by user.")
                        return

                    post = get_post_by_id(post_id)
                    if not post:
                        task_manager.log(f"Post {post_id} not found in database, skipping.")
                        continue

                    author = post.get("author_name", "Unknown")
                    prev_status = post.get("status") or "DISCOVERED"
                    task_manager.update_progress(idx - 1, f"Processing {idx}/{len(post_ids)}: {author}")
                    task_manager.log(f"[{idx}/{len(post_ids)}] Submitting JD for {author}...")

                    update_post_status(post_id, "GENERATING_EMAIL")

                    try:
                        jd_text = (post.get("full_text") or "").strip()
                        subject, body = send_jd_and_get_email(page, jd_text)

                        # If ChatGPT classifies the JD as unsuitable, auto-cancel immediately
                        is_unsuitable = (subject == "UNSUITABLE_JD" or is_unsuitable_response(body))
                        if is_unsuitable:
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
                        fallback_status = "EMAIL_GENERATED" if prev_status == "EMAIL_GENERATED" else "DISCOVERED"
                        update_post_status(post_id, fallback_status)
                        if task_manager.is_cancel_requested():
                            task_manager.log(f"  🛑 Generation stopped for {author} upon user request.")
                            return
                        err_str = str(post_err)
                        task_manager.log(f"  ✗ Failed for post {author}: {err_str}")
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
                        p_start = time.time()
                        while time.time() - p_start < pause:
                            if task_manager.is_cancel_requested():
                                task_manager.log("🛑 Pacing pause interrupted by user cancellation.")
                                return
                            time.sleep(0.5)

                task_manager.log("Closing browser session...")
                context.close()

                if task_manager.is_cancel_requested():
                    return

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
            finally:
                task_manager.clear_active_context()

    except Exception as e:
        if not task_manager.is_cancel_requested():
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


def run_interactive_login(service: str):
    """
    Launch headed Firefox (headless=False) so the user can interactively log into
    LinkedIn, ChatGPT, Gmail, or all services simultaneously.
    Saves session cookies and state directly into ~/.playwright_firefox_profile.
    """
    service_map = {
        "linkedin": {
            "name": "LinkedIn",
            "urls": ["https://www.linkedin.com/login"],
            "domains": ["linkedin.com"],
            "cookie_key": "linkedin",
        },
        "chatgpt": {
            "name": "ChatGPT",
            "urls": ["https://chatgpt.com/"],
            "domains": ["chatgpt.com", "openai.com"],
            "cookie_key": "chatgpt",
        },
        "gmail": {
            "name": "Gmail",
            "urls": ["https://mail.google.com/"],
            "domains": ["google.com", "gmail.com"],
            "cookie_key": "gmail",
        },
        "all": {
            "name": "All Services (LinkedIn, ChatGPT, Gmail)",
            "urls": [
                "https://www.linkedin.com/login",
                "https://chatgpt.com/",
                "https://mail.google.com/",
            ],
            "domains": ["linkedin.com", "chatgpt.com", "openai.com", "google.com", "gmail.com"],
            "cookie_key": None,
        }
    }

    target = service_map.get((service or "").strip().lower())
    if not target:
        task_manager.fail_task(f"Unknown login service: '{service}'")
        return

    service_name = target["name"]
    task_manager.start_task(f"Login Session — {service_name}", total_items=1)
    task_manager.log(f"Launching Firefox in headed mode (headless=False) for {service_name}...")

    try:
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=False,
                sync_cookies_domains=target["domains"],
            )
            task_manager.set_active_context(context)

            urls = target["urls"]
            first_page = context.pages[0] if context.pages else context.new_page()
            task_manager.log(f"Navigating to {urls[0]}...")
            try:
                first_page.goto(urls[0], wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                task_manager.log(f"Navigation note ({urls[0]}): {e}")

            for url in urls[1:]:
                task_manager.log(f"Opening {url} in new tab...")
                try:
                    new_p = context.new_page()
                    new_p.goto(url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    task_manager.log(f"Navigation note ({url}): {e}")

            task_manager.log("👉 Please complete login in the opened Firefox window.")
            task_manager.log("👉 When finished, simply close the Firefox browser window (or click Stop in Reach) to save.")

            while not task_manager.is_cancel_requested():
                try:
                    open_pages = [p for p in context.pages if not p.is_closed()]
                    if not open_pages:
                        break
                except Exception:
                    break
                time.sleep(1.0)

            try:
                context.close()
            except Exception:
                pass
            task_manager.clear_active_context()

            cookies = check_firefox_session_cookies()
            if target["cookie_key"]:
                is_authed = cookies.get(target["cookie_key"], False)
                if is_authed:
                    task_manager.log(f"✓ {service_name} authentication detected!")
                    task_manager.finish_task(f"{service_name} login successful.")
                else:
                    task_manager.log(f"⚠️ {service_name} cookies not yet detected. Refresh health if already logged in.")
                    task_manager.finish_task(f"{service_name} login session closed.")
            else:
                summary = [f"{k.capitalize()}: {'✓ Logged in' if v else '✗ Missing'}" for k, v in cookies.items()]
                task_manager.log(f"Session cookies: {', '.join(summary)}")
                task_manager.finish_task("Login session completed.")

    except Exception as e:
        task_manager.clear_active_context()
        if not task_manager.is_cancel_requested():
            task_manager.fail_task(f"Login Session Error: {str(e)}")



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

    recent = get_recently_sent_recipients([recipient], cooldown_days=SEND_COOLDOWN_DAYS)
    if recipient.strip().lower() in recent:
        hit = recent[recipient.strip().lower()]
        wait = hit["wait_seconds"]
        hours = wait // 3600
        task_manager.fail_task(
            f"An email was already sent to {recipient} within the last "
            f"{SEND_COOLDOWN_DAYS} days. Please wait ~{hours}h before sending again."
        )
        return

    hl = is_headless()
    try:
        mode_str = "headless mode (silent background)" if hl else "headed mode (visible window)"
        task_manager.log(f"Launching Firefox in {mode_str} for direct sending to {author} ({recipient})...")
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=hl,
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

    # Final cooldown guard: skip any recipients emailed within the cooldown window.
    posts_cache = {}
    candidate_emails = []
    for pid in post_ids:
        post = get_post_by_id(pid)
        if post:
            posts_cache[pid] = post
            post_emails = post.get("contact_emails", [])
            if post_emails:
                candidate_emails.append(post_emails[0])
    recent = get_recently_sent_recipients(candidate_emails, cooldown_days=SEND_COOLDOWN_DAYS)
    if recent:
        skipped = []
        remaining = []
        for pid in post_ids:
            post = posts_cache.get(pid)
            post_emails = (post or {}).get("contact_emails", [])
            recipient = post_emails[0].strip().lower() if post_emails else ""
            if recipient and recipient in recent:
                wait_h = recent[recipient]["wait_seconds"] // 3600
                skipped.append((post.get("author_name", pid), recipient, wait_h))
            else:
                remaining.append(pid)
        for author, recipient, wait_h in skipped:
            task_manager.log(
                f"  ⏭ Skipping {author} ({recipient}): already emailed within the last "
                f"{SEND_COOLDOWN_DAYS} days (~{wait_h}h remaining)."
            )
            failed.append((author, f"Already emailed recently (~{wait_h}h cooldown remaining)"))
        post_ids = remaining
        if not post_ids:
            task_manager.fail_task(
                f"All recipients were emailed within the last {SEND_COOLDOWN_DAYS} days. Nothing to send."
            )
            return

    hl = is_headless()
    try:
        mode_str = "headless mode (silent background)" if hl else "headed mode (visible window)"
        task_manager.log(f"Launching Firefox in {mode_str} to send {len(post_ids)} applications...")
        with sync_playwright() as playwright:
            context = launch_firefox_context(
                playwright,
                headless=hl,
                sync_cookies_domains=["google.com", "gmail.com"],
            )
            task_manager.set_active_context(context)
            try:
                page = context.pages[0] if context.pages else context.new_page()

                task_manager.log("Navigating to Gmail...")
                navigate_to_gmail(page)

                for idx, post_id in enumerate(post_ids, 1):
                    if task_manager.is_cancel_requested():
                        task_manager.log("🛑 Batch sending stopped by user.")
                        return

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
                        if task_manager.is_cancel_requested():
                            task_manager.log(f"  🛑 Sending stopped for {author} upon user request.")
                            return
                        task_manager.log(f"  ✗ Failed to send to {author}: {send_err}")
                        failed.append((author, str(send_err)))

                    task_manager.update_progress(idx)

                    if idx < len(post_ids):
                        pause = random.uniform(
                            config.get("pacing_min_seconds", 4),
                            config.get("pacing_max_seconds", 8)
                        )
                        task_manager.log(f"  Waiting {pause:.1f}s before sending next email...")
                        p_start = time.time()
                        while time.time() - p_start < pause:
                            if task_manager.is_cancel_requested():
                                task_manager.log("🛑 Pacing pause interrupted by user cancellation.")
                                return
                            time.sleep(0.5)

                task_manager.log("Closing browser session...")
                context.close()

                if task_manager.is_cancel_requested():
                    return

                if failed and successful == 0:
                    reasons = "; ".join([f"{a}: {m}" for a, m in failed[:3]])
                    task_manager.fail_task(f"Failed to send all {len(failed)} emails: {reasons}")
                elif failed:
                    task_manager.finish_task(f"Sent {successful} of {len(post_ids)} applications. ({len(failed)} failed)")
                else:
                    task_manager.finish_task(f"Successfully sent all {successful} applications via Gmail!")
            finally:
                task_manager.clear_active_context()

    except Exception as e:
        if not task_manager.is_cancel_requested():
            task_manager.fail_task(f"Batch Send Error: {str(e)}")


import subprocess
import threading


def run_scraper_subprocess_with_timeout(
    task_name: str,
    script_path: str,
    inactivity_timeout_seconds: float = 90.0,
    finish_message: str = "Scraping finished successfully.",
    extra_env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
):
    """
    Execute a scraping script in a subprocess monitored with an inactivity watchdog.
    If the scraper stops producing output / making progress for 90 seconds,
    the watchdog terminates the subprocess, closes the task cleanly, and
    preserves all jobs saved in the database up to that point.
    """
    task_manager.start_task(task_name, total_items=1)
    try:
        task_manager.log(f"Starting {task_name} (inactivity timeout: {int(inactivity_timeout_seconds)}s)...")

        env = os.environ.copy()
        if extra_env:
            env.update({k: str(v) for k, v in extra_env.items() if v is not None})

        proc = subprocess.Popen(
            [sys.executable, "-u", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=cwd or PROJECT_ROOT,
        )
        task_manager.set_active_proc(proc)

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
            if task_manager.is_cancel_requested():
                break
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
        task_manager.clear_active_proc()

        if task_manager.is_cancel_requested():
            task_manager.log(f"🛑 {task_name} was stopped upon user request.")
            return

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
        task_manager.clear_active_proc()
        if not task_manager.is_cancel_requested():
            task_manager.fail_task(str(e))


def run_infopark_scraper():
    """
    Run the Infopark Jobs Scraper via subprocess with 90-second inactivity timeout.
    Scrapes today's opportunities from https://infopark.in/companies-job,
    extracting full JDs and direct recruiter emails.
    """
    script_path = os.path.join(PROJECT_ROOT, "scripts", "infopark_jobs_search.py")
    run_scraper_subprocess_with_timeout(
        task_name="Infopark Jobs Scraper",
        script_path=script_path,
        inactivity_timeout_seconds=90.0,
        finish_message="Infopark jobs scraping finished successfully."
    )


def run_linkedin_scraper(query: Optional[str] = None, location: Optional[str] = None, time_filter: Optional[str] = None):
    """
    Run the LinkedIn Posts Scraper in headed Firefox (headless=False) via subprocess
    with 90-second inactivity timeout, with optional query, location, and time_filter parameters.
    """
    script_path = os.path.join(PROJECT_ROOT, "scripts", "linkedin_posts_search.py")
    task_label = "LinkedIn Posts Scraper"
    if location and location.strip():
        task_label = f"LinkedIn Posts Scraper ({location.strip()})"

    extra_env = {
        "HEADLESS": "true" if is_headless() else "false"
    }
    if query:
        extra_env["SCRAPER_QUERY"] = query.strip()
    if location:
        extra_env["SCRAPER_LOCATION"] = location.strip()
    if time_filter:
        extra_env["SCRAPER_TIME_FILTER"] = time_filter.strip()

    run_scraper_subprocess_with_timeout(
        task_name=task_label,
        script_path=script_path,
        inactivity_timeout_seconds=90.0,
        finish_message="LinkedIn scraping finished successfully.",
        extra_env=extra_env,
    )


def run_linkedin_easy_apply_scraper(query: Optional[str] = None, location: Optional[str] = None, time_filter: Optional[str] = None):
    """
    Run the LinkedIn Job Portal & Easy Apply crawler in persistent Firefox context.
    Filters specifically for Easy Apply listings (f_AL=true), extracts JDs, and auto-applies
    or saves for questionnaire screening.
    """
    from src.services.easy_apply_service import run_easy_apply_crawler
    q = query or get_setting("search_query", "Full Stack Developer") or "Full Stack Developer"
    loc = location or get_setting("search_location", "India") or "India"
    tf = time_filter or "24h"
    run_easy_apply_crawler(keywords=q, location=loc, time_filter=tf, max_jobs=25, task_manager=task_manager)


def run_single_easy_apply(post_id: str):
    """Run Easy Apply submission for a single job post in Firefox."""
    from src.services.easy_apply_service import apply_to_single_easy_apply_post
    apply_to_single_easy_apply_post(post_id, task_manager=task_manager)


SCRAPER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "linkedin": {
        "id": "linkedin",
        "name": "LinkedIn Posts",
        "icon": "💼",
        "description": "Scrapes hiring posts via search query in headed Firefox",
        "runner": run_linkedin_scraper,
    },
    "linkedin_jobs": {
        "id": "linkedin_jobs",
        "name": "LinkedIn Easy Apply",
        "icon": "⚡",
        "description": "Scrapes linkedin.com/jobs with Easy Apply (f_AL=true) and submits applications",
        "runner": run_linkedin_easy_apply_scraper,
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


def run_scraper_by_source(source_id: str, query: Optional[str] = None, location: Optional[str] = None, time_filter: Optional[str] = None):
    """Dispatch and run a scraper background task by source ID with optional query, location, and time filter."""
    source_lower = (source_id or "linkedin").strip().lower()
    scraper = SCRAPER_REGISTRY.get(source_lower)
    if not scraper:
        valid_sources = list(SCRAPER_REGISTRY.keys())
        raise ValueError(f"Unknown scraper source '{source_id}'. Supported sources: {valid_sources}")
    
    if source_lower == "linkedin":
        run_linkedin_scraper(query=query, location=location, time_filter=time_filter)
    elif source_lower in ("linkedin_jobs", "easy_apply"):
        run_linkedin_easy_apply_scraper(query=query, location=location, time_filter=time_filter)
    else:
        scraper["runner"]()

