import json
import tempfile
import unittest
from pathlib import Path

from tools.mirror_textbook import (
    BASE_URL,
    RUNTIME_ASSETS,
    inject_local_layer,
    local_path_for_url,
    relative_link,
    rewrite_html_links,
    rewrite_runtime_js,
)


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

    def test_runtime_handles_file_urls_inside_site_directory(self):
        source = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        self.assertIn("const marker = '/site/'", source)
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

    def test_intro_translation_has_required_terms(self):
        data = json.loads(Path("translations/intro_intro.json").read_text(encoding="utf-8"))
        intro = data["pages"]["/intro/intro.html"]["blocks"]
        joined = "\n".join(block["zh_html"] for block in intro)

        self.assertGreaterEqual(len(intro), 20)
        self.assertIn("互联网(Internet)", joined)
        self.assertIn("协议(protocols)", joined)
        self.assertIn("联邦式系统(federated system)", joined)


if __name__ == "__main__":
    unittest.main()
