import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_analyze_html_ai_site():
    """A page with Framer meta tag + Unsplash images should score above uncertain range."""
    # Builder (95, w=0.4) + image (100, w=0.1), others score 0
    # Expected: (95*0.4 + 100*0.1) / (0.4+0.3+0.2+0.1+0.3) = 48/1.3 ≈ 36
    html = """<html>
    <head><meta name="generator" content="Framer 5.0"></head>
    <body>
      <img src="https://images.unsplash.com/photo-1234567890-abc.jpg" alt="hero"/>
    </body></html>"""
    r = client.post("/analyze/html", json={"html": html})
    assert r.status_code == 200
    data = r.json()
    assert data["score"] > 30
    assert "breakdown" in data
    assert set(data["breakdown"].keys()) == {
        "builder_fingerprint", "content_patterns", "code_patterns",
        "image_signals", "ai_text", "stack_fingerprint", "bundle_scan", "visual"
    }


def test_analyze_html_plain_site():
    """A plain HTML page with no AI signals should score low."""
    html = """<html>
    <head><title>My blog</title></head>
    <body><p>I write about hiking and cooking.</p></body>
    </html>"""
    r = client.post("/analyze/html", json={"html": html})
    assert r.status_code == 200
    data = r.json()
    assert data["score"] < 30


def test_analyze_url_invalid_url():
    """Invalid URL should be rejected by Pydantic before hitting any logic."""
    r = client.post("/analyze/url", json={"url": "not-a-url"})
    assert r.status_code == 422  # Unprocessable Entity — Pydantic validation error


def test_response_has_label():
    html = "<html><body><p>Hello</p></body></html>"
    r = client.post("/analyze/html", json={"html": html})
    assert "label" in r.json()
