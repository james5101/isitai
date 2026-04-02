import pytest
from app.analyzers.builder import BuilderAnalyzer

analyzer = BuilderAnalyzer()


def test_framer_meta_tag():
    html = '<html><head><meta name="generator" content="Framer 5.0"></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95
    assert any("Framer generator meta tag" in e for e in result.evidence)


def test_framer_script_src():
    html = '<html><head><script src="https://assets.framer.com/releases/framer.js"></script></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95
    assert any("Framer script source" in e for e in result.evidence)


def test_wix_generator():
    html = '<html><head><meta name="generator" content="Wix.com Website Builder"></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95


def test_squarespace_generator():
    html = '<html><head><meta name="generator" content="Squarespace 7.1"></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95


def test_webflow_generator():
    html = '<html><head><meta name="generator" content="Webflow"></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95


def test_framer_html_comment():
    html = '<!doctype html>\n<!-- Made in Framer · framer.com -->\n<html><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95
    assert any("Framer HTML comment" in e for e in result.evidence)


def test_v0_dev_generator():
    html = '<html><head><meta name="generator" content="v0.dev"></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95
    assert any("v0.dev" in e for e in result.evidence)


def test_bolt_generator():
    html = '<html><head><meta name="generator" content="bolt"></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95


def test_lovable_generator():
    html = '<html><head><meta name="generator" content="lovable"></head><body></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 95


def test_plain_site_scores_zero():
    html = '<html><head><title>My hand-coded site</title></head><body><p>Hello</p></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 0
    assert result.evidence == []


def test_weight():
    assert analyzer.weight == 0.40
