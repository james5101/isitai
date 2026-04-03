# isitai

A FastAPI service that scores websites 0-100 for likelihood of being AI-generated or vibe-coded. Submit a URL and get back a score, a human-readable label, a per-analyzer breakdown, a detected tech stack, and a Playwright screenshot.

## How it works

Eight independent analyzers examine the HTML (and optionally a fetched JS bundle and a Playwright screenshot) for signals. Their scores are combined using a normalized weighted average — only analyzers that found something contribute to the denominator:

```
final = sum(score_i x weight_i) / sum(weight_i)   [where score_i > 0]
```

| Analyzer | What it looks for | Weight |
|---|---|---|
| Builder fingerprint | Framer, Wix, Squarespace, Webflow, v0, Bolt, Lovable, Cursor meta tags | 0.40 |
| Content patterns | AI buzzword density (seamless, leverage, cutting-edge, etc.) | 0.30 |
| Stack fingerprint | Vite assets, shadcn/ui classes, platform URLs, import maps, ESM CDNs, direct AI API calls | 0.30 |
| AI text | HuggingFace roberta-large-openai-detector — skipped if no HF_API_KEY | 0.35 |
| Bundle scan | Fetches the Vite JS bundle and scans for lovable-tagger, shadcn, Radix, Lucide, Sonner, etc. | 0.35 |
| Visual analysis | Vision LLM (claude-sonnet-4-6) scores a Playwright screenshot — skipped if no ANTHROPIC_API_KEY | 0.25 |
| Code patterns | Sequential class names, generic IDs, large inline scripts | 0.20 |
| Image signals | AI/stock CDN domains (Unsplash, Framer CDN, etc.) | 0.10 |

### Score labels

| Score | Label |
|---|---|
| 81-100 | Very likely AI |
| 61-80 | Likely AI |
| 41-60 | Uncertain |
| 21-40 | Probably human |
| 0-20 | Human-built |

### Fetching strategy

1. **httpx first** — fast plain HTTP fetch used for all HTML analysis
2. **Playwright fallback** — if httpx gets a 4xx (Cloudflare etc.), Playwright retries with real Chromium
3. **Screenshot** — always tries live Playwright navigation first for a fully-rendered page; falls back to `set_content()` if blocked; blank screenshots are discarded

## Setup

Requires Docker (Playwright/Chromium needs Linux).

```bash
git clone https://github.com/your-username/isitai.git
cd isitai
cp .env.example .env
docker compose up --build
```

The UI is at http://localhost:8000. API docs at http://localhost:8000/docs.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| HF_API_KEY | No | HuggingFace API token. Enables the AI text analyzer. |
| ANTHROPIC_API_KEY | No | Anthropic API token. Enables visual analysis via claude-sonnet-4-6. |
| OPENAI_API_KEY | No | OpenAI token. Stub only — not yet implemented. |

Get a free HuggingFace token at https://huggingface.co/settings/tokens (Read permission).

## API

### POST /analyze/url

Fetch and analyze a live URL.

```bash
curl -X POST http://localhost:8000/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

### POST /analyze/html

Analyze raw HTML directly. `base_url` is optional but enables bundle scanning for Vite SPA shells.

```bash
curl -X POST http://localhost:8000/analyze/html \
  -H "Content-Type: application/json" \
  -d '{"html": "<html>...</html>", "base_url": "https://example.com"}'
```

### Response shape

```json
{
  "score": 87,
  "label": "Very likely AI",
  "breakdown": {
    "builder_fingerprint": { "score": 95, "weight": 0.4,  "evidence": ["Framer generator meta tag"] },
    "bundle_scan":         { "score": 90, "weight": 0.35, "evidence": ["Lovable detected in JS bundle"] },
    "visual":              { "score": 75, "weight": 0.25, "evidence": ["shadcn/ui card layout", "AI hero image"] }
  },
  "stack": ["Vite", "React", "shadcn/ui", "Radix UI", "Lucide"],
  "screenshot": "<base64-encoded PNG or null>"
}
```

## Frontend features

- **Score + breakdown** — per-analyzer accordion with evidence list and mini progress bars
- **Tech stack pills** — detected technologies shown as tags
- **Page screenshot** — Playwright screenshot embedded in the results
- **Download Report** — exports a self-contained HTML file with score, screenshot, and full breakdown

## Browser extension

A Chrome MV3 extension lives in `extension/`. It auto-analyzes the current tab and shows the score, top evidence, and stack pills in a popup. Includes a "View full report" link that opens the main app pre-filled with the tab URL.

## Project structure

```
app/
  main.py              FastAPI app — CORS, Playwright lifespan, two endpoints
  scorer.py            Runs all analyzers, computes weighted average
  fetcher.py           httpx + Playwright fetch, FetchResult dataclass, screenshot logic
  bundle_scanner.py    Vite SPA detection and JS bundle scan
  vision_providers.py  VisionProvider ABC, AnthropicVisionProvider, OpenAI stub
  tech_detector.py     Informational stack detection (no scoring)
  models.py            Pydantic request/response models
  config.py            Loads .env via python-dotenv
  analyzers/
    base.py            Abstract base class all analyzers implement
    builder.py         Builder platform fingerprints (0.40)
    content.py         Buzzword density (0.30)
    stack.py           Vite/React/shadcn/platform stack signals (0.30)
    ai_text.py         HuggingFace roberta classifier (0.35)
    visual.py          Vision LLM screenshot analysis (0.25)
    code.py            Code structure patterns (0.20)
    images.py          Image CDN signals (0.10)
static/
  index.html           Single-file frontend (vanilla JS, no build step)
extension/
  manifest.json        Chrome MV3 manifest
  popup.html           Extension popup UI
  popup.js             Tab analysis, score display, settings
tests/                 pytest suite — 72 tests
Dockerfile             python:3.12-slim + Playwright Chromium
docker-compose.yml     Hot reload volume mounts
```

## Running tests

```bash
pytest tests/ -v
```
