"""
FastAPI router for post querying, filtering, manual ingestion, and status transitions.
"""

import re
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from src.db import (
    upsert_post,
    get_post_by_id,
    get_posts_paginated,
    get_distinct_locations,
    get_rejection_reasons_with_counts,
    update_post_email,
    move_post_to_review,
    mark_post_sent,
    revert_post_to_draft,
    revert_posts_batch,
    reject_posts_batch,
    update_post_status,
)
from src.services.experience_extractor import extract_experience
from .models import (
    ManualPostPayload,
    UpdateEmailPayload,
    RejectPostPayload,
    SpamPostPayload,
    BatchPostActionPayload,
    MAJOR_JOB_HUBS,
)

router = APIRouter(prefix="/api", tags=["Posts"])


@router.post("/posts/manual")
def api_create_manual_post(payload: ManualPostPayload):
    """Manually add a Job Description into Discovered Posts."""
    raw_content = (payload.full_text or payload.content or payload.description or "").strip()
    if not raw_content:
        raise HTTPException(status_code=400, detail="Job Description text is required.")

    author = (payload.author_name or payload.company or "Direct Company / Recruiter").strip()
    headline = (payload.author_headline or payload.title or "Software Opportunity").strip()

    emails = list(payload.contact_emails or [])
    if payload.email and payload.email.strip():
        emails.append(payload.email.strip())
    if not emails:
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_content)
    emails = list(dict.fromkeys(emails))

    exp_info = extract_experience(raw_content)
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
        return {"ok": True, "success": True, "id": post_id, "post_id": post_id, "post": saved_post}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/posts")
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


@router.get("/locations")
def api_get_locations():
    """Retrieve distinct locations saved in DB and predefined major job hubs."""
    try:
        saved_locs = get_distinct_locations()
        return {"locations": saved_locs, "presets": MAJOR_JOB_HUBS}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reasons")
def api_get_reasons():
    """Retrieve distinct cancellation/rejection reasons with counts for filtering."""
    try:
        counts = get_rejection_reasons_with_counts()
        reasons = [c["reason"] for c in counts]
        return {"reasons": reasons, "counts": counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/posts/{post_id}")
def api_get_post(post_id: str):
    """Retrieve single post details."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.put("/posts/{post_id}")
def api_update_post(post_id: str, payload: UpdateEmailPayload):
    """Update edited email subject and body for a post."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    try:
        subject = payload.subject or payload.generated_subject or ""
        body = payload.body or payload.generated_body or ""
        update_post_email(post_id, subject, body)
        return {"success": True, "message": "Email draft updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/posts/{post_id}/move-to-review")
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


@router.post("/posts/{post_id}/mark-sent")
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


@router.post("/posts/{post_id}/revert")
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


@router.post("/posts/revert-batch")
def api_revert_posts_batch(payload: BatchPostActionPayload):
    """Revert multiple sent or rejected posts back to review/draft status."""
    if not payload.post_ids:
        raise HTTPException(status_code=400, detail="No post IDs provided.")
    try:
        count = revert_posts_batch(payload.post_ids)
        return {"success": True, "count": count, "message": f"Successfully reverted {count} applications."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/posts/{post_id}/reject")
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


@router.post("/posts/reject-batch")
def api_reject_posts_batch(payload: BatchPostActionPayload):
    """Reject/cancel multiple posts with an optional cancellation reason."""
    if not payload.post_ids:
        raise HTTPException(status_code=400, detail="No post IDs provided.")
    try:
        count = reject_posts_batch(payload.post_ids, payload.reason)
        return {"success": True, "count": count, "message": f"Successfully cancelled {count} applications."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/posts/{post_id}/spam")
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
