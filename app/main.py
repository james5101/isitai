import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("isitai")
from pathlib import Path
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.models import UrlRequest, HtmlRequest, AnalysisResponse
from app.fetcher import fetch_url
from app.scorer import run_analyzers

_STATIC = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the Playwright browser process for the lifetime of the server.

    Lifespan replaces the old @app.on_event("startup"/"shutdown") pattern.
    Code before `yield` runs at startup; code after runs at shutdown.

    Analogy: this is like a long-lived SSH connection you open once and
    reuse for many commands, rather than reconnecting for every command.
    A new browser context (incognito window) is opened per request, but
    the browser process itself stays warm.

    Playwright is optional — if it isn't installed or Chromium fails to
    launch, browser stays None and fetch_url falls back to httpx.
    """
    browser = None
    playwright = None

    try:
        from playwright.async_api import async_playwright
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        logger.info("Playwright ready — using Chromium for rendering")
    except Exception as e:
        logger.warning(f"Playwright unavailable ({e}) — falling back to httpx")

    app.state.browser = browser

    yield  # ← server is running and handling requests

    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()


app = FastAPI(title="isitai", version="0.1.0", lifespan=lifespan)

# CORS — allows the browser extension (chrome-extension://*) and any other
# origin to call the API. Safe for a public read-only analysis API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def index():
    """Serve the frontend UI."""
    return FileResponse(_STATIC / "index.html")


@app.get("/health")
def health():
    """Liveness check — confirms the server is running."""
    return {"status": "ok"}


@app.post("/analyze/url", response_model=AnalysisResponse)
async def analyze_url(request: UrlRequest, req: Request):
    """
    Fetch a URL and analyze it for AI signals.

    Uses Playwright for rendering if available, falls back to httpx.
    req.app.state.browser is set by the lifespan — None if Playwright
    isn't installed, which triggers the httpx fallback in fetch_url.
    """
    browser = getattr(req.app.state, "browser", None)
    result = await fetch_url(str(request.url), browser)
    return await asyncio.to_thread(run_analyzers, result.html, str(request.url), result.screenshot)


@app.post("/analyze/html", response_model=AnalysisResponse)
async def analyze_html(request: HtmlRequest):
    """
    Analyze raw HTML directly — no fetch needed, no browser involved.
    bundle scanning may still fetch a JS bundle over the network via httpx.
    """
    return await asyncio.to_thread(run_analyzers, request.html, request.base_url)
