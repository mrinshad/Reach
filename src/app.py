"""
FastAPI Web Application & Automation Server

Provides a responsive REST API and static UI serving for the LinkedIn Job Automation
pipeline, with asynchronous background task management for headed Playwright runs.
"""

import os
import threading
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import uuid
import re
from datetime import datetime

from src.db import (
    get_posts,
    get_posts_paginated,
    get_post_by_id,
    get_stats,
    get_analytics_summary,
    update_post_status,
    update_post_email,
    mark_post_sent,
    revert_post_to_draft,
    move_post_to_review,
    upsert_post,
    get_distinct_rejection_reasons,
    get_rejection_reasons_with_counts,
    get_distinct_locations,
)
from src.experience_extractor import extract_experience
from src.config import load_config, save_config
from src.health_service import get_system_health
from src.automation_tasks import (
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="Reach Automation Hub", version="2.0.0")

# Mount static files
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def add_cache_control_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") or path == "/" or path == "/index.html" or path == "/sw.js":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Pydantic models for request bodies
class UpdateEmailPayload(BaseModel):
    subject: str
    body: str


class GenerateBatchPayload(BaseModel):
    post_ids: List[str]


class SendBatchPayload(BaseModel):
    post_ids: List[str]


class RejectPostPayload(BaseModel):
    reason: Optional[str] = None


class SpamPostPayload(BaseModel):
    reason: Optional[str] = "Scam"



class ManualPostPayload(BaseModel):
    author_name: Optional[str] = None
    company: Optional[str] = None
    author_headline: Optional[str] = None
    title: Optional[str] = None
    full_text: Optional[str] = None
    content: Optional[str] = None
    contact_emails: Optional[List[str]] = None
    post_url: Optional[str] = None
    location: Optional[str] = None


class SettingsPayload(BaseModel):
    resume_path: Optional[str] = None
    search_query: Optional[str] = None
    search_location: Optional[str] = None
    chatgpt_url: Optional[str] = None
    pacing_min_seconds: Optional[float] = None
    pacing_max_seconds: Optional[float] = None
    headless_mode: Optional[bool] = None
    headless: Optional[bool] = None


class HeadlessTogglePayload(BaseModel):
    headless: bool


class ScrapePayload(BaseModel):
    source: Optional[str] = "linkedin"
    location: Optional[str] = None
    search_query: Optional[str] = None


MAJOR_JOB_HUBS = [
    "San Francisco", "Seattle", "New York", "Boston", "Austin", "Los Angeles",
    "Toronto", "Vancouver", "Montreal",
    "London", "Dublin", "Amsterdam", "Berlin", "Paris", "Stockholm", "Copenhagen", "Zurich", "Munich",
    "Singapore", "Tokyo", "Seoul", "Beijing", "Shanghai", "Shenzhen", "Hong Kong",
    "Bengaluru", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi", "Kochi",
    "Dubai", "Abu Dhabi", "Riyadh", "Doha", "Manama", "Kuwait City", "Muscat", "Tel Aviv",
    "Sydney", "Melbourne", "Auckland",
    "São Paulo", "Mexico City", "Buenos Aires",
    "Cape Town", "Johannesburg", "Nairobi", "Remote"
]

DEFAULT_OPPORTUNITY_SUBJECT = "Full-Stack Software Engineer – Job Opportunities"
DEFAULT_OPPORTUNITY_BODY = """Hi,

I’m Mohammed Rinshad, a Full-Stack Software Engineer with 3+ years of experience in web and enterprise application development.

My experience includes React, Next.js, Node.js, TypeScript, .NET Core, REST APIs, PostgreSQL, SQL Server, Azure, GCP, CI/CD, authentication, RBAC, and database design. I’ve worked on ERP, accounting, education, and enterprise applications, including both frontend and backend development.

I’m currently looking for opportunities in Frontend, Backend, Full-Stack, DevOps, or Cloud Engineering. I’m open to relocating for the right opportunity and am also interested in remote roles.

I’ve attached my resume for reference. If there are any current or upcoming openings that match my background, I’d be grateful to be considered.

Regards,
Mohammed Rinshad P
+91 98956 12423
rinshadmorayur09@gmail.com
LinkedIn: linkedin.com/in/mrinshad
GitHub: github.com/mrinshad"""


class DirectOutreachPayload(BaseModel):
    recipient_email: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    mode: Optional[str] = "send"


@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    """Serve the single-page dashboard."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return FileResponse(index_file)


@app.api_route("/sw.js", methods=["GET", "HEAD"])
def serve_service_worker():
    """Serve service worker from root domain scope with Service-Worker-Allowed header."""
    sw_file = os.path.join(STATIC_DIR, "sw.js")
    if os.path.exists(sw_file):
        return FileResponse(
            sw_file,
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/"},
        )
    raise HTTPException(status_code=404, detail="Service worker not found")


@app.get("/api/health")
def api_get_health():
    """Return live session connectivity status for LinkedIn, ChatGPT, Gmail, and DB."""
    try:
        return get_system_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resume/upload")
async def api_upload_resume(file: UploadFile = File(...)):
    """Upload a new resume file anytime and set as the active global resume."""
    if not file.filename.lower().endswith((".pdf", ".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only PDF and Word documents (.pdf, .docx) are supported.")

    resumes_dir = os.path.join(os.path.dirname(BASE_DIR), "resumes")
    os.makedirs(resumes_dir, exist_ok=True)
    dest_path = os.path.join(resumes_dir, file.filename)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    updated = save_config({"resume_path": dest_path})
    return {
        "success": True,
        "filename": file.filename,
        "resume_path": dest_path,
        "config": updated,
    }


@app.post("/api/posts/manual")
def api_create_manual_post(payload: ManualPostPayload):
    """Manually add a Job Description into Discovered Posts."""
    raw_content = (payload.full_text or payload.content or "").strip()
    if not raw_content:
        raise HTTPException(status_code=400, detail="Job Description text is required.")

    author = (payload.author_name or payload.company or "Direct Company / Recruiter").strip()
    headline = (payload.author_headline or payload.title or "Software Opportunity").strip()

    # Auto-extract emails if not provided
    emails = payload.contact_emails or []
    if not emails:
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_content)
        emails = list(dict.fromkeys(emails))

    # Auto-extract experience
    exp_info = extract_experience(raw_content)

    # Unique URL if not provided
    post_url = payload.post_url or f"manual://{uuid.uuid4().hex[:12]}"

    post_record = {
        "author_name": author,
        "author_headline": headline,
        "author_profile": "",
        "post_date": datetime.now().strftime("%d-%m-%Y"),
        "post_url": post_url,
        "full_text": raw_content,
        "detected_emails": emails,
        "detected_links": [post_url] if post_url.startswith("http") else [],
        "experience": exp_info,
        "category": "EMAIL_OUTREACH" if emails else "DRAFT_PORTAL",
        "location": payload.location.strip() if payload.location else None,
    }

    try:
        post_id, created = upsert_post(post_record, skip_if_exists=False)
        saved_post = get_post_by_id(post_id)
        return {"ok": True, "success": True, "post_id": post_id, "post": saved_post}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def api_get_stats():
    """Return counts for dashboard metrics cards."""
    try:
        stats = get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics")
def api_get_analytics(days: Optional[int] = Query(30, ge=0, le=365)):
    """Return aggregated analytics for dashboard charts (applied trend, scraping inflow, status breakdown, etc.)."""
    try:
        data = get_analytics_summary(days=days)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/posts")
def api_get_posts(
    status: Optional[str] = None,
    gen_status: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    min_exp: Optional[float] = None,
    max_exp: Optional[float] = None,
    search: Optional[str] = None,
    order_by: Optional[str] = None,
    reason: Optional[str] = None,
    date_filter: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieve posts with filtering, search, sorting, location, and pagination."""
    try:
        limit_val = getattr(limit, "default", limit)
        offset_val = getattr(offset, "default", offset)
        safe_limit = int(limit_val) if limit_val is not None else 25
        safe_offset = int(offset_val) if offset_val is not None else 0

        result = get_posts_paginated(
            category=category,
            status=status,
            gen_status=gen_status,
            source=source,
            min_exp=min_exp,
            max_exp=max_exp,
            search=search,
            order_by=order_by,
            reason=reason,
            date_filter=date_filter,
            location=location,
            limit=safe_limit,
            offset=safe_offset,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/locations")
def api_get_locations():
    """Retrieve distinct locations saved in DB and predefined major job hubs."""
    try:
        saved_locs = get_distinct_locations()
        return {"locations": saved_locs, "presets": MAJOR_JOB_HUBS}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reasons")
def api_get_reasons():
    """Retrieve distinct cancellation/rejection reasons with counts for filtering."""
    try:
        counts = get_rejection_reasons_with_counts()
        reasons = [c["reason"] for c in counts]
        return {"reasons": reasons, "counts": counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/posts/{post_id}")
def api_get_post(post_id: str):
    """Retrieve single post details."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.put("/api/posts/{post_id}")
def api_update_post(post_id: str, payload: UpdateEmailPayload):
    """Update edited email subject and body for a post."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        update_post_email(post_id, payload.subject, payload.body)
        return {"success": True, "message": "Email draft updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/posts/{post_id}/move-to-review")
def api_move_to_review(post_id: str):
    """Move a discovered post directly to review/draft status."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        updated = move_post_to_review(post_id)
        return {"success": True, "message": "Post moved to Review & Drafts.", "post": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/posts/{post_id}/mark-sent")
def api_mark_sent(post_id: str):
    """Mark an application email as sent."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        mark_post_sent(post_id)
        return {"success": True, "message": "Post marked as SENT."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/posts/{post_id}/revert")
def api_revert_post(post_id: str):
    """Revert a sent or rejected post back to review/draft status."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        revert_post_to_draft(post_id)
        return {"success": True, "message": "Post reverted back to EMAIL_GENERATED draft."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/posts/{post_id}/reject")
def api_reject_post(post_id: str, payload: Optional[RejectPostPayload] = None):
    """Mark a post as rejected/cancelled with optional reason comment."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        reason = payload.reason if payload else None
        update_post_status(post_id, "REJECTED", rejection_reason=reason)
        return {"success": True, "message": "Post marked as REJECTED."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/posts/{post_id}/spam")
def api_mark_post_spam(post_id: str, payload: Optional[SpamPostPayload] = None):
    """1-click or commented action to mark a post as Spam / Scam, setting status to REJECTED with reason defaulting to 'Scam'."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        reason = payload.reason if (payload and payload.reason) else "Scam"
        is_potential = "potential" in reason.lower()
        update_post_status(
            post_id,
            "REJECTED",
            rejection_reason=reason,
            is_potential_spam=is_potential,
            potential_spam_reason=reason if is_potential else None,
        )
        return {"success": True, "message": f"Post marked as {reason} and moved to Others."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-email/{post_id}")
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


@app.post("/api/generate-batch")
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


@app.post("/api/open-gmail/{post_id}")
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


@app.post("/api/send-direct/{post_id}")
def api_send_direct(post_id: str):
    """Enqueue direct email sending in Gmail without manual interaction."""
    res = task_manager.enqueue_task(
        task_type="gmail_send",
        task_name=f"Direct Send (Post #{post_id})",
        runner_func=run_send_single_draft,
        args=(post_id,),
        metadata={"post_id": post_id},
    )
    msg = f"Queued email direct sending (Position #{res['position']})" if res["queued"] else "Directly sending application email via Gmail..."
    return {"success": True, "message": msg, **res}


@app.post("/api/send-batch")
def api_send_batch(payload: SendBatchPayload):
    """Enqueue multi-draft batch email sending in Gmail directly."""
    if not payload.post_ids:
        raise HTTPException(status_code=400, detail="No post IDs provided for batch sending.")

    count = len(payload.post_ids)
    res = task_manager.enqueue_task(
        task_type="gmail_send_batch",
        task_name=f"Batch Email Sending ({count} applications)",
        runner_func=run_send_batch_drafts,
        args=(payload.post_ids,),
        metadata={"count": count, "post_ids": payload.post_ids},
    )
    msg = f"Queued batch sending for {count} applications (Position #{res['position']})" if res["queued"] else f"Started direct sending for {count} applications."
    return {"success": True, "message": msg, **res}


@app.post("/api/direct-outreach")
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


@app.post("/api/scrape/infopark")
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


@app.post("/api/scrape/linkedin")
def api_trigger_scrape_linkedin(payload: Optional[ScrapePayload] = None):
    """Enqueue the LinkedIn scraper in headed Firefox with optional location and query."""
    query = payload.search_query if payload else None
    loc = payload.location if payload else None

    label = f"LinkedIn Crawler ({loc or 'Default'})" if loc else "LinkedIn Crawler"
    res = task_manager.enqueue_task(
        task_type="crawler",
        task_name=label,
        runner_func=run_linkedin_scraper,
        args=(query, loc),
        metadata={"source": "linkedin", "query": query, "location": loc},
    )
    msg = f"Queued LinkedIn scraper for {loc or 'default'} (Position #{res['position']})" if res["queued"] else "LinkedIn scraper started in headed Firefox."
    return {"success": True, "message": msg, **res}


@app.get("/api/scrapers")
def api_get_scrapers():
    """Return list of registered website scrapers for the crawler source selector."""
    return get_registered_scrapers()


@app.post("/api/scrape")
def api_trigger_scrape(payload: Optional[ScrapePayload] = None, source: Optional[str] = None):
    """Enqueue scraper by source using the extensible scraper registry with optional query and location."""
    src = "linkedin"
    query = None
    loc = None
    if payload:
        if payload.source:
            src = payload.source
        query = payload.search_query
        loc = payload.location
    elif source:
        src = source

    try:
        label = f"{src.capitalize()} Crawler" + (f" ({loc})" if loc else "")
        res = task_manager.enqueue_task(
            task_type="crawler",
            task_name=label,
            runner_func=run_scraper_by_source,
            args=(src, query, loc),
            metadata={"source": src, "query": query, "location": loc},
        )
        msg = f"Queued {label} (Position #{res['position']})" if res["queued"] else f"Scraper for '{src}' started."
        return {"success": True, "message": msg, **res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks/status")
def api_get_task_status():
    """Poll current active or recent automation task status and real-time logs."""
    return task_manager.get_state()


@app.post("/api/tasks/clear")
def api_clear_task():
    """Reset task state to idle."""
    task_manager.clear_task()
    return {"success": True, "message": "Task state cleared."}


@app.post("/api/tasks/queue/cancel/{task_id}")
def api_cancel_queued_task(task_id: str):
    """Cancel a queued automation task before it executes."""
    ok = task_manager.cancel_queued_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Queued task not found or already running.")
    return {"success": True, "message": f"Task {task_id} removed from queue."}


@app.post("/api/tasks/queue/clear")
def api_clear_task_queue():
    """Clear all pending tasks in the execution queue."""
    cleared = task_manager.clear_queue()
    return {"success": True, "cleared": cleared, "message": f"Cleared {cleared} task(s) from the queue."}


@app.get("/api/settings")
def api_get_settings():
    """Retrieve current application configuration."""
    return load_config()


@app.post("/api/settings")
def api_update_settings(payload: SettingsPayload):
    """Update application configuration."""
    data = {k: v for k, v in payload.dict().items() if v is not None}
    updated = save_config(data)
    return {"success": True, "config": updated}


@app.post("/api/settings/headless")
def api_toggle_headless(payload: HeadlessTogglePayload):
    """Instant 1-click toggle between Headless background mode and Headed visible mode."""
    updated = save_config({"headless_mode": payload.headless, "headless": payload.headless})
    mode_text = "Headless Mode (Silent Background)" if payload.headless else "Headed Mode (Visible Window)"
    return {
        "success": True,
        "headless": payload.headless,
        "headless_mode": payload.headless,
        "message": f"Switched browser automation to {mode_text}.",
        "config": updated,
    }
