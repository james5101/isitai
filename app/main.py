import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.models import UrlRequest, HtmlRequest, AnalysisResponse
from app.fetcher import fetch_url
from app.scorer import run_analyzers

# Resolve the static directory relative to this file so the path works
# regardless of where uvicorn is launched from.
_STATIC = Path(__file__).parent.parent / "static"

app = FastAPI(title="isitai", version="0.1.0")


@app.get("/")
def index():
    """Serve the frontend UI."""
    return FileResponse(_STATIC / "index.html")


@app.get("/health")
def health():
    """Liveness check — confirms the server is running."""
    return {"status": "ok"}


@app.post("/analyze/url", response_model=AnalysisResponse)
async def analyze_url(request: UrlRequest):
    """
    Fetch a URL and analyze it for AI signals.

    `async def` here because we await fetch_url (a network call).
    FastAPI handles the event loop — you just write async/await naturally.
    """
    html = await fetch_url(str(request.url))
    # asyncio.to_thread runs run_analyzers in a thread pool so the
    # blocking GPTZero HTTP call doesn't freeze the event loop.
    # Analogy: like running a slow Ansible task async so other plays
    # can continue while it waits.
    return await asyncio.to_thread(run_analyzers, html, str(request.url))


@app.post("/analyze/html", response_model=AnalysisResponse)
async def analyze_html(request: HtmlRequest):
    """
    Analyze raw HTML directly.

    Now async because bundle scanning may fetch a JS bundle over the network.
    asyncio.to_thread offloads the blocking httpx call to a thread pool so
    the event loop stays free — same pattern as analyze_url.
    base_url is optional; if provided it lets the bundle scanner resolve
    relative asset URLs (e.g. /assets/index-AbCd1234.js → full URL).
    """
    return await asyncio.to_thread(run_analyzers, request.html, request.base_url)
