from app.analyzers.stack import StackAnalyzer

analyzer = StackAnalyzer()


def test_lovable_url_detected():
    html = '<html><head><script src="https://cdn.gptengineer.app/bundle.js"></script></head><body><div id="root"></div></body></html>'
    result = analyzer.analyze(html)
    assert result.score >= 80
    assert any("Lovable" in e for e in result.evidence)


def test_replit_url_detected():
    html = '<html><head><script src="https://myapp.replit.app/static/main.js"></script></head><body><div id="root"></div></body></html>'
    result = analyzer.analyze(html)
    assert result.score >= 80
    assert any("Replit" in e for e in result.evidence)


def test_vite_assets_detected():
    html = '''<html><head>
      <script type="module" src="/assets/index-BxYz1234.js"></script>
      <link rel="stylesheet" href="/assets/index-AbCd5678.css">
    </head><body><div id="root"></div></body></html>'''
    result = analyzer.analyze(html)
    assert result.score >= 35
    assert any("Vite" in e for e in result.evidence)


def test_shadcn_classes_detected():
    html = '''<html><body>
      <button class="inline-flex items-center ring-offset-background focus-visible:ring-ring bg-background text-foreground">
        Click me
      </button>
    </body></html>'''
    result = analyzer.analyze(html)
    assert result.score >= 35
    assert any("shadcn" in e for e in result.evidence)


def test_nextjs_detected():
    html = '''<html><head>
      <script src="/_next/static/chunks/main-abc123.js"></script>
    </head><body><div id="__next"></div></body></html>'''
    result = analyzer.analyze(html)
    assert result.score >= 25
    assert any("Next.js" in e for e in result.evidence)


def test_full_vibe_stack():
    """Vite + React root + shadcn + Inter = strong combined signal."""
    html = '''<html>
    <head>
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
      <script type="module" src="/assets/index-XkPq9rTs.js"></script>
      <link rel="stylesheet" href="/assets/index-MnBv3wXy.css">
    </head>
    <body>
      <div id="root">
        <button class="inline-flex items-center ring-offset-background focus-visible:ring-ring">
          Get Started
        </button>
      </div>
    </body></html>'''
    result = analyzer.analyze(html)
    assert result.score >= 80
    assert len(result.evidence) >= 3


def test_plain_site_scores_low():
    html = '''<html><head><title>My site</title></head>
    <body><h1>Hello</h1><p>Hand-coded with love.</p></body></html>'''
    result = analyzer.analyze(html)
    assert result.score == 0


def test_weight():
    assert analyzer.weight == 0.30
