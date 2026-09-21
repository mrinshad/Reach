"""
FastAPI router for resume uploads, application settings, and Headless mode switching.
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File

from src.config import load_config, save_config
from .models import SettingsPayload, HeadlessTogglePayload

router = APIRouter(prefix="/api", tags=["Settings"])


@router.post("/resume/upload")
async def api_upload_resume(file: UploadFile = File(...)):
    """Upload a new resume file anytime and set as the active global resume."""
    if not file.filename.lower().endswith((".pdf", ".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only PDF and Word documents (.pdf, .docx) are supported.")

    base_project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    resumes_dir = os.path.join(base_project_dir, "resumes")
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


@router.get("/settings")
def api_get_settings():
    """Retrieve current application configuration."""
    return load_config()


@router.post("/settings")
def api_update_settings(payload: SettingsPayload):
    """Update application configuration."""
    data = {k: v for k, v in payload.dict().items() if v is not None}
    updated = save_config(data)
    return {"success": True, "config": updated}


@router.post("/settings/headless")
def api_toggle_headless(payload: Optional[HeadlessTogglePayload] = None):
    """Instant 1-click toggle between Headless background mode and Headed visible mode."""
    from src.config import is_headless
    if payload is not None:
        target_mode = payload.headless
    else:
        target_mode = not is_headless()

    updated = save_config({"headless_mode": target_mode, "headless": target_mode})
    mode_text = "Headless Mode (Silent Background)" if target_mode else "Headed Mode (Visible Window)"
    return {
        "success": True,
        "headless": target_mode,
        "headless_mode": target_mode,
        "message": f"Switched browser automation to {mode_text}.",
        "config": updated,
    }
