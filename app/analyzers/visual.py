"""
Visual analyzer — scores a website screenshot using a vision LLM.

Unlike the other analyzers, this one can't implement BaseAnalyzer because it
needs screenshot bytes in addition to HTML. It follows the same pattern as
bundle_scanner: a standalone function called explicitly in scorer.py.

Requires:
  - Playwright running (screenshot captured in fetcher.py)
  - A vision API key (ANTHROPIC_API_KEY or OPENAI_API_KEY in .env)

Returns weight=0.0 and is excluded from scoring if either is unavailable.
"""
import json
import logging

from app.models import AnalyzerResult
from app.vision_providers import VisionProvider, load_provider

logger = logging.getLogger("isitai")

# Load provider once at import time — same pattern as AiTextAnalyzer loading
# the HuggingFace key. No key = provider is None = analyzer silently skips.
_PROVIDER: VisionProvider | None = load_provider()

# ── Prompt ────────────────────────────────────────────────────────────────────
# Specific enough to avoid false positives on any clean modern design,
# focused on the combination of patterns rather than any single signal.
_PROMPT = """\
Analyze this website screenshot to determine if it was created using AI coding \
tools (like v0.dev, Lovable, Bolt, Cursor) or vibe-coded with an AI assistant.

Score it 0-100 for likelihood of being AI-generated based purely on visual design \
patterns. Look for combinations of:

- shadcn/ui component aesthetics: specific card border radius, ring-offset styling, \
  ghost/outline button variants
- Hero sections with gradient or glow backgrounds and floating UI mockups
- Feature grids with icon + heading + one-liner description (3 or 6 per row)
- Dark mode with slate-950/zinc-900 backgrounds and blue or violet accents
- Glass morphism in navigation bars or cards
- Inter, Geist, or Plus Jakarta Sans at very specific weight/size combinations
- Testimonial sections with circular avatar grid
- Layouts that look algorithmically symmetrical rather than hand-crafted
- Generic AI-generated or stock photography
- CTA buttons with specific rounded styles and gradient fills common in AI tooling

Respond with ONLY valid JSON, no other text:
{"score": <0-100>, "evidence": ["specific visual observation", ...]}

Score guide:
  0-20:  Clearly hand-crafted, distinctive visual style
  21-40: Mostly human, some generic elements
  41-60: Uncertain — clean and modern but not definitively AI
  61-80: Likely AI — multiple characteristic patterns present
  81-100: Very likely AI — strong visual fingerprints throughout

Keep evidence items specific and visual. Good: "shadcn card components with \
ring-offset borders and ghost button variants". Bad: "looks AI-generated".\
"""


def analyze_visual(screenshot: bytes | None) -> AnalyzerResult:
    """
    Run visual analysis on a screenshot.

    Returns weight=0.0 (excluded from scoring) if:
      - No screenshot was captured (Playwright not running)
      - No vision provider is configured (no API key)
      - The API call fails for any reason

    Returns weight=0.25 with a real score when analysis succeeds.
    Weight is intentionally lower than text-based analyzers — visual
    patterns are suggestive but less deterministic than code fingerprints.
    """
    if screenshot is None:
        return AnalyzerResult(
            score=0, weight=0.0,
            evidence=["Skipped — Playwright not running (no screenshot)"],
        )

    if _PROVIDER is None:
        return AnalyzerResult(
            score=0, weight=0.0,
            evidence=["Skipped — no vision API key configured (set ANTHROPIC_API_KEY)"],
        )

    try:
        raw = _PROVIDER.analyze(screenshot, _PROMPT)

        # Strip markdown code fences if the model wraps its JSON
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(clean)

        score = max(0, min(100, int(data.get("score", 0))))
        evidence = [str(e) for e in data.get("evidence", [])]

        logger.info(f"Visual analysis score: {score}")
        return AnalyzerResult(score=score, weight=0.25, evidence=evidence)

    except Exception as e:
        logger.warning(f"Visual analysis failed: {e}")
        return AnalyzerResult(
            score=0, weight=0.0,
            evidence=[f"Visual analysis error (skipped): {e}"],
        )
