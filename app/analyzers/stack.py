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

        score = min(100, points)
        return AnalyzerResult(score=score, weight=self.weight, evidence=evidence)
