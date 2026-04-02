import re
from bs4 import BeautifulSoup
from app.analyzers.base import BaseAnalyzer
from app.models import AnalyzerResult

# AI code generators tend to produce very generic, sequential class names
# and IDs. Real developers use semantic names; AI tools use these patterns.
_SEQUENTIAL_CLASS_PATTERN = re.compile(
    r'\b(section|block|container|wrapper|row|col|div|item|component)-\d+\b', re.I
)
_GENERIC_ID_PATTERN = re.compile(
    r'\b(hero|banner|cta|main-content|section|wrapper|container|block)-?(section|area|wrapper|container|button|block)?\b',
    re.I
)

# Data attributes left by specific AI website tools
_AI_DATA_ATTRS = [
    re.compile(r'^data-framer-', re.I),   # Framer AI
    re.compile(r'^data-wf-', re.I),        # Webflow
    re.compile(r'^data-duda-', re.I),      # Duda
]


class CodeAnalyzer(BaseAnalyzer):
    """
    Detects AI-generated code patterns in HTML structure.

    AI code generators leave tell-tale signs: sequential class names,
    overly generic IDs, and tool-specific data attributes.
    Weight: 0.20
    """

    @property
    def weight(self) -> float:
        return 0.20

    def analyze(self, html: str) -> AnalyzerResult:
        soup = BeautifulSoup(html, "lxml")
        evidence = []
        signals = 0

        # Check 1: Sequential/generic class names (e.g. "section-1", "block-2")
        sequential_hits = []
        for tag in soup.find_all(True):  # True = all tags
            for cls in tag.get("class", []):
                if _SEQUENTIAL_CLASS_PATTERN.search(cls):
                    sequential_hits.append(cls)
        if sequential_hits:
            signals += 1
            unique = list(dict.fromkeys(sequential_hits))[:5]  # show first 5 unique
            evidence.append(f"Sequential class names: {', '.join(unique)}")

        # Check 2: Generic IDs
        generic_id_hits = []
        for tag in soup.find_all(id=True):
            if _GENERIC_ID_PATTERN.search(tag["id"]):
                generic_id_hits.append(tag["id"])
        if len(generic_id_hits) >= 3:  # a few generics is fine; many is suspicious
            signals += 1
            evidence.append(f"Generic IDs ({len(generic_id_hits)}): {', '.join(generic_id_hits[:5])}")

        # Check 3: AI tool data attributes
        for tag in soup.find_all(True):
            for attr in tag.attrs:
                for pattern in _AI_DATA_ATTRS:
                    if pattern.search(attr):
                        signals += 2  # data attrs are a strong signal
                        evidence.append(f"AI tool data attribute: {attr}")
                        break

        # Scale: each signal adds ~25 points, capped at 100
        score = min(100, signals * 25)

        return AnalyzerResult(score=score, weight=self.weight, evidence=evidence)
