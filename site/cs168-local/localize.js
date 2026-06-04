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
    document.documentElement.removeAttribute('data-cs168-local-fallback');
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