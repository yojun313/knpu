// ============================================================================
// 공통 테마 시스템 (statistics / kemkim / network 공용)
// - <html data-ui-theme="glass|neu|mesh">를 켜고 끄는 설정 모달을 #themeSettingsBtn
//   옆에 붙여준다. 실제 배색/질감은 theme.css가 이 속성 값에 따라 담당한다.
// - domain=.knpu.re.kr 쿠키(ui_theme_style)에 저장한다. localStorage는 서브도메인마다
//   따로 격리되어 사이트 간에 공유되지 않으므로, 로그인 세션 쿠키(homepage/server의
//   COOKIE_DOMAIN)와 같은 방식으로 최상위 도메인 쿠키를 써서 모든 KNPU 사이트가 같은
//   테마 값을 읽고 쓰게 한다. 각 페이지 <head>의 인라인 스니펫도 이 쿠키를 읽어
//   첫 렌더 전에 미리 적용해 테마가 바뀌는 깜빡임(FOUC)을 막는다.
// ============================================================================
(function () {
  'use strict';

  var COOKIE_KEY = 'ui_theme_style';
  var MODE_COOKIE_KEY = 'ui_theme_mode';
  var NAV_COOKIE_KEY = 'ui_nav_visibility';
  var THEMES = [
    { id: 'default', label: '기본' },
    { id: 'glass', label: '글래스모피즘' },
    { id: 'apple', label: '애플 글래스' },
    { id: 'neu', label: '뉴모피즘' },
    { id: 'mesh', label: '그라디언트 메시' },
  ];

  function cookieDomainAttr() {
    return /(^|\.)knpu\.re\.kr$/.test(location.hostname) ? '; domain=.knpu.re.kr' : '';
  }

  function setCookie(key, value) {
    try {
      var maxAge = 60 * 60 * 24 * 365;
      document.cookie = key + '=' + encodeURIComponent(value) +
        '; path=/; max-age=' + maxAge + '; samesite=lax' +
        cookieDomainAttr() + (location.protocol === 'https:' ? '; secure' : '');
    } catch (e) { /* noop */ }
  }

  function getCookie(key) {
    try {
      var m = document.cookie.match(new RegExp('(?:^|; )' + key + '=([^;]*)'));
      return m ? decodeURIComponent(m[1]) : null;
    } catch (e) { return null; }
  }

  function currentTheme() { return getCookie(COOKIE_KEY) || 'default'; }

  function applyTheme(id) {
    if (id === 'default') document.documentElement.removeAttribute('data-ui-theme');
    else document.documentElement.setAttribute('data-ui-theme', id);
    setCookie(COOKIE_KEY, id);
  }

  function currentMode() { return getCookie(MODE_COOKIE_KEY) || 'light'; }

  function applyMode(mode) {
    if (mode === 'dark') document.documentElement.setAttribute('data-ui-theme-mode', 'dark');
    else document.documentElement.removeAttribute('data-ui-theme-mode');
    setCookie(MODE_COOKIE_KEY, mode);
    // 각 앱(statistics/kemkim/network)이 자체 다크모드 버튼 없이도 캔버스/차트처럼
    // CSS만으로는 못 바꾸는 JS 렌더링 색상을 이 이벤트를 듣고 즉시 다시 그릴 수 있게 한다.
    try {
      window.dispatchEvent(new CustomEvent('knpu-ui-theme-mode-change', { detail: { mode: mode } }));
    } catch (e) { /* noop */ }
  }

  function currentNav() { return getCookie(NAV_COOKIE_KEY) || 'show'; }

  function applyNav(mode) {
    if (mode === 'autohide') document.documentElement.setAttribute('data-ui-nav', 'autohide');
    else document.documentElement.removeAttribute('data-ui-nav');
    setCookie(NAV_COOKIE_KEY, mode);
  }

  function buildModal() {
    var overlay = document.createElement('div');
    overlay.id = 'themeModalOverlay';
    overlay.className = 'theme-modal-overlay';
    overlay.hidden = true;

    var optionsHtml = THEMES.map(function (t) {
      return (
        '<button type="button" class="theme-option" data-theme="' + t.id + '">'
        + '<span class="theme-swatch theme-swatch-' + t.id + '"><span></span><span></span><span></span></span>'
        + '<span class="theme-option-label"><span class="theme-option-check">✓</span>' + t.label + '</span>'
        + '</button>'
      );
    }).join('');

    overlay.innerHTML =
      '<div class="theme-modal" role="dialog" aria-modal="true" aria-label="테마 설정">'
      + '<div class="theme-modal-head">'
      + '<div><h3>테마 설정</h3><p class="theme-modal-sub">원하는 테마를 골라보세요. 모든 KNPU 사이트에 동일하게 적용됩니다.</p></div>'
      + '<button type="button" class="theme-modal-close" aria-label="닫기">&times;</button>'
      + '</div>'
      + '<div class="theme-modal-body">' + optionsHtml + '</div>'
      + '<div class="theme-mode-row"><span>다크 모드</span>'
      + '<button type="button" class="theme-mode-switch" id="themeModeSwitch" aria-label="다크 모드 전환"></button></div>'
      + '<div class="theme-nav-row"><span>상단 네비게이션 바 자동 숨김 (마우스를 올리면 표시)</span>'
      + '<button type="button" class="theme-mode-switch" id="themeNavSwitch" aria-label="네비게이션 바 자동 숨김 전환"></button></div>'
      + '</div>';

    document.body.appendChild(overlay);
    return overlay;
  }

  function markSelected(overlay) {
    var active = currentTheme();
    overlay.querySelectorAll('.theme-option').forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-theme') === active);
    });
    overlay.querySelector('#themeModeSwitch').classList.toggle('on', currentMode() === 'dark');
    overlay.querySelector('#themeNavSwitch').classList.toggle('on', currentNav() === 'autohide');
  }

  function init() {
    var btn = document.getElementById('themeSettingsBtn');
    if (!btn) return;

    var overlay = buildModal();

    function open() { markSelected(overlay); overlay.hidden = false; }
    function close() { overlay.hidden = true; }

    btn.addEventListener('click', open);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    overlay.querySelector('.theme-modal-close').addEventListener('click', close);
    overlay.querySelectorAll('.theme-option').forEach(function (opt) {
      opt.addEventListener('click', function () {
        applyTheme(opt.getAttribute('data-theme'));
        markSelected(overlay);
        close();
      });
    });
    overlay.querySelector('#themeModeSwitch').addEventListener('click', function () {
      applyMode(currentMode() === 'dark' ? 'light' : 'dark');
      markSelected(overlay);
    });
    overlay.querySelector('#themeNavSwitch').addEventListener('click', function () {
      applyNav(currentNav() === 'autohide' ? 'show' : 'autohide');
      markSelected(overlay);
    });
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !overlay.hidden) close();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ----------------------------------------------------------------------
  // dev 서브도메인(dev-xxx.knpu.re.kr)에서 보고 있을 때, 상단 네비게이션의
  // 다른 서비스 링크(MANAGER/NETWORK/...)도 같은 dev 쪽으로 데려가 준다.
  // 로그인/홈(knpu.re.kr)은 dev/prod 공통이라 건드리지 않는다.
  // ----------------------------------------------------------------------
  var CROSS_SERVICE_SUBDOMAINS = [
    'manager', 'crawler', 'network', 'kemkim', 'statistics', 'ahp', 'dashboard',
  ];

  function fixCrossServiceNavLinks() {
    var m = /^dev-([a-z0-9.-]+\.knpu\.re\.kr)$/i.exec(location.hostname);
    if (!m) return;
    document.querySelectorAll('a[href^="https://"]').forEach(function (a) {
      var url;
      try { url = new URL(a.getAttribute('href'), location.href); } catch (e) { return; }
      var hm = /^([a-z0-9-]+)\.knpu\.re\.kr$/i.exec(url.hostname);
      if (!hm) return;
      var sub = hm[1].toLowerCase();
      if (CROSS_SERVICE_SUBDOMAINS.indexOf(sub) === -1) return;
      url.hostname = 'dev-' + sub + '.knpu.re.kr';
      a.setAttribute('href', url.toString());
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fixCrossServiceNavLinks);
  } else {
    fixCrossServiceNavLinks();
  }
})();
