import re
from bs4 import BeautifulSoup
from app.analyzers.base import BaseAnalyzer
from app.models import AnalyzerResult

# Words and phrases that appear heavily in AI-generated marketing copy.
# These were chosen because they're rarely used in hand-written technical
# or personal content, but appear constantly in AI-generated business sites.
_BUZZWORDS = [
    "leverage", "leveraging", "seamless", "seamlessly",
    "cutting-edge", "cutting edge", "innovative", "innovate",
    "empower", "empowering", "streamline", "streamlining",
    "elevate", "elevating", "robust", "scalable", "scalability",
    "unlock", "game-changing", "game changing", "revolutionize",
    "synergy", "synergize", "holistic", "transformative",
    "in today's digital landscape", "digital landscape",
    "in today's fast-paced", "fast-paced world",
    "take your business to the next level",
    "solutions tailored", "tailored solutions",
    "best-in-class", "world-class", "state-of-the-art",
    "dynamic", "comprehensive solutions", "end-to-end",
    "drive growth", "drive results", "drive success",
]

# Pre-compile patterns for performance (avoids recompiling on every call)
_PATTERNS = [re.compile(r'\b' + re.escape(w) + r'\b', re.I) for w in _BUZZWORDS]


class ContentAnalyzer(BaseAnalyzer):
    """
    Detects AI writing patterns in page text.

    AI tools tend to produce dense, buzzword-heavy marketing copy.
    We measure the density of known AI phrases per 100 words.
    Weight: 0.30
    """

    @property
    def weight(self) -> float:
        return 0.30

    def analyze(self, html: str) -> AnalyzerResult:
        soup = BeautifulSoup(html, "lxml")

        # Extract visible text only — strip scripts, styles, and nav clutter
        for tag in soup(["script", "style", "nav", "footer", "head"]):
            tag.decompose()
        text = soup.get_text(separator=" ")

        words = text.split()
        word_count = len(words)

        if word_count < 50:
            # Not enough text to make a meaningful judgement
            return AnalyzerResult(score=0, weight=self.weight, evidence=["Not enough text to analyze"])

        evidence = []
        hit_count = 0
        for pattern, phrase in zip(_PATTERNS, _BUZZWORDS):
            matches = pattern.findall(text)
            if matches:
                hit_count += len(matches)
                evidence.append(f'"{phrase}" ×{len(matches)}')

        # Density formula: hits per 100 words, scaled up aggressively.
        # 1 hit per 100 words → score of 10
        # 10 hits per 100 words → score of 100 (capped)
        density = (hit_count / word_count) * 100
        score = min(100, int(density * 10))

        return AnalyzerResult(score=score, weight=self.weight, evidence=evidence)
