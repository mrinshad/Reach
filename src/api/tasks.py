"""
FastAPI router for sequential FIFO task queue management and automation job triggers.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query

from src.db import (
    upsert_post,
    get_post_by_id,
    get_recently_sent_recipients,
    SEND_COOLDOWN_DAYS,
    get_activity_logs,
    get_activity_log_by_id,
    clear_activity_logs,
)
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
    run_interactive_login,
)
from .models import (
    GenerateBatchPayload,
    SendBatchPayload,
    DirectOutreachPayload,
    ScrapePayload,
    EasyApplyBatchScrapePayload,
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


def build_crawler_labels(source: str, query: Optional[str] = None, location: Optional[str] = None, time_filter: Optional[str] = None):
    """Generate clean full_name, short_name, and descriptive snippet for crawler tasks."""
    s_lower = (source or "").lower()
    if s_lower in ("linkedin_jobs", "easy_apply"):
        src_title = "LinkedIn Easy Apply"
        short_name = "Easy Apply Crawler"
    elif s_lower == "linkedin":
        src_title = "LinkedIn"
        short_name = "LinkedIn Scraper"
    else:
        src_title = (source or "Web").capitalize()
        short_name = f"{src_title} Scraper"

    snippet_parts = []
    if query and query.strip():
        clean_q = query.strip().strip("'\"")
        if len(clean_q) > 22:
            clean_q = clean_q[:20] + "..."
        snippet_parts.append(f'"{clean_q}"')
    if location and location.strip():
        clean_loc = location.strip().split(",")[0].strip()
        snippet_parts.append(clean_loc)
    if time_filter and time_filter.lower() not in ("24h", "today"):
        snippet_parts.append(f"[{time_filter}]")
    snippet = " • ".join(snippet_parts) if snippet_parts else "Default Search"
    full_name = f"{short_name} ({snippet})"
    return full_name, short_name, snippet


@router.post("/generate-email/{post_id}")
def api_generate_email(post_id: str, force: bool = False):
    """Enqueue ChatGPT generation for a single post with optional force override."""
    post = get_post_by_id(post_id)
    author = (post.get("author_name") if post else None) or f"Post #{post_id[:8]}"
    res = task_manager.enqueue_task(
        task_type="chatgpt",
        task_name=f"Generate Email — {author}",
        short_name="ChatGPT Email",
        snippet=author,
        runner_func=run_chatgpt_batch,
        args=([post_id], force),
        metadata={"post_id": post_id, "count": 1, "force": force, "author": author},
    )
    msg = f"Queued for email generation (Position #{res['position']})" if res["queued"] else f"ChatGPT email generation started for {author}."
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
        short_name="Batch Email Gen",
        snippet=f"{count} posts",
        runner_func=run_chatgpt_batch,
        args=(payload.post_ids, payload.force),
        metadata={"count": count, "post_ids": payload.post_ids, "force": payload.force},
    )
    msg = f"Queued batch generation of {count} posts (Position #{res['position']})" if res["queued"] else f"Started email generation for {count} posts."
    return {"success": True, "message": msg, **res}


@router.post("/open-gmail/{post_id}")
def api_open_gmail(post_id: str):
    """Enqueue Gmail draft creation in headed Firefox with resume attached."""
    post = get_post_by_id(post_id)
    author = (post.get("author_name") if post else None) or f"Post #{post_id[:8]}"
    res = task_manager.enqueue_task(
        task_type="gmail_draft",
        task_name=f"Gmail Draft — {author}",
        short_name="Gmail Draft",
        snippet=author,
        runner_func=run_open_gmail_draft,
        args=(post_id,),
        metadata={"post_id": post_id, "author": author},
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

    post = get_post_by_id(post_id)
    author = (post.get("author_name") if post else None) or "Recruiter"
    res = task_manager.enqueue_task(
        task_type="gmail_send",
        task_name=f"Send Email — {author}",
        short_name="Send Email",
        snippet=author,
        runner_func=run_send_single_draft,
        args=(post_id,),
        metadata={"post_id": post_id, "author": author},
    )
    msg = f"Queued email direct sending (Position #{res['position']})" if res["queued"] else f"Directly sending application email to {author} via Gmail..."
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
        short_name="Batch Send",
        snippet=f"{count} applications",
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
                short_name="Direct Draft",
                snippet=recipient,
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
                short_name="Direct Send",
                snippet=recipient,
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
        task_name="Infopark Jobs Scraper",
        short_name="Infopark Scraper",
        snippet="Kochi Openings",
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

    full_name, short_name, snippet = build_crawler_labels("linkedin", query=query, location=loc, time_filter=time_filter)
    res = task_manager.enqueue_task(
        task_type="crawler",
        task_name=full_name,
        short_name=short_name,
        snippet=snippet,
        runner_func=run_linkedin_scraper,
        args=(query, loc, time_filter),
        metadata={"source": "linkedin", "query": query, "location": loc, "time_filter": time_filter},
    )
    msg = f"Queued {short_name} ({snippet}) (Position #{res['position']})" if res["queued"] else f"{short_name} started in headed Firefox."
    return {"success": True, "message": msg, **res}


@router.post("/scrape/easy-apply")
def api_trigger_scrape_easy_apply(payload: Optional[ScrapePayload] = None):
    """Enqueue the LinkedIn Job Portal & Easy Apply crawler in persistent Firefox."""
    from src.services.automation_tasks import run_linkedin_easy_apply_scraper
    query = payload.search_query if payload else None
    loc = payload.location if payload else None
    time_filter = (payload.time_filter or "24h") if payload else "24h"

    full_name, short_name, snippet = build_crawler_labels("linkedin_jobs", query=query, location=loc, time_filter=time_filter)
    res = task_manager.enqueue_task(
        task_type="crawler",
        task_name=full_name,
        short_name=short_name,
        snippet=snippet,
        runner_func=run_linkedin_easy_apply_scraper,
        args=(query, loc, time_filter),
        metadata={"source": "linkedin_jobs", "query": query, "location": loc, "time_filter": time_filter},
    )
    msg = f"Queued {short_name} ({snippet}) (Position #{res['position']})" if res["queued"] else f"{short_name} started."
    return {"success": True, "message": msg, **res}


@router.post("/scrape/easy-apply/batch")
def api_trigger_scrape_easy_apply_batch(payload: EasyApplyBatchScrapePayload):
    """Enqueue multiple LinkedIn Easy Apply crawler tasks sequentially for a list of keywords."""
    from src.services.automation_tasks import run_linkedin_easy_apply_scraper
    keywords = [k.strip() for k in payload.keywords if k and k.strip()]
    if not keywords:
        raise HTTPException(status_code=400, detail="No valid keywords provided for bulk search.")

    queued = []
    loc = payload.location or "India"
    time_filter = payload.time_filter or "24h"

    for kw in keywords:
        full_name, short_name, snippet = build_crawler_labels("linkedin_jobs", query=kw, location=loc, time_filter=time_filter)
        res = task_manager.enqueue_task(
            task_type="crawler",
            task_name=full_name,
            short_name=short_name,
            snippet=snippet,
            runner_func=run_linkedin_easy_apply_scraper,
            args=(kw, loc, time_filter),
            metadata={"source": "linkedin_jobs", "query": kw, "location": loc, "time_filter": time_filter},
        )
        queued.append({"keyword": kw, **res})

    first_pos = queued[0]["position"] if queued else 1
    return {
        "success": True,
        "message": f"Queued {len(queued)} Easy Apply searches in FIFO queue (starting at Position #{first_pos}).",
        "count": len(queued),
        "tasks": queued,
    }


@router.post("/easy-apply/{post_id}")
def api_trigger_single_easy_apply(post_id: str):
    """Enqueue Easy Apply submission for a specific job post."""
    from src.services.automation_tasks import run_single_easy_apply
    post = get_post_by_id(post_id)
    title = (post.get("author_headline") if post else None) or f"Job #{post_id[:8]}"
    company = (post.get("author_name") if post else None) or "Company"

    res = task_manager.enqueue_task(
        task_type="easy_apply",
        task_name=f"Easy Apply — {title} @ {company}",
        short_name="Easy Apply",
        snippet=f"{company}",
        runner_func=run_single_easy_apply,
        args=(post_id,),
        metadata={"post_id": post_id, "title": title, "company": company},
    )
    msg = f"Queued Easy Apply for {title} (Position #{res['position']})" if res["queued"] else f"Easy Apply started for {title}."
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
        full_name, short_name, snippet = build_crawler_labels(src, query=query, location=loc, time_filter=time_filter)
        res = task_manager.enqueue_task(
            task_type="crawler",
            task_name=full_name,
            short_name=short_name,
            snippet=snippet,
            runner_func=run_scraper_by_source,
            args=(src, query, loc, time_filter),
            metadata={"source": src, "query": query, "location": loc, "time_filter": time_filter},
        )
        msg = f"Queued {short_name} ({snippet}) (Position #{res['position']})" if res["queued"] else f"Scraper for '{src}' started."
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


@router.post("/tasks/cancel")
def api_cancel_active_task():
    """Cancel the currently executing automation task."""
    stopped = task_manager.cancel_active_task()
    if not stopped:
        return {"success": False, "message": "No automation task is currently running."}
    return {"success": True, "message": "Ongoing task has been stopped."}


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


@router.post("/tasks/login/{service}")
def api_launch_service_login(service: str):
    """
    Launch headed Firefox persistent context for interactive login to
    LinkedIn, ChatGPT, Gmail, or All services.
    """
    valid_services = {
        "linkedin": "LinkedIn",
        "chatgpt": "ChatGPT",
        "gmail": "Gmail",
        "all": "All Services (LinkedIn, ChatGPT, Gmail)",
    }
    svc_lower = (service or "").strip().lower()
    if svc_lower not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service '{service}'. Choose from: {list(valid_services.keys())}",
        )

    # Check if an automation task is currently executing to avoid browser profile locks
    current_state = task_manager.get_state()
    if current_state.get("status") == "running":
        current_name = current_state.get("task_name") or "Another automation task"
        raise HTTPException(
            status_code=409,
            detail=f"An automation task ('{current_name}') is currently running. Please wait for it to complete or stop it before launching an interactive login session.",
        )

    label = valid_services[svc_lower]
    res = task_manager.enqueue_task(
        task_type="service_login",
        task_name=f"Interactive Login — {label}",
        short_name=f"{svc_lower.capitalize()} Login",
        snippet="Browser Authentication",
        runner_func=run_interactive_login,
        args=(svc_lower,),
        metadata={"service": svc_lower, "service_name": label},
    )
    return {
        "success": True,
        "message": f"Opening headed Firefox for {label} login...",
        **res,
    }


# =====================================================================
# ACTIVITY RUN LOGS & AUTOMATION HISTORY ENDPOINTS
# =====================================================================

@router.get("/activity-logs")
def api_get_activity_logs(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: Optional[str] = Query(None, description="Filter by task type, e.g. scraper, easy_apply"),
    status: Optional[str] = Query(None, description="Filter by status, e.g. completed, error, stopped"),
):
    """Retrieve paginated activity run logs for automated background operations."""
    return get_activity_logs(limit=limit, offset=offset, task_type=type, status=status)


@router.get("/activity-logs/{log_id}")
def api_get_activity_log_detail(log_id: str):
    """Retrieve full activity log record including all console terminal logs."""
    run = get_activity_log_by_id(log_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Activity log with ID '{log_id}' not found.")
    return run


@router.delete("/activity-logs")
def api_clear_activity_logs():
    """Clear all stored activity logs history."""
    count = clear_activity_logs()
    return {"success": True, "message": f"Cleared {count} activity log(s).", "count": count}

