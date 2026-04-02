import re
from bs4 import BeautifulSoup
from app.analyzers.base import BaseAnalyzer
from app.models import AnalyzerResult

# Each entry is a (label, detection_function) pair.
# The detection function receives a BeautifulSoup object and returns a
# human-readable evidence string, or None if no match.
#
# Organized by known AI website builder tools.
_FINGERPRINTS: list[tuple[str, callable]] = [
    # --- Framer AI ---
    (
        "Framer generator meta tag",
        lambda soup: _check_meta_generator(soup, "framer"),
    ),
    (
        "Framer HTML comment",
        lambda soup: _check_html_comment(soup, r"made in framer|framer\.com"),
    ),
    (
        "Framer script source",
        lambda soup: _check_script_src(soup, r"assets\.framer\.com|framerusercontent\.com"),
    ),

    # --- Wix ---
    (
        "Wix generator meta tag",
        lambda soup: _check_meta_generator(soup, "wix"),
    ),
    (
        "Wix script source",
        lambda soup: _check_script_src(soup, r"static\.wixstatic\.com|wix\.com"),
    ),

    # --- Squarespace ---
    (
        "Squarespace generator meta tag",
        lambda soup: _check_meta_generator(soup, "squarespace"),
    ),
    (
        "Squarespace script source",
        lambda soup: _check_script_src(soup, r"squarespace\.com"),
    ),

    # --- Webflow ---
    (
        "Webflow generator meta tag",
        lambda soup: _check_meta_generator(soup, "webflow"),
    ),
    (
        "Webflow script source",
        lambda soup: _check_script_src(soup, r"webflow\.com"),
    ),

    # --- GoDaddy Website Builder ---
    (
        "GoDaddy generator meta tag",
        lambda soup: _check_meta_generator(soup, "godaddy"),
    ),

    # --- Duda ---
    (
        "Duda generator meta tag",
        lambda soup: _check_meta_generator(soup, "duda"),
    ),
    (
        "Duda script source",
        lambda soup: _check_script_src(soup, r"ironsrc\.net|dudaone\.com"),
    ),

    # --- 10Web AI ---
    (
        "10Web generator meta tag",
        lambda soup: _check_meta_generator(soup, "10web"),
    ),

    # --- WordPress (commonly used by AI content farms) ---
    (
        "WordPress generator meta tag",
        lambda soup: _check_meta_generator(soup, "wordpress"),
    ),

    # --- v0.dev (Vercel's AI coding tool) ---
    (
        "v0.dev generator meta tag",
        lambda soup: _check_meta_generator(soup, "v0.dev"),
    ),

    # --- Bolt (StackBlitz AI coding tool) ---
    (
        "Bolt generator meta tag",
        lambda soup: _check_meta_generator(soup, "bolt"),
    ),

    # --- Lovable ---
    (
        "Lovable generator meta tag",
        lambda soup: _check_meta_generator(soup, "lovable"),
    ),

    # --- Cursor (AI code editor, sometimes embeds attribution) ---
    (
        "Cursor generator meta tag",
        lambda soup: _check_meta_generator(soup, "cursor"),
    ),
]


def _check_html_comment(soup: BeautifulSoup, pattern: str) -> str | None:
    """Search HTML comments for a keyword pattern — e.g. '<!-- Made in Framer -->'."""
    from bs4 import Comment
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if re.search(pattern, comment, re.I):
            return f"HTML comment: {comment.strip()[:80]}"
    return None


def _check_meta_generator(soup: BeautifulSoup, keyword: str) -> str | None:
    """Look for <meta name='generator' content='...'> containing keyword."""
    tag = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    if tag:
        content = tag.get("content", "")
        if keyword.lower() in content.lower():
            return f'{tag}'
    return None


def _check_script_src(soup: BeautifulSoup, pattern: str) -> str | None:
    """Look for any <script src='...'> whose src matches the regex pattern."""
    for tag in soup.find_all("script", src=True):
        if re.search(pattern, tag["src"], re.I):
            return f'script src="{tag["src"]}"'
    return None


class BuilderAnalyzer(BaseAnalyzer):
    """
    Detects known AI website builder fingerprints.

    This is the highest-confidence signal: if we find a Framer or Wix
    generator tag, we can be very confident the site was AI-assisted.
    Weight: 0.40
    """

    @property
    def weight(self) -> float:
        return 0.40

    def analyze(self, html: str) -> AnalyzerResult:
        soup = BeautifulSoup(html, "lxml")
        evidence = []

        for label, check_fn in _FINGERPRINTS:
            result = check_fn(soup)
            if result:
                evidence.append(f"{label}: {result}")

        # Scoring logic:
        # Any confirmed match → 95 (very likely AI, but not 100 — could be false positive)
        # No match → 0
        score = 95 if evidence else 0

        return AnalyzerResult(score=score, weight=self.weight, evidence=evidence)
