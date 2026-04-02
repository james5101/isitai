from app.models import AnalyzerResult, AnalysisResponse
from app.analyzers.base import BaseAnalyzer
from app.analyzers.builder import BuilderAnalyzer
from app.analyzers.content import ContentAnalyzer
from app.analyzers.code import CodeAnalyzer
from app.analyzers.images import ImageAnalyzer
from app.analyzers.ai_text import AiTextAnalyzer
from app.analyzers.stack import StackAnalyzer
from app.tech_detector import detect_stack
from app.bundle_scanner import fetch_and_scan

# All active analyzers in one place.
# To add a new analyzer later, just append it here.
ANALYZERS: list[BaseAnalyzer] = [
    BuilderAnalyzer(),
    ContentAnalyzer(),
    CodeAnalyzer(),
    ImageAnalyzer(),
    AiTextAnalyzer(),
    StackAnalyzer(),
]

_ANALYZER_KEYS = [
    "builder_fingerprint",
    "content_patterns",
    "code_patterns",
    "image_signals",
    "ai_text",
    "stack_fingerprint",
]

_LABELS = [
    (81, "Very likely AI"),
    (61, "Likely AI"),
    (41, "Uncertain"),
    (21, "Probably human"),
    (0,  "Human-built"),
]


def _score_to_label(score: int) -> str:
    for threshold, label in _LABELS:
        if score >= threshold:
            return label
    return "Human-built"


def run_analyzers(html: str, base_url: str | None = None) -> AnalysisResponse:
    """
    Run all analyzers against the HTML and return an aggregated response.

    base_url is used to resolve relative asset URLs for bundle scanning.
    It's optional — existing callers (tests) that don't pass it still work.

    Weighted average formula:
        final = sum(score_i * weight_i) / sum(weight_i)

    We normalize by total weight so the math works even if weights
    don't sum to exactly 1.0 (gives us flexibility to add analyzers).
    """
    results: dict[str, AnalyzerResult] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for key, analyzer in zip(_ANALYZER_KEYS, ANALYZERS):
        result = analyzer.analyze(html)
        results[key] = result
        weighted_sum += result.score * result.weight
        total_weight += result.weight

    # Bundle scan — only fires for Vite SPA shells (thin HTML + hashed JS bundle).
    # Fetches the main JS bundle and searches for vibe-coding library signatures.
    # Returns weight=0.0 and is excluded from scoring if skipped or failed.
    bundle_result, bundle_techs = fetch_and_scan(html, base_url)
    results["bundle_scan"] = bundle_result
    weighted_sum += bundle_result.score * bundle_result.weight
    total_weight += bundle_result.weight

    final_score = int(weighted_sum / total_weight) if total_weight > 0 else 0

    # Merge HTML-detected and bundle-detected techs, preserving order, no duplicates.
    # dict.fromkeys() is the idiomatic Python deduplication trick — like a list but ordered.
    all_techs = list(dict.fromkeys(detect_stack(html) + bundle_techs))

    return AnalysisResponse(
        score=final_score,
        label=_score_to_label(final_score),
        breakdown=results,
        stack=all_techs,
    )
