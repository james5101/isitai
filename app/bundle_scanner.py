import re
from urllib.parse import urljoin, urlparse
import httpx
from app.models import AnalyzerResult

# ── Vite SPA detection ────────────────────────────────────────────────────────
# Vite outputs a hashed main module entry point, always loaded as type="module".
# Pattern: <script type="module" crossorigin src="/assets/index-AbCd1234.js">
_VITE_MODULE_SCRIPT = re.compile(
    r'<script[^>]+type=["\']module["\'][^>]+src=["\']([^"\']*assets/[^"\']*-[a-zA-Z0-9]{8,}\.js)["\']',
    re.I,
)

# Max HTML size to qualify as a "thin SPA shell".
# Framer sites can be 180KB of HTML — we don't want to bundle-scan those.
_MAX_SHELL_SIZE = 10_000

# Max bundle size to scan. 600KB covers most Vite bundles without going huge.
_MAX_BUNDLE_BYTES = 600_000

# ── Bundle signal rules ───────────────────────────────────────────────────────
# Each entry: (tech_name, search_string, points)
# We search the raw minified bundle text for these strings.
# Minified JS preserves string literals and module identifiers.
_BUNDLE_SIGNALS: list[tuple[str, str, int]] = [
    # Lovable's own dev-time package — strongest possible signal
    ("Lovable",         "lovable-tagger",       90),

    # shadcn/ui CSS variable — only present if shadcn is used
    ("shadcn/ui",       "ring-offset-background", 35),

    # Radix UI — the headless component library shadcn is built on
    ("Radix UI",        "radix-ui",             20),

    # Lucide React — the icon library Lovable/v0 default to
    ("Lucide",          "lucide-react",         20),

    # Sonner — toast notifications, near-universal in Lovable apps
    ("Sonner",          '"sonner"',             20),

    # TanStack Query/Router — common in vibe-coded data-fetching apps
    ("TanStack",        "@tanstack",            15),

    # cmdk — command palette, a shadcn component
    ("cmdk",            '"cmdk"',               15),

    # Vaul — drawer component, shadcn ecosystem
    ("Vaul",            '"vaul"',               15),

    # React Hook Form — AI tools default to this for forms
    ("React Hook Form", "react-hook-form",      10),

    # Zod — schema validation, almost always paired with React Hook Form in vibe coding
    ("Zod",             '"zod"',                10),
]


def extract_bundle_url(html: str, base_url: str | None) -> str | None:
    """
    Find the Vite main bundle script src and resolve it to an absolute URL.

    Returns None if this doesn't look like a Vite SPA shell.

    Why resolve to absolute? The src in the HTML is usually relative
    (/assets/index-AbCd.js). We need the full URL to fetch it.
    urljoin() handles this the same way a browser does.
    """
    if len(html) > _MAX_SHELL_SIZE:
        return None  # Too much HTML — not a thin SPA shell

    match = _VITE_MODULE_SCRIPT.search(html)
    if not match:
        return None

    src = match.group(1)

    # Already absolute URL
    if src.startswith("http"):
        return src

    # Relative URL — needs a base to resolve against
    if not base_url:
        return None

    return urljoin(base_url, src)


def scan_bundle(bundle: str) -> tuple[int, list[str], list[str]]:
    """
    Scan the raw bundle text for vibe-coding library fingerprints.

    Returns:
        score     — 0–100 AI confidence from bundle signals
        evidence  — human-readable list of what fired
        techs     — list of technology names for the stack pills
    """
    points = 0
    evidence = []
    techs = []

    for tech_name, needle, pts in _BUNDLE_SIGNALS:
        if needle in bundle:
            points += pts
            evidence.append(f"{tech_name} detected in JS bundle ({needle})")
            techs.append(tech_name)

    score = min(100, points)
    return score, evidence, techs


def fetch_and_scan(html: str, base_url: str | None) -> tuple[AnalyzerResult, list[str]]:
    """
    Full pipeline: detect SPA shell → resolve bundle URL → fetch → scan.

    Returns (AnalyzerResult, detected_tech_names).
    Always returns safely — fetch errors yield weight=0.0 so the main
    analysis is never blocked by a bundle fetch failure.

    Uses sync httpx — called inside asyncio.to_thread in scorer.py,
    so it runs in a thread pool and doesn't block the event loop.
    """
    _skip = AnalyzerResult(score=0, weight=0.0, evidence=["Bundle scan skipped"]), []

    bundle_url = extract_bundle_url(html, base_url)
    if not bundle_url:
        return _skip

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(bundle_url)
            response.raise_for_status()

            # Guard against huge bundles
            if len(response.content) > _MAX_BUNDLE_BYTES:
                return AnalyzerResult(
                    score=0, weight=0.0,
                    evidence=[f"Bundle too large to scan ({len(response.content):,} bytes)"],
                ), []

            bundle_text = response.text

    except httpx.HTTPError:
        return _skip

    score, evidence, techs = scan_bundle(bundle_text)

    return AnalyzerResult(
        score=score,
        weight=0.35,   # significant weight — bundle signals are reliable
        evidence=evidence if evidence else ["No vibe-coding signals found in bundle"],
    ), techs
