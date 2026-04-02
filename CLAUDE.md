# CLAUDE.md — isitai

## Project overview

FastAPI service that scores websites 0–100 for likelihood of being AI-generated or vibe-coded.
Seven analyzers examine HTML (and optionally a fetched JS bundle) and produce weighted scores that are combined into a final result.

## Commands

```bash
# Run the development server
uvicorn app.main:app --reload

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_bundle_scanner.py -v
```

## Architecture

```
Request → fetcher.py (fetch HTML) → scorer.py (run all analyzers) → AnalysisResponse
                                          │
                    ┌─────────────────────┼──────────────────────┐
               analyzers/           bundle_scanner.py       tech_detector.py
               (7 analyzers)        (Vite SPA → fetch JS)   (informational only)
```

### Key design decisions

- **Analyzers are independent** — each implements `BaseAnalyzer` (ABC) with a `weight` property and `analyze(html) -> AnalyzerResult`. Adding a new analyzer means: create the file, add to `ANALYZERS` list and `_ANALYZER_KEYS` in `scorer.py`.
- **Weighted average, normalized** — `sum(score × weight) / sum(weight)`. Weights don't need to sum to 1.0. Analyzers that abstain return `weight=0.0` and are excluded from the denominator automatically.
- **Bundle scanner is opt-in** — only fires for Vite SPA shells (HTML < 10,000 chars + hashed module script). Returns `weight=0.0` and never blocks the main analysis if skipped or fetch fails.
- **Sync analyzers, async endpoints** — analyzers use sync httpx (inside `asyncio.to_thread`) so they don't need to be async. The FastAPI endpoints are async and offload blocking work via `to_thread`.
- **No Accept-Encoding header** — httpx manages decompression automatically. Setting Accept-Encoding manually bypasses decompression and returns raw bytes.

## File reference

| File | Role |
|---|---|
| `app/main.py` | FastAPI app. Two POST endpoints + static file serving. |
| `app/scorer.py` | Runs all analyzers + bundle scan. Returns `AnalysisResponse`. |
| `app/fetcher.py` | Async HTTP fetch with browser-like headers. Handles error hints (403, 429, etc.). |
| `app/bundle_scanner.py` | Detects Vite SPA shells, fetches JS bundle, scans for vibe-coding library signals. |
| `app/tech_detector.py` | Informational only — detects 30+ technologies for the stack pills. Not scored. |
| `app/models.py` | Pydantic models: `UrlRequest`, `HtmlRequest`, `AnalyzerResult`, `AnalysisResponse`. |
| `app/config.py` | Loads `HF_API_KEY` from `.env` via python-dotenv. |
| `app/analyzers/base.py` | `BaseAnalyzer` ABC. All analyzers extend this. |
| `app/analyzers/builder.py` | Framer, Wix, Squarespace, Webflow, etc. Weight 0.40. |
| `app/analyzers/content.py` | AI buzzword density. Weight 0.30. |
| `app/analyzers/code.py` | Code structure patterns. Weight 0.20. |
| `app/analyzers/images.py` | AI/stock CDN image domains. Weight 0.10. |
| `app/analyzers/ai_text.py` | HuggingFace roberta classifier. Weight 0.35 (0 if no key). |
| `app/analyzers/stack.py` | Vite/shadcn/platform URL fingerprints. Weight 0.30. |
| `static/index.html` | Single-file frontend. No build step. Vanilla JS. |

## Environment

Copy `.env.example` to `.env`. The only variable is `HF_API_KEY` (HuggingFace token, free). The app runs without it — the AI text analyzer silently abstains (`weight=0.0`).

## Tests

69 tests across 7 files. All use `pytest` (no async test framework needed — the analyzers are sync).
Bundle scanner tests use `unittest.mock.patch` to mock `httpx.Client` — no real HTTP calls in tests.

When adding a new analyzer:
1. Create `app/analyzers/your_analyzer.py`
2. Add instance to `ANALYZERS` list in `scorer.py`
3. Add key string to `_ANALYZER_KEYS` in `scorer.py`
4. Add `tests/test_your_analyzer.py`
5. Update `test_analyze_html_ai_site` in `tests/test_api.py` to include the new breakdown key
