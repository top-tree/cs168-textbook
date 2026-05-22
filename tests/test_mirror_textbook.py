import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))

from tools.mirror_textbook import (
    BASE_URL,
    RUNTIME_ASSETS,
    inject_local_layer,
    local_path_for_url,
    relative_link,
    rewrite_html_links,
    rewrite_runtime_js,
)
from tools.translation_coverage import canonical_translation_key


class MirrorTextbookTests(unittest.TestCase):
    def test_local_path_for_url_maps_pages_and_assets(self):
        site = Path("/tmp/site")

        self.assertEqual(local_path_for_url(BASE_URL, site), site / "index.html")
        self.assertEqual(
            local_path_for_url(BASE_URL + "intro/", site),
            site / "intro" / "index.html",
        )
        self.assertEqual(
            local_path_for_url(BASE_URL + "intro/intro.html", site),
            site / "intro" / "intro.html",
        )
        self.assertEqual(
            local_path_for_url(BASE_URL + "assets/intro/1-01-lan.png", site),
            site / "assets" / "intro" / "1-01-lan.png",
        )

    def test_relative_link_rewrites_same_site_urls(self):
        site = Path("/tmp/site")
        current = site / "intro" / "intro.html"

        self.assertEqual(relative_link("/assets/css/site.css", current, site), "../assets/css/site.css")
        self.assertEqual(relative_link("/routing/", current, site), "../routing/index.html")
        self.assertEqual(relative_link("#protocols", current, site), "#protocols")
        self.assertEqual(
            relative_link("https://cs168.io", current, site),
            "https://cs168.io",
        )

    def test_rewrite_html_links_keeps_external_links(self):
        site = Path("/tmp/site")
        current = site / "intro" / "intro.html"
        html = '<a href="/intro/">Intro</a><img src="/assets/intro/a.png"><a href="https://cs168.io">CS</a>'

        rewritten = rewrite_html_links(html, current, site)

        self.assertIn('href="index.html"', rewritten)
        self.assertIn('src="../assets/intro/a.png"', rewritten)
        self.assertIn('href="https://cs168.io"', rewritten)

    def test_inject_local_layer_adds_assets_and_switcher_hooks(self):
        html = "<html><head></head><body><footer class=\"site-footer\">Footer</footer></body></html>"
        injected = inject_local_layer(html, Path("/tmp/site/intro/intro.html"), Path("/tmp/site"))

        self.assertIn("cs168-local/local.css", injected)
        self.assertIn("cs168-local/translations.js", injected)
        self.assertIn("cs168-local/localize.js", injected)
        self.assertIn("data-cs168-localized", injected)

    def test_inject_local_layer_bootstraps_theme_before_stylesheets(self):
        html = (
            '<html><head>'
            '<link rel="stylesheet" href="../assets/css/just-the-docs-default.css">'
            '<script> let toggleDark = () => { localStorage.setItem(\'darkMode\', String(true)); }; </script>'
            '</head><body></body></html>'
        )
        injected = inject_local_layer(html, Path("/tmp/site/intro/intro.html"), Path("/tmp/site"))

        self.assertIn('data-cs168-theme-boot="true"', injected)
        self.assertIn("just-the-docs-' + theme + '.css", injected)
        self.assertIn("stored === 'false' ? 'default' : 'dark'", injected)
        self.assertNotIn("let toggleDark = ()", injected)
        self.assertLess(
            injected.index('data-cs168-theme-boot="true"'),
            injected.index("cs168-local/local.css"),
        )

    def test_runtime_handles_file_urls_inside_site_directory(self):
        source = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        self.assertIn("marker = '/site/'", source)
        self.assertIn("markerIndex", source)

    def test_runtime_assets_are_mirrored(self):
        self.assertIn("/logo.png", RUNTIME_ASSETS)
        self.assertIn("/assets/css/just-the-docs-dark.css", RUNTIME_ASSETS)
        self.assertIn("/assets/js/search-data.json", RUNTIME_ASSETS)

    def test_runtime_js_uses_local_asset_paths(self):
        js = """(function (jtd, undefined) {
  request.open('GET', '/assets/js/search-data.json', true);
  cssFile.setAttribute('href', '/assets/css/just-the-docs-' + theme + '.css');
"""

        rewritten = rewrite_runtime_js(js)

        self.assertIn("function localAssetPath(path)", rewritten)
        self.assertIn("localAssetPath('/assets/js/search-data.json')", rewritten)
        self.assertIn("localAssetPath('/assets/css/just-the-docs-' + theme + '.css')", rewritten)

    def test_runtime_js_resolves_relative_sidebar_links(self):
        js = Path("site/assets/js/just-the-docs.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for source in (js, generator):
            self.assertIn("function localNavCanonicalPath(url)", source)
            self.assertIn("function localNavLinkMatchesCurrent(link)", source)
            self.assertIn("new URL(link.getAttribute('href'), document.location.href)", source)
            self.assertIn("querySelectorAll('a[href]')", source)
        self.assertNotIn("querySelector('a[href=\"' + pathname + '\"]')", js)

    def test_runtime_does_not_override_just_the_docs_sidebar_navigation(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertNotIn("style.display", js)
            self.assertNotIn("cs168-nav-open", js)
            self.assertNotIn("cs168-nav-scroll", js)
            self.assertNotIn("NAV_SCROLL_KEY", js)
            self.assertNotIn("function initNav()", js)
            self.assertNotIn("nav-list-expander", js)
            self.assertNotIn("beforeunload", js)
            self.assertNotIn("scrollTop", js)

    def test_runtime_realines_sidebar_after_translation_without_persisting_scroll(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function alignSidebarToActiveLink()", js)
            self.assertIn("active.scrollIntoView({ block: 'center' })", js)
            self.assertNotIn("localStorage.setItem(NAV", js)

    def test_runtime_places_language_controls_in_top_aux_nav(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("document.querySelector('.aux-nav-list')", js)
            self.assertIn("aux.insertBefore(item, aux.firstElementChild)", js)
            self.assertIn("cs168-local-controls-item", js)
            self.assertLess(js.index("document.querySelector('.aux-nav-list')"), js.index("document.querySelector('.site-footer')"))

    def test_runtime_nav_supports_bilingual_mode(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function escapeHtml(value)", js)
            self.assertIn("mode === 'both'", js)
            self.assertIn("cs168-i18n-en", js)
            self.assertIn("cs168-i18n-zh", js)
            self.assertIn("escapeHtml(titles[original])", js)

    def test_runtime_respects_saved_theme_choice_without_overriding(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function syncThemeChoice()", js)
            self.assertIn("window.CS168_THEME.apply(theme)", js)
            self.assertIn("localStorage.getItem('darkMode')", js)
            self.assertNotIn("function setDarkDefault()", js)
            self.assertNotIn("localStorage.setItem('darkMode', 'true')", js)

    def test_translation_coverage_key_normalizes_html_and_typographic_punctuation(self):
        plain = "We’ve seen a bottom-up view of the Internet."
        html = "We&apos;ve seen a <strong>bottom-up</strong> view of the Internet."

        self.assertEqual(canonical_translation_key(plain), canonical_translation_key(html))

    def test_intro_translation_has_required_terms(self):
        data = json.loads(Path("translations/intro_intro.json").read_text(encoding="utf-8"))
        intro = data["pages"]["/intro/intro.html"]["blocks"]
        joined = "\n".join(block["zh_html"] for block in intro)

        self.assertGreaterEqual(len(intro), 20)
        self.assertIn("互联网(Internet)", joined)
        self.assertIn("协议(protocols)", joined)
        self.assertIn("联邦式系统(federated system)", joined)

    def test_beyond_client_server_nav_title_keeps_original_term(self):
        data = json.loads(Path("translations/intro_intro.json").read_text(encoding="utf-8"))

        self.assertEqual(
            data["nav_titles"]["Beyond Client-Server"],
            "超越客户端-服务器(Beyond Client-Server)",
        )


if __name__ == "__main__":
    unittest.main()
