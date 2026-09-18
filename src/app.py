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
)
from src.experience_extractor import extract_experience
from src.config import load_config, save_config
from src.health_service import get_system_health
from src.automation_tasks import (
    task_manager,
    run_chatgpt_batch,
    run_open_gmail_draft,
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


# Pydantic models for request bodies
class UpdateEmailPayload(BaseModel):
    subject: str
    body: str


class GenerateBatchPayload(BaseModel):
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


class SettingsPayload(BaseModel):
    resume_path: Optional[str] = None
    search_query: Optional[str] = None
    chatgpt_url: Optional[str] = None
    pacing_min_seconds: Optional[float] = None
    pacing_max_seconds: Optional[float] = None


class ScrapePayload(BaseModel):
    source: Optional[str] = "linkedin"


@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    """Serve the single-page dashboard."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return FileResponse(index_file)


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
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieve posts with filtering, search, and pagination."""
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
            limit=safe_limit,
            offset=safe_offset,
        )
        return result
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
        update_post_status(post_id, "REJECTED", rejection_reason=reason)
        return {"success": True, "message": f"Post marked as {reason} and moved to Others."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-email/{post_id}")
def api_generate_email(post_id: str):
    """Trigger ChatGPT generation for a single post in headed Firefox."""
    current_state = task_manager.get_state()
    if current_state["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Another task is already running: {current_state['task_name']}")

    thread = threading.Thread(target=run_chatgpt_batch, args=([post_id],), daemon=True)
    thread.start()
    return {"success": True, "message": f"ChatGPT email generation started for post {post_id}."}


@app.post("/api/generate-batch")
def api_generate_batch(payload: GenerateBatchPayload):
    """Trigger ChatGPT generation for selected posts in headed Firefox."""
    if not payload.post_ids:
        raise HTTPException(status_code=400, detail="No post IDs provided.")

    current_state = task_manager.get_state()
    if current_state["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Another task is already running: {current_state['task_name']}")

    thread = threading.Thread(target=run_chatgpt_batch, args=(payload.post_ids,), daemon=True)
    thread.start()
    return {"success": True, "message": f"Started email generation for {len(payload.post_ids)} posts."}


@app.post("/api/open-gmail/{post_id}")
def api_open_gmail(post_id: str):
    """Trigger Gmail draft creation in headed Firefox with resume attached."""
    current_state = task_manager.get_state()
    if current_state["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Another task is already running: {current_state['task_name']}")

    thread = threading.Thread(target=run_open_gmail_draft, args=(post_id,), daemon=True)
    thread.start()
    return {"success": True, "message": "Opening Gmail compose in headed Firefox..."}


@app.post("/api/scrape/infopark")
def api_trigger_scrape_infopark():
    """Trigger the Infopark jobs scraper."""
    current_state = task_manager.get_state()
    if current_state["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Another task is already running: {current_state['task_name']}")

    thread = threading.Thread(target=run_infopark_scraper, daemon=True)
    thread.start()
    return {"success": True, "message": "Infopark jobs scraper started."}


@app.post("/api/scrape/linkedin")
def api_trigger_scrape_linkedin():
    """Trigger the LinkedIn scraper in headed Firefox."""
    current_state = task_manager.get_state()
    if current_state["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Another task is already running: {current_state['task_name']}")

    thread = threading.Thread(target=run_linkedin_scraper, daemon=True)
    thread.start()
    return {"success": True, "message": "LinkedIn scraper started in headed Firefox."}


@app.get("/api/scrapers")
def api_get_scrapers():
    """Return list of registered website scrapers for the crawler source selector."""
    return get_registered_scrapers()


@app.post("/api/scrape")
def api_trigger_scrape(payload: Optional[ScrapePayload] = None, source: Optional[str] = None):
    """Trigger scraper by source using the extensible scraper registry."""
    src = "linkedin"
    if payload and payload.source:
        src = payload.source
    elif source:
        src = source

    current_state = task_manager.get_state()
    if current_state["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Another task is already running: {current_state['task_name']}")

    try:
        thread = threading.Thread(target=run_scraper_by_source, args=(src,), daemon=True)
        thread.start()
        return {"success": True, "message": f"Scraper for '{src}' started."}
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
