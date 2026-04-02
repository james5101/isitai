import httpx
from fastapi import HTTPException

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


async def fetch_url(url: str) -> str:
    """
    Fetches a URL and returns its HTML content as a string.

    async def = this function is a coroutine; callers must `await` it.
    The `async with` block ensures the HTTP connection is properly closed
    even if an exception occurs — same idea as a context manager in sync code.
    """
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,  # follow 301/302 redirects automatically
            timeout=15.0,           # some large sites are slow to respond
        ) as client:
            response = await client.get(url)
            response.raise_for_status()  # raises HTTPStatusError if status >= 400
            return response.text

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timed out fetching {url}")

    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = _STATUS_HINTS.get(code, f"Upstream returned HTTP {code}.")
        raise HTTPException(status_code=502, detail=hint)

    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach {url}: {e}")
