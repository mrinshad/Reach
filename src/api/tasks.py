"""
FastAPI router for sequential FIFO task queue management and automation job triggers.
"""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException

from src.db import upsert_post, get_post_by_id, get_recently_sent_recipients, SEND_COOLDOWN_DAYS
from src.services.automation_tasks import (
    task_manager,
    run_chatgpt_batch,
    run_open_gmail_draft,
    run_send_single_draft,
    run_send_batch_drafts,
    run_infopark_scraper,
    run_linkedin_scraper,
    get_registered_scrapers,
    run_scraper_by_source,
)
from .models import (
    GenerateBatchPayload,
    SendBatchPayload,
    DirectOutreachPayload,
    ScrapePayload,
    DEFAULT_OPPORTUNITY_SUBJECT,
    DEFAULT_OPPORTUNITY_BODY,
)

router = APIRouter(prefix="/api", tags=["Tasks & Automation"])


def check_send_cooldown(post_ids):
    """
    Check which of the given posts target a recipient email that was already
    emailed within the cooldown window. Returns (blocked, allowed) lists where
    each blocked entry carries the remaining wait time.
    """
    posts = []
    for pid in post_ids:
        post = get_post_by_id(pid)
        if post:
            posts.append(post)

    primary_emails = []
    for post in posts:
        emails = post.get("contact_emails") or []
        if emails:
            primary_emails.append(emails[0])

    recent = get_recently_sent_recipients(primary_emails, cooldown_days=SEND_COOLDOWN_DAYS)

    blocked = []
    allowed = []
    for post in posts:
        emails = post.get("contact_emails") or []
        recipient = (emails[0].strip().lower() if emails else "")
        hit = recent.get(recipient) if recipient else None
        if hit:
            blocked.append({
                "post_id": post["id"],
                "author_name": post.get("author_name", "Recruiter"),
                "email": recipient,
                "last_sent_at": hit["last_sent_at"],
                "wait_seconds": hit["wait_seconds"],
            })
        else:
            allowed.append(post["id"])
    return blocked, allowed


def format_wait_time(wait_seconds: int) -> str:
    """Human-readable remaining cooldown, e.g. '2 days 5 hours' or '4 hours 12 minutes'."""
    days = wait_seconds // 86400
    hours = (wait_seconds % 86400) // 3600
    minutes = (wait_seconds % 3600) // 60
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if not parts and minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts:
        parts.append("less than a minute")
    return " ".join(parts[:2])


@router.post("/generate-email/{post_id}")
def api_generate_email(post_id: str, force: bool = False):
    """Enqueue ChatGPT generation for a single post with optional force override."""
    res = task_manager.enqueue_task(
        task_type="chatgpt",
        task_name=f"ChatGPT Email Generation (Post #{post_id})",
        runner_func=run_chatgpt_batch,
        args=([post_id], force),
        metadata={"post_id": post_id, "count": 1, "force": force},
    )
    msg = f"Queued for email generation (Position #{res['position']})" if res["queued"] else f"ChatGPT email generation started for post {post_id}."
    return {"success": True, "message": msg, **res}


@router.post("/generate-batch")
def api_generate_batch(payload: GenerateBatchPayload):
    """Enqueue ChatGPT generation for selected posts in headed Firefox."""
    if not payload.post_ids:
        raise HTTPException(status_code=400, detail="No post IDs provided.")

    count = len(payload.post_ids)
    res = task_manager.enqueue_task(
        task_type="chatgpt",
        task_name=f"Batch Email Generation ({count} posts)",
        runner_func=run_chatgpt_batch,
        args=(payload.post_ids,),
        metadata={"count": count, "post_ids": payload.post_ids},
    )
    msg = f"Queued batch generation of {count} posts (Position #{res['position']})" if res["queued"] else f"Started email generation for {count} posts."
    return {"success": True, "message": msg, **res}


@router.post("/open-gmail/{post_id}")
def api_open_gmail(post_id: str):
    """Enqueue Gmail draft creation in headed Firefox with resume attached."""
    res = task_manager.enqueue_task(
        task_type="gmail_draft",
        task_name=f"Gmail Draft (Post #{post_id})",
        runner_func=run_open_gmail_draft,
        args=(post_id,),
        metadata={"post_id": post_id},
    )
    msg = f"Queued Gmail draft opening (Position #{res['position']})" if res["queued"] else "Opening Gmail compose in headed Firefox..."
    return {"success": True, "message": msg, **res}


@router.post("/send-direct/{post_id}")
def api_send_direct(post_id: str):
    """Enqueue direct email sending in Gmail without manual interaction."""
    blocked, _ = check_send_cooldown([post_id])
    if blocked:
        b = blocked[0]
        wait = format_wait_time(b["wait_seconds"])
        raise HTTPException(
            status_code=409,
            detail=(
                f"An application email was already sent to {b['email']} "
                f"within the last {SEND_COOLDOWN_DAYS} days. "
                f"Please wait {wait} before sending again."
            ),
        )

    res = task_manager.enqueue_task(
        task_type="gmail_send",
        task_name=f"Direct Send (Post #{post_id})",
        runner_func=run_send_single_draft,
        args=(post_id,),
        metadata={"post_id": post_id},
    )
    msg = f"Queued email direct sending (Position #{res['position']})" if res["queued"] else "Directly sending application email via Gmail..."
    return {"success": True, "message": msg, **res}


@router.post("/send-batch")
def api_send_batch(payload: SendBatchPayload):
    """Enqueue multi-draft batch email sending in Gmail directly."""
    if not payload.post_ids:
        raise HTTPException(status_code=400, detail="No post IDs provided for batch sending.")

    blocked, allowed = check_send_cooldown(payload.post_ids)
    if blocked and not allowed:
        details = "; ".join(
            f"{b['email']} (wait {format_wait_time(b['wait_seconds'])})" for b in blocked
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"All selected recipients were emailed within the last "
                f"{SEND_COOLDOWN_DAYS} days: {details}."
            ),
        )

    count = len(allowed)
    res = task_manager.enqueue_task(
        task_type="gmail_send_batch",
        task_name=f"Batch Email Sending ({count} applications)",
        runner_func=run_send_batch_drafts,
        args=(allowed,),
        metadata={"count": count, "post_ids": allowed, "skipped_cooldown": [b["post_id"] for b in blocked]},
    )
    msg = f"Queued batch sending for {count} applications (Position #{res['position']})" if res["queued"] else f"Started direct sending for {count} applications."
    if blocked:
        msg += f" Skipped {len(blocked)} recently-emailed recipient(s)."
    return {
        "success": True,
        "message": msg,
        "skipped_cooldown": blocked,
        **res,
    }


@router.post("/send-preflight")
def api_send_preflight(payload: SendBatchPayload):
    """
    Check which posts target recipients already emailed within the cooldown
    window. Lets the UI warn the user before queueing any browser automation.
    """
    if not payload.post_ids:
        return {"success": True, "cooldown_days": SEND_COOLDOWN_DAYS, "blocked": [], "allowed": []}
    blocked, allowed = check_send_cooldown(payload.post_ids)
    return {
        "success": True,
        "cooldown_days": SEND_COOLDOWN_DAYS,
        "blocked": blocked,
        "allowed": allowed,
    }


@router.post("/direct-outreach")
def api_direct_outreach(payload: DirectOutreachPayload):
    """
    Direct opportunity cold outreach.
    Persists a record in PostgreSQL and enqueues Gmail automated sending or draft review.
    """
    recipient = (payload.recipient_email or "").strip()
    if not recipient or "@" not in recipient:
        raise HTTPException(status_code=400, detail="A valid recipient email address is required.")

    company = (payload.company_name or "").strip()
    author_name = company if company else recipient
    subject = (payload.subject or "").strip() or DEFAULT_OPPORTUNITY_SUBJECT
    body = (payload.body or "").strip() or DEFAULT_OPPORTUNITY_BODY
    location = (payload.location or "").strip() or None
    mode = (payload.mode or "send").strip().lower()

    unique_token = uuid.uuid4().hex[:12]
    post_url = f"direct://{unique_token}"

    post_data = {
        "author_name": author_name,
        "author_headline": "Direct Opportunity Outreach",
        "author_profile": "",
        "posted_date_raw": datetime.now().strftime("%d-%m-%Y"),
        "full_text": f"Direct opportunity outreach to {author_name} ({recipient}).\n\nSubject: {subject}\n\n{body}",
        "contact_emails": [recipient],
        "external_links": [],
        "min_experience": 3.0,
        "max_experience": None,
        "raw_experience": "3+ years",
        "seniority_level": "Mid",
        "is_fresher": False,
        "category": "EMAIL_OUTREACH",
        "status": "EMAIL_GENERATED",
        "generated_subject": subject,
        "generated_body": body,
        "post_url": post_url,
        "location": location,
    }

    try:
        post_id, _ = upsert_post(post_data)

        if mode == "draft":
            res = task_manager.enqueue_task(
                task_type="gmail_draft",
                task_name=f"Direct Opportunity Draft ({recipient})",
                runner_func=run_open_gmail_draft,
                args=(post_id,),
                metadata={"post_id": post_id, "recipient": recipient},
            )
            msg = f"Queued Gmail draft for {recipient} (Position #{res['position']})" if res["queued"] else f"Opening Gmail draft for {recipient} in headed Firefox..."
            return {"success": True, "post_id": post_id, "message": msg, **res}
        else:
            res = task_manager.enqueue_task(
                task_type="gmail_send",
                task_name=f"Direct Opportunity Send ({recipient})",
                runner_func=run_send_single_draft,
                args=(post_id,),
                metadata={"post_id": post_id, "recipient": recipient},
            )
            msg = f"Queued email sending to {recipient} (Position #{res['position']})" if res["queued"] else f"Sending opportunity email to {recipient} directly via Gmail..."
            return {"success": True, "post_id": post_id, "message": msg, **res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape/infopark")
def api_trigger_scrape_infopark():
    """Enqueue the Infopark jobs scraper."""
    res = task_manager.enqueue_task(
        task_type="crawler",
        task_name="Infopark Jobs Crawler",
        runner_func=run_infopark_scraper,
        metadata={"source": "infopark"},
    )
    msg = f"Queued Infopark scraper (Position #{res['position']})" if res["queued"] else "Infopark jobs scraper started."
    return {"success": True, "message": msg, **res}


@router.post("/scrape/linkedin")
def api_trigger_scrape_linkedin(payload: Optional[ScrapePayload] = None):
    """Enqueue the LinkedIn scraper in headed Firefox with optional location, query, and time_filter."""
    query = payload.search_query if payload else None
    loc = payload.location if payload else None
    time_filter = (payload.time_filter or "24h") if payload else "24h"

    label = f"LinkedIn Crawler ({loc or 'Default'})" if loc else "LinkedIn Crawler"
    if time_filter and time_filter != "24h":
        label += f" [{time_filter}]"
    res = task_manager.enqueue_task(
        task_type="crawler",
        task_name=label,
        runner_func=run_linkedin_scraper,
        args=(query, loc, time_filter),
        metadata={"source": "linkedin", "query": query, "location": loc, "time_filter": time_filter},
    )
    msg = f"Queued LinkedIn scraper for {loc or 'default'} (Position #{res['position']})" if res["queued"] else "LinkedIn scraper started in headed Firefox."
    return {"success": True, "message": msg, **res}


@router.get("/scrapers")
def api_get_scrapers():
    """Return list of registered website scrapers for the crawler source selector."""
    return get_registered_scrapers()


@router.post("/scrape")
def api_trigger_scrape(payload: Optional[ScrapePayload] = None, source: Optional[str] = None):
    """Enqueue scraper by source using the extensible scraper registry with optional query, location, and time_filter."""
    src = "linkedin"
    query = None
    loc = None
    time_filter = "24h"
    if payload:
        if payload.source:
            src = payload.source
        query = payload.search_query
        loc = payload.location
        if payload.time_filter:
            time_filter = payload.time_filter
    elif source:
        src = source

    try:
        label = f"{src.capitalize()} Crawler" + (f" ({loc})" if loc else "")
        if src == "linkedin" and time_filter and time_filter != "24h":
            label += f" [{time_filter}]"
        res = task_manager.enqueue_task(
            task_type="crawler",
            task_name=label,
            runner_func=run_scraper_by_source,
            args=(src, query, loc, time_filter),
            metadata={"source": src, "query": query, "location": loc, "time_filter": time_filter},
        )
        msg = f"Queued {label} (Position #{res['position']})" if res["queued"] else f"Scraper for '{src}' started."
        return {"success": True, "message": msg, **res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/status")
def api_get_task_status():
    """Poll current active or recent automation task status and real-time logs."""
    return task_manager.get_state()


@router.post("/tasks/clear")
def api_clear_task():
    """Reset task state to idle."""
    task_manager.clear_task()
    return {"success": True, "message": "Task state cleared."}


@router.post("/tasks/queue/cancel/{task_id}")
def api_cancel_queued_task(task_id: str):
    """Cancel a queued automation task before it executes."""
    ok = task_manager.cancel_queued_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Queued task not found or already running.")
    return {"success": True, "message": f"Task {task_id} removed from queue."}


@router.post("/tasks/queue/clear")
def api_clear_task_queue():
    """Clear all pending tasks in the execution queue."""
    cleared = task_manager.clear_queue()
    return {"success": True, "cleared": cleared, "message": f"Cleared {cleared} task(s) from the queue."}
