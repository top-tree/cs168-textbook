# CS168 Local Bilingual Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local static CS168 textbook site that preserves the upstream Just the Docs presentation, defaults to dark mode and Chinese mode, supports English and bilingual modes, and includes one fully translated sample chapter.

**Architecture:** Import the upstream Jekyll source as the base. Add a small client-side translation layer backed by Jekyll data, plus a post-build portability script that rewrites generated root-relative links so `_site/index.html` works through a local HTML entry point. Keep original Markdown and theme structure intact except for additive includes, data, JavaScript, and CSS.

**Tech Stack:** Jekyll/GitHub Pages, Just the Docs, Liquid data files, vanilla JavaScript, SCSS, Python standard-library tests and build post-processing.

---

## File Structure

- Import upstream files from `berkeley-cs168/textbook` into the repository root.
- Modify `_includes/head_custom.html` to load the language script and make dark mode default.
- Create `_includes/nav_footer_custom.html` for the sidebar language switcher while preserving the original Just the Docs footer text.
- Modify `_sass/custom/custom.scss` for language switcher and bilingual text styling.
- Create `_data/i18n.yml` for translated page blocks and navigation labels.
- Create `assets/js/cs168-i18n.js` as a Liquid-rendered translation payload.
- Create `assets/js/lang-mode.js` for mode persistence and DOM rendering.
- Create `scripts/make_portable_site.py` to rewrite generated links and create `_site/open-local.html`.
- Create `tests/test_i18n_static.py` for static framework checks.

## Task 1: Import Upstream Source

**Files:**
- Create/modify: upstream Jekyll source files in repository root
- Preserve: `docs/superpowers/specs/2026-05-21-cs168-local-bilingual-site-design.md`
- Preserve: `docs/superpowers/plans/2026-05-21-cs168-local-bilingual-site.md`

- [ ] **Step 1: Copy upstream source into the repository**

Run:

```bash
cp -R /tmp/cs168-textbook-src/textbook-main/. .
```

Expected: repository root contains `_config.yml`, `_includes/`, `_layouts/`, `_sass/`, `assets/`, `intro/`, `routing/`, `transport/`, and other upstream files.

- [ ] **Step 2: Inspect imported source**

Run:

```bash
test -f _config.yml && test -f intro/intro.md && test -f _includes/head_custom.html
```

Expected: command exits with status 0.

- [ ] **Step 3: Commit source import**

```bash
git add .
git commit -m "Import upstream CS168 textbook source"
```

## Task 2: Write Static Framework Tests

**Files:**
- Create: `tests/test_i18n_static.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_i18n_static.py`:

```python
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class I18nStaticTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_language_assets_are_wired_into_head(self):
        head = self.read("_includes/head_custom.html")
        self.assertIn("/assets/js/cs168-i18n.js", head)
        self.assertIn("/assets/js/lang-mode.js", head)
        self.assertIn("defaultDarkMode", head)

    def test_sidebar_language_switcher_exists(self):
        switcher = self.read("_includes/nav_footer_custom.html")
        self.assertIn('data-lang-mode="zh"', switcher)
        self.assertIn('data-lang-mode="en"', switcher)
        self.assertIn('data-lang-mode="both"', switcher)

    def test_intro_translation_data_has_sample_chapter(self):
        data = self.read("_data/i18n.yml")
        self.assertIn("/intro/intro/", data)
        self.assertIn("互联网(Internet)", data)
        self.assertIn("协议(protocols)", data)
        self.assertGreaterEqual(data.count("zh_html:"), 18)

    def test_language_runtime_supports_required_modes(self):
        runtime = self.read("assets/js/lang-mode.js")
        self.assertIn("const DEFAULT_MODE = 'zh'", runtime)
        self.assertRegex(runtime, re.compile(r"case ['\"]en['\"]"))
        self.assertRegex(runtime, re.compile(r"case ['\"]both['\"]"))
        self.assertRegex(runtime, re.compile(r"case ['\"]zh['\"]"))

    def test_portable_site_rewriter_creates_clickable_entry(self):
        script = self.read("scripts/make_portable_site.py")
        self.assertIn("open-local.html", script)
        self.assertIn("href", script)
        self.assertIn("src", script)
        self.assertIn("relative_to_html", script)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_i18n_static
```

Expected: FAIL because multilingual files and wiring do not exist yet.

## Task 3: Add Language Data And Runtime

**Files:**
- Create: `_data/i18n.yml`
- Create: `assets/js/cs168-i18n.js`
- Create: `assets/js/lang-mode.js`

- [ ] **Step 1: Add translation data**

Create `_data/i18n.yml` with title translations and block translations for `/` and `/intro/intro/`. The `/intro/intro/` block must include every heading and paragraph from `intro/intro.md`, with Chinese phrasing that is readable and technically precise.

- [ ] **Step 2: Add Liquid-rendered translation payload**

Create `assets/js/cs168-i18n.js`:

```javascript
---
---
window.CS168_I18N = {{ site.data.i18n | jsonify }};
```

- [ ] **Step 3: Add language runtime**

Create `assets/js/lang-mode.js` with these exported behaviors in an immediately invoked function:

```javascript
(function () {
  const STORAGE_KEY = 'cs168LangMode';
  const DEFAULT_MODE = 'zh';

  function normalizeText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function pageKey() {
    let path = window.location.pathname;
    if (path.endsWith('/index.html')) path = path.slice(0, -10) || '/';
    if (!path.endsWith('/')) path += '/';
    return path;
  }

  function currentMode() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored || DEFAULT_MODE;
  }

  function setMode(mode) {
    localStorage.setItem(STORAGE_KEY, mode);
    render(mode);
  }

  function translationsForPage() {
    const data = window.CS168_I18N || {};
    const pages = data.pages || {};
    return pages[pageKey()] || pages[decodeURIComponent(pageKey())] || null;
  }

  function cacheOriginal(el) {
    if (!el.dataset.cs168OriginalHtml) {
      el.dataset.cs168OriginalHtml = el.innerHTML;
      el.dataset.cs168OriginalText = normalizeText(el.textContent);
    }
  }

  function resetTranslatedElements() {
    document.querySelectorAll('[data-cs168Translated="true"]').forEach((el) => {
      el.innerHTML = el.dataset.cs168OriginalHtml || el.innerHTML;
      el.removeAttribute('data-cs168Translated');
    });
  }

  function renderBlock(el, zhHtml, mode) {
    cacheOriginal(el);
    const original = el.dataset.cs168OriginalHtml;
    el.dataset.cs168Translated = 'true';

    switch (mode) {
      case 'en':
        el.innerHTML = original;
        break;
      case 'both':
        el.innerHTML =
          '<span class="cs168-i18n-line cs168-i18n-en">' +
          original +
          '</span><span class="cs168-i18n-line cs168-i18n-zh">' +
          zhHtml +
          '</span>';
        break;
      case 'zh':
      default:
        el.innerHTML = zhHtml;
        break;
    }
  }

  function renderNav(mode) {
    const titles = ((window.CS168_I18N || {}).nav_titles || {});
    document.querySelectorAll('.nav-list-link, .site-title').forEach((link) => {
      cacheOriginal(link);
      const original = link.dataset.cs168OriginalText;
      if (mode === 'en') {
        link.innerHTML = link.dataset.cs168OriginalHtml;
      } else if (titles[original]) {
        link.textContent = titles[original];
      }
    });
  }

  function renderMissingNotice(mode, pageData) {
    const existing = document.querySelector('.cs168-i18n-missing');
    if (existing) existing.remove();
    if (mode === 'en' || pageData) return;
    const main = document.querySelector('.main-content');
    if (!main) return;
    const notice = document.createElement('div');
    notice.className = 'cs168-i18n-missing';
    notice.textContent = '此页尚未加入中文翻译，暂显示英文原文。';
    main.prepend(notice);
  }

  function render(mode) {
    resetTranslatedElements();
    document.documentElement.dataset.langMode = mode;
    document.querySelectorAll('[data-lang-mode]').forEach((button) => {
      const active = button.dataset.langMode === mode;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });

    const pageData = translationsForPage();
    renderNav(mode);
    renderMissingNotice(mode, pageData);

    if (!pageData || mode === 'en') return;
    const blocks = pageData.blocks || [];
    const candidates = Array.from(
      document.querySelectorAll('.main-content h1, .main-content h2, .main-content h3, .main-content p'),
    );

    blocks.forEach((block) => {
      const target = candidates.find(
        (el) => normalizeText(el.dataset.cs168OriginalText || el.textContent) === normalizeText(block.en),
      );
      if (target) renderBlock(target, block.zh_html, mode);
    });
  }

  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-lang-mode]').forEach((button) => {
      button.addEventListener('click', () => setMode(button.dataset.langMode));
    });
    render(currentMode());
  });
})();
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m unittest tests.test_i18n_static
```

Expected: remaining failures only mention missing include/CSS/portable script wiring.

## Task 4: Wire Theme Includes And Styles

**Files:**
- Modify: `_includes/head_custom.html`
- Create: `_includes/nav_footer_custom.html`
- Modify: `_sass/custom/custom.scss`

- [ ] **Step 1: Update dark-mode and script wiring in `_includes/head_custom.html`**

Replace the existing dark-mode script with one that finds the `Dark Mode` button by text, defaults to dark mode when no preference exists, and loads the language scripts:

```html
<script src="{{ '/assets/js/cs168-i18n.js' | relative_url }}"></script>
<script src="{{ '/assets/js/lang-mode.js' | relative_url }}" defer></script>
```

The script must include a `defaultDarkMode` variable and set `darkMode` to `true` on first load.

- [ ] **Step 2: Add sidebar language controls**

Create `_includes/nav_footer_custom.html`:

```html
<footer class="site-footer cs168-local-footer">
  <div class="cs168-lang-switcher" aria-label="Language mode">
    <button type="button" class="cs168-lang-button" data-lang-mode="zh" aria-pressed="false">
      中文
    </button>
    <button type="button" class="cs168-lang-button" data-lang-mode="en" aria-pressed="false">
      English
    </button>
    <button type="button" class="cs168-lang-button" data-lang-mode="both" aria-pressed="false">
      中英对照
    </button>
  </div>
  <div>
    This site uses
    <a href="https://github.com/just-the-docs/just-the-docs">Just the Docs</a>,
    a documentation theme for Jekyll.
  </div>
</footer>
```

- [ ] **Step 3: Add styles**

Append scoped styles to `_sass/custom/custom.scss` for `.cs168-lang-switcher`, `.cs168-lang-button`, `.cs168-i18n-line`, `.cs168-i18n-zh`, and `.cs168-i18n-missing`.

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m unittest tests.test_i18n_static
```

Expected: only portable-site script test still fails.

## Task 5: Add Portable Static Build Script

**Files:**
- Create: `scripts/make_portable_site.py`

- [ ] **Step 1: Add post-build script**

Create `scripts/make_portable_site.py` that:

- Walks `_site/**/*.html`.
- Rewrites `href="/..."`, `src="/..."`, and `action="/..."` to paths relative to the current HTML file.
- Converts internal directory links such as `/intro/intro/` to `intro/intro/index.html` with the right relative prefix.
- Leaves external links, anchors, `mailto:`, `tel:`, and protocol-relative URLs unchanged.
- Creates `_site/open-local.html` that redirects to `index.html` and also contains a clickable fallback link.

- [ ] **Step 2: Run tests**

Run:

```bash
python3 -m unittest tests.test_i18n_static
```

Expected: all tests pass.

## Task 6: Build And Verify Site

**Files:**
- Generated: `_site/`

- [ ] **Step 1: Install Ruby dependencies if needed**

Run:

```bash
bundle install
```

Expected: dependencies install or are already available.

- [ ] **Step 2: Build with Jekyll**

Run:

```bash
bundle exec jekyll build
```

Expected: generated site appears under `_site/` with no build errors.

- [ ] **Step 3: Make generated site portable**

Run:

```bash
python3 scripts/make_portable_site.py
```

Expected: `_site/open-local.html` exists and generated HTML links are relative.

- [ ] **Step 4: Run test suite again**

Run:

```bash
python3 -m unittest tests.test_i18n_static
```

Expected: all tests pass.

- [ ] **Step 5: Start a local server for browser verification**

Run:

```bash
python3 -m http.server 8765 --directory _site
```

Expected: site is available at `http://localhost:8765/open-local.html`.

- [ ] **Step 6: Browser-check required behavior**

Open `http://localhost:8765/open-local.html` and verify:

- First load uses dark mode.
- First load uses Chinese mode.
- `English` restores original English content.
- `中英对照` shows English above Chinese.
- Sidebar navigation still works.
- `Introduction / Introduction to the Internet` has a polished Chinese translation.

## Task 7: Commit Implementation

**Files:**
- All implementation and test files

- [ ] **Step 1: Review git diff**

Run:

```bash
git status --short
git diff -- _includes/head_custom.html _includes/nav_footer_custom.html _sass/custom/custom.scss _data/i18n.yml assets/js/cs168-i18n.js assets/js/lang-mode.js scripts/make_portable_site.py tests/test_i18n_static.py
```

Expected: diff shows only source import plus scoped multilingual additions.

- [ ] **Step 2: Commit implementation**

```bash
git add .
git commit -m "Add local bilingual CS168 site framework"
```
