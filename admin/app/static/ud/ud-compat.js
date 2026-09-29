// UnivDash 공통 유틸리티 — KNPU 관리자 대시보드용으로 옮김 (UnivDash 의 Git · Server 페이지 스크립트가 사용)
(function () {
  'use strict';

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  async function api(url, options = {}) {
    // 방금 누른 버튼이 이 요청을 시작했다면, 응답이 늦을 때(120ms+) 그 버튼에 '기다리는 중' 표시
    const tap = lastTap && performance.now() - lastTap.t < 80 ? lastTap.el : null;
    if (tap) {
      lastTap = null;
      const timer = setTimeout(() => tap.classList.add('is-busy'), 120);
      try { return await request(url, options); } finally { clearTimeout(timer); tap.classList.remove('is-busy'); }
    }
    return request(url, options);
  }
  let lastTap = null;
  document.addEventListener('click', (event) => {
    if (hapticLabel && hapticLabel.contains(event.target)) return;   // 햅틱용 가짜 클릭은 무시
    const el = event.target.closest?.('button, [role="button"]');
    lastTap = el && !el.closest('.sheet-overlay, #sheetOverlay') ? { el, t: performance.now() } : null;
  }, true);

  async function request(url, options = {}) {
    const init = { ...options, headers: { ...(options.headers || {}) } };
    if (init.body !== undefined && typeof init.body !== 'string') {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(init.body);
    }
    const response = await fetch(url, init);
    // 관리자 대시보드는 세션이 끝나면 로그인 페이지로 리다이렉트한다(307) — 새로 고쳐 로그인으로 보낸다.
    if (response.status === 401 || (response.redirected && !response.url.includes('/api/'))) {
      location.reload();
      throw new Error('로그인이 필요합니다.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : '요청이 실패했습니다.';
      throw new Error(detail);
    }
    return data;
  }

  // 레이아웃의 #toastHost 에 app.css 의 .toast 모양으로 띄운다 (Workspace 알림과 같은 모양).
  function toast(message, type = 'info') {
    const host = document.getElementById('toastHost');
    if (!host) return;
    const kind = { success: 'ok', error: 'error', info: 'info', warn: 'warn' }[type] || 'info';
    const icon = { ok: 'fa-circle-check', error: 'fa-circle-exclamation', info: 'fa-circle-info', warn: 'fa-hand' }[kind];
    const item = document.createElement('div');
    item.className = `toast ${kind}`;
    item.innerHTML = `<i class="fas ${icon}"></i><span class="min-w-0 flex-1 whitespace-pre-wrap break-words"></span>`;
    item.querySelector('span').textContent = message;
    host.appendChild(item);
    while (host.children.length > 3) host.firstElementChild.remove();
    setTimeout(() => item.remove(), kind === 'error' ? 6000 : 3500);
  }

  function formatNumber(value) {
    const amount = Number(value || 0);
    if (amount >= 1e9) return `${(amount / 1e9).toFixed(2)}B`;
    if (amount >= 1e6) return `${(amount / 1e6).toFixed(amount >= 1e7 ? 1 : 2)}M`;
    if (amount >= 1e3) return `${(amount / 1e3).toFixed(amount >= 1e5 ? 0 : 1)}K`;
    return amount.toLocaleString('ko-KR');
  }

  function relativeTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    const seconds = Math.round((Date.now() - date.getTime()) / 1000);
    const future = seconds < 0;
    const abs = Math.abs(seconds);
    let text;
    if (abs < 60) text = `${abs}초`;
    else if (abs < 3600) text = `${Math.floor(abs / 60)}분`;
    else if (abs < 86400) text = `${Math.floor(abs / 3600)}시간`;
    else text = `${Math.floor(abs / 86400)}일`;
    return future ? `${text} 후` : `${text} 전`;
  }

  function duration(ms) {
    if (ms <= 0) return '곧';
    const minutes = Math.floor(ms / 60000);
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    const mins = minutes % 60;
    if (days > 0) return `${days}일 ${hours}시간`;
    if (hours > 0) return `${hours}시간 ${mins}분`;
    return `${mins}분`;
  }

  function formatDate(value, withYear = false) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value || '—';
    return new Intl.DateTimeFormat('ko-KR', {
      ...(withYear ? { year: '2-digit' } : {}),
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    }).format(date);
  }

  function chartColors() {
    const light = document.documentElement.getAttribute('data-ui-theme-mode') !== 'dark';
    return light
      ? { grid: 'rgba(15, 23, 42, 0.08)', ticks: '#5a6781', tooltipBg: 'rgba(255,255,255,0.96)', tooltipText: '#101828' }
      : { grid: 'rgba(255, 255, 255, 0.07)', ticks: 'rgba(255, 255, 255, 0.45)', tooltipBg: 'rgba(15,20,36,0.95)', tooltipText: '#e8e9ee' };
  }

  // 단축키용: 지금 글자를 입력하는 중인지 (입력창 · 편집기 · 터미널 · 직접 입력 모드) 또는 시트 · 메뉴가 열려 있는지
  function typingOrBusy(event) {
    const el = event.target;
    if (el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.closest?.('.xterm'))) return true;
    const sheet = document.getElementById('sheetOverlay');
    if (sheet && !sheet.hidden) return true;
    // 열려 있는(보이는) 메뉴만 — 숨겨 둔 메뉴 요소(Git 페이지 등)는 무시
    return [...document.querySelectorAll('.git-menu, .ex-menu')].some((menu) => !menu.classList.contains('hidden') && menu.offsetParent !== null);
  }
  // 한/영 상관없이 같은 자리 키 (w · ㅈ): event.code 로 본다
  function plainKey(event, code) {
    return event.code === code && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey && !event.isComposing && !event.repeat;
  }

  // ── 아이폰 앱처럼 누르는 느낌 ────────────────────────────────────────────────
  // 햅틱: 안드로이드는 vibrate, iOS(18+)는 숨긴 스위치 체크박스를 눌러 시스템 햅틱을 낸다.
  // iOS 는 사용자 제스처(click/touchend) 안에서 불러야 울린다 — await 뒤나 타이머 안에서는 조용히 무시된다.
  let hapticLabel = null;
  function haptic(pattern = 8) {
    try {
      if (typeof navigator.vibrate === 'function') { navigator.vibrate(pattern); return; }
      if (!document.body) return;
      if (!hapticLabel) {
        hapticLabel = document.createElement('label');
        hapticLabel.setAttribute('aria-hidden', 'true');
        hapticLabel.style.cssText = 'position:fixed;left:-100px;top:0;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden';
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.setAttribute('switch', '');
        box.tabIndex = -1;
        hapticLabel.appendChild(box);
        // 이 가짜 클릭이 "바깥 클릭 → 메뉴 닫기" 같은 처리로 번지지 않게 막는다
        const stop = (event) => event.stopPropagation();
        hapticLabel.addEventListener('click', stop);
        box.addEventListener('click', stop);
        document.body.appendChild(hapticLabel);
      }
      hapticLabel.click();
    } catch (e) { /* noop */ }
  }

  // 눌림 표시: 누르는 순간 바로(0ms) 어두워지고, 뗄 때 천천히(200ms) 돌아온다.
  // - 버튼은 즉시, 목록 줄은 50ms 뒤에 (스크롤하려고 댄 손가락에 줄이 번쩍이지 않게 — UITableView 와 같은 방식)
  // - 손가락이 움직이거나 스크롤이 시작되면 바로 취소
  const PRESSABLE = 'button, [role="button"], a[href], summary, label.check-row, .key-chip, .tab-item, .filter-chip, .win-item, .ex-row, .ex-root, .sheet-action, .wt, .tt-tab, .exv-tab, .fp-row, .folder-head, .org-item, .git-file-row, .git-repo-item';
  const ROW = '.win-item, .ex-row, .ex-root, .sheet-action, .fp-row, .folder-head, .org-item, .git-file-row, .git-repo-item';
  let pressed = null;
  let pressTimer = 0;
  let pressStart = null;
  function release(fade = true) {
    clearTimeout(pressTimer);
    const el = pressed;
    pressed = null;
    if (!el || !el.classList.contains('is-pressed')) return;
    el.classList.remove('is-pressed');
    if (!fade) return;
    el.classList.add('press-release');
    setTimeout(() => el.classList.remove('press-release'), 220);
  }
  document.addEventListener('pointerdown', (event) => {
    if (event.button > 0) return;
    release(false);
    // 줄 안의 작은 버튼(⋯, ✕)을 누르면 줄 전체가 아니라 그 버튼만 (closest 가 가장 안쪽을 고른다)
    const target = event.target.closest?.(PRESSABLE);
    if (!target || target.disabled || target.getAttribute('aria-disabled') === 'true' || target.closest('.xterm')) return;
    pressed = target;
    pressStart = { x: event.clientX, y: event.clientY };
    if (event.pointerType !== 'mouse' && target.matches(ROW)) pressTimer = setTimeout(() => pressed?.classList.add('is-pressed'), 50);
    else target.classList.add('is-pressed');
  }, { capture: true, passive: true });
  document.addEventListener('pointermove', (event) => {
    if (!pressed || !pressStart) return;
    if (Math.hypot(event.clientX - pressStart.x, event.clientY - pressStart.y) > 10) release(false);
  }, { capture: true, passive: true });
  document.addEventListener('pointerup', () => {
    // 줄을 짧게 톡 친 경우(50ms 전에 뗌)도 눌림을 한 번 보여 준다
    if (pressed && !pressed.classList.contains('is-pressed')) {
      clearTimeout(pressTimer);
      const el = pressed;
      el.classList.add('is-pressed');
      pressTimer = setTimeout(() => { if (pressed === el) release(true); }, 90);
      return;
    }
    release(true);
  }, { capture: true, passive: true });
  document.addEventListener('pointercancel', () => release(false), { capture: true, passive: true });
  document.addEventListener('scroll', () => release(false), { capture: true, passive: true });
  document.addEventListener('dragstart', () => release(false), { capture: true, passive: true });
  // 고르는 동작(모드 전환 · 필터 · 스위치 · 확인)에는 가벼운 햅틱 — UISelectionFeedbackGenerator 자리
  document.addEventListener('click', (event) => {
    if (event.target.closest?.('.ws-switch button, .filter-chip, .pmd-mode-switch, .sheet-form input[type="checkbox"], [data-yes], [data-haptic]')) haptic(6);
  });
  // 탭바 · 사이드바 이동은 손가락이 닿는 순간 시작한다 (iOS 탭바처럼 — 떼기를 기다리는 ~100ms 절약).
  // 선택 표시도 바로 옮겨서 서버 응답 전에 눌린 탭이 켜진다.
  let navTo = '';
  document.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest?.('.tabbar a.tab-item, a.nav-link');
    if (!link || link.getAttribute('aria-current') === 'page' || link.target) return;
    // 사이드바는 휴대폰에서 스크롤되는 서랍이라 터치는 평소처럼 click 에서
    if (event.pointerType !== 'mouse' && !link.closest('.tabbar')) return;
    for (const other of document.querySelectorAll('.tabbar a.tab-item.active')) other.classList.remove('active');
    if (link.classList.contains('tab-item')) link.classList.add('active');
    navTo = link.href;
    location.href = link.href;
  }, { capture: true });
  document.addEventListener('click', (event) => {
    const link = event.target.closest?.('a[href]');
    if (link && navTo && link.href === navTo) event.preventDefault();   // 이미 이동 중 — 두 번 이동하지 않게
  }, true);
  window.addEventListener('pageshow', () => { navTo = ''; });

  // iOS Safari 는 touchstart 리스너가 하나라도 있어야 :active 를 적용한다 (CSS :active 만 쓰는 곳 대비)
  document.addEventListener('touchstart', () => {}, { passive: true });

  // 오래 걸리는 버튼: 일이 끝날 때까지 흐리게 두고 다시 못 누르게 한다.
  async function busy(button, work) {
    if (!button) return work();
    button.classList.add('is-busy');
    button.setAttribute('aria-busy', 'true');
    try { return await work(); } finally { button.classList.remove('is-busy'); button.removeAttribute('aria-busy'); }
  }

  // 수식 (탐색기 마크다운 · 채팅 공용): marked 가 \qquad · _ · \\ 같은 TeX 기호를 망가뜨리므로, 변환 전에 수식을 자리표시(KTXM0Z)로 빼 두고
  // marked → DOMPurify 정리가 끝난 뒤 KaTeX 로 그려 넣는다 (KaTeX 결과는 trust:false 라 링크 · HTML 명령이 막혀 있다).
  // 코드 블록(``` ~~~)과 인라인 코드(`…`) 안의 $ 는 건드리지 않는다.
  function extractMath(src) {
    const math = [];
    if (!window.katex || !/\$|\\\(|\\\[/.test(src)) return { text: src, math };
    const put = (tex, display) => { math.push({ tex: tex.trim(), display }); return `KTXM${math.length - 1}Z`; };
    const inText = (text) => text
      .replace(/\$\$([\s\S]+?)\$\$/g, (m, tex) => put(tex, true))
      .replace(/\\\[([\s\S]+?)\\\]/g, (m, tex) => put(tex, true))
      .replace(/\\\(([\s\S]+?)\\\)/g, (m, tex) => put(tex, false))
      // $…$: 여는 $ 뒤 · 닫는 $ 앞에 공백이 없고, 닫는 $ 뒤가 숫자가 아닐 때만 ($5 와 $10 같은 금액 제외)
      .replace(/(^|[^\\$])\$(?![\s$])((?:\\.|[^$\n\\])+?)(?<!\s)\$(?!\d)/g, (m, pre, tex) => pre + put(tex, false));
    const text = src.split(/(^[ \t]*(?:```|~~~)[^\n]*\n[\s\S]*?^[ \t]*(?:```|~~~)[ \t]*$)/m)
      .map((part, i) => (i % 2 ? part : part.split(/(`+[^`\n]*?`+)/).map((piece, j) => (j % 2 ? piece : inText(piece))).join('')))
      .join('');
    return { text, math };
  }
  function renderMath(html, math) {
    if (!math.length) return html;
    return html.replace(/KTXM(\d+)Z/g, (m, index) => {
      const item = math[Number(index)];
      if (!item) return m;
      try {
        return window.katex.renderToString(item.tex, { displayMode: item.display, throwOnError: false, trust: false, strict: 'ignore', maxSize: 50, maxExpand: 1000, output: 'htmlAndMathml' });
      } catch (e) { return `<code>${escapeHtml(item.tex)}</code>`; }
    });
  }

  window.UnivDash = { escapeHtml, api, toast, formatNumber, relativeTime, duration, formatDate, chartColors, typingOrBusy, plainKey, haptic, busy, math: { extract: extractMath, render: renderMath } };
})();

// 시트(하단 시트 / 가운데 모달) · 토스트 — UnivDash app.js 에서 Git · Server 페이지가 쓰는 부분만 옮김
(function () {
  'use strict';
  const { escapeHtml, toast } = window.UnivDash;
  const $ = (sel) => document.querySelector(sel);
  const coarsePointer = window.matchMedia('(pointer: coarse)').matches;
  function ensureHost() {
    if (!document.getElementById('sheetOverlay')) {
      document.body.insertAdjacentHTML('beforeend',
        '<div id="sheetOverlay" class="sheet-overlay ud-scope" hidden><div id="sheet" class="tdx-sheet scale-up-animation" role="dialog" aria-modal="true"><div class="sheet-grip"></div><div id="sheetBody"></div></div></div>');
    }
    if (!document.getElementById('toastHost')) {
      document.body.insertAdjacentHTML('beforeend', '<div id="toastHost" class="toast-host ud-scope" aria-live="polite"></div>');
    }
  }
  ensureHost();
  // ── 시트(하단 시트 / 모달) ────────────────────────────────────────────
  const sheetOverlay = $('#sheetOverlay');
  const sheetBody = $('#sheetBody');
  let sheetOnClose = null;

  let sheetReturnFocus = null;
  function openSheet(html, onMount, onClose) {
    if (sheetOverlay.hidden) sheetReturnFocus = document.activeElement;   // 닫으면 원래 자리로 초점을 돌려준다 (단축키가 이어지게)
    sheetBody.innerHTML = html;
    sheetOverlay.hidden = false;
    sheetOnClose = onClose || null;
    onMount?.(sheetBody);
  }
  function closeSheet() {
    if (sheetOverlay.hidden) return;
    sheetOverlay.hidden = true;
    sheetBody.innerHTML = '';
    const callback = sheetOnClose;
    sheetOnClose = null;
    callback?.();
    const back = sheetReturnFocus;
    sheetReturnFocus = null;
    if (back?.isConnected && sheetOverlay.hidden && !coarsePointer) { try { back.focus({ preventScroll: true }); } catch (e) { /* noop */ } }
  }
  sheetOverlay.addEventListener('click', (event) => { if (event.target === sheetOverlay) closeSheet(); });

  function sheetHead(title, subtitle) {
    return `<div class="sheet-head"><h3>${escapeHtml(title)}</h3>${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ''}</div>`;
  }

  // actions: [{icon, label, sub, danger, current, onClick}] 또는 'sep'
  function actionSheet({ title, subtitle, actions }) {
    const items = actions.map((action, index) => {
      if (action === 'sep') return '<div class="sheet-sep"></div>';
      return `<button type="button" class="sheet-action ${action.danger ? 'danger' : ''} ${action.current ? 'current' : ''}" data-index="${index}">
          <i class="fas ${action.icon || 'fa-circle'} lead"></i><span class="min-w-0 ${action.desc ? 'flex-1' : 'truncate'}">${action.desc
            ? `<span class="block truncate">${escapeHtml(action.label)}</span><span class="block text-[11px] font-medium opacity-55 mt-0.5">${escapeHtml(action.desc)}</span>`
            : escapeHtml(action.label)}</span>
          ${action.sub ? `<span class="sub">${escapeHtml(action.sub)}</span>` : ''}</button>`;
    }).join('');
    openSheet(`${sheetHead(title, subtitle)}<div class="sheet-actions">${items}</div>
      <div class="sheet-buttons"><button type="button" class="sheet-cancel" data-close>닫기</button></div>`, (body) => {
      body.querySelector('[data-close]').addEventListener('click', closeSheet);
      body.querySelectorAll('.sheet-action').forEach((button) => {
        button.addEventListener('click', () => {
          const action = actions[Number(button.dataset.index)];
          closeSheet();
          action.onClick?.();
        });
      });
    });
  }

  // fields: [{name, label, value, placeholder, maxlength, autocomplete}]
  function formSheet({ title, subtitle, fields = [], extraHtml = '', submitLabel = '저장', onMount, onSubmit }) {
    const inputs = fields.map((field) => `
      <label>${escapeHtml(field.label)}
        <input name="${field.name}" value="${escapeHtml(field.value ?? '')}" placeholder="${escapeHtml(field.placeholder ?? '')}"
          maxlength="${field.maxlength || 100}" autocomplete="off" autocapitalize="off" spellcheck="false" ${field.inputmode ? `inputmode="${field.inputmode}"` : ''}>
      </label>`).join('');
    openSheet(`${sheetHead(title, subtitle)}<form class="sheet-form-wrap"><div class="sheet-form">${inputs}${extraHtml}</div>
      <div class="sheet-buttons"><button type="button" class="sheet-cancel" data-close>취소</button><button type="submit" class="btn-glow">${escapeHtml(submitLabel)}</button></div></form>`, (body) => {
      const form = body.querySelector('form');
      body.querySelector('[data-close]').addEventListener('click', closeSheet);
      onMount?.(body);
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const values = Object.fromEntries(new FormData(form).entries());
        const submit = form.querySelector('[type="submit"]');
        submit.disabled = true;
        try {
          const keepOpen = await onSubmit(values, body);
          if (!keepOpen) closeSheet();
        } catch (error) {
          toast(error.message || '처리하지 못했습니다.', 'error');
        } finally {
          submit.disabled = false;
        }
      });
      const first = body.querySelector('input');
      if (first && !coarsePointer) setTimeout(() => first.focus(), 30);
    });
  }

  function confirmSheet({ title, message, confirmLabel = '확인', danger = false }) {
    return new Promise((resolve) => {
      let answered = false;
      let keyHandler = null;
      openSheet(`${sheetHead(title, message)}<div class="sheet-buttons">
          <button type="button" class="sheet-cancel" data-no>취소</button>
          <button type="button" class="${danger ? 'sheet-danger' : 'btn-glow'}" data-yes>${escapeHtml(confirmLabel)}</button></div>`, (body) => {
        const yes = body.querySelector('[data-yes]');
        body.querySelector('[data-no]').addEventListener('click', () => closeSheet());
        yes.addEventListener('click', () => { answered = true; closeSheet(); resolve(true); });
        // Enter = 확인 · Esc = 취소 (확인 버튼에 초점을 두어 키보드로 바로 누를 수 있게)
        keyHandler = (event) => {
          if (event.isComposing || event.repeat) return;
          if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); yes.click(); }
          else if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeSheet(); }
        };
        document.addEventListener('keydown', keyHandler, true);
        setTimeout(() => yes.focus({ preventScroll: true }), 30);
      }, () => {
        document.removeEventListener('keydown', keyHandler, true);
        if (!answered) resolve(false);
      });
    });
  }

  // 다른 페이지 스크립트(server.js 등)도 같은 시트 · 토스트를 쓰도록 공개한다.
  // 정보만 보여주는 시트 (bodyHtml 은 호출한 쪽에서 escape 한 HTML). onMount 로 나중에 값을 채울 수 있다.
  function infoSheet({ title, subtitle, bodyHtml, onMount, onClose }) {
    openSheet(`${sheetHead(title, subtitle)}<div class="sheet-info">${bodyHtml}</div>
      <div class="sheet-buttons"><button type="button" class="sheet-cancel" data-close>닫기</button></div>`, (body) => {
      body.querySelector('[data-close]').addEventListener('click', closeSheet);
      onMount?.(body);
    }, onClose);
  }

  window.UnivDashUI = { actionSheet, formSheet, confirmSheet, closeSheet, toast, infoSheet };
  window.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeSheet(); });
  // 차트 색 등에 쓰는 현재 밝기 (KNPU 는 다크일 때만 data-ui-theme-mode="dark")
  window.UnivDashTheme = { current: () => (document.documentElement.getAttribute('data-ui-theme-mode') === 'dark' ? 'dark' : 'light') };
})();
