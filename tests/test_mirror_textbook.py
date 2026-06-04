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
    rewrite_theme_runtime,
    rewrite_runtime_js,
)
from tools.translation_coverage import canonical_translation_key

EXPECTED_LOCAL_ASSET_VERSION = "20260604-index-path-v9"


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
        html = (
            '<html><head></head><body><ul class="aux-nav-list">'
            '<li class="aux-nav-list-item">Dark Mode</li>'
            '</ul><footer class="site-footer">Footer</footer></body></html>'
        )
        injected = inject_local_layer(html, Path("/tmp/site/intro/intro.html"), Path("/tmp/site"))

        self.assertIn(f"cs168-local/local.css?v={EXPECTED_LOCAL_ASSET_VERSION}", injected)
        self.assertIn(f"cs168-local/translations.js?v={EXPECTED_LOCAL_ASSET_VERSION}", injected)
        self.assertIn(f"cs168-local/localize.js?v={EXPECTED_LOCAL_ASSET_VERSION}", injected)
        self.assertIn("data-cs168-localized", injected)
        self.assertIn('data-cs168-local-boot="true"', injected)
        self.assertIn('data-cs168-static-controls="true"', injected)
        self.assertIn('data-cs168-mode="zh"', injected)
        self.assertIn('data-cs168-mode="en"', injected)
        self.assertIn('data-cs168-mode="both"', injected)
        self.assertLess(
            injected.index('data-cs168-local-boot="true"'),
            injected.index("cs168-local/local.css"),
        )
        self.assertLess(
            injected.index('data-cs168-static-controls="true"'),
            injected.index('Dark Mode'),
        )

    def test_inject_local_layer_handles_aux_nav_with_extra_attributes(self):
        html = (
            "<html><head></head><body><ul data-role='auxiliary' class='js-ready aux-nav-list compact'>"
            '<li class="aux-nav-list-item">Dark Mode</li>'
            '</ul></body></html>'
        )

        injected = inject_local_layer(html, Path("/tmp/site/index.html"), Path("/tmp/site"))

        self.assertIn('data-cs168-static-controls="true"', injected)
        self.assertLess(
            injected.index('data-cs168-static-controls="true"'),
            injected.index('Dark Mode'),
        )

    def test_static_language_controls_do_not_claim_current_mode_before_boot_sync(self):
        html = '<html><head></head><body><ul class="aux-nav-list"></ul></body></html>'

        injected = inject_local_layer(html, Path("/tmp/site/index.html"), Path("/tmp/site"))

        self.assertIn('data-cs168-mode="zh" aria-pressed="false" aria-current="false"', injected)
        self.assertIn('data-cs168-mode="en" aria-pressed="false" aria-current="false"', injected)
        self.assertIn('data-cs168-mode="both" aria-pressed="false" aria-current="false"', injected)

    def test_local_boot_syncs_static_controls_and_marks_fallback(self):
        html = '<html><head></head><body><ul class="aux-nav-list"></ul></body></html>'

        injected = inject_local_layer(html, Path("/tmp/site/index.html"), Path("/tmp/site"))

        self.assertIn("function syncStaticControls(mode)", injected)
        self.assertIn("syncStaticControls(mode);", injected)
        self.assertIn("data-cs168-localizing', 'fallback'", injected)
        self.assertIn("data-cs168-local-fallback", injected)

    def test_inject_local_layer_refreshes_existing_local_asset_versions(self):
        html = (
            '<html><head>'
            '<link rel="stylesheet" href="../cs168-local/local.css?v=old" data-cs168-localized="true">'
            '</head><body>'
            '<script src="../cs168-local/translations.js?v=old" data-cs168-localized="true"></script>'
            '<script src="../cs168-local/localize.js?v=old" data-cs168-localized="true"></script>'
            '</body></html>'
        )

        injected = inject_local_layer(html, Path("/tmp/site/intro/intro.html"), Path("/tmp/site"))

        self.assertIn(f"../cs168-local/local.css?v={EXPECTED_LOCAL_ASSET_VERSION}", injected)
        self.assertIn(f"../cs168-local/translations.js?v={EXPECTED_LOCAL_ASSET_VERSION}", injected)
        self.assertIn(f"../cs168-local/localize.js?v={EXPECTED_LOCAL_ASSET_VERSION}", injected)
        self.assertNotIn("?v=old", injected)

    def test_inject_local_layer_refreshes_local_boot_and_static_controls(self):
        html = (
            '<html><head>'
            '<script data-cs168-local-boot="true">old local boot</script>'
            '<link rel="stylesheet" href="../cs168-local/local.css?v=old" data-cs168-localized="true">'
            '</head><body><ul class="aux-nav-list">'
            '<li class="aux-nav-list-item cs168-local-controls-item" data-cs168-static-controls="true">old controls</li>'
            '<li class="aux-nav-list-item">Dark Mode</li>'
            '</ul>'
            '<script src="../cs168-local/translations.js?v=old" data-cs168-localized="true"></script>'
            '<script src="../cs168-local/localize.js?v=old" data-cs168-localized="true"></script>'
            '</body></html>'
        )

        injected = inject_local_layer(html, Path("/tmp/site/intro/intro.html"), Path("/tmp/site"))

        self.assertNotIn("old local boot", injected)
        self.assertNotIn("old controls", injected)
        self.assertIn('data-cs168-local-boot="true"', injected)
        self.assertIn("document.documentElement.dataset.langMode = mode;", injected)
        self.assertIn("data-cs168-localizing", injected)
        self.assertIn('data-cs168-static-controls="true"', injected)
        self.assertEqual(injected.count('data-cs168-static-controls="true"'), 1)
        self.assertLess(
            injected.index('data-cs168-local-boot="true"'),
            injected.index("../cs168-local/local.css"),
        )
        self.assertLess(
            injected.index('data-cs168-static-controls="true"'),
            injected.index('Dark Mode'),
        )

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
        self.assertIn("CS168_LOCAL_STATE:", injected)
        self.assertIn("windowState.darkMode", injected)
        self.assertNotIn("let toggleDark = ()", injected)
        self.assertLess(
            injected.index('data-cs168-theme-boot="true"'),
            injected.index("cs168-local/local.css"),
        )

    def test_rewrite_theme_runtime_refreshes_existing_theme_boot_script(self):
        html = (
            '<html><head>'
            '<script data-cs168-theme-boot="true">old boot without global state</script>'
            '<noscript>old fallback</noscript>'
            '<script> let toggleDark = () => { localStorage.setItem(\'darkMode\', String(true)); }; </script>'
            '</head><body></body></html>'
        )

        rewritten = rewrite_theme_runtime(html, Path("/tmp/site/intro/intro.html"), Path("/tmp/site"))

        self.assertIn('data-cs168-theme-boot="true"', rewritten)
        self.assertIn("CS168_LOCAL_STATE:", rewritten)
        self.assertIn("windowState.darkMode", rewritten)
        self.assertNotIn("old boot without global state", rewritten)
        self.assertNotIn("old fallback", rewritten)
        self.assertNotIn("let toggleDark = ()", rewritten)

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
            self.assertIn("var controls = document.querySelector('.cs168-local-controls');", js)
            self.assertIn("button.dataset.cs168Bound = 'true';", js)
            self.assertLess(js.index("document.querySelector('.aux-nav-list')"), js.index("document.querySelector('.site-footer')"))

    def test_runtime_initializes_local_mode_before_dom_content_loaded_when_body_exists(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("var initialized = false;", js)
            self.assertIn("function init()", js)
            self.assertIn("if (document.body) {", js)
            self.assertIn("init();", js)
            self.assertIn("document.documentElement.setAttribute('data-cs168-localizing', 'ready')", js)

    def test_runtime_nav_supports_bilingual_mode(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function escapeHtml(value)", js)
            self.assertIn("mode === 'both'", js)
            self.assertIn("cs168-i18n-en", js)
            self.assertIn("cs168-i18n-zh", js)
            self.assertIn("escapeHtml(titles[original])", js)

    def test_runtime_keeps_site_title_in_english(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertNotIn(".site-title", js)
            self.assertNotIn("CS 168 教材", js)

    def test_runtime_separates_sidebar_and_in_page_toc_translation(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn(
                "document.querySelectorAll('#site-nav .nav-list-link, .breadcrumb-nav-list-item > a, .breadcrumb-nav-list-item > span')",
                js,
            )
            self.assertIn("document.querySelectorAll('.content-nav a.nav-list-link')", js)
            self.assertNotIn("document.querySelectorAll('.nav-list-link, .site-title, .breadcrumb-nav-list-item span')", js)

    def test_runtime_translates_in_page_toc_links_without_removing_anchors(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function renderInPageNav(mode, pageData)", js)
            self.assertIn("document.querySelectorAll('.content-nav a.nav-list-link')", js)
            self.assertIn("link.innerHTML = renderTranslatedHtml", js)
            self.assertIn("renderInPageNav(mode, pageData)", js)

    def test_runtime_strips_heading_anchor_before_reusing_translation_html(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function stripHeadingAnchor(html)", js)
            self.assertIn("wrapper.querySelectorAll('a.anchor-heading')", js)
            self.assertIn("var cleanZh = stripHeadingAnchor(zhHtml);", js)
            self.assertIn("var cleanHtml = stripHeadingAnchor(html);", js)
            self.assertIn("renderTranslatedHtml(link.dataset.cs168OriginalHtml, block.zh_html, mode)", js)

    def test_runtime_keeps_one_heading_anchor_in_bilingual_body_headings(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function renderBlock(el, zhHtml, mode)", js)
            self.assertIn("var cleanZh = stripHeadingAnchor(zhHtml);\n    var original", js)
            self.assertIn(
                "'</span><span class=\"cs168-i18n-line cs168-i18n-zh\">' +\n        cleanZh +\n        '</span>'",
                js,
            )

    def test_runtime_does_not_translate_in_page_toc_list_items_as_body_blocks(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("!el.closest('.content-nav')", js)

    def test_runtime_respects_saved_theme_choice_without_overriding(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function syncThemeChoice()", js)
            self.assertIn("window.CS168_THEME.apply(theme)", js)
            self.assertIn("localStorage.getItem('darkMode')", js)
            self.assertNotIn("function setDarkDefault()", js)
            self.assertNotIn("localStorage.setItem('darkMode', 'true')", js)

    def test_runtime_persists_modes_with_window_name_for_file_navigation(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("var STATE_PREFIX = 'CS168_LOCAL_STATE:'", js)
            self.assertIn("function readGlobalState()", js)
            self.assertIn("function writeGlobalState(nextState)", js)
            self.assertIn("readGlobalState().lang", js)
            self.assertIn("writeGlobalState({ lang: mode })", js)
            self.assertIn("readGlobalState().darkMode", js)

    def test_runtime_translation_lookup_handles_section_index_pages(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("function translationPaths()", js)
            self.assertIn("candidates.push(path + 'index.html');", js)
            self.assertIn("candidates.push(path.slice(0, -10) || '/');", js)
            self.assertIn("for (var index = 0; index < candidates.length; index++)", js)
            self.assertIn("if (pages[candidates[index]]) return pages[candidates[index]];", js)

    def test_runtime_prioritizes_url_mode_and_syncs_internal_links(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("var LANG_PARAM = 'cs168-lang';", js)
            self.assertIn("var THEME_PARAM = 'cs168-theme';", js)
            self.assertIn("function readUrlLanguageMode()", js)
            self.assertIn("var urlMode = readUrlLanguageMode();", js)
            self.assertLess(js.index("var urlMode = readUrlLanguageMode();"), js.index("var globalMode = readGlobalState().lang;"))
            self.assertIn("function refreshInternalLinks(mode)", js)
            self.assertIn("url.searchParams.set(LANG_PARAM, mode);", js)
            self.assertIn("url.searchParams.set(THEME_PARAM, currentTheme());", js)
            self.assertIn("document.addEventListener('click', syncClickedLinkState, true)", js)
            self.assertIn("document.documentElement.removeAttribute('data-cs168-local-fallback')", js)

    def test_runtime_marks_active_language_mode_without_extra_current_text(self):
        source = Path("site/cs168-local/localize.js").read_text(encoding="utf-8")
        generator = Path("tools/mirror_textbook.py").read_text(encoding="utf-8")
        css = Path("site/cs168-local/local.css").read_text(encoding="utf-8")

        for js in (source, generator):
            self.assertIn("button.setAttribute('aria-current', active ? 'true' : 'false')", js)
            self.assertIn("button.classList.toggle('active', active)", js)
            self.assertNotIn("data-cs168-mode-status", js)
            self.assertNotIn("function modeLabel(mode)", js)
            self.assertNotIn("cs168BaseLabel", js)
            self.assertNotIn("（当前）", js)
            self.assertNotIn("当前：", js)
        self.assertIn(".cs168-local-button.active", css)
        self.assertIn('html[data-cs168-localizing="pending"] #site-nav', css)
        self.assertIn('html:not([data-cs168-localizing="fallback"])[data-lang-mode="zh"] [data-cs168-mode="zh"]', css)
        self.assertIn("font-weight: 700", css)
        self.assertNotIn("outline:", css)
        self.assertNotIn("outline-offset", css)
        self.assertNotIn("border-color: currentColor", css)
        self.assertNotIn(".cs168-local-status", css)

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
