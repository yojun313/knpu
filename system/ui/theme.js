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
  var CHATBOT_COOKIE_KEY = 'ui_chatbot';
  var THEMES = [
    { id: 'default', label: '기본 테마' },
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

  // 설정 창: 왼쪽 사이드바(섹션) + 오른쪽 내용. 모든 KNPU 사이트에서 같은 창이 열린다.
  var SECTIONS = [
    { id: 'appearance', label: '테마', icon: '<path d="M12 3a9 9 0 1 0 9 9c0-.5-.4-.9-.9-.9h-3.6a2.5 2.5 0 0 1-1.8-4.3l.7-.7A1.8 1.8 0 0 0 14.2 3.3 9 9 0 0 0 12 3z"/><circle cx="7.5" cy="10.5" r="1"/><circle cx="12" cy="7.5" r="1"/>' },
    { id: 'ai', label: 'AI 모델', icon: '<path d="M12 2l2 5.5L19.5 9 14 11l-2 5.5L10 11 4.5 9 10 7.5z"/><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>' },
    { id: 'labapi', label: '로컬 AI API', icon: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4M7 9l2 2-2 2M12 13h4"/>' },
    { id: 'chatbot', label: '챗봇', icon: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>' },
    { id: 'account', label: '내 계정', icon: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>' },
    { id: 'links', label: '바로가기', icon: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>' },
  ];
  function svgIcon(d) { return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>'; }
  function switchRow(id, title, desc) {
    return '<div class="st-row"><div><b>' + title + '</b>' + (desc ? '<span>' + desc + '</span>' : '') + '</div>'
      + '<button type="button" class="theme-mode-switch" id="' + id + '" aria-label="' + title + '"></button></div>';
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
    var nav = SECTIONS.map(function (sec) {
      return '<button type="button" class="st-nav-item" data-pane="' + sec.id + '">' + svgIcon(sec.icon) + '<span>' + sec.label + '</span></button>';
    }).join('');

    overlay.innerHTML =
      '<div class="theme-modal st-modal" role="dialog" aria-modal="true" aria-label="설정">'
      + '<aside class="st-side"><div class="st-side-title"><h3>설정</h3><p>모든 KNPU 사이트에 똑같이 적용돼요</p></div>'
      + '<nav class="st-nav">' + nav + '</nav></aside>'
      + '<div class="st-main">'
      + '<div class="st-head"><h4 id="stTitle">테마</h4><button type="button" class="theme-modal-close" aria-label="닫기">&times;</button></div>'
      + '<div class="st-body">'
      // 테마
      + '<section class="st-pane" data-pane="appearance">'
      + '<div class="st-group"><div class="st-group-title">테마 스타일</div><div class="theme-modal-body">' + optionsHtml + '</div></div>'
      + '<div class="st-group"><div class="st-group-title">화면</div>'
      + switchRow('themeModeSwitch', '다크 모드', '어두운 배경으로 바꿉니다')
      + switchRow('themeNavSwitch', '상단 네비게이션 바 자동 숨김', '마우스를 화면 위쪽에 올리면 나타납니다')
      + '</div></section>'
      // AI 모델
      + '<section class="st-pane" data-pane="ai">'
      + '<section class="llm-settings" id="llmSettings" hidden>'
      + '<div class="llm-head"><span class="theme-modal-sub">AI 해석·요약·챗봇에 쓸 모델을 고릅니다. 로컬 LLM은 연구실 서버에서 무료로 동작하고, 내 GPT API를 연결하면 로컬이 실패할 때나 항상 GPT를 쓸 수 있어요.</span></div>'
      + '<div class="llm-modes" id="llmModes"></div>'
      + '<div class="llm-openai" id="llmOpenai">'
      + '<label class="llm-field"><span>OpenAI API 키</span><input type="password" id="llmKey" autocomplete="off" placeholder="sk-..."><small id="llmKeyHint"></small></label>'
      + '<div class="llm-row"><label class="llm-field"><span>모델</span><select id="llmModel"></select></label>'
      + '<label class="llm-field"><span>월 사용 한도 (USD)</span><input type="number" id="llmLimit" min="0" max="1000" step="0.5"></label></div>'
      + '<div class="llm-usage" id="llmUsage"></div>'
      + '</div>'
      + '<div class="llm-actions"><span class="llm-status" id="llmStatus"></span><button type="button" class="llm-save" id="llmSave">저장</button></div>'
      + '</section>'
      + '<div class="st-empty" id="llmLogin" hidden>로그인하면 AI 모델을 고를 수 있어요.</div>'
      + '</section>'
      // 로컬 AI API
      + '<section class="st-pane" data-pane="labapi"><div id="labApi"><div class="st-empty">불러오는 중…</div></div></section>'
      // 챗봇
      + '<section class="st-pane" data-pane="chatbot">'
      + '<div class="st-group"><div class="st-group-title">AI 챗봇</div>'
      + switchRow('themeChatbotSwitch', 'AI 챗봇 버튼 표시', '모든 사이트 오른쪽 아래의 동그라미 버튼')
      + '<div class="st-row"><div><b>탭 전체로 열기</b><span>챗봇을 브라우저 탭 하나에 크게 띄웁니다</span></div><a class="st-btn" href="/shared-ui/chatbot.html" target="_blank" rel="noopener">새 탭에서 열기</a></div>'
      + '<div class="st-row"><div><b>이 브라우저의 비로그인 대화 지우기</b><span>로그인한 대화는 계정에 저장되며 챗봇의 대화 목록에서 지울 수 있어요</span></div><button type="button" class="st-btn" id="stClearAnon">지우기</button></div>'
      + '</div>'
      + '<p class="st-note">홈페이지에서는 외부인용 "홈페이지 안내"와 구성원용을 전환할 수 있고, 다른 사이트에서는 로그인한 구성원용만 보입니다.</p>'
      + '</section>'
      // 내 계정
      + '<section class="st-pane" data-pane="account"><div id="stAccount"><div class="st-empty">불러오는 중…</div></div></section>'
      // 바로가기
      + '<section class="st-pane" data-pane="links"><div id="stLinks"></div></section>'
      + '</div></div></div>';

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
    overlay.querySelector('#themeChatbotSwitch').classList.toggle('on', getCookie(CHATBOT_COOKIE_KEY) !== 'off');
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

  // ── 사용자별 AI 모델 설정 (로컬 LLM / 내 GPT API · 월 한도 · 사용량) ──────────
  var llmState = null;
  function llmEsc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function llmMode() { var el = document.querySelector('#llmModes input:checked'); return el ? el.value : 'local'; }
  function renderLlmSettings(st) {
    llmState = st;
    var sec = document.getElementById('llmSettings');
    sec.hidden = false;
    document.getElementById('llmModes').innerHTML = Object.keys(st.modes).map(function (k) {
      return '<label class="llm-mode"><input type="radio" name="llmMode" value="' + k + '"' + (st.mode === k ? ' checked' : '') + '>'
        + '<span>' + llmEsc(st.modes[k]) + (k === 'local' ? ' <em>(' + llmEsc(st.local_model) + ')</em>' : '') + '</span></label>';
    }).join('');
    document.getElementById('llmModel').innerHTML = st.models.map(function (m) {
      return '<option value="' + llmEsc(m.id) + '"' + (m.id === st.model ? ' selected' : '') + '>' + llmEsc(m.id)
        + ' ($' + m.input_per_1m + ' / $' + m.output_per_1m + ')</option>';
    }).join('');
    document.getElementById('llmLimit').value = st.monthly_limit_usd;
    document.getElementById('llmKey').value = '';
    document.getElementById('llmKeyHint').innerHTML = st.has_key
      ? '저장된 키: ••••' + llmEsc(st.key_hint) + ' · 새로 입력하면 교체됩니다 <button type="button" class="llm-link" id="llmClearKey">키 삭제</button>'
      : '키는 서버에 암호화해 저장하며 다시 보여 주지 않습니다.';
    var u = st.usage, limit = st.monthly_limit_usd || 0;
    var pct = limit > 0 ? Math.min(100, u.cost_usd / limit * 100) : 0;
    document.getElementById('llmUsage').innerHTML =
      '<div class="llm-usage-head"><span>' + llmEsc(u.month) + ' 사용량 (추정)</span><b>$' + u.cost_usd.toFixed(4) + ' / $' + Number(limit).toFixed(2) + '</b></div>'
      + '<div class="llm-bar"><span style="width:' + pct + '%"' + (pct >= 90 ? ' class="warn"' : '') + '></span></div>'
      + '<div class="llm-usage-meta">호출 ' + u.calls + '회 · 입력 ' + u.input_tokens.toLocaleString() + ' / 출력 ' + u.output_tokens.toLocaleString() + ' 토큰 · 남은 한도 $' + u.remaining_usd.toFixed(2) + '</div>'
      + (u.recent && u.recent.length ? '<details class="llm-recent"><summary>최근 사용 내역</summary><ul>' + u.recent.map(function (r) {
          return '<li><span>' + llmEsc((r.at || '').replace('T', ' ').slice(0, 16)) + ' · ' + llmEsc(r.purpose || r.model) + '</span><b>$' + Number(r.cost_usd).toFixed(4) + '</b></li>';
        }).join('') + '</ul></details>' : '')
      + '<div class="llm-usage-meta">토큰 수 × 모델 요금으로 계산한 추정치입니다. 실제 청구액은 OpenAI 대시보드에서 확인하세요.</div>';
    syncLlmMode();
    var clear = document.getElementById('llmClearKey');
    if (clear) clear.addEventListener('click', function () { saveLlmSettings({ clear_key: true }); });
  }
  function syncLlmMode() {
    document.getElementById('llmOpenai').hidden = llmMode() === 'local' && !(llmState && llmState.has_key);
  }
  function llmSetStatus(text, kind) {
    var el = document.getElementById('llmStatus');
    el.textContent = text || ''; el.className = 'llm-status' + (kind ? ' ' + kind : '');
  }
  function loadLlmSettings() {
    var sec = document.getElementById('llmSettings');
    if (!sec) return;
    fetch('/api/llm-settings', { credentials: 'same-origin' }).then(function (res) {
      if (!res.ok) throw new Error('unavailable');
      return res.json();
    }).then(function (st) { var l = document.getElementById('llmLogin'); if (l) l.hidden = true; renderLlmSettings(st); })
      .catch(function () { sec.hidden = true; var l = document.getElementById('llmLogin'); if (l) { l.hidden = false; l.innerHTML = loginBox('로그인하면 AI 모델을 고를 수 있어요.').replace(/^<div class="st-empty">|<\/div>$/g, ''); } });
  }
  function saveLlmSettings(extra) {
    var body = {
      mode: llmMode(),
      model: document.getElementById('llmModel').value,
      monthly_limit_usd: parseFloat(document.getElementById('llmLimit').value || '0'),
      api_key: document.getElementById('llmKey').value.trim(),
    };
    Object.keys(extra || {}).forEach(function (k) { body[k] = extra[k]; });
    var btn = document.getElementById('llmSave');
    btn.disabled = true;
    llmSetStatus(body.api_key ? 'API 키를 확인하는 중...' : '저장하는 중...');
    fetch('/api/llm-settings', {
      method: 'PUT', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }).then(function (res) {
      return res.text().then(function (t) {
        var j = null; try { j = JSON.parse(t); } catch (e) { }
        if (!res.ok) throw new Error((j && j.detail) || ('저장하지 못했습니다 (HTTP ' + res.status + ')'));
        return j;
      });
    }).then(function (st) {
      btn.disabled = false;
      renderLlmSettings(st);
      llmSetStatus('저장했습니다.', 'ok');
    }).catch(function (err) {
      btn.disabled = false;
      llmSetStatus(err.message, 'err');
    });
  }


  // ── 설정 창 섹션 전환 ───────────────────────────────────────────────────────
  var PANE_KEY = 'knpu_settings_pane';
  function stEsc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function stFetch(url, opts) {
    return fetch(url, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opts || {})).then(function (r) {
      return r.text().then(function (t) {
        var j = null; try { j = JSON.parse(t); } catch (e) { }
        if (!r.ok) { var err = new Error((j && typeof j.detail === 'string' && j.detail) || ('HTTP ' + r.status)); err.status = r.status; throw err; }
        return j || {};
      });
    });
  }
  function homeOrigin() {
    var s = window.KNPU_SERVICES && KNPU_SERVICES.services && KNPU_SERVICES.services.homepage;
    return 'https://' + ((s && s.prodDomain) || 'knpu.re.kr');
  }
  function loginHref() {
    try { if (window.KNPU && KNPU.loginUrl) return KNPU.loginUrl(); } catch (e) { }
    return homeOrigin() + '/login?redirect=' + encodeURIComponent(location.href);
  }
  function loginBox(text) {
    return '<div class="st-empty">' + stEsc(text) + '<br><a class="st-btn primary" href="' + stEsc(loginHref()) + '">로그인</a></div>';
  }
  function copyText(text, btn) {
    function done() { var t = btn.textContent; btn.textContent = '복사됨'; setTimeout(function () { btn.textContent = t; }, 1200); }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () { });
    else { var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); done(); } catch (e) { } ta.remove(); }
  }

  function showPane(overlay, id) {
    if (!SECTIONS.some(function (x) { return x.id === id; })) id = 'appearance';
    try { localStorage.setItem(PANE_KEY, id); } catch (e) { }
    overlay.querySelectorAll('.st-nav-item').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-pane') === id); });
    overlay.querySelectorAll('.st-pane').forEach(function (p) { p.hidden = p.getAttribute('data-pane') !== id; });
    overlay.querySelector('#stTitle').textContent = SECTIONS.filter(function (x) { return x.id === id; })[0].label;
    overlay.querySelector('.st-body').scrollTop = 0;
    if (id === 'ai') loadLlmSettings();
    if (id === 'labapi') loadLabApi();
    if (id === 'account') loadAccount();
    if (id === 'links') renderLinks();
  }

  // ── 로컬 AI API 안내 (토큰은 .env 의 LAB_LLM_PUBLIC_TOKEN, 로그인한 구성원만) ──────
  function loadLabApi() {
    var host = document.getElementById('labApi');
    stFetch('/shared-ui/account/api/lab-llm').then(function (info) {
      var base = info.base_url, token = info.token || '';
      var tokenShown = token ? token : '(서버 .env 에 LAB_LLM_PUBLIC_TOKEN 이 아직 없습니다)';
      var model = 'MODEL_ID';
      var curl = 'curl ' + base + '/chat/completions \\\n  -H "Authorization: Bearer ' + (token || 'TOKEN') + '" \\\n  -H "Content-Type: application/json" \\\n  -d \'{"model": "' + model + '", "messages": [{"role": "user", "content": "안녕하세요"}]}\'';
      var py = 'from openai import OpenAI\n\nclient = OpenAI(base_url="' + base + '", api_key="' + (token || 'TOKEN') + '")\nmodel = client.models.list().data[0].id  # 서버에 올라간 모델 자동 선택\nres = client.chat.completions.create(\n    model=model,\n    messages=[{"role": "user", "content": "안녕하세요"}],\n)\nprint(res.choices[0].message.content)';
      var js = 'const res = await fetch("' + base + '/chat/completions", {\n  method: "POST",\n  headers: { "Authorization": "Bearer ' + (token || 'TOKEN') + '", "Content-Type": "application/json" },\n  body: JSON.stringify({ model: "' + model + '", messages: [{ role: "user", content: "안녕하세요" }] }),\n});\nconsole.log((await res.json()).choices[0].message.content);';
      host.innerHTML =
        '<p class="st-note">연구실 GPU 서버의 로컬 LLM을 <b>OpenAI API 형식</b>으로 쓸 수 있어요. OpenAI SDK·LangChain 등에서 주소와 토큰만 바꾸면 됩니다. 비용은 들지 않지만 연구실 공용 자원이니 대량 요청은 자제해 주세요.</p>'
        + '<div class="st-group"><div class="st-group-title">접속 정보</div>'
        + '<div class="st-kv"><span>Base URL</span><code id="labBase">' + stEsc(base) + '</code><button type="button" class="st-btn sm" data-copy="base">복사</button></div>'
        + '<div class="st-kv"><span>토큰</span><code id="labToken" class="st-secret">' + stEsc(token ? token.replace(/./g, '•').slice(0, 24) : tokenShown) + '</code>'
        + (token ? '<button type="button" class="st-btn sm" id="labShow">보기</button><button type="button" class="st-btn sm" data-copy="token">복사</button>' : '') + '</div>'
        + '<div class="st-kv"><span>모델</span><code id="labModels">연결 테스트로 확인</code><button type="button" class="st-btn sm" id="labTest">연결 테스트</button></div>'
        + '<p class="st-note">토큰은 개인에게 발급된 것이 아니라 연구실 공용 토큰입니다. 외부에 공개하거나 저장소에 올리지 마세요. 모델 이름은 <code>/models</code>로 조회해 쓰면 서버 모델이 바뀌어도 코드를 고칠 필요가 없어요.</p>'
        + '</div>'
        + '<div class="st-group"><div class="st-group-title">사용 예시</div>'
        + '<div class="st-tabs"><button type="button" class="on" data-ex="py">Python (openai)</button><button type="button" data-ex="curl">curl</button><button type="button" data-ex="js">JavaScript</button></div>'
        + '<pre class="st-code" data-ex="py">' + stEsc(py) + '</pre><pre class="st-code" data-ex="curl" hidden>' + stEsc(curl) + '</pre><pre class="st-code" data-ex="js" hidden>' + stEsc(js) + '</pre>'
        + '<div class="st-actions"><button type="button" class="st-btn sm" id="labCopyEx">예시 복사</button></div>'
        + '<p class="st-note">추론 모델(gpt-oss 등)은 답을 쓰기 전에 생각하는 데도 토큰을 씁니다. 답이 비어 있으면 <code>max_tokens</code>를 넉넉히(예: 4000 이상) 주세요.</p>'
        + '</div>';
      host.querySelectorAll('[data-copy]').forEach(function (b) {
        b.addEventListener('click', function () { copyText(b.getAttribute('data-copy') === 'token' ? token : base, b); });
      });
      var show = document.getElementById('labShow');
      if (show) show.addEventListener('click', function () {
        var el = document.getElementById('labToken'), on = show.textContent === '보기';
        el.textContent = on ? token : token.replace(/./g, '•').slice(0, 24); show.textContent = on ? '숨기기' : '보기';
      });
      host.querySelectorAll('.st-tabs button').forEach(function (b) {
        b.addEventListener('click', function () {
          host.querySelectorAll('.st-tabs button').forEach(function (x) { x.classList.toggle('on', x === b); });
          host.querySelectorAll('pre.st-code').forEach(function (p) { p.hidden = p.getAttribute('data-ex') !== b.getAttribute('data-ex'); });
        });
      });
      document.getElementById('labCopyEx').addEventListener('click', function (e) {
        var pre = host.querySelector('pre.st-code:not([hidden])'); copyText(pre.textContent, e.currentTarget);
      });
      document.getElementById('labTest').addEventListener('click', function (e) {
        var btn = e.currentTarget, out = document.getElementById('labModels');
        btn.disabled = true; out.textContent = '확인 중…';
        stFetch('/shared-ui/account/api/lab-llm/models').then(function (r) {
          btn.disabled = false;
          out.textContent = r.ok ? ((r.models || []).join(', ') || '(모델 없음)') : ('실패: ' + r.error);
          out.className = r.ok ? 'ok' : 'err';
        }).catch(function (err) { btn.disabled = false; out.textContent = '실패: ' + err.message; out.className = 'err'; });
      });
    }).catch(function (err) {
      host.innerHTML = err.status === 401
        ? loginBox('로컬 AI API 접속 정보는 로그인한 연구실 구성원에게만 보여요.')
        : '<div class="st-empty">접속 정보를 불러오지 못했어요: ' + stEsc(err.message) + '</div>';
    });
  }

  // ── 내 계정 (이름 · 비밀번호 · 패스키 · 모든 기기 로그아웃) ─────────────────────
  var ROLE_LABEL = { admin: '관리자', user: '구성원', member: '구성원' };
  function loadAccount() {
    var host = document.getElementById('stAccount');
    stFetch('/shared-ui/account/api/me').then(function (me) {
      var initial = (me.name || '?').trim().charAt(0);
      host.innerHTML =
        '<div class="st-profile"><div class="st-avatar">' + stEsc(initial) + '</div><div><b>' + stEsc(me.name) + '</b>'
        + '<span>' + stEsc(me.username || '') + (me.email ? ' · ' + stEsc(me.email) : '') + (me.email_verified ? ' ✓' : '') + '</span>'
        + '<span class="st-tags"><em>' + stEsc(ROLE_LABEL[me.role] || me.role || '') + '</em>'
        + (me.member ? '<em>' + stEsc([me.member.section, me.member.position].filter(Boolean).join(' · ') || '홈페이지 구성원 연결됨') + '</em>' : '')
        + (me.created_at ? '<em class="muted">가입 ' + stEsc(me.created_at.slice(0, 10)) + '</em>' : '') + '</span></div></div>'
        + '<div class="st-group"><div class="st-group-title">이름</div>'
        + '<div class="st-inline"><input type="text" id="accName" maxlength="40" value="' + stEsc(me.name) + '"><button type="button" class="st-btn primary" id="accNameSave">변경</button></div>'
        + '<p class="st-note">홈페이지 구성원 소개에 표시되는 정보(사진·연구·학력 등)는 홈페이지 계정 화면에서 바꿀 수 있어요.</p></div>'
        + '<div class="st-group"><div class="st-group-title">비밀번호 변경</div>'
        + '<div class="st-form"><input type="password" id="accCur" placeholder="현재 비밀번호" autocomplete="current-password">'
        + '<input type="password" id="accNew" placeholder="새 비밀번호 (8자 이상)" autocomplete="new-password">'
        + '<input type="password" id="accNew2" placeholder="새 비밀번호 확인" autocomplete="new-password"></div>'
        + '<div class="st-actions"><span class="llm-status" id="accPwStatus"></span><button type="button" class="st-btn primary" id="accPwSave">비밀번호 변경</button></div>'
        + '<p class="st-note">비밀번호를 바꾸면 다른 기기에서는 모두 로그아웃돼요.</p></div>'
        + '<div class="st-group"><div class="st-group-title">패스키</div><div id="accPasskeys"><div class="st-empty sm">불러오는 중…</div></div>'
        + '<div class="st-actions"><a class="st-btn" href="' + stEsc(homeOrigin()) + '/account" target="_blank" rel="noopener">새 패스키 등록 (홈페이지 계정 화면)</a></div></div>'
        + '<div class="st-group"><div class="st-group-title">로그인</div>'
        + '<div class="st-row"><div><b>모든 기기에서 로그아웃</b><span>분실한 기기나 공용 PC에 남은 로그인을 모두 끊어요. 이 기기도 로그아웃됩니다.</span></div><button type="button" class="st-btn danger" id="accLogoutAll">모두 로그아웃</button></div>'
        + '<div class="st-row"><div><b>이 기기에서 로그아웃</b></div><button type="button" class="st-btn" id="accLogout">로그아웃</button></div></div>';
      document.getElementById('accNameSave').addEventListener('click', function (e) {
        var btn = e.currentTarget, name = document.getElementById('accName').value.trim();
        if (!name) return;
        btn.disabled = true;
        stFetch('/shared-ui/account/api/me', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name }) })
          .then(function () { btn.disabled = false; btn.textContent = '변경됨'; setTimeout(function () { btn.textContent = '변경'; }, 1500); })
          .catch(function (err) { btn.disabled = false; alert(err.message); });
      });
      document.getElementById('accPwSave').addEventListener('click', function (e) {
        var btn = e.currentTarget, st = document.getElementById('accPwStatus');
        var cur = document.getElementById('accCur').value, nw = document.getElementById('accNew').value, nw2 = document.getElementById('accNew2').value;
        function say(t, k) { st.textContent = t; st.className = 'llm-status' + (k ? ' ' + k : ''); }
        if (!cur || !nw) return say('현재 비밀번호와 새 비밀번호를 입력하세요.', 'err');
        if (nw.length < 8) return say('새 비밀번호는 8자 이상이어야 해요.', 'err');
        if (nw !== nw2) return say('새 비밀번호 확인이 일치하지 않아요.', 'err');
        btn.disabled = true; say('변경하는 중…');
        stFetch('/shared-ui/account/api/me', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ current_password: cur, new_password: nw }) })
          .then(function () { say('변경했어요. 잠시 후 다시 로그인해 주세요.', 'ok'); setTimeout(function () { location.href = loginHref(); }, 1600); })
          .catch(function (err) { btn.disabled = false; say(err.message, 'err'); });
      });
      document.getElementById('accLogoutAll').addEventListener('click', function (e) {
        var btn = e.currentTarget;
        if (btn.getAttribute('data-armed') !== '1') { btn.setAttribute('data-armed', '1'); btn.textContent = '한 번 더 누르면 실행'; setTimeout(function () { btn.removeAttribute('data-armed'); btn.textContent = '모두 로그아웃'; }, 3000); return; }
        stFetch('/shared-ui/account/api/logout-all', { method: 'POST' }).then(function () { location.href = loginHref(); }).catch(function (err) { alert(err.message); });
      });
      document.getElementById('accLogout').addEventListener('click', function () {
        var url = (window.KNPU && KNPU.logoutUrl) ? KNPU.logoutUrl() : homeOrigin() + '/api/auth/logout';
        fetch(url, { method: 'POST', credentials: 'include' }).finally(function () { location.href = loginHref(); });
      });
      loadPasskeys();
    }).catch(function (err) {
      host.innerHTML = err.status === 401 ? loginBox('로그인하면 계정 정보를 관리할 수 있어요.') : '<div class="st-empty">계정 정보를 불러오지 못했어요: ' + stEsc(err.message) + '</div>';
    });
  }
  function loadPasskeys() {
    var host = document.getElementById('accPasskeys');
    stFetch('/shared-ui/account/api/passkeys').then(function (r) {
      var items = r.passkeys || [];
      if (!items.length) { host.innerHTML = '<div class="st-empty sm">등록된 패스키가 없어요. 패스키를 등록하면 비밀번호 없이 지문·얼굴 인식으로 로그인할 수 있어요.</div>'; return; }
      host.innerHTML = items.map(function (p) {
        return '<div class="st-row"><div><b>' + stEsc(p.device_name) + (p.backed_up ? ' <em class="st-chip">동기화</em>' : '') + '</b>'
          + '<span>등록 ' + stEsc(p.created_at || '') + (p.last_used_at ? ' · 마지막 사용 ' + stEsc(p.last_used_at) : '') + '</span></div>'
          + '<button type="button" class="st-btn sm danger" data-pk="' + stEsc(p.credential_id) + '">삭제</button></div>';
      }).join('');
      host.querySelectorAll('[data-pk]').forEach(function (b) {
        b.addEventListener('click', function () {
          if (b.getAttribute('data-armed') !== '1') { b.setAttribute('data-armed', '1'); b.textContent = '확인'; setTimeout(function () { b.removeAttribute('data-armed'); b.textContent = '삭제'; }, 2500); return; }
          stFetch('/shared-ui/account/api/passkeys/' + encodeURIComponent(b.getAttribute('data-pk')), { method: 'DELETE' }).then(loadPasskeys).catch(function (err) { alert(err.message); });
        });
      });
    }).catch(function () { host.innerHTML = '<div class="st-empty sm">패스키 목록을 불러오지 못했어요.</div>'; });
  }

  // ── 바로가기: 연구실 서비스와 설명서 ────────────────────────────────────────────
  var LINKS = [
    { key: 'homepage', name: '홈페이지', desc: '연구원 소개 · 구성원 · 논문 · 입학 안내' },
    { key: 'crawler', name: 'CRAWLER', desc: '뉴스 · 블로그 · 카페 · 유튜브 수집' },
    { key: 'statistics', name: 'STATISTICS', desc: '통계 분석 · AI 리포트', manual: '/manual' },
    { key: 'kemkim', name: 'KEMKIM', desc: '미래신호(약한 신호) 분석', manual: '/manual' },
    { key: 'network', name: 'NETWORK', desc: '단어 네트워크 분석', manual: '/manual' },
    { key: 'mcdm', name: 'POLYDECISION', desc: 'AHP 다기준 의사결정' },
    { key: 'whisper', name: 'WHISPER', desc: '음성 → 텍스트 노트' },
    { key: 'manager', name: 'MANAGER', desc: '데스크톱 앱 다운로드 · 설명서' },
  ];
  function renderLinks() {
    var host = document.getElementById('stLinks');
    var svc = (window.KNPU_SERVICES && KNPU_SERVICES.services) || {};
    host.innerHTML = '<div class="st-links">' + LINKS.map(function (l) {
      var s = svc[l.key], url = 'https://' + ((s && s.prodDomain) || (l.key === 'homepage' ? 'knpu.re.kr' : l.key + '.knpu.re.kr')) + ((s && s.publicPath) || '');
      return '<div class="st-link"><a href="' + stEsc(url) + '"><b>' + stEsc(l.name) + '</b><span>' + stEsc(l.desc) + '</span></a>'
        + (l.manual ? '<a class="st-btn sm" href="' + stEsc(url + l.manual) + '" target="_blank" rel="noopener">설명서</a>' : '') + '</div>';
    }).join('') + '</div>'
      + '<p class="st-note">사용법이 궁금하면 오른쪽 아래 AI 챗봇(구성원용)에게 물어보세요. 코드를 직접 읽고 화면 기준으로 알려 줍니다.</p>';
  }

  // 사이드바 아래 연결 상태 점(.sb-conn): 로그인 API를 주기적으로 확인한다.
  function initConnStatus() {
    var box = document.querySelector('.sb-conn');
    if (!box || !window.fetch) return;
    var label = box.querySelector('.conn-label');
    function set(ok) {
      box.classList.toggle('ok', ok); box.classList.toggle('bad', !ok);
      if (label) label.textContent = ok ? '서버 연결됨' : '연결 끊김 · 재시도 중';
    }
    function ping() {
      fetch(box.getAttribute('data-conn-url') || '/shared-ui/services.js', { credentials: 'same-origin', cache: 'no-store' })
        .then(function (r) {
          var fallback = box.getAttribute('data-conn-fallback');
          if (r.status === 404 && fallback) {
            return fetch(fallback, { credentials: 'same-origin', cache: 'no-store' })
              .then(function (alt) { set(alt.ok || alt.status === 401); });
          }
          set(r.ok || r.status === 401);
        })
        .catch(function () { set(false); })
        .then(function () { setTimeout(ping, document.hidden ? 60000 : 30000); });
    }
    ping();
  }

  // 연구실 챗봇(오른쪽 아래 동그라미 버튼)을 불러온다. <meta name="knpu-chatbot" content="off"> 면 끈다.
  function loadChatbot() {
    if (window.__knpuChatbot || document.querySelector('meta[name="knpu-chatbot"][content="off"]')) return;
    if (getCookie(CHATBOT_COOKIE_KEY) === 'off') return; // 설정에서 끈 경우
    if (!document.querySelector('link[href="/shared-ui/chatbot.css"]')) {
      var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/shared-ui/chatbot.css';
      document.head.appendChild(css);
    }
    var js = document.createElement('script'); js.src = '/shared-ui/chatbot.js'; js.defer = true;
    document.head.appendChild(js);
  }

  function init() {
    initLiquidGlass();
    initConnStatus();
    loadChatbot();
    var btn = document.getElementById('themeSettingsBtn');
    if (!btn) return;

    var overlay = buildModal();

    function open(pane) {
      markSelected(overlay); overlay.hidden = false;
      var saved = null; try { saved = localStorage.getItem(PANE_KEY); } catch (e) { }
      showPane(overlay, typeof pane === 'string' ? pane : (saved || 'appearance'));
    }
    window.KNPUSettings = { open: open }; // 다른 스크립트에서 특정 섹션으로 열 때: KNPUSettings.open('ai')
    overlay.querySelectorAll('.st-nav-item').forEach(function (b) {
      b.addEventListener('click', function () { showPane(overlay, b.getAttribute('data-pane')); });
    });
    overlay.querySelector('#stClearAnon').addEventListener('click', function (e) {
      try { localStorage.removeItem('knpu_chatbot_public_v1'); } catch (err) { }
      e.currentTarget.textContent = '지웠어요';
    });
    function close() { overlay.hidden = true; }

    btn.addEventListener('click', function () { open(); });
    // 사이드바 아래 줄의 테마 버튼 등, 같은 설정 창을 여는 다른 버튼들
    document.querySelectorAll('[data-theme-settings]').forEach(function (b) { b.addEventListener('click', function () { open(); }); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    overlay.querySelector('.theme-modal-close').addEventListener('click', close);
    overlay.querySelectorAll('.theme-option').forEach(function (opt) {
      opt.addEventListener('click', function () {
        applyTheme(opt.getAttribute('data-theme'));
        markSelected(overlay);
      });
    });
    overlay.querySelector('#llmSave').addEventListener('click', function () { saveLlmSettings(); });
    overlay.querySelector('#llmModes').addEventListener('change', syncLlmMode);
    overlay.querySelector('#themeModeSwitch').addEventListener('click', function () {
      applyMode(currentMode() === 'dark' ? 'light' : 'dark');
      markSelected(overlay);
    });
    overlay.querySelector('#themeNavSwitch').addEventListener('click', function () {
      applyNav(currentNav() === 'autohide' ? 'show' : 'autohide');
      markSelected(overlay);
    });
    overlay.querySelector('#themeChatbotSwitch').addEventListener('click', function () {
      // 모든 KNPU 사이트에 같이 적용되도록 공용 쿠키에 저장한다
      var on = getCookie(CHATBOT_COOKIE_KEY) === 'off';
      setCookie(CHATBOT_COOKIE_KEY, on ? 'on' : 'off');
      if (on) loadChatbot();
      window.dispatchEvent(new CustomEvent('knpu-chatbot-visibility', { detail: { visible: on } }));
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
