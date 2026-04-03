# CLAUDE.md — isitai

## Project overview

FastAPI service that scores websites 0–100 for likelihood of being AI-generated or vibe-coded.
Eight analyzers examine HTML (and optionally a fetched JS bundle + Playwright screenshot) and produce weighted scores combined into a final result.

**Requires Docker** — Playwright/Chromium won't run on Windows without it.

## Commands

```bash
# Run the development server
docker compose up --build   # first time or after requirements change
docker compose up           # after that

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_bundle_scanner.py -v
```

## Architecture

```
Request → fetcher.py (httpx → Playwright fallback) → scorer.py (run all analyzers) → AnalysisResponse
                                          │
                    ┌─────────────────────┼──────────────────────┐
               analyzers/           bundle_scanner.py       tech_detector.py
               (6 text analyzers)   (Vite SPA → fetch JS)   (informational only)
                    │
               analyzers/visual.py  ← screenshot bytes (PNG)
               vision_providers.py  ← AnthropicVisionProvider (claude-sonnet-4-6)
```

### Fetching strategy

1. **httpx always runs first** — fast, no bot footprint, used for all HTML analysis
2. **Playwright navigation fallback** — fires only if httpx gets a 4xx (Cloudflare etc.)
3. **Screenshot** — always tries live Playwright navigation first (full CSS/JS render); falls back to `set_content()` if navigation fails; screenshots under 15KB are discarded as blank

### Key design decisions

- **Analyzers are independent** — each implements `BaseAnalyzer` (ABC) with a `weight` property and `analyze(html) -> AnalyzerResult`. Adding a new analyzer means: create the file, add to `ANALYZERS` list and `_ANALYZER_KEYS` in `scorer.py`.
- **Weighted average, normalized** — `sum(score × weight) / sum(weight)`. Only analyzers with `score > 0` contribute — zero-score analyzers abstain rather than diluting positive signals.
- **Bundle scanner is opt-in** — only fires for Vite SPA shells (HTML < 10,000 chars + hashed module script). Returns `weight=0.0` and never blocks the main analysis if skipped or fetch fails.
- **Visual analyzer is opt-in** — requires `ANTHROPIC_API_KEY` and a non-blank Playwright screenshot. Returns `weight=0.0` otherwise.
- **Sync analyzers, async endpoints** — analyzers use sync httpx (inside `asyncio.to_thread`) so they don't need to be async. The FastAPI endpoints are async and offload blocking work via `to_thread`.
- **No Accept-Encoding header** — httpx manages decompression automatically. Setting Accept-Encoding manually bypasses decompression and returns raw bytes.
- **Screenshot base64 in response** — `AnalysisResponse.screenshot` carries the PNG as a base64 string so the frontend can render it as an `<img>` tag without a separate endpoint.

## File reference

| File | Role |
|---|---|
| `app/main.py` | FastAPI app. CORS middleware. Playwright lifespan manager. Two POST endpoints + static file serving. |
| `app/scorer.py` | Runs all analyzers + bundle scan + visual. Returns `AnalysisResponse` with base64 screenshot. |
| `app/fetcher.py` | `FetchResult` dataclass. httpx+Playwright fetch. Screenshot via live nav or set_content fallback. |
| `app/bundle_scanner.py` | Detects Vite SPA shells, fetches JS bundle, scans for vibe-coding library signals. |
| `app/vision_providers.py` | `VisionProvider` ABC. `AnthropicVisionProvider` (claude-sonnet-4-6). OpenAI stub. `load_provider()` factory. |
| `app/analyzers/visual.py` | Calls vision provider with screenshot. Returns `AnalyzerResult`. Weight 0.25. |
| `app/tech_detector.py` | Informational only — detects 30+ technologies for the stack pills. Not scored. |
| `app/models.py` | Pydantic models: `UrlRequest`, `HtmlRequest`, `AnalyzerResult`, `AnalysisResponse`. |
| `app/config.py` | Loads `HF_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` from `.env` via python-dotenv. |
| `app/analyzers/base.py` | `BaseAnalyzer` ABC. All analyzers extend this. |
| `app/analyzers/builder.py` | Framer, Wix, Squarespace, Webflow, v0, Bolt, Lovable, Cursor. Weight 0.40. |
| `app/analyzers/content.py` | AI buzzword density. Weight 0.30. |
| `app/analyzers/code.py` | Code structure patterns + large inline scripts. Weight 0.20. |
| `app/analyzers/images.py` | AI/stock CDN image domains. Weight 0.10. |
| `app/analyzers/ai_text.py` | HuggingFace roberta classifier. Weight 0.35 (0 if no key). |
| `app/analyzers/stack.py` | Vite/shadcn/platform URLs, import maps, ESM CDNs, direct AI API calls. Weight 0.30. |
| `static/index.html` | Single-file frontend. No build step. Vanilla JS. Screenshot preview + Download Report. |
| `extension/` | Chrome MV3 browser extension. Auto-analyzes current tab. |
| `Dockerfile` | python:3.12-slim + playwright install --with-deps chromium. |
| `docker-compose.yml` | Volume mounts for hot reload, env_file. |

## Environment

Copy `.env.example` to `.env`.

| Variable | Required | Description |
|---|---|---|
| `HF_API_KEY` | No | HuggingFace token — enables AI text analyzer (roberta-large) |
| `ANTHROPIC_API_KEY` | No | Anthropic token — enables visual analysis via claude-sonnet-4-6 |
| `OPENAI_API_KEY` | No | OpenAI token — stub only, not yet implemented |

## Tests

72 tests across 8 files. All use `pytest` (no async test framework needed — the analyzers are sync).
Bundle scanner tests use `unittest.mock.patch` to mock `httpx.Client` — no real HTTP calls in tests.

When adding a new analyzer:
1. Create `app/analyzers/your_analyzer.py`
2. Add instance to `ANALYZERS` list in `scorer.py`
3. Add key string to `_ANALYZER_KEYS` in `scorer.py`
4. Add `tests/test_your_analyzer.py`
5. Update `test_analyze_html_ai_site` in `tests/test_api.py` to include the new breakdown key
