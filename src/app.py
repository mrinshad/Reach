"""
Reach FastAPI Application Root

Coordinates modular API routers, dynamic template assembly, root static routes, and CORS.
"""

import os
import re
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.api import api_router
from src.api.models import (
    MAJOR_JOB_HUBS,
    DEFAULT_OPPORTUNITY_SUBJECT,
    DEFAULT_OPPORTUNITY_BODY,
    ManualPostPayload,
    UpdateEmailPayload,
    RejectPostPayload,
    SpamPostPayload,
    GenerateBatchPayload,
    SendBatchPayload,
    DirectOutreachPayload,
    SettingsPayload,
    HeadlessTogglePayload,
    ScrapePayload,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="Reach Automation Hub", version="2.0.0")

# Mount static directory
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Enable CORS for local cross-device development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    """Prevent aggressive browser caching during development."""
    response = await call_next(request)
    if (
        request.url.path.endswith((".js", ".css", ".html"))
        or request.url.path in ("/", "/index.html", "/sw.js")
        or request.url.path.startswith("/api/")
    ):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
def startup_event():
    """Recover orphaned posts on server startup and initialize settings."""
    try:
        from src.db.posts import cleanup_stuck_generating_posts
        recovered = cleanup_stuck_generating_posts()
        if recovered > 0:
            print(f"✓ Recovered {recovered} post(s) stuck in GENERATING_EMAIL status on startup.")
    except Exception as e:
        print(f"Notice: startup post cleanup check: {e}")



def get_rendered_index_html() -> str:
    """Dynamically assemble index_layout.html with partials from src/static/partials/."""
    layout_path = os.path.join(STATIC_DIR, "index_layout.html")
    if not os.path.exists(layout_path):
        fallback_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(fallback_file):
            with open(fallback_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<html><body><h3>Reach Dashboard</h3></body></html>"

    try:
        with open(layout_path, "r", encoding="utf-8") as f:
            content = f.read()

        def replace_include(match):
            rel_path = match.group(1).strip()
            full_path = os.path.join(STATIC_DIR, rel_path)
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as pf:
                    return pf.read()
            return f"<!-- Missing include: {rel_path} -->"

        pattern = re.compile(r"<!--\s*@include\s+([^\s]+)\s*-->")
        assembled = pattern.sub(replace_include, content)

        # Keep static index.html in sync on disk for static file serving/caching
        try:
            index_file = os.path.join(STATIC_DIR, "index.html")
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(assembled)
        except Exception:
            pass

        return assembled
    except Exception as e:
        fallback_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(fallback_file):
            with open(fallback_file, "r", encoding="utf-8") as f:
                return f.read()
        return f"<html><body><h3>Error assembling dashboard: {e}</h3></body></html>"


@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    """Serve the modularly assembled single-page dashboard."""
    html_content = get_rendered_index_html()
    return HTMLResponse(content=html_content, media_type="text/html")


@app.api_route("/index.html", methods=["GET", "HEAD"])
def serve_index_html():
    """Serve index.html explicitly."""
    html_content = get_rendered_index_html()
    return HTMLResponse(content=html_content, media_type="text/html")


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


# Mount all API routes
app.include_router(api_router)

__all__ = [
    "app",
    "get_rendered_index_html",
    "MAJOR_JOB_HUBS",
    "DEFAULT_OPPORTUNITY_SUBJECT",
    "DEFAULT_OPPORTUNITY_BODY",
    "ManualPostPayload",
    "UpdateEmailPayload",
    "RejectPostPayload",
    "SpamPostPayload",
    "GenerateBatchPayload",
    "SendBatchPayload",
    "DirectOutreachPayload",
    "SettingsPayload",
    "HeadlessTogglePayload",
    "ScrapePayload",
]
