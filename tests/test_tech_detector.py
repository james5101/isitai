from app.tech_detector import detect_stack


def test_nextjs_detected():
    html = '<html><head><script src="/_next/static/chunks/main.js"></script></head><body></body></html>'
    assert "Next.js" in detect_stack(html)


def test_react_root_detected():
    html = '<html><body><div id="root"></div></body></html>'
    assert "React" in detect_stack(html)


def test_vue_app_detected():
    html = '<html><body><div id="app" data-v-app></div></body></html>'
    assert "Vue" in detect_stack(html)


def test_vite_detected():
    html = '<html><head><script type="module" src="/assets/index-BxYz1234.js"></script></head><body></body></html>'
    assert "Vite" in detect_stack(html)


def test_tailwind_via_cdn():
    html = '<html><head><script src="https://cdn.tailwindcss.com"></script></head><body></body></html>'
    assert "Tailwind CSS" in detect_stack(html)


def test_tailwind_via_classes():
    html = '''<html><body>
      <div class="flex items-center justify-between px-4 py-2 bg-white rounded shadow">
        hello
      </div>
    </body></html>'''
    assert "Tailwind CSS" in detect_stack(html)


def test_bootstrap_detected():
    html = '<html><head><link rel="stylesheet" href="bootstrap.min.css"></head><body></body></html>'
    assert "Bootstrap" in detect_stack(html)


def test_wordpress_detected():
    html = '<html><head><link rel="stylesheet" href="/wp-content/themes/main.css"></head><body></body></html>'
    assert "WordPress" in detect_stack(html)


def test_google_analytics_detected():
    html = '<html><head><script>gtag("config", "G-XXXX")</script></head><body></body></html>'
    assert "Google Analytics" in detect_stack(html)


def test_shadcn_detected():
    html = '<html><body><button class="ring-offset-background focus-visible:ring-ring">Click</button></body></html>'
    assert "shadcn/ui" in detect_stack(html)


def test_jquery_detected():
    html = '<html><head><script src="https://code.jquery.com/jquery-3.6.0.min.js"></script></head><body></body></html>'
    assert "jQuery" in detect_stack(html)


def test_multiple_techs_detected():
    """A typical Next.js + Tailwind + Google Analytics site."""
    html = '''<html>
    <head>
      <script src="/_next/static/chunks/main.js"></script>
      <script src="https://cdn.tailwindcss.com"></script>
      <script>gtag("config", "G-XXXX")</script>
    </head>
    <body><div id="__next"></div></body></html>'''
    detected = detect_stack(html)
    assert "Next.js" in detected
    assert "Tailwind CSS" in detected
    assert "Google Analytics" in detected


def test_plain_page_detects_nothing():
    html = '<html><head><title>My page</title></head><body><p>Hello world</p></body></html>'
    assert detect_stack(html) == []


def test_broken_html_does_not_raise():
    """Malformed HTML should never raise — detect_stack always returns a list."""
    result = detect_stack("<html><<<<broken>")
    assert isinstance(result, list)
