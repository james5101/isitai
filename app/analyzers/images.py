import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from app.analyzers.base import BaseAnalyzer
from app.models import AnalyzerResult

# Known CDNs used by AI website builders and AI image generation tools.
# If a site loads images from these domains, it's a strong signal.
_AI_IMAGE_DOMAINS = [
    "images.unsplash.com",       # Unsplash — AI builders love free stock photos
    "images.pexels.com",         # Pexels stock
    "cdn.midjourney.com",        # Midjourney AI images
    "oaidalleapiprodscus.blob.core.windows.net",  # DALL-E CDN
    "framerusercontent.com",     # Framer image CDN
    "static.wixstatic.com",      # Wix image CDN
    "images.squarespace-cdn.com", # Squarespace image CDN
]

# Regex for filenames that look like auto-generated (stock photo IDs)
# e.g. "photo-1234567890123-abc123def456.jpg"
_STOCK_FILENAME_PATTERN = re.compile(r'photo-\d{10,}', re.I)


class ImageAnalyzer(BaseAnalyzer):
    """
    Detects AI-generated or AI-sourced imagery signals.

    Looks at image src URLs and alt text patterns.
    Weight: 0.10
    """

    @property
    def weight(self) -> float:
        return 0.10

    def analyze(self, html: str) -> AnalyzerResult:
        soup = BeautifulSoup(html, "lxml")
        evidence = []

        images = soup.find_all("img")
        if not images:
            return AnalyzerResult(score=0, weight=self.weight, evidence=[])

        suspect_count = 0

        for img in images:
            src = img.get("src", "") or img.get("data-src", "")

            # Check 1: Image served from known AI/stock CDN
            if src:
                try:
                    domain = urlparse(src).netloc.lower()
                    for ai_domain in _AI_IMAGE_DOMAINS:
                        if domain == ai_domain or domain.endswith("." + ai_domain):
                            suspect_count += 1
                            evidence.append(f"AI/stock CDN image: {domain}")
                            break
                except Exception:
                    pass

                # Check 2: Filename looks like a stock photo auto-ID
                if _STOCK_FILENAME_PATTERN.search(src):
                    suspect_count += 1
                    evidence.append(f"Stock photo filename pattern in: {src[:80]}")

        # Score based on ratio of suspect images to total images
        if suspect_count == 0:
            score = 0
        else:
            ratio = suspect_count / len(images)
            score = min(100, int(ratio * 100))

        # De-duplicate evidence while preserving order
        evidence = list(dict.fromkeys(evidence))

        return AnalyzerResult(score=score, weight=self.weight, evidence=evidence)
