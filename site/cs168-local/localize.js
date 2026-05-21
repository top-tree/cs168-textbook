(function () {
  const MODE_KEY = 'cs168-local-lang';
  const DEFAULT_MODE = 'zh';

  function normalize(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function canonicalPath() {
    let path = decodeURIComponent(window.location.pathname || '/');
    const marker = '/site/';
    const markerIndex = path.indexOf(marker);
    if (markerIndex >= 0) {
      path = path.slice(markerIndex + marker.length - 1);
    }
    if (path.endsWith('/index.html')) path = path.slice(0, -10) || '/';
    if (!path.startsWith('/')) path = '/' + path;
    return path;
  }

  function pageTranslations() {
    const data = window.CS168_TRANSLATIONS || {};
    const pages = data.pages || {};
    return pages[canonicalPath()] || null;
  }

  function cache(el) {
    if (!el.dataset.cs168OriginalHtml) {
      el.dataset.cs168OriginalHtml = el.innerHTML;
      el.dataset.cs168OriginalText = normalize(el.textContent);
    }
  }

  function restoreTranslated() {
    document.querySelectorAll('[data-cs168-translated="true"]').forEach((el) => {
      el.innerHTML = el.dataset.cs168OriginalHtml || el.innerHTML;
      el.removeAttribute('data-cs168-translated');
    });
  }

  function keepAnchor(el, html) {
    const anchor = el.querySelector('.anchor-heading');
    return anchor ? anchor.outerHTML + ' ' + html : html;
  }

  function renderBlock(el, zhHtml, mode) {
    cache(el);
    const original = el.dataset.cs168OriginalHtml;
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

  function renderNav(mode) {
    const titles = (window.CS168_TRANSLATIONS || {}).nav_titles || {};
    document.querySelectorAll('.nav-list-link, .site-title, .breadcrumb-nav-list-item span').forEach((el) => {
      cache(el);
      const original = el.dataset.cs168OriginalText;
      if (mode === 'en') {
        el.innerHTML = el.dataset.cs168OriginalHtml;
      } else if (titles[original]) {
        el.textContent = titles[original];
      }
    });
  }

  function renderNotice(mode, hasTranslation) {
    const old = document.querySelector('.cs168-i18n-missing');
    if (old) old.remove();
    if (mode === 'en' || hasTranslation) return;
    const main = document.querySelector('.main-content');
    if (!main) return;
    const notice = document.createElement('div');
    notice.className = 'cs168-i18n-missing';
    notice.textContent = '此页尚未加入中文翻译，暂显示英文原文。';
    main.prepend(notice);
  }

  function setDarkDefault() {
    if (localStorage.getItem('darkMode') === null) {
      localStorage.setItem('darkMode', 'true');
    }
    document.documentElement.setAttribute('data-theme', 'dark');
    if (window.jtd && typeof window.jtd.setTheme === 'function') {
      window.jtd.setTheme('dark');
    }
  }

  function render(mode) {
    restoreTranslated();
    document.documentElement.dataset.langMode = mode;
    document.querySelectorAll('[data-cs168-mode]').forEach((button) => {
      const active = button.dataset.cs168Mode === mode;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });

    const pageData = pageTranslations();
    renderNav(mode);
    renderNotice(mode, Boolean(pageData));
    if (!pageData || mode === 'en') return;

    const candidates = Array.from(
      document.querySelectorAll('.main-content h1, .main-content h2, .main-content h3, .main-content p')
    );
    (pageData.blocks || []).forEach((block) => {
      const target = candidates.find((el) => {
        cache(el);
        return normalize(el.dataset.cs168OriginalText) === normalize(block.en);
      });
      if (target) renderBlock(target, block.zh_html, mode);
    });
  }

  function addControls() {
    if (document.querySelector('.cs168-local-controls')) return;
    const controls = document.createElement('div');
    controls.className = 'cs168-local-controls';
    controls.innerHTML =
      '<button class="cs168-local-button" type="button" data-cs168-mode="zh" aria-pressed="false">中文</button>' +
      '<button class="cs168-local-button" type="button" data-cs168-mode="en" aria-pressed="false">English</button>' +
      '<button class="cs168-local-button" type="button" data-cs168-mode="both" aria-pressed="false">中英对照</button>';

    const footer = document.querySelector('.site-footer');
    if (footer) footer.prepend(controls);
    else document.body.prepend(controls);

    controls.querySelectorAll('[data-cs168-mode]').forEach((button) => {
      button.addEventListener('click', () => {
        localStorage.setItem(MODE_KEY, button.dataset.cs168Mode);
        render(button.dataset.cs168Mode);
      });
    });
  }

  window.addEventListener('DOMContentLoaded', () => {
    setDarkDefault();
    addControls();
    render(localStorage.getItem(MODE_KEY) || DEFAULT_MODE);
  });
})();
