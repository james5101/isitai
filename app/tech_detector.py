import re
from bs4 import BeautifulSoup

# ── Detection rules ────────────────────────────────────────────────────────────
#
# Each rule is a (tech_name, check_fn) pair.
# check_fn receives (html: str, soup: BeautifulSoup) and returns True/False.
#
# Rules are grouped by category for readability, but the list is flat —
# we just iterate through all of them and collect the ones that fire.
# Think of it like a Nagios check catalogue: each check is independent.

def _any_script_src(soup: BeautifulSoup, pattern: re.Pattern) -> bool:
    return any(pattern.search(tag.get("src", "")) for tag in soup.find_all("script", src=True))

def _any_link_href(soup: BeautifulSoup, pattern: re.Pattern) -> bool:
    return any(pattern.search(tag.get("href", "")) for tag in soup.find_all("link", href=True))

def _in_html(html: str, pattern: re.Pattern) -> bool:
    return bool(pattern.search(html))


_RULES: list[tuple[str, callable]] = [

    # ── AI Website Builders ──────────────────────────────────────────────────

    ("Framer", lambda html, soup:
        _in_html(html, re.compile(r'framer\.com|framerusercontent\.com', re.I))),

    # ── JS Frameworks ────────────────────────────────────────────────────────

    ("Next.js", lambda html, soup:
        _in_html(html, re.compile(r'__NEXT_DATA__|/_next/static/', re.I))),

    ("Nuxt.js", lambda html, soup:
        _in_html(html, re.compile(r'__NUXT_DATA__|/_nuxt/', re.I))),

    ("Astro", lambda html, soup:
        _in_html(html, re.compile(r'astro-island|astro-slot', re.I))),

    ("SvelteKit", lambda html, soup:
        _in_html(html, re.compile(r'__sveltekit|sveltekit:component', re.I))),

    ("React", lambda html, soup:
        soup.find("div", id="root") is not None
        or _in_html(html, re.compile(r'data-reactroot|__reactFiber|__reactProps', re.I))),

    ("Vue", lambda html, soup:
        soup.find("div", id="app") is not None
        or _in_html(html, re.compile(r'__vue_app__|data-v-app', re.I))),

    ("Angular", lambda html, soup:
        _in_html(html, re.compile(r'ng-version|ng-app|angular\.min\.js', re.I))),

    # ── Build tools ──────────────────────────────────────────────────────────

    ("Vite", lambda html, soup:
        bool(re.search(r'/assets/[a-zA-Z0-9_-]+-[a-zA-Z0-9]{8,}\.(js|css)', html))),

    ("webpack", lambda html, soup:
        _in_html(html, re.compile(r'__webpack_require__|webpackChunk', re.I))),

    ("Parcel", lambda html, soup:
        _in_html(html, re.compile(r'parcelRequire', re.I))),

    # ── CSS frameworks ───────────────────────────────────────────────────────

    ("Tailwind CSS", lambda html, soup: _any_link_href(soup, re.compile(r'tailwind', re.I))
        or _in_html(html, re.compile(r'tailwindcss|cdn\.tailwindcss\.com', re.I))
        or _has_tailwind_classes(soup)),

    ("Bootstrap", lambda html, soup:
        _any_link_href(soup, re.compile(r'bootstrap', re.I))
        or _any_script_src(soup, re.compile(r'bootstrap', re.I))),

    ("Bulma", lambda html, soup:
        _any_link_href(soup, re.compile(r'bulma', re.I))),

    # ── UI component libraries ────────────────────────────────────────────────

    ("shadcn/ui", lambda html, soup:
        "ring-offset-background" in html and "focus-visible:ring-ring" in html),

    ("Material UI", lambda html, soup:
        _in_html(html, re.compile(r'MuiButton|MuiBox|MuiContainer|@mui', re.I))),

    ("Ant Design", lambda html, soup:
        _in_html(html, re.compile(r'ant-btn|ant-layout|antd', re.I))),

    ("Radix UI", lambda html, soup:
        _in_html(html, re.compile(r'data-radix-|radix-ui', re.I))),

    # ── Hosting / CDN ────────────────────────────────────────────────────────

    ("Vercel", lambda html, soup:
        _any_script_src(soup, re.compile(r'vercel\.live|/_vercel/', re.I))
        or _in_html(html, re.compile(r'vercel\.app', re.I))),

    ("Netlify", lambda html, soup:
        _in_html(html, re.compile(r'netlify\.app|netlify\.com/img', re.I))),

    ("Cloudflare", lambda html, soup:
        _any_script_src(soup, re.compile(r'cloudflare', re.I))
        or _in_html(html, re.compile(r'__cf_chl|cdn-cgi/challenge', re.I))),

    # ── Analytics ─────────────────────────────────────────────────────────────

    ("Google Analytics", lambda html, soup:
        _in_html(html, re.compile(r'gtag\(|google-analytics\.com|googletagmanager\.com', re.I))),

    ("Plausible", lambda html, soup:
        _any_script_src(soup, re.compile(r'plausible\.io', re.I))),

    ("Hotjar", lambda html, soup:
        _in_html(html, re.compile(r'hotjar\.com|hjSetting', re.I))),

    ("Mixpanel", lambda html, soup:
        _in_html(html, re.compile(r'mixpanel\.com|mixpanel\.init', re.I))),

    # ── CMS / Platforms ───────────────────────────────────────────────────────

    ("WordPress", lambda html, soup:
        _in_html(html, re.compile(r'/wp-content/|/wp-includes/', re.I))),

    ("Shopify", lambda html, soup:
        _any_script_src(soup, re.compile(r'cdn\.shopify\.com', re.I))
        or _in_html(html, re.compile(r'Shopify\.theme', re.I))),

    ("Ghost", lambda html, soup:
        _in_html(html, re.compile(r'ghost\.org|content\.ghost\.io', re.I))),

    ("Contentful", lambda html, soup:
        _in_html(html, re.compile(r'ctfassets\.net|contentful\.com', re.I))),

    # ── Misc JS libraries ────────────────────────────────────────────────────

    ("jQuery", lambda html, soup:
        _any_script_src(soup, re.compile(r'jquery', re.I))
        or _in_html(html, re.compile(r'jQuery\.fn\.jquery', re.I))),

    ("Alpine.js", lambda html, soup:
        _in_html(html, re.compile(r'x-data=|x-bind:|alpinejs', re.I))),

    ("HTMX", lambda html, soup:
        _in_html(html, re.compile(r'hx-get=|hx-post=|htmx\.org', re.I))),
]


def _has_tailwind_classes(soup: BeautifulSoup) -> bool:
    """
    Detect Tailwind by looking for its characteristic utility class patterns.
    A single element with 3+ Tailwind-style utilities is a strong signal.
    We use a sampling approach (first 50 tags) for performance.
    """
    tailwind_pattern = re.compile(
        r'\b(flex|grid|block|inline|hidden|text-\w+|bg-\w+|p-\d|px-\d|py-\d|'
        r'm-\d|mx-\d|my-\d|w-\d|h-\d|rounded|shadow|border|gap-\d|space-\w+|'
        r'items-\w+|justify-\w+|font-\w+|overflow-\w+)\b'
    )
    for tag in soup.find_all(True, limit=50):
        classes = " ".join(tag.get("class", []))
        if len(tailwind_pattern.findall(classes)) >= 3:
            return True
    return False


def detect_stack(html: str) -> list[str]:
    """
    Run all detection rules against the HTML and return a sorted list
    of detected technology names.

    Returns an empty list if nothing is detected — never raises.
    This is informational only; no scoring involved.
    """
    soup = BeautifulSoup(html, "lxml")
    detected = []

    for name, check_fn in _RULES:
        try:
            if check_fn(html, soup):
                detected.append(name)
        except Exception:
            # A broken rule should never crash the whole detector.
            pass

    return detected
