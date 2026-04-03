import httpx
import logging
from dataclasses import dataclass, field
from fastapi import HTTPException

logger = logging.getLogger("isitai")


@dataclass
class FetchResult:
    """
    Carries the HTML and an optional screenshot from a page fetch.

    screenshot is only populated when Playwright renders the page.
    httpx-only fetches leave it None — the visual analyzer silently skips.
    """
    html: str
    screenshot: bytes | None = field(default=None)

# Full browser-like headers. Sites do fingerprint these — a missing Accept
# or a bare User-Agent is a common bot tell. These match a real Chrome request.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # Accept-Encoding is intentionally omitted — httpx manages compression
    # negotiation and decompression automatically. Setting it manually here
    # bypasses that and returns raw compressed bytes as response.text.
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Human-readable explanations for common upstream error codes.
_STATUS_HINTS = {
    403: "Site blocked the request (anti-bot / Cloudflare protection). This is a known limitation — sites using JS challenges cannot be fetched server-side.",
    404: "Page not found (404). Check the URL.",
    429: "Site is rate-limiting requests. Wait a moment and try again.",
    503: "Site is temporarily unavailable (503).",
}

# Resource types we block in Playwright to speed up page loads.
# We only need the rendered HTML — images, fonts and media add latency
# without contributing anything to our text/code analysis.
_BLOCK_TYPES = {"image", "font", "media"}


async def fetch_url(url: str, browser=None) -> FetchResult:
    """
    Fetch a URL and return its HTML + an optional screenshot.

    1. httpx fetches the HTML — fast, reliable, no bot-detection footprint.
    2. If httpx is blocked (4xx), Playwright retries — browsers can pass
       JS challenges that plain HTTP can't.
    3. Screenshot is always taken via set_content() — Playwright renders
       the already-fetched HTML locally, no outbound navigation required.
       This means bot detection never applies to the screenshot step.
    """
    html: str | None = None

    # ── Step 1: httpx ────────────────────────────────────────────────────────
    try:
        logger.info(f"httpx fetching {url}")
        html = await _fetch_with_httpx(url)
    except HTTPException as e:
        if browser is None:
            raise
        # httpx was blocked — let Playwright try with a real browser
        logger.info(f"httpx failed ({e.status_code}) for {url} — trying Playwright")
        try:
            result = await _fetch_with_playwright(url, browser)
            logger.info(f"playwright fetched {url} ({len(result.html):,} chars)")
            return result  # includes screenshot from live page
        except Exception as pw_err:
            logger.warning(f"playwright also failed for {url}: {pw_err}")
            raise e  # re-raise the original httpx error

    # ── Step 2: screenshot ───────────────────────────────────────────────────
    # Prefer a live Playwright navigation — it runs JS, loads the CSS bundle,
    # and gives a properly-styled screenshot. set_content() renders the raw
    # HTML string locally, so bundled CSS (Vite, etc.) never executes and the
    # page looks unstyled.
    #
    # If live navigation fails (timeout, bot block) we fall back to set_content.
    # The 15KB blank-detection in set_content handles the worst case.
    screenshot = None
    if browser is not None:
        try:
            pw_result = await _fetch_with_playwright(url, browser)
            screenshot = pw_result.screenshot
            logger.info(f"screenshot from live navigation for {url}")
        except Exception as e:
            logger.info(f"playwright navigation failed for screenshot ({e}) — falling back to set_content")
            screenshot = await _screenshot_from_html(html, url, browser)

    return FetchResult(html=html, screenshot=screenshot)


async def _fetch_with_playwright(url: str, browser) -> FetchResult:
    """
    Open a fresh browser context, navigate to the URL, wait for the page to
    load, then return the fully-rendered HTML.

    Each request gets its own context — isolated cookies, storage and cache —
    so requests can't interfere with each other. Think of it like a fresh
    incognito window per request.
    """
    context = await browser.new_context(
        user_agent=_HEADERS["User-Agent"],
        locale="en-US",
        viewport={"width": 1280, "height": 800},
        # Ignore HTTPS errors so we can analyze sites with cert issues
        ignore_https_errors=True,
    )
    try:
        page = await context.new_page()

        # Block images, fonts and media — we only need HTML and JS to execute.
        # This cuts load time significantly on image-heavy sites.
        async def _intercept(route):
            if route.request.resource_type in _BLOCK_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", _intercept)

        # wait_until="domcontentloaded" fires as soon as the HTML is parsed
        # and inline scripts have run — fast and sufficient for SPA shells.
        # "load" waits for every resource (fonts, analytics, ads) which can
        # hang indefinitely on sites with slow third-party scripts.
        await page.goto(url, wait_until="domcontentloaded", timeout=15_000)

        # Give JS a moment to render the initial component tree.
        # 1.5s covers most React/Vue first-render cycles without waiting for
        # lazy-loaded content or network requests to complete.
        try:
            await page.wait_for_load_state("networkidle", timeout=3_000)
        except Exception:
            pass  # networkidle timed out — proceed with what we have

        html = await page.content()

        # Capture viewport screenshot for visual analysis.
        # full_page=False keeps it to ~100-400KB; full page can be several MB.
        screenshot = await page.screenshot(type="png", full_page=False)

        return FetchResult(html=html, screenshot=screenshot)

    finally:
        # Always close the context — releases memory and browser resources.
        # The browser process itself keeps running for the next request.
        await context.close()


async def _screenshot_from_html(html: str, base_url: str, browser) -> bytes | None:
    """
    Render already-fetched HTML in Playwright and return a screenshot.

    Uses page.set_content() instead of page.goto() — no outbound navigation,
    so bot detection is bypassed entirely. External stylesheets (Tailwind CDN,
    shadcn, Google Fonts) still load because Playwright resolves them against
    base_url. JS executes too, so React/Vue components render their initial state.

    This is the fallback path when Playwright can't navigate to a URL directly
    but httpx successfully retrieved the HTML.
    """
    context = await browser.new_context(
        user_agent=_HEADERS["User-Agent"],
        locale="en-US",
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
        # base_url tells Playwright how to resolve relative resource paths in
        # set_content() — without it, /assets/style.css would try to load from
        # the local filesystem instead of the real domain.
        base_url=base_url,
    )
    try:
        page = await context.new_page()

        await page.set_content(html)

        # Wait for stylesheets and fonts to load so the screenshot looks right.
        # Short timeout — if CDN resources are slow we still take the screenshot.
        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            pass

        screenshot = await page.screenshot(type="png", full_page=False)

        # Blank/white screenshots are useless for visual analysis and waste
        # vision API credits. A real page at 1280×800 always has entropy from
        # text, shadows, and colors — its PNG is typically 50KB+.
        # A pure white screen compresses to ~5KB. Threshold of 15KB is safe.
        if len(screenshot) < 15_000:
            logger.info(
                f"screenshot appears blank for {base_url} "
                f"({len(screenshot):,} bytes) — JS bundle likely blocked, skipping"
            )
            return None

        logger.info(f"screenshot captured via set_content for {base_url} ({len(screenshot):,} bytes)")
        return screenshot

    except Exception as e:
        logger.warning(f"set_content screenshot failed for {base_url}: {e}")
        return None
    finally:
        await context.close()


async def _fetch_with_httpx(url: str) -> str:  # returns str; caller wraps in FetchResult
    """Plain async HTTP fetch — the original fetcher, now the fallback path."""
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=(
                f"Timed out fetching {url}. "
                "The site may be down, or it may be blocking server-side requests — "
                "some sites use Cloudflare or similar protection that rejects "
                "requests from cloud hosting IP ranges."
            ),
        )

    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = _STATUS_HINTS.get(code, f"Upstream returned HTTP {code}.")
        raise HTTPException(status_code=502, detail=hint)

    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach {url}: {e}")
