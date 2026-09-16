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
    { id: 'aurora', label: '오로라' },
    { id: 'glass', label: '글래스모피즘' },
    { id: 'apple', label: '애플 리퀴드 글래스' },
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

  // ── 리퀴드 글래스(애플 테마) 가장자리 굴절 필터 ──────────────────────────
  // 패널 뒷배경을 가장자리에서만 렌즈처럼 휘게 하는 SVG displacement 필터.
  // 변위 맵: R채널=가로 변위, G채널=세로 변위. 중앙은 0.5(변위 없음)로 평평하고
  // 바깥 14% 구간에서만 0→1로 굴절이 걸려 "두꺼운 유리의 모서리 굴절"이 된다.
  // backdrop-filter: url(#...)은 Chromium 계열에서만 동작하므로 lg-refract
  // 클래스로 표시해 두고, 그 외 브라우저는 CSS 림/블러만으로 표현한다.
  function initLiquidGlass() {
    if (document.getElementById('knpuLGDefs')) return;

    var MAP =
      "data:image/svg+xml;utf8," + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
        + '<linearGradient id="gx" x1="0" y1="0" x2="1" y2="0">'
        + '<stop offset="0" stop-color="#000000"/><stop offset="0.14" stop-color="#800000"/>'
        + '<stop offset="0.86" stop-color="#800000"/><stop offset="1" stop-color="#ff0000"/>'
        + '</linearGradient>'
        + '<linearGradient id="gy" x1="0" y1="0" x2="0" y2="1">'
        + '<stop offset="0" stop-color="#000000"/><stop offset="0.14" stop-color="#008000"/>'
        + '<stop offset="0.86" stop-color="#008000"/><stop offset="1" stop-color="#00ff00"/>'
        + '</linearGradient>'
        + '<rect width="64" height="64" fill="url(#gx)"/>'
        + '<rect width="64" height="64" fill="url(#gy)" style="mix-blend-mode:screen"/>'
        + '</svg>');

    var holder = document.createElement('div');
    holder.id = 'knpuLGDefs';
    holder.setAttribute('aria-hidden', 'true');
    holder.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;pointer-events:none';
    holder.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0">'
      + '<filter id="knpuLG" x="0" y="0" width="100%" height="100%" primitiveUnits="objectBoundingBox" color-interpolation-filters="sRGB">'
      + '<feImage href="' + MAP + '" x="0" y="0" width="1" height="1" preserveAspectRatio="none" result="map"/>'
      + '<feDisplacementMap in="SourceGraphic" in2="map" scale="0.5" xChannelSelector="R" yChannelSelector="G"/>'
      + '</filter>'
      + '</svg>';
    document.body.appendChild(holder);

    // Chromium 계열에서만 굴절 활성화 (Safari/Firefox는 backdrop-filter: url() 미지원)
    var isChromium = false;
    try {
      if (navigator.userAgentData && navigator.userAgentData.brands) {
        isChromium = navigator.userAgentData.brands.some(function (b) {
          return /Chromium/i.test(b.brand);
        });
      } else {
        // Chrome/Edge/Opera/Whale 등 Chromium 파생은 모두 "Chrome/"을 포함하고,
        // Safari·Firefox UA에는 없다.
        isChromium = /Chrome\//.test(navigator.userAgent);
      }
    } catch (e) { /* noop */ }
    if (isChromium) document.documentElement.classList.add('lg-refract');
  }

  function init() {
    initLiquidGlass();
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

})();
