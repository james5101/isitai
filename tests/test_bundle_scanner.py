"""
Tests for app/bundle_scanner.py

We mock httpx.Client so no real network calls happen.
unittest.mock.patch replaces the real httpx.Client with a fake one
that returns whatever response we configure — same idea as mocking
an AWS API call in a Terraform test.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.bundle_scanner import extract_bundle_url, scan_bundle, fetch_and_scan


# ── extract_bundle_url ────────────────────────────────────────────────────────

def test_extract_bundle_url_relative_src():
    """Relative /assets/... src gets resolved to an absolute URL."""
    html = '<script type="module" crossorigin src="/assets/index-AbCd1234.js"></script>'
    url = extract_bundle_url(html, "https://example.com")
    assert url == "https://example.com/assets/index-AbCd1234.js"


def test_extract_bundle_url_absolute_src():
    """Already-absolute src is returned unchanged."""
    html = '<script type="module" crossorigin src="https://cdn.example.com/assets/index-AbCd1234.js"></script>'
    url = extract_bundle_url(html, "https://example.com")
    assert url == "https://cdn.example.com/assets/index-AbCd1234.js"


def test_extract_bundle_url_no_match():
    """Non-Vite HTML returns None."""
    html = '<script src="/app.js"></script>'
    url = extract_bundle_url(html, "https://example.com")
    assert url is None


def test_extract_bundle_url_too_large():
    """HTML over 10,000 chars is not a thin SPA shell — skip it."""
    html = "x" * 10_001
    url = extract_bundle_url(html, "https://example.com")
    assert url is None


def test_extract_bundle_url_no_base_url():
    """Relative src with no base_url can't be resolved — returns None."""
    html = '<script type="module" crossorigin src="/assets/index-AbCd1234.js"></script>'
    url = extract_bundle_url(html, None)
    assert url is None


def test_extract_bundle_url_short_hash_ignored():
    """Hash must be 8+ chars — shorter ones don't match."""
    html = '<script type="module" crossorigin src="/assets/index-Ab12.js"></script>'
    url = extract_bundle_url(html, "https://example.com")
    assert url is None


# ── scan_bundle ───────────────────────────────────────────────────────────────

def test_scan_bundle_lovable():
    """lovable-tagger alone gives 90 points."""
    score, evidence, techs = scan_bundle('require("lovable-tagger")')
    assert score == 90
    assert "Lovable" in techs
    assert any("lovable-tagger" in e for e in evidence)


def test_scan_bundle_shadcn_stack():
    """shadcn + Radix + Lucide + Sonner → 35+20+20+20 = 95."""
    bundle = 'ring-offset-background radix-ui lucide-react "sonner"'
    score, evidence, techs = scan_bundle(bundle)
    assert score == 95
    assert "shadcn/ui" in techs
    assert "Radix UI" in techs
    assert "Lucide" in techs
    assert "Sonner" in techs


def test_scan_bundle_capped_at_100():
    """Points exceeding 100 are capped at 100."""
    # lovable-tagger(90) + shadcn(35) = 125 → capped at 100
    bundle = 'lovable-tagger ring-offset-background'
    score, evidence, techs = scan_bundle(bundle)
    assert score == 100


def test_scan_bundle_no_signals():
    """Plain bundle with no vibe-coding signals scores 0."""
    score, evidence, techs = scan_bundle("var x = 1; function hello() { return 'world'; }")
    assert score == 0
    assert techs == []
    assert evidence == []


def test_scan_bundle_zod_and_rhf():
    """Zod(10) + React Hook Form(10) = 20."""
    bundle = '"zod" react-hook-form'
    score, evidence, techs = scan_bundle(bundle)
    assert score == 20
    assert "Zod" in techs
    assert "React Hook Form" in techs


# ── fetch_and_scan ────────────────────────────────────────────────────────────

_SPA_HTML = '<script type="module" crossorigin src="/assets/index-AbCd1234.js"></script>'

_LOVABLE_BUNDLE = 'require("lovable-tagger"); ring-offset-background; radix-ui; lucide-react;'


def _make_mock_response(text: str, status_code: int = 200, content: bytes | None = None):
    """Build a fake httpx response object."""
    mock_resp = MagicMock()
    mock_resp.text = text
    mock_resp.content = content if content is not None else text.encode()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()  # no-op — success
    return mock_resp


def test_fetch_and_scan_lovable_site():
    """
    Full pipeline: Vite SPA shell → fetch bundle → find lovable signals.

    patch() swaps httpx.Client with our fake for the duration of the test.
    The 'with httpx.Client() as client' block in fetch_and_scan gets our mock.
    """
    mock_resp = _make_mock_response(_LOVABLE_BUNDLE)
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get = MagicMock(return_value=mock_resp)

    with patch("app.bundle_scanner.httpx.Client", return_value=mock_client):
        result, techs = fetch_and_scan(_SPA_HTML, "https://example.com")

    assert result.weight == 0.35         # bundle was scanned, weight is active
    assert result.score > 50             # lovable-tagger alone gives 90
    assert "Lovable" in techs


def test_fetch_and_scan_not_a_spa():
    """Non-SPA HTML (no Vite module script) → weight=0.0, no fetch."""
    html = "<html><body><p>Hello world</p></body></html>"
    result, techs = fetch_and_scan(html, "https://example.com")
    assert result.weight == 0.0
    assert techs == []
    assert any("skipped" in e.lower() for e in result.evidence)


def test_fetch_and_scan_html_too_large():
    """HTML > 10,000 chars → weight=0.0, bundle not fetched."""
    html = "x" * 10_001
    result, techs = fetch_and_scan(html, "https://example.com")
    assert result.weight == 0.0
    assert techs == []


def test_fetch_and_scan_fetch_error():
    """Network error during bundle fetch → weight=0.0, no crash."""
    import httpx

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get = MagicMock(side_effect=httpx.HTTPError("connection refused"))

    with patch("app.bundle_scanner.httpx.Client", return_value=mock_client):
        result, techs = fetch_and_scan(_SPA_HTML, "https://example.com")

    assert result.weight == 0.0
    assert techs == []


def test_fetch_and_scan_bundle_too_large():
    """Bundle over 600KB → weight=0.0, not scanned."""
    big_content = b"x" * 600_001
    mock_resp = _make_mock_response("", content=big_content)
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get = MagicMock(return_value=mock_resp)

    with patch("app.bundle_scanner.httpx.Client", return_value=mock_client):
        result, techs = fetch_and_scan(_SPA_HTML, "https://example.com")

    assert result.weight == 0.0
    assert techs == []
    assert any("too large" in e for e in result.evidence)


def test_fetch_and_scan_no_signals_still_scanned():
    """
    Bundle fetched successfully but no vibe-coding signals found.
    Weight is still 0.35 — we did the work, just found nothing.
    """
    mock_resp = _make_mock_response("var x = 1; console.log('hello');")
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get = MagicMock(return_value=mock_resp)

    with patch("app.bundle_scanner.httpx.Client", return_value=mock_client):
        result, techs = fetch_and_scan(_SPA_HTML, "https://example.com")

    assert result.weight == 0.35   # scanned successfully
    assert result.score == 0       # but nothing found
    assert techs == []
