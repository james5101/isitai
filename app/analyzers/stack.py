import re
from bs4 import BeautifulSoup
from app.analyzers.base import BaseAnalyzer
from app.models import AnalyzerResult

# --- Known vibe-coding platform URL patterns ---
# If any script/link/img src contains these domains, it's a very strong signal.
_PLATFORM_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Framer",      re.compile(r'framer\.com|framerusercontent\.com', re.I)),
    ("Lovable",     re.compile(r'gptengineer\.app|lovable\.app', re.I)),
    ("Replit",      re.compile(r'replit\.app|repl\.co|replit\.com', re.I)),
    ("Bolt/StackBlitz", re.compile(r'stackblitz\.io|bolt\.new', re.I)),
    ("v0.dev",      re.compile(r'v0\.dev', re.I)),
]

# --- Vite build signature ---
# Vite outputs hashed asset filenames like /assets/index-BxYz1234.js
# The hash is 8+ alphanumeric chars. Very few hand-rolled build pipelines produce this exact pattern.
_VITE_ASSET = re.compile(r'/assets/[a-zA-Z0-9_-]+-[a-zA-Z0-9]{8,}\.(js|css)', re.I)

# --- shadcn/ui class signature ---
# These Tailwind CSS variable names are defined by shadcn/ui's base styles.
# They don't appear in hand-written Tailwind projects that don't use shadcn.
_SHADCN_CLASSES = [
    "ring-offset-background",
    "focus-visible:ring-ring",
    "bg-background",
    "text-foreground",
    "border-input",
    "ring-offset-2",
]

# --- Next.js markers ---
_NEXTJS_PATTERNS = [
    re.compile(r'/_next/static/', re.I),
    re.compile(r'__NEXT_DATA__', re.I),
]

# --- AI SDK packages in import maps ---
# These packages loaded via an import map mean someone is running an AI SDK
# directly in the browser — an extremely strong signal.
# import maps + esm.sh is also the pattern used by Gemini Canvas, bolt.new,
# and other AI coding tools that skip the build step entirely.
_AI_SDK_PACKAGES = [
    "@google/genai",
    "@anthropic-ai/sdk",
    "openai",
    "@mistralai/mistralai",
    "@cohere-ai/cohere-sdk",
]

_IMPORTMAP_RE = re.compile(
    r'<script[^>]+type=["\']importmap["\'][^>]*>(.*?)</script>',
    re.I | re.DOTALL,
)

# --- esm.sh / skypack CDN (no-build pattern) ---
# Real production apps use a build pipeline. Loading React or Three.js
# directly from esm.sh/skypack in an import map means no build step —
# a pattern almost exclusive to AI coding tools and throwaway prototypes.
_ESM_CDN_RE = re.compile(r'esm\.sh|cdn\.skypack\.dev', re.I)

# --- Inline Tailwind config ---
# AI tools use the Tailwind CDN + an inline config script.
# Real projects use PostCSS/Vite plugin — never this pattern in production.
_TAILWIND_CONFIG_RE = re.compile(r'tailwind\.config\s*=', re.I)

# --- CDN-loaded frameworks ---
# Loading React/Vue/Angular from unpkg or jsdelivr via a plain <script> tag
# means there's no build pipeline. Common in AI-generated demos/prototypes.
_CDN_FRAMEWORK_RE = re.compile(
    r'(unpkg\.com|cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com)'
    r'.*?(react|vue|angular|svelte|three\.js)',
    re.I,
)

# --- Direct AI API calls ---
# If a site calls an AI API directly from the browser, it was almost
# certainly built with AI assistance. No false positives — real devs
# never expose AI API keys client-side on purpose.
_AI_API_ENDPOINTS = [
    ("Google Gemini",    "generativelanguage.googleapis.com"),
    ("OpenAI",           "api.openai.com"),
    ("Anthropic",        "api.anthropic.com"),
    ("Mistral",          "api.mistral.ai"),
    ("Cohere",           "api.cohere.ai"),
    ("Groq",             "api.groq.com"),
]


class StackAnalyzer(BaseAnalyzer):
    """
    Detects vibe-coding stack fingerprints: Vite+React, shadcn/ui,
    Next.js, and known vibe-coding platform URLs (Lovable, Replit, Bolt, v0).

    Scoring uses a points accumulation model — each signal adds points,
    capped at 100. Unlike a weighted average, this rewards finding
    multiple corroborating signals.

    Weight: 0.30
    """

    @property
    def weight(self) -> float:
        return 0.30

    def analyze(self, html: str) -> AnalyzerResult:
        soup = BeautifulSoup(html, "lxml")
        evidence = []
        points = 0

        # Collect all URL-bearing attributes in one pass for platform checks
        all_urls = []
        for tag in soup.find_all(True):
            for attr in ("src", "href", "action", "data-src"):
                val = tag.get(attr, "")
                if val:
                    all_urls.append(val)
        url_blob = " ".join(all_urls)

        # --- Check 1: Known vibe-coding platform URLs (strong signal) ---
        for platform, pattern in _PLATFORM_PATTERNS:
            if pattern.search(url_blob):
                points += 80
                evidence.append(f"{platform} platform URL detected")

        # --- Check 2: Vite hashed asset pattern ---
        vite_hits = _VITE_ASSET.findall(html)
        if vite_hits:
            points += 35
            evidence.append(f"Vite build assets: {vite_hits[0][0] if vite_hits else ''} ({len(vite_hits)} file(s))")

        # --- Check 3: React SPA shell ---
        root_div = soup.find("div", id="root") or soup.find("div", id="app")
        if root_div is not None:
            points += 20
            evidence.append(f'SPA root element: <div id="{root_div.get("id")}">')

        # --- Check 4: shadcn/ui class signatures ---
        # Get all class attribute text in one blob for efficient searching
        class_blob = " ".join(
            " ".join(tag.get("class", []))
            for tag in soup.find_all(True)
        )
        shadcn_hits = [cls for cls in _SHADCN_CLASSES if cls in class_blob]
        if shadcn_hits:
            points += 35
            evidence.append(f"shadcn/ui class signatures: {', '.join(shadcn_hits[:3])}")

        # --- Check 5: Next.js markers ---
        for pattern in _NEXTJS_PATTERNS:
            if pattern.search(html):
                points += 25
                evidence.append("Next.js detected")
                break  # one evidence entry is enough

        # --- Check 6: Inter font (weak signal, commonly AI-chosen) ---
        if "fonts.googleapis.com" in html and "Inter" in html:
            points += 10
            evidence.append("Inter font via Google Fonts (common AI default)")

        # --- Check 7: AI SDK packages in import map ---
        # An import map loading @google/genai, openai, etc. means an AI SDK
        # is running directly in the browser — near-certain AI involvement.
        # This pattern is common in Gemini Canvas, bolt.new, and AI tools
        # that skip the build step and load modules straight from esm.sh.
        importmap_match = _IMPORTMAP_RE.search(html)
        if importmap_match:
            importmap_content = importmap_match.group(1)

            # AI SDK packages — near-certain signal
            found_sdks = [pkg for pkg in _AI_SDK_PACKAGES if pkg in importmap_content]
            if found_sdks:
                points += 85
                evidence.append(f"AI SDK(s) in import map: {', '.join(found_sdks)}")

            # esm.sh / skypack CDN without AI SDK — moderate signal
            elif _ESM_CDN_RE.search(importmap_content):
                points += 30
                evidence.append("Import map using esm.sh/skypack CDN (no build tooling)")

        # --- Check 8: Inline Tailwind config ---
        if _TAILWIND_CONFIG_RE.search(html):
            points += 25
            evidence.append("Inline tailwind.config (CDN + config pattern, not a real build)")

        # --- Check 9: CDN-loaded frameworks ---
        cdn_hits = _CDN_FRAMEWORK_RE.findall(html)
        if cdn_hits:
            points += 25
            cdn_names = list(dict.fromkeys(f"{fw} via {cdn}" for cdn, fw in cdn_hits))
            evidence.append(f"Framework loaded from CDN: {', '.join(cdn_names[:3])}")

        # --- Check 10: Direct AI API calls in page source ---
        # Search the full HTML (including inline scripts) for AI API hostnames.
        found_apis = [name for name, host in _AI_API_ENDPOINTS if host in html]
        if found_apis:
            points += 80
            evidence.append(f"Direct AI API call in page source: {', '.join(found_apis)}")

        score = min(100, points)
        return AnalyzerResult(score=score, weight=self.weight, evidence=evidence)
