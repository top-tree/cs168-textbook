#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://textbook.cs168.io/"
LOCAL_DIR = "cs168-local"
LOCAL_ASSET_VERSION = "20260603-fast-mode-boot-v5"
REQUEST_HEADERS = {"User-Agent": "cs168-local-mirror/1.0"}

HTML_ATTR_RE = re.compile(
    r"(?P<prefix>\b(?:href|src|action)=)(?P<quote>[\"'])(?P<url>[^\"']+)(?P=quote)"
)
CSS_URL_RE = re.compile(r"url\((?P<quote>[\"']?)(?P<url>[^)\"']+)(?P=quote)\)")
JTD_DEFAULT_CSS_RE = re.compile(
    r"<link rel=\"stylesheet\" href=\"[^\"]*just-the-docs-default\.css\">"
)
DARK_MODE_SCRIPT_RE = re.compile(r"<script>\s*let toggleDark = \(\) => \{.*?</script>", re.DOTALL)
THEME_BOOT_SCRIPT_RE = re.compile(
    r"<script data-cs168-theme-boot=\"true\">.*?</script>\s*<noscript>.*?</noscript>",
    re.DOTALL,
)
LOCAL_BOOT_SCRIPT_RE = re.compile(
    r"<script data-cs168-local-boot=\"true\">.*?</script>",
    re.DOTALL,
)
LOCAL_STYLESHEET_RE = re.compile(
    r"<link rel=\"stylesheet\" href=\"[^\"]*cs168-local/local\.css(?:\?[^\"]*)?\" data-cs168-localized=\"true\">"
)
LOCAL_ASSET_ATTR_RE = re.compile(
    r"(?P<prefix>\b(?:href|src)=)(?P<quote>[\"'])"
    r"(?P<url>[^\"']*/?cs168-local/(?:local\.css|translations\.js|localize\.js))"
    r"(?:\?[^\"']*)?(?P=quote)"
)
AUX_NAV_LIST_RE = re.compile(
    r"(<ul\b(?=[^>]*\bclass\s*=\s*([\"'])[^\"']*\baux-nav-list\b[^\"']*\2)[^>]*>\s*)",
    re.IGNORECASE,
)
STATIC_CONTROLS_RE = re.compile(
    r"<li\b(?=[^>]*\bdata-cs168-static-controls\s*=\s*([\"'])true\1)[^>]*>.*?</li>",
    re.DOTALL,
)
LOCAL_CONTROLS_HTML = (
    '<li class="aux-nav-list-item cs168-local-controls-item" data-cs168-static-controls="true">'
    '<div class="cs168-local-controls">'
    '<button class="cs168-local-button" type="button" data-cs168-mode="zh" aria-pressed="true" aria-current="true">中文</button>'
    '<button class="cs168-local-button" type="button" data-cs168-mode="en" aria-pressed="false" aria-current="false">English</button>'
    '<button class="cs168-local-button" type="button" data-cs168-mode="both" aria-pressed="false" aria-current="false">中英对照</button>'
    "</div></li>"
)
RUNTIME_ASSETS = (
    "/logo.png",
    "/assets/css/just-the-docs-dark.css",
    "/assets/js/search-data.json",
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value for name, value in attrs if value}
        if tag == "a" and attr_map.get("href"):
            self.links.append(attr_map["href"])
        for attr in ("src", "href", "poster"):
            if attr in attr_map:
                value = attr_map[attr]
                if looks_like_asset(value):
                    self.assets.append(value)


@dataclass(frozen=True)
class MirrorConfig:
    base_url: str
    output_dir: Path
    delay: float = 0.05


def is_same_site(url: str, base_url: str = BASE_URL) -> bool:
    parsed = urlparse(urljoin(base_url, url))
    base = urlparse(base_url)
    return parsed.scheme in {"http", "https"} and parsed.netloc == base.netloc


def clean_url(url: str, base_url: str = BASE_URL) -> str:
    joined = urljoin(base_url, url)
    clean, _fragment = urldefrag(joined)
    return clean


def looks_like_page(url: str) -> bool:
    path = urlparse(url).path
    return path == "/" or path.endswith("/") or path.endswith(".html")


def looks_like_asset(url: str) -> bool:
    path = urlparse(url).path.lower()
    suffix = Path(path).suffix
    return suffix in {
        ".css",
        ".js",
        ".json",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".map",
    }


def local_path_for_url(url: str, site_dir: Path, base_url: str = BASE_URL) -> Path:
    parsed = urlparse(clean_url(url, base_url))
    path = parsed.path or "/"

    if path == "/":
        return site_dir / "index.html"

    relative = path.lstrip("/")
    target = site_dir / relative
    if path.endswith("/"):
        return target / "index.html"
    if target.suffix:
        return target
    return target / "index.html"


def relative_link(url: str, current_file: Path, site_dir: Path, base_url: str = BASE_URL) -> str:
    if url.startswith("#"):
        return url

    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return url
    if parsed.netloc and not is_same_site(url, base_url):
        return url
    if url.startswith("//"):
        return url

    clean, fragment = urldefrag(url)
    absolute = clean_url(clean, base_url)
    if not is_same_site(absolute, base_url):
        return url

    target = local_path_for_url(absolute, site_dir, base_url)
    rendered = _relpath(target, current_file.parent)
    return f"{rendered}#{fragment}" if fragment else rendered


def _relpath(target: Path, start: Path) -> str:
    import os

    return os.path.relpath(target, start).replace(os.sep, "/")


def rewrite_html_links(html: str, current_file: Path, site_dir: Path, base_url: str = BASE_URL) -> str:
    def replace(match: re.Match[str]) -> str:
        url = match.group("url")
        rewritten = relative_link(url, current_file, site_dir, base_url)
        return f"{match.group('prefix')}{match.group('quote')}{rewritten}{match.group('quote')}"

    return HTML_ATTR_RE.sub(replace, html)


def theme_boot_script(current_file: Path, site_dir: Path) -> str:
    css_prefix = _relpath(site_dir / "assets/css/just-the-docs-default.css", current_file.parent)
    css_prefix = css_prefix[: -len("default.css")]
    dark_css = _relpath(site_dir / "assets/css/just-the-docs-dark.css", current_file.parent)
    return f"""<script data-cs168-theme-boot="true">
(function () {{
  var STATE_PREFIX = 'CS168_LOCAL_STATE:';
  var THEME_PARAM = 'cs168-theme';
  function readGlobalState() {{
    try {{
      if (window.name && window.name.indexOf(STATE_PREFIX) === 0) {{
        return JSON.parse(window.name.slice(STATE_PREFIX.length)) || {{}};
      }}
    }} catch (_error) {{}}
    return {{}};
  }}
  function writeGlobalState(nextState) {{
    try {{
      var state = readGlobalState();
      Object.keys(nextState || {{}}).forEach(function (key) {{
        state[key] = nextState[key];
      }});
      window.name = STATE_PREFIX + JSON.stringify(state);
    }} catch (_error) {{}}
  }}
  function readLocalDarkMode() {{
    try {{
      return localStorage.getItem('darkMode');
    }} catch (_error) {{
      return null;
    }}
  }}
  function readUrlTheme() {{
    try {{
      var value = new URL(window.location.href).searchParams.get(THEME_PARAM);
      return value === 'default' || value === 'dark' ? value : null;
    }} catch (_error) {{
      return null;
    }}
  }}
  function writeUrlTheme(nextTheme) {{
    try {{
      var url = new URL(window.location.href);
      url.searchParams.set(THEME_PARAM, nextTheme);
      history.replaceState(null, '', url.href);
    }} catch (_error) {{}}
  }}
  var windowState = readGlobalState();
  var urlTheme = readUrlTheme();
  var stored = urlTheme === 'default' ? 'false' : urlTheme === 'dark' ? 'true' : windowState.darkMode;
  if (stored === null || typeof stored === 'undefined') {{
    stored = readLocalDarkMode();
  }}
  var theme = stored === 'false' ? 'default' : 'dark';
  function themePath(theme) {{
    return '{css_prefix}' + theme + '.css';
  }}
  function normalizeTheme(value) {{
    return value === 'default' ? 'default' : 'dark';
  }}
  function applyTheme(nextTheme, persist) {{
    theme = normalizeTheme(nextTheme);
    document.documentElement.setAttribute('data-theme', theme);
    var link = document.querySelector('[data-cs168-theme-stylesheet="true"]') || document.querySelector('[rel="stylesheet"]');
    if (link) {{
      link.setAttribute('href', themePath(theme));
    }}
    if (persist) {{
      try {{
        localStorage.setItem('darkMode', String(theme === 'dark'));
      }} catch (_error) {{}}
      writeGlobalState({{ darkMode: String(theme === 'dark') }});
      writeUrlTheme(theme);
      try {{
        window.dispatchEvent(new CustomEvent('cs168-theme-change', {{ detail: {{ theme: theme }} }}));
      }} catch (_error) {{}}
    }}
  }}
  document.documentElement.setAttribute('data-theme', theme);
  window.CS168_THEME = {{
    current: function () {{
      return theme;
    }},
    apply: function (nextTheme) {{
      applyTheme(nextTheme, true);
    }},
    toggle: function () {{
      applyTheme(theme === 'dark' ? 'default' : 'dark', true);
    }}
  }};
  document.write('<link rel="stylesheet" href="' + themePath(theme) + '" data-cs168-theme-stylesheet="true">');
}})();
</script><noscript><link rel="stylesheet" href="{dark_css}" data-cs168-theme-stylesheet="true"></noscript>"""


def theme_controls_script() -> str:
    return """<script data-cs168-theme-controls="true">
window.addEventListener('DOMContentLoaded', function () {
  var darkButton = Array.from(document.querySelectorAll('.site-button')).find(function (button) {
    return button.textContent.trim() === 'Dark Mode';
  });
  if (!darkButton || !window.CS168_THEME) return;
  darkButton.addEventListener('click', function (event) {
    event.preventDefault();
    window.CS168_THEME.toggle();
  });
});
</script>"""


def rewrite_theme_runtime(html: str, current_file: Path, site_dir: Path) -> str:
    if 'data-cs168-theme-boot="true"' in html:
        html = THEME_BOOT_SCRIPT_RE.sub(
            lambda _match: theme_boot_script(current_file, site_dir),
            html,
            count=1,
        )
    else:
        html = JTD_DEFAULT_CSS_RE.sub(
            lambda _match: theme_boot_script(current_file, site_dir),
            html,
            count=1,
        )
    html = DARK_MODE_SCRIPT_RE.sub(theme_controls_script(), html, count=1)
    return html


def local_boot_script() -> str:
    return """<script data-cs168-local-boot="true">
(function () {
  var MODE_KEY = 'cs168-local-lang';
  var DEFAULT_MODE = 'zh';
  var STATE_PREFIX = 'CS168_LOCAL_STATE:';
  var LANG_PARAM = 'cs168-lang';
  function isLanguageMode(value) {
    return value === 'zh' || value === 'en' || value === 'both';
  }
  function readGlobalState() {
    try {
      if (window.name && window.name.indexOf(STATE_PREFIX) === 0) {
        return JSON.parse(window.name.slice(STATE_PREFIX.length)) || {};
      }
    } catch (_error) {}
    return {};
  }
  function readLocalValue(key) {
    try {
      return localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }
  function readUrlLanguageMode() {
    try {
      var value = new URL(window.location.href).searchParams.get(LANG_PARAM);
      return isLanguageMode(value) ? value : null;
    } catch (_error) {
      return null;
    }
  }
  var urlMode = readUrlLanguageMode();
  var globalMode = readGlobalState().lang;
  var storedMode = readLocalValue(MODE_KEY);
  var mode = isLanguageMode(urlMode)
    ? urlMode
    : isLanguageMode(globalMode)
    ? globalMode
    : isLanguageMode(storedMode)
    ? storedMode
    : DEFAULT_MODE;
  document.documentElement.dataset.langMode = mode;
  document.documentElement.setAttribute('data-cs168-localizing', mode === 'en' ? 'ready' : 'pending');
  window.setTimeout(function () {
    if (document.documentElement.getAttribute('data-cs168-localizing') === 'pending') {
      document.documentElement.setAttribute('data-cs168-localizing', 'ready');
    }
  }, 2500);
})();
</script>"""


def rewrite_local_boot(html: str) -> str:
    boot = local_boot_script()
    if 'data-cs168-local-boot="true"' in html:
        return LOCAL_BOOT_SCRIPT_RE.sub(lambda _match: boot, html, count=1)

    stylesheet = LOCAL_STYLESHEET_RE.search(html)
    if stylesheet:
        return html[: stylesheet.start()] + boot + html[stylesheet.start() :]

    if "</head>" in html:
        return html.replace("</head>", f"{boot}</head>", 1)
    return boot + html


def inject_static_controls(html: str) -> str:
    html = STATIC_CONTROLS_RE.sub("", html)
    return AUX_NAV_LIST_RE.sub(lambda match: match.group(1) + LOCAL_CONTROLS_HTML, html, count=1)


def versioned_local_asset(url: str) -> str:
    return f"{url}?v={LOCAL_ASSET_VERSION}"


def refresh_local_asset_versions(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return (
            f"{match.group('prefix')}{match.group('quote')}"
            f"{versioned_local_asset(match.group('url'))}{match.group('quote')}"
        )

    return LOCAL_ASSET_ATTR_RE.sub(replace, html)


def inject_local_layer(html: str, current_file: Path, site_dir: Path) -> str:
    html = rewrite_theme_runtime(html, current_file, site_dir)
    html = rewrite_local_boot(html)
    html = inject_static_controls(html)
    if "data-cs168-localized" in html:
        return refresh_local_asset_versions(html)

    local_css = versioned_local_asset(_relpath(site_dir / LOCAL_DIR / "local.css", current_file.parent))
    translations_js = versioned_local_asset(_relpath(site_dir / LOCAL_DIR / "translations.js", current_file.parent))
    local_js = versioned_local_asset(_relpath(site_dir / LOCAL_DIR / "localize.js", current_file.parent))
    head_bits = (
        f'<link rel="stylesheet" href="{local_css}" data-cs168-localized="true">'
    )
    body_bits = (
        f'<script src="{translations_js}" data-cs168-localized="true"></script>'
        f'<script src="{local_js}" data-cs168-localized="true"></script>'
    )

    if "</head>" in html:
        html = html.replace("</head>", f"{head_bits}</head>", 1)
    else:
        html = head_bits + html

    if "</body>" in html:
        html = html.replace("</body>", f"{body_bits}</body>", 1)
    else:
        html += body_bits

    return html


def merge_translations(paths: Iterable[Path]) -> dict:
    merged: dict = {"nav_titles": {}, "pages": {}}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged["nav_titles"].update(data.get("nav_titles", {}))
        merged["pages"].update(data.get("pages", {}))
    return merged


def default_translation_paths(translations_dir: Path = Path("translations")) -> list[Path]:
    return sorted(
        path for path in translations_dir.glob("*.json") if not path.name.startswith("_")
    )


def write_local_assets(site_dir: Path, translations: dict) -> None:
    local_dir = site_dir / LOCAL_DIR
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "local.css").write_text(LOCAL_CSS, encoding="utf-8")
    (local_dir / "localize.js").write_text(LOCAL_JS, encoding="utf-8")
    (local_dir / "translations.js").write_text(
        "window.CS168_TRANSLATIONS = "
        + json.dumps(translations, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


def fetch_bytes(url: str, attempts: int = 3) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = Request(url, headers=REQUEST_HEADERS)
        try:
            with urlopen(request, timeout=20) as response:
                content_type = response.headers.get("content-type", "")
                return response.read(), content_type
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(0.5 * attempt)
    assert last_error is not None
    raise last_error


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def rewrite_css_urls(css: str, css_file: Path, site_dir: Path, base_url: str) -> str:
    def replace(match: re.Match[str]) -> str:
        url = match.group("url").strip()
        if url.startswith("data:") or url.startswith("#"):
            return match.group(0)
        rewritten = relative_link(url, css_file, site_dir, base_url)
        return f"url({match.group('quote')}{rewritten}{match.group('quote')})"

    return CSS_URL_RE.sub(replace, css)


def rewrite_runtime_js(js: str) -> str:
    if "function localAssetPath(path)" not in js:
        js = js.replace(
            "(function (jtd, undefined) {\n",
            """(function (jtd, undefined) {

function localAssetPath(path) {
  var script = document.querySelector('script[src$="/assets/js/just-the-docs.js"], script[src$="assets/js/just-the-docs.js"]');
  if (!script || !script.src) {
    return path;
  }
  return script.src.replace(/\\/assets\\/js\\/just-the-docs\\.js(?:\\?.*)?$/, path);
}
""",
            1,
        )
    js = js.replace(
        "request.open('GET', '/assets/js/search-data.json', true);",
        "request.open('GET', localAssetPath('/assets/js/search-data.json'), true);",
    )
    js = js.replace(
        "cssFile.setAttribute('href', '/assets/css/just-the-docs-' + theme + '.css');",
        "cssFile.setAttribute('href', localAssetPath('/assets/css/just-the-docs-' + theme + '.css'));",
    )
    old_nav = """function navLink() {
  var pathname = document.location.pathname;

  var navLink = document.getElementById('site-nav').querySelector('a[href="' + pathname + '"]');
  if (navLink) {
    return navLink;
  }

  // The `permalink` setting may produce navigation links whose `href` ends with `/` or `.html`.
  // To find these links when `/` is omitted from or added to pathname, or `.html` is omitted:

  if (pathname.endsWith('/') && pathname != '/') {
    pathname = pathname.slice(0, -1);
  }

  if (pathname != '/') {
    navLink = document.getElementById('site-nav').querySelector('a[href="' + pathname + '"], a[href="' + pathname + '/"], a[href="' + pathname + '.html"]');
    if (navLink) {
      return navLink;
    }
  }

  return null; // avoids `undefined`
}
"""
    new_nav = """function navLink() {
  var links = document.getElementById('site-nav').querySelectorAll('a[href]');
  for (var i = 0; i < links.length; i++) {
    if (localNavLinkMatchesCurrent(links[i])) {
      return links[i];
    }
  }

  return null; // avoids `undefined`
}

function localNavCanonicalPath(url) {
  var path = decodeURIComponent(url.pathname || '/');
  if (path.endsWith('/index.html')) {
    path = path.slice(0, -10) || '/';
  }
  if (path.endsWith('/') && path != '/') {
    path = path.slice(0, -1);
  }
  if (!path.startsWith('/')) {
    path = '/' + path;
  }
  return path;
}

function localNavEquivalentPath(left, right) {
  return left === right || (left != '/' && left + '.html' === right) || (right != '/' && right + '.html' === left);
}

function localNavLinkMatchesCurrent(link) {
  try {
    var currentPath = localNavCanonicalPath(new URL(document.location.href));
    var linkPath = localNavCanonicalPath(new URL(link.getAttribute('href'), document.location.href));
    return localNavEquivalentPath(currentPath, linkPath);
  } catch (_error) {
    return false;
  }
}
"""
    js = js.replace(old_nav, new_nav)
    return js


def discover_from_html(html: str, page_url: str, base_url: str) -> tuple[set[str], set[str]]:
    parser = LinkParser()
    parser.feed(html)
    pages: set[str] = set()
    assets: set[str] = set()

    for href in parser.links:
        absolute = clean_url(href, page_url)
        if is_same_site(absolute, base_url) and looks_like_page(absolute):
            pages.add(absolute)

    for asset in parser.assets:
        absolute = clean_url(asset, page_url)
        if is_same_site(absolute, base_url) and looks_like_asset(absolute):
            assets.add(absolute)

    return pages, assets


def mirror(config: MirrorConfig, translations: dict) -> None:
    if config.output_dir.exists():
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True)

    pending_pages = [clean_url(config.base_url, config.base_url)]
    seen_pages: set[str] = set()
    pending_assets: set[str] = {clean_url(asset, config.base_url) for asset in RUNTIME_ASSETS}

    while pending_pages:
        page_url = pending_pages.pop(0)
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)

        try:
            content, content_type = fetch_bytes(page_url)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            print(f"Skipping page after retries: {page_url} ({error})", file=sys.stderr)
            continue
        text = content.decode("utf-8", errors="replace")
        current_file = local_path_for_url(page_url, config.output_dir, config.base_url)
        pages, assets = discover_from_html(text, page_url, config.base_url)
        pending_assets.update(assets)
        for page in sorted(pages):
            if page not in seen_pages and page not in pending_pages:
                pending_pages.append(page)

        rewritten = rewrite_html_links(text, current_file, config.output_dir, config.base_url)
        injected = inject_local_layer(rewritten, current_file, config.output_dir)
        current_file.parent.mkdir(parents=True, exist_ok=True)
        current_file.write_text(injected, encoding="utf-8")
        time.sleep(config.delay)

    asset_urls = sorted(pending_assets)

    def download_asset(asset_url: str) -> tuple[str, bool]:
        target = local_path_for_url(asset_url, config.output_dir, config.base_url)
        try:
            content, content_type = fetch_bytes(asset_url)
        except (HTTPError, URLError):
            return asset_url, False

        if "text/css" in content_type or target.suffix == ".css":
            css = content.decode("utf-8", errors="replace")
            css = rewrite_css_urls(css, target, config.output_dir, config.base_url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(css, encoding="utf-8")
            for css_asset in CSS_URL_RE.findall(css):
                url = css_asset[1].strip()
                absolute = clean_url(url, asset_url)
                if is_same_site(absolute, config.base_url) and looks_like_asset(absolute):
                    nested_target = local_path_for_url(absolute, config.output_dir, config.base_url)
                    if not nested_target.exists():
                        try:
                            nested_content, _nested_type = fetch_bytes(absolute)
                            write_bytes(nested_target, nested_content)
                        except (HTTPError, URLError):
                            pass
        elif "javascript" in content_type or target.suffix == ".js":
            js = content.decode("utf-8", errors="replace")
            js = rewrite_runtime_js(js)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(js, encoding="utf-8")
        else:
            write_bytes(target, content)
        return asset_url, True

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(download_asset, asset_url) for asset_url in asset_urls]
        for index, future in enumerate(as_completed(futures), start=1):
            _asset_url, _ok = future.result()
            if index == 1 or index % 50 == 0 or index == len(futures):
                print(f"Downloaded assets: {index}/{len(futures)}", flush=True)

    write_local_assets(config.output_dir, translations)


LOCAL_CSS = """
html[data-cs168-localizing="pending"] #site-nav,
html[data-cs168-localizing="pending"] .main-content,
html[data-cs168-localizing="pending"] .breadcrumb-nav,
html[data-cs168-localizing="pending"] .content-nav {
  visibility: hidden;
}

.cs168-local-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0.75rem 0 0;
}

.aux-nav-list-item.cs168-local-controls-item {
  align-items: center;
  display: flex;
}

.aux-nav-list-item .cs168-local-controls {
  margin: 0;
}

.cs168-local-button {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--body-background-color);
  color: var(--body-text-color);
  cursor: pointer;
  font: inherit;
  line-height: 1.1;
  min-height: 2rem;
  padding: 0.35rem 0.55rem;
  white-space: nowrap;
}

html[data-lang-mode="zh"] [data-cs168-mode="zh"],
html[data-lang-mode="en"] [data-cs168-mode="en"],
html[data-lang-mode="both"] [data-cs168-mode="both"],
.cs168-local-button.active,
.cs168-local-button:hover {
  background: var(--link-color, transparent);
  color: var(--body-text-color);
  font-weight: 700;
  text-decoration: underline;
  text-underline-offset: 0.15em;
}

.cs168-i18n-line {
  display: block;
}

.cs168-i18n-zh {
  margin-top: 0.4rem;
}

h1 .cs168-i18n-zh,
h2 .cs168-i18n-zh,
h3 .cs168-i18n-zh {
  font-size: 0.78em;
}

.cs168-i18n-missing {
  border-left: 4px solid var(--link-color);
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
}
""".strip()


LOCAL_JS = r"""
(function () {
  var MODE_KEY = 'cs168-local-lang';
  var DEFAULT_MODE = 'zh';
  var STATE_PREFIX = 'CS168_LOCAL_STATE:';
  var LANG_PARAM = 'cs168-lang';
  var THEME_PARAM = 'cs168-theme';
  var initialized = false;

  function readGlobalState() {
    try {
      if (window.name && window.name.indexOf(STATE_PREFIX) === 0) {
        return JSON.parse(window.name.slice(STATE_PREFIX.length)) || {};
      }
    } catch (_error) {}
    return {};
  }

  function writeGlobalState(nextState) {
    try {
      var state = readGlobalState();
      Object.keys(nextState || {}).forEach(function (key) {
        state[key] = nextState[key];
      });
      window.name = STATE_PREFIX + JSON.stringify(state);
    } catch (_error) {}
  }

  function readLocalValue(key) {
    try {
      return localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function writeLocalValue(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (_error) {}
  }

  function readLocalDarkMode() {
    try {
      return localStorage.getItem('darkMode');
    } catch (_error) {
      return null;
    }
  }

  function isLanguageMode(value) {
    return value === 'zh' || value === 'en' || value === 'both';
  }

  function readUrlLanguageMode() {
    try {
      var value = new URL(window.location.href).searchParams.get(LANG_PARAM);
      return isLanguageMode(value) ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function readUrlThemeChoice() {
    try {
      var value = new URL(window.location.href).searchParams.get(THEME_PARAM);
      return value === 'default' || value === 'dark' ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function currentTheme() {
    if (window.CS168_THEME && typeof window.CS168_THEME.current === 'function') {
      return window.CS168_THEME.current() === 'default' ? 'default' : 'dark';
    }
    return document.documentElement.getAttribute('data-theme') === 'default' ? 'default' : 'dark';
  }

  function isStatefulLocalLink(url) {
    if (!url || (url.protocol !== 'file:' && url.origin !== window.location.origin)) {
      return false;
    }
    if (url.pathname === window.location.pathname && url.hash && !url.search) {
      return false;
    }
    var currentPath = decodeURIComponent(window.location.pathname || '');
    var nextPath = decodeURIComponent(url.pathname || '');
    if (currentPath.indexOf('/site/') >= 0) {
      return nextPath.indexOf('/site/') >= 0;
    }
    return true;
  }

  function statefulHref(rawHref, mode) {
    if (!rawHref || rawHref.charAt(0) === '#') {
      return rawHref;
    }
    try {
      var url = new URL(rawHref, window.location.href);
      if (!isStatefulLocalLink(url)) return rawHref;
      url.searchParams.set(LANG_PARAM, mode);
      url.searchParams.set(THEME_PARAM, currentTheme());
      return url.href;
    } catch (_error) {
      return rawHref;
    }
  }

  function refreshInternalLinks(mode) {
    document.querySelectorAll('a[href]').forEach(function (link) {
      if (!link.dataset.cs168OriginalHref) {
        link.dataset.cs168OriginalHref = link.getAttribute('href');
      }
      link.setAttribute('href', statefulHref(link.dataset.cs168OriginalHref, mode));
    });
  }

  function updateCurrentUrl(mode) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set(LANG_PARAM, mode);
      url.searchParams.set(THEME_PARAM, currentTheme());
      history.replaceState(null, '', url.href);
    } catch (_error) {}
  }

  function persistLanguageMode(mode) {
    if (!isLanguageMode(mode)) return;
    writeLocalValue(MODE_KEY, mode);
    writeGlobalState({ lang: mode });
    updateCurrentUrl(mode);
    refreshInternalLinks(mode);
  }

  function currentLanguageMode() {
    return isLanguageMode(document.documentElement.dataset.langMode)
      ? document.documentElement.dataset.langMode
      : savedLanguageMode();
  }

  function syncClickedLinkState(event) {
    var target = event.target;
    var link = target && typeof target.closest === 'function' ? target.closest('a[href]') : null;
    if (!link) return;
    var mode = currentLanguageMode();
    persistLanguageMode(mode);
    if (!link.dataset.cs168OriginalHref) {
      link.dataset.cs168OriginalHref = link.getAttribute('href');
    }
    link.setAttribute('href', statefulHref(link.dataset.cs168OriginalHref, mode));
  }

  function savedLanguageMode() {
    var urlMode = readUrlLanguageMode();
    if (isLanguageMode(urlMode)) {
      writeLocalValue(MODE_KEY, urlMode);
      writeGlobalState({ lang: urlMode });
      return urlMode;
    }
    var globalMode = readGlobalState().lang;
    if (isLanguageMode(globalMode)) {
      return globalMode;
    }
    var stored = readLocalValue(MODE_KEY);
    if (isLanguageMode(stored)) {
      writeGlobalState({ lang: stored });
      return stored;
    }
    return DEFAULT_MODE;
  }

  function normalize(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function escapeHtml(value) {
    var span = document.createElement('span');
    span.textContent = String(value || '');
    return span.innerHTML;
  }

  function canonicalPath() {
    var path = decodeURIComponent(window.location.pathname || '/');
    var marker = '/site/';
    var markerIndex = path.indexOf(marker);
    if (markerIndex >= 0) {
      path = path.slice(markerIndex + marker.length - 1);
    }
    if (path.endsWith('/index.html')) path = path.slice(0, -10) || '/';
    if (!path.startsWith('/')) path = '/' + path;
    return path;
  }

  function pageTranslations() {
    var data = window.CS168_TRANSLATIONS || {};
    var pages = data.pages || {};
    return pages[canonicalPath()] || null;
  }

  function cache(el) {
    if (!el.dataset.cs168OriginalHtml) {
      el.dataset.cs168OriginalHtml = el.innerHTML;
      el.dataset.cs168OriginalText = normalize(el.textContent);
    }
  }

  function restoreTranslated() {
    document.querySelectorAll('[data-cs168-translated="true"]').forEach(function (el) {
      el.innerHTML = el.dataset.cs168OriginalHtml || el.innerHTML;
      el.removeAttribute('data-cs168-translated');
    });
  }

  function keepAnchor(el, html) {
    var anchor = el.querySelector('.anchor-heading');
    return anchor ? anchor.outerHTML + ' ' + html : html;
  }

  function renderBlock(el, zhHtml, mode) {
    cache(el);
    var original = el.dataset.cs168OriginalHtml;
    el.dataset.cs168Translated = 'true';
    if (mode === 'en') {
      el.innerHTML = original;
    } else if (mode === 'both') {
      el.innerHTML =
        '<span class="cs168-i18n-line cs168-i18n-en">' +
        original +
        '</span><span class="cs168-i18n-line cs168-i18n-zh">' +
        keepAnchor(el, zhHtml) +
        '</span>';
    } else {
      el.innerHTML = keepAnchor(el, zhHtml);
    }
  }

  function renderTranslatedHtml(originalHtml, zhHtml, mode) {
    if (mode === 'en') {
      return originalHtml;
    }
    if (mode === 'both') {
      return (
        '<span class="cs168-i18n-line cs168-i18n-en">' +
        originalHtml +
        '</span><span class="cs168-i18n-line cs168-i18n-zh">' +
        zhHtml +
        '</span>'
      );
    }
    return zhHtml;
  }

  function alignSidebarToActiveLink() {
    var nav = document.getElementById('site-nav');
    var active = nav ? nav.querySelector('.nav-list-link.active') : null;
    if (active && typeof active.scrollIntoView === 'function') {
      active.scrollIntoView({ block: 'center' });
    }
  }

  function renderNav(mode) {
    var titles = (window.CS168_TRANSLATIONS || {}).nav_titles || {};
    document.querySelectorAll('#site-nav .nav-list-link, .breadcrumb-nav-list-item > a, .breadcrumb-nav-list-item > span').forEach(function (el) {
      cache(el);
      var original = el.dataset.cs168OriginalText;
      if (mode === 'en') {
        el.innerHTML = el.dataset.cs168OriginalHtml;
      } else if (mode === 'both' && titles[original]) {
        el.innerHTML =
          '<span class="cs168-i18n-line cs168-i18n-en">' +
          el.dataset.cs168OriginalHtml +
          '</span><span class="cs168-i18n-line cs168-i18n-zh">' +
          escapeHtml(titles[original]) +
          '</span>';
      } else if (titles[original]) {
        el.textContent = titles[original];
      }
    });
  }

  function renderInPageNav(mode, pageData) {
    if (!pageData) return;
    var blocksByEnglish = {};
    (pageData.blocks || []).forEach(function (block) {
      blocksByEnglish[normalize(block.en)] = block;
    });
    document.querySelectorAll('.content-nav a.nav-list-link').forEach(function (link) {
      cache(link);
      var block = blocksByEnglish[normalize(link.dataset.cs168OriginalText)];
      if (!block) return;
      link.dataset.cs168Translated = 'true';
      link.innerHTML = renderTranslatedHtml(link.dataset.cs168OriginalHtml, block.zh_html, mode);
    });
  }

  function renderNotice(mode, hasTranslation) {
    var old = document.querySelector('.cs168-i18n-missing');
    if (old) old.remove();
    if (mode === 'en' || hasTranslation) return;
    var main = document.querySelector('.main-content');
    if (!main) return;
    var notice = document.createElement('div');
    notice.className = 'cs168-i18n-missing';
    notice.textContent = '此页尚未加入中文翻译，暂显示英文原文。';
    main.prepend(notice);
  }

  function syncThemeChoice() {
    var urlTheme = readUrlThemeChoice();
    var stored = urlTheme === 'default' ? 'false' : urlTheme === 'dark' ? 'true' : readGlobalState().darkMode;
    if (stored === null || typeof stored === 'undefined') {
      stored = readLocalDarkMode();
    }
    var theme = stored === 'false' ? 'default' : 'dark';
    if (window.CS168_THEME && typeof window.CS168_THEME.apply === 'function') {
      window.CS168_THEME.apply(theme);
    } else {
      document.documentElement.setAttribute('data-theme', theme);
      writeGlobalState({ darkMode: String(theme === 'dark') });
      if (window.jtd && typeof window.jtd.setTheme === 'function') {
        window.jtd.setTheme(theme);
      }
    }
  }

  function render(mode) {
    restoreTranslated();
    document.documentElement.dataset.langMode = mode;
    document.querySelectorAll('[data-cs168-mode]').forEach(function (button) {
      var active = button.dataset.cs168Mode === mode;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
      button.setAttribute('aria-current', active ? 'true' : 'false');
    });

    var pageData = pageTranslations();
    renderNav(mode);
    renderInPageNav(mode, pageData);
    renderNotice(mode, Boolean(pageData));
    refreshInternalLinks(mode);
    if (!pageData || mode === 'en') return;

    var candidates = Array.from(
      document.querySelectorAll('.main-content h1, .main-content h2, .main-content h3, .main-content p, .main-content li')
    ).filter(function (el) {
      return !el.closest('.content-nav');
    });
    (pageData.blocks || []).forEach(function (block) {
      var target = candidates.find(function (el) {
        cache(el);
        return normalize(el.dataset.cs168OriginalText) === normalize(block.en);
      });
      if (target) renderBlock(target, block.zh_html, mode);
    });
  }

  function markLocalReady() {
    document.documentElement.setAttribute('data-cs168-localizing', 'ready');
  }

  function addControls() {
    var controls = document.querySelector('.cs168-local-controls');
    if (!controls) {
      controls = document.createElement('div');
      controls.className = 'cs168-local-controls';
      controls.innerHTML =
        '<button class="cs168-local-button" type="button" data-cs168-mode="zh" aria-pressed="false">中文</button>' +
        '<button class="cs168-local-button" type="button" data-cs168-mode="en" aria-pressed="false">English</button>' +
        '<button class="cs168-local-button" type="button" data-cs168-mode="both" aria-pressed="false">中英对照</button>';

      var aux = document.querySelector('.aux-nav-list');
      if (aux) {
        var item = document.createElement('li');
        item.className = 'aux-nav-list-item cs168-local-controls-item';
        item.appendChild(controls);
        aux.insertBefore(item, aux.firstElementChild);
      } else {
        var footer = document.querySelector('.site-footer');
        if (footer) footer.prepend(controls);
        else document.body.prepend(controls);
      }
    }

    controls.querySelectorAll('[data-cs168-mode]').forEach(function (button) {
      if (button.dataset.cs168Bound === 'true') return;
      button.dataset.cs168Bound = 'true';
      button.addEventListener('click', function () {
        persistLanguageMode(button.dataset.cs168Mode);
        render(button.dataset.cs168Mode);
        markLocalReady();
      });
    });
  }

  // ---- entry point ----

  function init() {
    if (initialized) return;
    initialized = true;
    syncThemeChoice();
    addControls();
    var mode = savedLanguageMode();
    persistLanguageMode(mode);
    render(mode);
    markLocalReady();
    document.addEventListener('click', syncClickedLinkState, true);
    window.addEventListener('cs168-theme-change', function () {
      refreshInternalLinks(currentLanguageMode());
    });
    setTimeout(alignSidebarToActiveLink, 0);
  }

  if (document.body) {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  }
})();
""".strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirror textbook.cs168.io as local HTML.")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--output", default="site")
    parser.add_argument("--translation", action="append", default=["translations/intro_intro.json"])
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args(argv)

    translations = merge_translations(Path(path) for path in args.translation)
    mirror(MirrorConfig(args.base_url, Path(args.output), args.delay), translations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
