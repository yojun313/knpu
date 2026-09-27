/* FPEI AI 고소장 — SPA (프레임워크 없이, 해시 라우팅) */
(function () {
  'use strict';

  // ── 아이콘 ──────────────────────────────────────────────────────────────
  const ICONS = {
    chat: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    form: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    right: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    left: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    spark: '<path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2Z"/>',
    book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    ext: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    list: '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    bank: '<path d="M3 22h18"/><path d="M6 18v-7"/><path d="M10 18v-7"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M12 2 20 7H4z"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    eye: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
  };
  const icon = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ''}</svg>`;

  // ── 유틸 ────────────────────────────────────────────────────────────────
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const rich = (s) => esc(s).replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const fmtDate = (s) => (s && s.length === 8 ? `${s.slice(0, 4)}. ${+s.slice(4, 6)}. ${+s.slice(6)}.` : s || '');
  const isTouch = matchMedia('(pointer: coarse)').matches;

  const LS_KEY = 'complaint.caseId';
  const store = {
    get: () => { try { return localStorage.getItem(LS_KEY); } catch (e) { return null; } },
    set: (v) => { try { localStorage.setItem(LS_KEY, v); } catch (e) {} },
    clear: () => { try { localStorage.removeItem(LS_KEY); } catch (e) {} },
  };

  async function api(path, opts = {}) {
    const res = await fetch('/api' + path, {
      method: opts.method || 'GET',
      headers: opts.body ? { 'Content-Type': 'application/json' } : {},
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      const err = new Error((data && data.detail && (typeof data.detail === 'string' ? data.detail : '입력값을 확인해 주세요.')) || `요청에 실패했습니다 (${res.status})`);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  async function ndjson(path, body, onEvent, signal) {
    const res = await fetch('/api' + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
    });
    if (!res.ok) {
      let msg = `요청에 실패했습니다 (${res.status})`;
      try { const d = await res.json(); if (typeof d.detail === 'string') msg = d.detail; } catch (e) {}
      const err = new Error(msg); err.status = res.status; throw err;
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) { try { onEvent(JSON.parse(line)); } catch (e) { console.error(e); } }
      }
    }
    if (buf.trim()) { try { onEvent(JSON.parse(buf)); } catch (e) {} }
  }

  function toast(msg, kind = '') {
    const host = $('#toasts');
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.innerHTML = `${icon(kind === 'error' ? 'alert' : kind === 'ok' ? 'check' : 'info')}<span>${esc(msg)}</span>`;
    host.appendChild(el);
    while (host.children.length > 3) host.firstChild.remove();
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 300); }, 3600);
  }

  // 시트(데스크톱: 가운데 모달 / 모바일: 바텀 시트)
  function openSheet(html, { wide = false, onMount } = {}) {
    closeSheet();
    const ov = document.createElement('div');
    ov.className = 'sheet-overlay';
    ov.id = 'sheet';
    ov.innerHTML = `<div class="sheet ${wide ? 'wide' : ''}" role="dialog" aria-modal="true"><div class="sheet-grip"></div>${html}</div>`;
    ov.addEventListener('click', (e) => { if (e.target === ov) closeSheet(); });
    document.body.appendChild(ov);
    document.body.style.overflow = 'hidden';
    if (onMount) onMount(ov.firstElementChild);
    return ov.firstElementChild;
  }
  function closeSheet() {
    const ov = $('#sheet');
    if (ov) ov.remove();
    if (!$('.case-panel.open')) document.body.style.overflow = '';
  }
  addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });

  function confirmSheet({ title, message, ok = '확인', cancel = '취소', danger = false }) {
    return new Promise((resolve) => {
      openSheet(`<h3>${esc(title)}</h3><div class="muted">${message}</div>
        <div class="sheet-actions"><button class="btn btn-outline" data-a="no">${esc(cancel)}</button>
        <button class="btn ${danger ? 'btn-dark' : 'btn-primary'}" data-a="yes">${esc(ok)}</button></div>`, {
        onMount: (s) => {
          s.addEventListener('click', (e) => {
            const a = e.target.closest('[data-a]');
            if (!a) return;
            closeSheet();
            resolve(a.dataset.a === 'yes');
          });
        },
      });
    });
  }

  // ── 테마 (다른 KNPU 사이트와 쿠키 공유) ───────────────────────────────────
  function setThemeCookie(mode) {
    const domain = /(^|\.)knpu\.re\.kr$/.test(location.hostname) ? '; domain=.knpu.re.kr' : '';
    document.cookie = `ui_theme_mode=${mode}; path=/; max-age=31536000; samesite=lax${domain}${location.protocol === 'https:' ? '; secure' : ''}`;
  }
  function paintThemeBtn() {
    const dark = document.documentElement.dataset.theme === 'dark';
    $('#themeBtn').innerHTML = icon(dark ? 'sun' : 'moon');
    $('#themeBtn').setAttribute('aria-label', dark ? '라이트 모드로' : '다크 모드로');
  }
  $('#themeBtn').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    setThemeCookie(next);
    paintThemeBtn();
  });
  paintThemeBtn();

  // ── 상태 ────────────────────────────────────────────────────────────────
  const S = { meta: null, case: null, pendingParty: null, busy: false };
  const app = $('#app');

  const crimeById = (id) => (S.meta ? S.meta.crimes.find((c) => c.id === id) : null);
  const factDef = (k) => (S.meta ? S.meta.facts[k] : null) || { label: k, type: 'text' };

  async function loadMeta() {
    if (!S.meta) S.meta = await api('/meta');
    return S.meta;
  }
  async function loadCase(id, force = false) {
    if (!force && S.case && S.case.id === id) return S.case;
    S.case = await api(`/cases/${id}`);
    store.set(id);
    return S.case;
  }

  function go(hash) { if (location.hash !== hash) location.hash = hash; else route(); }

  function caseHome(c) {
    if (c.files) return `#/result/${c.id}`;
    if (c.mode === 'chat') return `#/chat/${c.id}`;
    return c.state.crime_type ? `#/form/${c.id}/facts` : `#/form/${c.id}/type`;
  }

  async function startCase(mode, crimeType) {
    if (S.busy) return;
    S.busy = true;
    try {
      const c = await api('/cases', { method: 'POST', body: { mode, crime_type: crimeType || null } });
      S.case = c;
      store.set(c.id);
      go(mode === 'chat' ? `#/chat/${c.id}` : (crimeType ? `#/form/${c.id}/facts` : `#/form/${c.id}/type`));
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      S.busy = false;
    }
  }

  // ── 라우터 ──────────────────────────────────────────────────────────────
  async function route() {
    closeSheet();
    // 모바일 사건 정리 패널의 가림막은 #app 밖(body)에 붙어 있어 화면이 바뀌어도 남는다
    $$('.panel-scrim').forEach((el) => el.remove());
    document.body.style.overflow = '';
    window.scrollTo(0, 0);
    const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
    const [view, id, sub] = parts;
    $('#resumeBtn').hidden = true;
    try {
      await loadMeta();
      if (!view) return renderHome();
      await loadCase(id, true);
      if (view === 'chat') return renderChat();
      if (view === 'form') return renderForm(sub || 'type');
      if (view === 'party') return renderParty();
      if (view === 'generating') return renderGenerating();
      if (view === 'result') return renderResult();
      return renderHome();
    } catch (e) {
      if (e.status === 404) {
        store.clear();
        toast('작성하던 내용을 찾을 수 없습니다. 보존 기간이 지나 삭제되었을 수 있어요.', 'error');
        location.hash = '#/';
        return;
      }
      app.innerHTML = `<div class="container narrow page"><div class="card card-pad"><h2 class="page-title">불러오지 못했습니다</h2><p class="page-sub">${esc(e.message)}</p><div class="row" style="margin-top:18px"><button class="btn btn-primary" onclick="location.reload()">${icon('refresh')}다시 시도</button><a class="btn btn-outline" href="#/">처음으로</a></div></div></div>`;
    }
  }
  addEventListener('hashchange', route);

  // ── 홈 ──────────────────────────────────────────────────────────────────
  async function renderHome() {
    const m = S.meta;
    const savedId = store.get();
    app.innerHTML = `<div class="view">
      <section class="hero"><div class="container">
        <span class="eyebrow">${icon('shield')}경찰청 표준 양식 · 국가법령정보센터 원문 기반</span>
        <h1>사기 피해, <em>AI와 대화하며</em><br>고소장으로 정리하세요</h1>
        <p class="lead">있었던 일을 편하게 말씀해 주시면 AI가 법령과 판례를 근거로 꼭 필요한 내용을 되묻고, 경찰청 표준 양식의 고소장 초안을 만들어 드립니다.</p>
        <div id="resumeSlot"></div>
        <div class="mode-grid">
          <button class="mode-card featured" data-start="chat">
            <span class="badge badge-primary">추천</span>
            <span class="mode-icon">${icon('chat')}</span>
            <h3>AI와 대화로 작성</h3>
            <p>상황을 이야기하듯 적으면 AI가 필요한 질문을 이어 가며 사실관계를 정리합니다. 무엇을 써야 할지 막막할 때 좋아요.</p>
            <span class="go">대화 시작하기 ${icon('right')}</span>
          </button>
          <button class="mode-card" data-start="form">
            <span class="mode-icon">${icon('form')}</span>
            <h3>양식으로 직접 작성</h3>
            <p>사건 유형을 고르고 항목별 입력칸을 채웁니다. 내용이 이미 정리되어 있다면 더 빠릅니다.</p>
            <span class="go">양식 작성하기 ${icon('right')}</span>
          </button>
        </div>
      </div></section>

      <section class="home-section"><div class="container">
        <h2 class="section-title">고소장이 만들어지는 과정</h2>
        <div class="steps4">
          <div class="step4"><div class="num">1</div><h4>사실관계 정리</h4><p>대화나 양식으로 언제·어디서·어떤 말에 속아·얼마를 넘겼는지 모읍니다.</p></div>
          <div class="step4"><div class="num">2</div><h4>법령·판례 검토</h4><p>공식 법령 원문과 대법원 판례로 사기죄 구성요건을 하나씩 점검합니다.</p></div>
          <div class="step4"><div class="num">3</div><h4>초안 작성·교차 검토</h4><p>초안을 쓴 뒤 수사관 시각으로 다시 검토해 빠진 사실과 오류를 고칩니다.</p></div>
          <div class="step4"><div class="num">4</div><h4>표준 양식 문서</h4><p>경찰청 표준 고소장 양식의 Word·PDF로 받아 바로 수정·출력할 수 있습니다.</p></div>
        </div>
      </div></section>

      <section class="home-section"><div class="container">
        <div class="row between wrap" style="margin-bottom:14px"><h2 class="section-title" style="margin:0">지원하는 사기 유형</h2><span class="muted small">유형을 누르면 바로 시작할 수 있어요</span></div>
        <div class="type-grid">${m.crimes.map((c) => `<button class="type-card" data-type="${esc(c.id)}"><strong>${esc(c.label)}</strong><span>${esc(c.summary)}</span></button>`).join('')}</div>
      </div></section>

      <section class="home-section"><div class="container">
        <div class="trust">
          <div class="trust-item"><div class="ic">${icon('book')}</div><div><h4>근거는 공식 원문만 씁니다</h4>
            <p>AI의 기억이 아니라 국가법령정보센터에서 받은 현행 법령과 판례 원문만 근거로 삼고, 인용한 조문은 원문과 함께 보여 드립니다.</p>
            <div class="kb-stats muted small"><span><b>${m.kb.statutes}</b>개 조문</span><span><b>${m.kb.precedents}</b>건 판례</span><span>기준일 ${esc(m.kb.built)}</span></div></div></div>
          <div class="trust-item warn"><div class="ic">${icon('alert')}</div><div><h4>꼭 확인해 주세요</h4>
            <p>AI가 만든 문서는 법률 자문이 아닌 초안입니다. 제출 전에 사실관계를 반드시 직접 확인하세요. 허위 사실로 고소하면 무고죄(형법 제156조)로 처벌받을 수 있습니다.</p></div></div>
        </div>
      </div></section>
      <footer class="app-footer"><div class="container"><span>경찰대학 데이터사이언스전공 미래치안공학연구원(FPEI)</span><span>입력한 정보는 작성 후 ${72}시간이 지나면 자동으로 삭제됩니다.</span></div></footer>
    </div>`;

    $$('[data-start]', app).forEach((b) => b.addEventListener('click', () => startCase(b.dataset.start)));
    $$('[data-type]', app).forEach((b) => b.addEventListener('click', () => {
      const c = crimeById(b.dataset.type);
      openSheet(`<h3>${esc(c.label)}</h3><p class="muted" style="margin:0 0 18px">${esc(c.summary)}</p>
        <div class="stack"><button class="btn btn-primary btn-lg btn-block" data-m="chat">${icon('chat')}AI와 대화로 작성</button>
        <button class="btn btn-outline btn-lg btn-block" data-m="form">${icon('form')}양식으로 직접 작성</button></div>`, {
        onMount: (s) => $$('[data-m]', s).forEach((x) => x.addEventListener('click', () => { closeSheet(); startCase(x.dataset.m, c.id); })),
      });
    }));

    if (savedId) {
      try {
        const c = await api(`/cases/${savedId}`);
        S.case = c;
        const label = c.state.crime_label ? `${c.state.crime_label} · ` : '';
        const where = c.files ? '완성된 고소장이 있습니다' : `작성 중 (${Math.round(c.state.completeness * 100)}%)`;
        $('#resumeSlot').innerHTML = `<div class="resume-banner">${icon('clock')}<div class="grow"><b>이어서 작성할 수 있어요</b><div class="muted small">${esc(label + where)}</div></div>
          <a class="btn btn-soft btn-sm" href="${caseHome(c)}">${c.files ? '고소장 보기' : '이어서 작성'}</a>
          <button class="btn btn-ghost btn-sm btn-icon" id="forgetBtn" aria-label="지우기">${icon('x')}</button></div>`;
        $('#forgetBtn').addEventListener('click', async () => {
          if (!(await confirmSheet({ title: '작성 내용을 지울까요?', message: '서버에 저장된 대화·사건 정리·문서를 지금 바로 삭제합니다.', ok: '삭제', danger: true }))) return;
          try { await api(`/cases/${savedId}`, { method: 'DELETE' }); } catch (e) {}
          store.clear();
          $('#resumeSlot').innerHTML = '';
          toast('삭제했습니다.', 'ok');
        });
      } catch (e) {
        if (e.status === 404) store.clear();
      }
    }
  }

  // ── 사건 정리 패널 (채팅) ────────────────────────────────────────────────
  function lawCards(items, kind) {
    if (!items || !items.length) return '<p class="muted small" style="margin:0 0 8px">사건 내용이 모이면 관련 근거를 찾아 드려요.</p>';
    return items.map((x) => kind === 'statute'
      ? `<details class="law-card"><summary><div class="t"><b>${esc(x.label)} <span>(${esc(x.title)})</span></b><span>${esc(x.reason || '')}</span></div>${icon('down').replace('class="i"', 'class="i chev"')}</summary>
          <div class="law-text">${esc(x.text)}<div class="law-meta"><span>시행 ${esc(fmtDate(x.effective))}</span><a href="${esc(x.url)}" target="_blank" rel="noopener">원문 ${icon('ext')}</a></div></div></details>`
      : `<details class="law-card"><summary><div class="t"><b>${esc(x.court)} ${esc(x.case_no)}</b><span>${esc((x.points || '').slice(0, 90))}…</span></div>${icon('down').replace('class="i"', 'class="i chev"')}</summary>
          <div class="law-text"><b>판결요지</b>\n${esc(x.summary)}<div class="law-meta"><span>선고 ${esc(fmtDate(x.date))}</span><a href="${esc(x.url)}" target="_blank" rel="noopener">원문 ${icon('ext')}</a></div></div></details>`).join('');
  }

  function factRows(state, changed = []) {
    const crime = crimeById(state.crime_type);
    const required = new Set(crime ? crime.required : []);
    const keys = state.fields || [];
    return keys.map((k) => {
      const d = factDef(k);
      const v = state.facts[k];
      const req = required.has(k);
      const cls = v ? 'done' : req ? 'need' : '';
      return `<button class="fact-row ${cls} ${changed.includes(k) ? 'flash' : ''}" data-fact="${esc(k)}">
        <span class="st">${v ? icon('check') : ''}</span>
        <span class="grow"><span class="lbl">${esc(d.label)}${req && !v ? '<span class="badge badge-warn" style="height:19px;font-size:11px">필요</span>' : ''}</span>
        <span class="val">${v ? esc(v) : req ? '아직 확인되지 않았어요' : '선택 사항'}</span></span></button>`;
    }).join('');
  }

  function renderPanel(state, changed = []) {
    const panel = $('#casePanel');
    if (!panel) return;
    const crime = crimeById(state.crime_type);
    const req = crime ? crime.required.length : 0;
    const done = req - state.missing.length;
    const pct = Math.round((state.completeness || 0) * 100);
    const prevBody = $('.case-panel-body', panel);
    const keepScroll = prevBody ? prevBody.scrollTop : 0;
    const openCards = new Set($$('details.law-card[open] b', panel).map((b) => b.textContent));
    panel.innerHTML = `<div class="sheet-grip"></div>
      <div class="case-panel-head">
        <div class="row between" style="margin-bottom:10px"><h3 style="font-size:16px;font-weight:800">사건 정리</h3>
          <button class="btn btn-ghost btn-sm btn-icon only-mobile" id="panelClose" aria-label="닫기">${icon('x')}</button></div>
        <select class="select" id="crimeSelect" aria-label="사건 유형">
          <option value="">사건 유형 — 대화에서 자동으로 파악해요</option>
          ${S.meta.crimes.map((c) => `<option value="${esc(c.id)}" ${c.id === state.crime_type ? 'selected' : ''}>${esc(c.label)}</option>`).join('')}
        </select>
        <div class="row between small" style="margin:12px 0 6px"><span class="muted">필수 항목</span><b>${crime ? `${done} / ${req}` : '-'}</b></div>
        <div class="progress"><span style="width:${pct}%"></span></div>
      </div>
      <div class="case-panel-body">
        <div class="panel-section"><h4>${icon('list')}정리된 사실 <span class="muted" style="text-transform:none;font-weight:600">· 눌러서 고칠 수 있어요</span></h4>${state.crime_type ? factRows(state, changed) : '<p class="muted small" style="margin:0">어떤 피해인지 말씀해 주시면 필요한 항목을 보여 드릴게요.</p>'}</div>
        <div class="panel-section"><h4>${icon('scale')}관련 법령</h4>${lawCards(state.statutes, 'statute')}</div>
        <div class="panel-section"><h4>${icon('book')}참고 판례</h4>${lawCards(state.precedents, 'prec')}</div>
      </div>
      <div class="case-panel-foot">
        <button class="btn btn-primary btn-lg btn-block" id="toParty" ${state.crime_type ? '' : 'disabled'}>${icon('form')}고소장 작성하기</button>
        <div class="tiny muted" style="text-align:center;margin-top:8px">${state.ready ? '필수 항목이 모두 모였어요.' : state.crime_type ? `필수 항목 ${state.missing.length}개가 더 필요해요.` : '사건 유형이 정해지면 진행할 수 있어요.'}</div>
      </div>`;
    // 메시지마다 다시 그려도 보던 위치와 펼친 조문 카드는 유지한다
    $('.case-panel-body', panel).scrollTop = keepScroll;
    $$('details.law-card', panel).forEach((d) => { if (openCards.has($('b', d).textContent)) d.open = true; });
    const pill = $('#progressPill');
    if (pill) pill.innerHTML = `${icon('list')}${crime ? `${done}/${req}` : '정리'}`;

    $('#crimeSelect', panel).addEventListener('change', async (e) => {
      try {
        const r = await api(`/cases/${S.case.id}/facts`, { method: 'PUT', body: { crime_type: e.target.value || null, facts: {} } });
        S.case.state = r.state;
        renderPanel(r.state);
      } catch (err) { toast(err.message, 'error'); }
    });
    $$('[data-fact]', panel).forEach((b) => b.addEventListener('click', () => editFact(b.dataset.fact)));
    $('#toParty', panel).addEventListener('click', proceedToParty);
    const close = $('#panelClose', panel);
    if (close) close.addEventListener('click', () => togglePanel(false));
  }

  function togglePanel(open) {
    const p = $('#casePanel');
    if (!p) return;
    p.classList.toggle('open', open);
    let scrim = $('.panel-scrim');
    if (open && !scrim) {
      scrim = document.createElement('div');
      scrim.className = 'panel-scrim';
      scrim.addEventListener('click', () => togglePanel(false));
      document.body.appendChild(scrim);
    } else if (!open && scrim) scrim.remove();
    document.body.style.overflow = open ? 'hidden' : '';
  }

  function factInputHtml(k, value, id = 'factInput') {
    const d = factDef(k);
    if (d.type === 'choice') {
      return `<div class="seg" id="${id}" data-choice="${esc(k)}">${d.options.map((o) => `<button type="button" aria-pressed="${o === value}" data-v="${esc(o)}">${esc(o)}</button>`).join('')}</div>`;
    }
    if (d.type === 'datetime') {
      return `<input class="input" id="${id}" value="${esc(value || '')}" placeholder="예: 2025-03-02 15:00 (모르면 대략적으로)">`;
    }
    if (d.type === 'long') return `<textarea class="textarea" id="${id}" rows="5" placeholder="${esc(d.hint || '')}">${esc(value || '')}</textarea>`;
    return `<input class="input" id="${id}" value="${esc(value || '')}" placeholder="${esc(d.hint || '')}">`;
  }
  function readChoice(el) { const on = $('[aria-pressed="true"]', el); return on ? on.dataset.v : ''; }
  function wireChoices(root) {
    $$('.seg[data-choice]', root).forEach((seg) => seg.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      $$('button', seg).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      seg.dispatchEvent(new Event('change', { bubbles: true }));
    }));
  }

  function editFact(k) {
    const d = factDef(k);
    const v = S.case.state.facts[k] || '';
    openSheet(`<h3>${esc(d.label)}</h3><p class="muted small" style="margin:0 0 14px">${esc(d.ask || '')}</p>
      ${factInputHtml(k, v)}
      <div class="sheet-actions">${v ? `<button class="btn btn-danger-ghost" data-a="clear">${icon('trash')}비우기</button><span class="grow"></span>` : ''}
      <button class="btn btn-outline" data-a="cancel">취소</button><button class="btn btn-primary" data-a="save">저장</button></div>`, {
      onMount: (s) => {
        wireChoices(s);
        const input = $('#factInput', s);
        if (!isTouch && input && input.focus) input.focus();
        s.addEventListener('click', async (e) => {
          const a = e.target.closest('[data-a]');
          if (!a) return;
          if (a.dataset.a === 'cancel') return closeSheet();
          const val = a.dataset.a === 'clear' ? '' : (input.classList.contains('seg') ? readChoice(input) : input.value.trim());
          try {
            const r = await api(`/cases/${S.case.id}/facts`, { method: 'PUT', body: { facts: { [k]: val } } });
            S.case.state = r.state;
            closeSheet();
            renderPanel(r.state, [k]);
            toast('사건 정리를 고쳤습니다.', 'ok');
          } catch (err) { toast(err.message, 'error'); }
        });
      },
    });
  }

  async function proceedToParty() {
    const st = S.case.state;
    if (!st.crime_type) return toast('사건 유형을 먼저 정해 주세요.', 'error');
    if (st.missing.length) {
      const list = st.missing.map((k) => `<li>${esc(factDef(k).label)}</li>`).join('');
      const ok = await confirmSheet({
        title: '아직 비어 있는 필수 항목이 있어요',
        message: `<p style="margin:0 0 8px">아래 내용이 빠지면 고소장의 설득력이 떨어질 수 있어요.</p><ul class="list-clean">${list}</ul>`,
        ok: '그래도 진행', cancel: '더 이야기하기',
      });
      if (!ok) return;
    }
    togglePanel(false);
    go(`#/party/${S.case.id}`);
  }

  // ── 채팅 ────────────────────────────────────────────────────────────────
  function msgHtml(m) {
    if (m.role === 'user') return `<div class="msg user"><div class="bubble">${esc(m.content)}</div></div>`;
    return `<div class="msg ai"><div class="avatar">${icon('scale')}</div><div class="bubble">${rich(m.content)}</div></div>`;
  }

  function renderChat() {
    const c = S.case;
    app.innerHTML = `<div class="chat-layout view">
      <section class="chat-main">
        <div class="chat-bar">
          <a class="btn btn-ghost btn-sm btn-icon" href="#/" aria-label="처음으로">${icon('left')}</a>
          <div class="grow"><h2>AI 고소장 상담</h2><div class="tiny muted" id="chatSub">${c.state.crime_label ? esc(c.state.crime_label) : '사건 유형을 파악하는 중'}</div></div>
          <button class="btn btn-soft btn-sm progress-pill" id="progressPill"></button>
        </div>
        <div class="chat-scroll" id="chatScroll"><div class="chat-inner" id="chatInner">${c.messages.map(msgHtml).join('')}</div></div>
        <div class="composer-wrap"><div class="composer-inner">
          <div class="suggestions" id="suggestions"></div>
          <form class="composer" id="composer">
            <textarea id="chatInput" rows="1" placeholder="있었던 일을 편하게 적어 주세요" aria-label="메시지"></textarea>
            <button class="send" id="sendBtn" type="submit" aria-label="보내기" disabled>${icon('send')}</button>
          </form>
          <div class="composer-note">AI는 실수할 수 있어요. 사건 정리에서 내용을 확인하고 직접 고칠 수 있습니다.</div>
        </div></div>
      </section>
      <aside class="case-panel" id="casePanel" aria-label="사건 정리"></aside>
    </div>`;
    renderPanel(c.state);
    renderSuggestions(c.state.suggestions);
    $('#progressPill').addEventListener('click', () => togglePanel(true));
    scrollChat(false);

    const input = $('#chatInput');
    const send = $('#sendBtn');
    const autosize = () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 200) + 'px'; send.disabled = S.busy || !input.value.trim(); };
    input.addEventListener('input', autosize);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !isTouch) { e.preventDefault(); $('#composer').requestSubmit(); }
    });
    $('#composer').addEventListener('submit', (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text || S.busy) return;
      input.value = '';
      autosize();
      sendChat(text);
    });
    if (!isTouch) input.focus();
  }

  function renderSuggestions(list) {
    const box = $('#suggestions');
    if (!box) return;
    box.innerHTML = (list || []).map((s) => `<button type="button" class="chip">${esc(s)}</button>`).join('');
    $$('.chip', box).forEach((b) => b.addEventListener('click', () => { if (!S.busy) sendChat(b.textContent); }));
  }

  function scrollChat(smooth = true) {
    const el = $('#chatScroll');
    if (!el) return;
    el.style.scrollBehavior = smooth ? 'smooth' : 'auto';
    el.scrollTop = el.scrollHeight;
  }

  async function sendChat(text) {
    S.busy = true;
    const inner = $('#chatInner');
    $('#sendBtn').disabled = true;
    renderSuggestions([]);
    inner.insertAdjacentHTML('beforeend', msgHtml({ role: 'user', content: text }));
    inner.insertAdjacentHTML('beforeend', `<div class="msg ai" id="pending"><div class="avatar">${icon('scale')}</div><div class="bubble"><span class="thinking"><span class="dots"><i></i><i></i><i></i></span><span id="pendingText">생각하고 있어요</span></span></div></div>`);
    scrollChat();
    let reply = '';
    let bubble = null;
    let failed = false;
    try {
      await ndjson(`/cases/${S.case.id}/chat`, { message: text }, (ev) => {
        if (ev.type === 'status') {
          const t = $('#pendingText'); if (t) t.textContent = ev.text;
        } else if (ev.type === 'state') {
          S.case.state = ev;
          renderPanel(ev, ev.changed || []);
          $('#chatSub').textContent = ev.crime_label || '사건 유형을 파악하는 중';
          const n = (ev.changed || []).filter((k) => k !== 'crime_type').length;
          if (n) {
            $('#pending').insertAdjacentHTML('beforebegin', `<div class="fact-toast">${icon('check')}사건 정리에 ${n}개 항목을 반영했어요</div>`);
          }
          const pt = $('#pendingText'); if (pt) pt.textContent = '답변을 쓰고 있어요';
        } else if (ev.type === 'delta') {
          if (!bubble) { bubble = $('#pending .bubble'); bubble.classList.add('cursor'); }
          reply += ev.text;
          bubble.innerHTML = rich(reply);
          bubble.classList.add('cursor');
          scrollChat(false);
        } else if (ev.type === 'error') {
          failed = true;
          const p = $('#pending');
          p.classList.add('error');
          p.querySelector('.bubble').textContent = ev.message;
        }
      });
    } catch (e) {
      failed = true;
      const p = $('#pending');
      if (p) { p.classList.add('error'); p.querySelector('.bubble').textContent = e.message; }
    }
    const p = $('#pending');
    if (p) { p.removeAttribute('id'); const b = p.querySelector('.bubble'); if (b) b.classList.remove('cursor'); }
    if (failed) {
      // 실패하면 입력을 되돌려 다시 보낼 수 있게
      const input = $('#chatInput');
      if (input && !input.value) { input.value = text; input.dispatchEvent(new Event('input')); }
    } else {
      S.case.messages.push({ role: 'user', content: text }, { role: 'assistant', content: reply });
    }
    S.busy = false;
    renderSuggestions(S.case.state.suggestions);
    const input = $('#chatInput');
    if (input) { $('#sendBtn').disabled = !input.value.trim(); if (!isTouch) input.focus(); }
    scrollChat();
  }

  // ── 양식 모드 ────────────────────────────────────────────────────────────
  const FORM_GROUPS = [
    { title: '언제, 어디서', icon: 'clock', keys: ['incident_datetime', 'incident_place'] },
    { title: '무슨 일이 있었나요', icon: 'chat', keys: ['relationship', 'background', 'contact_channel', 'item_name', 'trade_url', 'company_name', 'company_relation', 'contract_details', 'contract_document', 'counterparty_capacity', 'actual_performance', 'other_contractors', 'insurance_reason', 'insurance_payment', 'court', 'claim', 'false_reason', 'lawsuit_motive', 'deception', 'belief_reason'] },
    { title: '피해 내용', icon: 'bank', keys: ['disposition', 'damage_amount', 'repayment', 'post_conduct'] },
    { title: '처음부터 속일 생각이었다고 볼 사정', icon: 'search', keys: ['intent_evidence', 'other_victims', 'suspect_description'] },
    { title: '증거와 기타 사항', icon: 'list', keys: ['evidence', 'additional_notes'] },
    { title: '고소 관련 확인', icon: 'shield', keys: ['settlement', 'punishment_wish', 'same_complaint', 'related_investigation'] },
  ];

  function stepper(active) {
    const steps = ['사건 유형', '사건 내용', '당사자 정보', '고소장 완성'];
    return `<div class="stepper">${steps.map((s, i) => `${i ? '<span class="bar"></span>' : ''}<span class="s ${i === active ? 'on' : i < active ? 'done' : ''}"><span class="n">${i < active ? icon('check') : i + 1}</span>${s}</span>`).join('')}</div>`;
  }

  function renderForm(step) {
    const c = S.case;
    if (step === 'type' || !c.state.crime_type) {
      app.innerHTML = `<div class="container narrow page view">${stepper(0)}
        <div class="page-head"><h1 class="page-title">어떤 사기 피해를 입으셨나요?</h1><p class="page-sub">가장 가까운 유형을 골라 주세요. 유형에 맞는 질문으로 양식을 구성합니다.</p></div>
        <div class="type-grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr))">${S.meta.crimes.map((x) => `<button class="type-card" data-type="${esc(x.id)}" aria-pressed="${x.id === c.state.crime_type}"><strong>${esc(x.label)}</strong><span>${esc(x.summary)}</span></button>`).join('')}</div>
        <div class="form-actions"><a class="btn btn-outline" href="#/">${icon('left')}처음으로</a>
          <a class="btn btn-ghost" href="#" id="toChat">${icon('chat')}잘 모르겠어요 — AI와 대화로 작성</a></div></div>`;
      $$('[data-type]', app).forEach((b) => b.addEventListener('click', async () => {
        try {
          const r = await api(`/cases/${c.id}/facts`, { method: 'PUT', body: { crime_type: b.dataset.type, facts: {} } });
          c.state = r.state;
          go(`#/form/${c.id}/facts`);
        } catch (e) { toast(e.message, 'error'); }
      }));
      $('#toChat').addEventListener('click', (e) => { e.preventDefault(); startCase('chat'); });
      return;
    }

    const crime = crimeById(c.state.crime_type);
    const fields = new Set(crime.fields);
    const required = new Set(crime.required);
    const groups = FORM_GROUPS.map((g) => ({ ...g, keys: g.keys.filter((k) => fields.has(k)) })).filter((g) => g.keys.length);
    const fieldHtml = (k) => {
      const d = factDef(k);
      const wide = d.type === 'long' || d.type === 'choice';
      return `<label class="field ${wide ? 'span-2' : ''}" data-field="${esc(k)}"><span class="field-label">${esc(d.label)}${required.has(k) ? '<span class="req">*</span>' : ''}</span>
        ${factInputHtml(k, c.state.facts[k], `f_${k}`)}${d.hint && (d.type === 'choice' || d.type === 'datetime') ? `<div class="field-hint">${esc(d.hint)}</div>` : ''}</label>`;
    };
    app.innerHTML = `<div class="container narrow page view">${stepper(1)}
      <div class="page-head row between wrap"><div><h1 class="page-title">${esc(crime.label)} 내용 입력</h1><p class="page-sub">입력한 내용은 자동으로 저장됩니다. <span class="req">*</span> 표시는 꼭 필요한 항목이에요.</p></div>
        <a class="btn btn-ghost btn-sm" href="#/form/${c.id}/type">유형 바꾸기</a></div>
      ${groups.map((g) => `<div class="card form-section"><div class="card-head"><h3>${icon(g.icon)}${esc(g.title)}</h3></div><div class="card-body grid-2">${g.keys.map(fieldHtml).join('')}</div></div>`).join('')}
      <div class="callout"><span class="i">${icon('info')}</span><div>상대방이 한 말은 <b>따옴표로 그대로</b>, 금액과 날짜는 <b>숫자로 정확히</b> 적을수록 좋은 고소장이 됩니다. 모르는 부분은 “모름”이라고 적어도 괜찮아요.</div></div>
      <div class="sticky-actions"><div class="form-actions" style="margin:0"><a class="btn btn-outline" href="#/form/${c.id}/type">${icon('left')}이전</a>
        <button class="btn btn-primary btn-lg" id="formNext">다음: 당사자 정보 ${icon('right')}</button></div></div></div>`;
    wireChoices(app);

    const dirty = {};
    const save = debounce(async () => {
      const facts = { ...dirty };
      Object.keys(dirty).forEach((k) => delete dirty[k]);
      try { const r = await api(`/cases/${c.id}/facts`, { method: 'PUT', body: { facts } }); c.state = r.state; } catch (e) { toast(e.message, 'error'); }
    }, 600);
    const valueOf = (k) => { const el = $(`#f_${CSS.escape(k)}`); return el.classList.contains('seg') ? readChoice(el) : el.value.trim(); };
    crime.fields.forEach((k) => {
      const el = $(`#f_${CSS.escape(k)}`);
      if (!el) return;
      const on = () => { dirty[k] = valueOf(k); el.removeAttribute('aria-invalid'); save(); };
      el.addEventListener(el.classList.contains('seg') ? 'change' : 'input', on);
    });
    $('#formNext').addEventListener('click', async () => {
      const missing = crime.required.filter((k) => fields.has(k) && !valueOf(k));
      missing.forEach((k) => $(`#f_${CSS.escape(k)}`).setAttribute('aria-invalid', 'true'));
      if (missing.length) {
        const first = $(`[data-field="${CSS.escape(missing[0])}"]`);
        first.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const ok = await confirmSheet({
          title: `필수 항목 ${missing.length}개가 비어 있어요`,
          message: `<ul class="list-clean">${missing.map((k) => `<li>${esc(factDef(k).label)}</li>`).join('')}</ul>`,
          ok: '그래도 진행', cancel: '채우러 가기',
        });
        if (!ok) return;
      }
      crime.fields.forEach((k) => { dirty[k] = valueOf(k); });
      try {
        const r = await api(`/cases/${c.id}/facts`, { method: 'PUT', body: { facts: { ...dirty } } });
        c.state = r.state;
        go(`#/party/${c.id}`);
      } catch (e) { toast(e.message, 'error'); }
    });
  }

  // ── 당사자 정보 ──────────────────────────────────────────────────────────
  let policeData = null;
  let postcodeLoading = null;
  function loadPostcode() {
    if (window.daum && window.daum.Postcode) return Promise.resolve();
    if (!postcodeLoading) {
      postcodeLoading = new Promise((res, rej) => {
        const s = document.createElement('script');
        s.src = 'https://t1.daumcdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js';
        s.onload = res; s.onerror = () => { postcodeLoading = null; rej(new Error('주소 검색을 불러오지 못했습니다.')); };
        document.head.appendChild(s);
      });
    }
    return postcodeLoading;
  }

  function personFields(prefix, p, required) {
    const r = required ? '<span class="req">*</span>' : '';
    const hasRrn = p && p.has_rrn;
    return `<div class="grid-2">
      <label class="field"><span class="field-label">성명${r}</span><input class="input" id="${prefix}_name" value="${esc(p.name || '')}" autocomplete="${required ? 'name' : 'off'}" ${required ? '' : 'placeholder="모르면 비워 두세요"'}></label>
      <label class="field"><span class="field-label">주민등록번호${r}</span><div class="input-group">
        <input class="input" id="${prefix}_rrn1" inputmode="numeric" maxlength="6" placeholder="앞 6자리" autocomplete="off">
        <input class="input" id="${prefix}_rrn2" type="password" inputmode="numeric" maxlength="7" placeholder="${hasRrn ? '입력한 번호 유지' : '뒤 7자리'}" autocomplete="off"></div>
        ${hasRrn ? '<div class="field-hint">이전에 입력한 번호가 있어요. 바꾸려면 새로 입력하세요.</div>' : ''}</label>
      <label class="field span-2"><span class="field-label">주소${r}</span><div class="input-group">
        <input class="input" id="${prefix}_addr1" value="${esc(p.address || '')}" placeholder="주소 검색을 눌러 주세요"><button type="button" class="btn btn-outline" data-postcode="${prefix}">${icon('search')}주소 검색</button></div>
        <input class="input" id="${prefix}_addr2" placeholder="상세 주소" style="margin-top:8px"></label>
      <label class="field"><span class="field-label">직업</span><input class="input" id="${prefix}_job" value="${esc(p.job || '')}"></label>
      <label class="field"><span class="field-label">전화번호${r}</span><input class="input" id="${prefix}_phone" value="${esc(p.phone || '')}" inputmode="tel" placeholder="010-0000-0000" autocomplete="${required ? 'tel' : 'off'}"></label>
      <label class="field span-2"><span class="field-label">이메일</span><input class="input" id="${prefix}_email" type="email" value="${esc(p.email || '')}" autocomplete="${required ? 'email' : 'off'}"></label>
    </div>`;
  }

  async function renderParty() {
    const c = S.case;
    const party = c.party || {};
    const comp = party.complainant || {};
    const susp = party.suspect || {};
    app.innerHTML = `<div class="container narrow page view">${stepper(2)}
      <div class="page-head"><h1 class="page-title">당사자 정보</h1><p class="page-sub">이 정보는 고소장 양식의 인적사항 칸에만 들어가며, <b>AI에게는 보내지 않습니다.</b></p></div>
      <div class="card form-section"><div class="card-head"><h3>${icon('user')}고소인 (본인)</h3></div><div class="card-body">${personFields('c', comp, true)}</div></div>
      <div class="card form-section"><div class="card-head"><h3>${icon('user')}피고소인 (상대방)</h3><span class="badge">아는 것만</span></div><div class="card-body">
        <p class="muted small" style="margin:0 0 16px">모르는 칸은 비워 두세요. 닉네임·계좌 명의 등 사건 정리에 적은 특정 정보는 ‘기타사항’에 자동으로 들어갑니다.</p>${personFields('s', susp, false)}</div></div>
      <div class="card form-section"><div class="card-head"><h3>${icon('bank')}제출 정보</h3></div><div class="card-body grid-2">
        <label class="field"><span class="field-label">시·도 경찰청<span class="req">*</span></span><select class="select" id="sido"><option value="">불러오는 중…</option></select></label>
        <label class="field"><span class="field-label">제출할 경찰서<span class="req">*</span></span><select class="select" id="station" disabled><option value="">경찰청을 먼저 고르세요</option></select></label>
        <label class="field"><span class="field-label">고소일자<span class="req">*</span></span><input class="input" type="date" id="filingDate" value="${esc(party.filing_date || today())}" max="9999-12-31"></label>
        <div class="field span-2"><div class="field-hint" style="margin:0">거주지 또는 사건 발생지 관할 경찰서에 제출하는 것이 일반적이며, 가까운 경찰서 민원실에 제출해도 됩니다.</div></div>
      </div></div>
      <div class="card card-pad form-section stack">
        <label class="check"><input type="checkbox" id="agree1"><span>AI가 작성한 고소장은 <b>법률 자문이 아닌 초안</b>이며, 제출 전에 내용을 직접 확인·수정해야 함을 이해했습니다.</span></label>
        <label class="check"><input type="checkbox" id="agree2"><span>입력한 내용은 사실이며, 허위 사실로 고소하면 <b>무고죄(형법 제156조)</b>로 처벌받을 수 있음을 알고 있습니다.</span></label>
      </div>
      <div class="sticky-actions"><div class="form-actions" style="margin:0">
        <a class="btn btn-outline" href="${c.mode === 'chat' ? `#/chat/${c.id}` : `#/form/${c.id}/facts`}">${icon('left')}사건 내용으로</a>
        <button class="btn btn-primary btn-lg" id="genBtn">${icon('spark')}고소장 생성하기</button></div></div></div>`;

    // 주소 검색
    $$('[data-postcode]', app).forEach((b) => b.addEventListener('click', async () => {
      try {
        await loadPostcode();
        new window.daum.Postcode({
          oncomplete: (d) => {
            const addr = d.userSelectedType === 'R' ? d.roadAddress : d.jibunAddress;
            $(`#${b.dataset.postcode}_addr1`).value = addr + (d.buildingName ? ` (${d.buildingName})` : '');
            $(`#${b.dataset.postcode}_addr2`).focus();
          },
        }).open();
      } catch (e) { toast(e.message, 'error'); }
    }));
    // 전화번호 자동 하이픈
    $$('#c_phone, #s_phone', app).forEach((el) => el.addEventListener('input', () => {
      const n = el.value.replace(/\D/g, '').slice(0, 11);
      el.value = n.length < 4 ? n : n.length < 8 ? `${n.slice(0, 3)}-${n.slice(3)}` : `${n.slice(0, 3)}-${n.slice(3, n.length - 4)}-${n.slice(-4)}`;
    }));
    $$('[id$="_rrn1"], [id$="_rrn2"]', app).forEach((el) => el.addEventListener('input', () => {
      el.value = el.value.replace(/\D/g, '');
      if (el.id.endsWith('rrn1') && el.value.length === 6) $(`#${el.id.replace('1', '2')}`).focus();
    }));

    // 경찰서
    const sido = $('#sido');
    const station = $('#station');
    try {
      policeData = policeData || await api('/police/stations');
      sido.innerHTML = '<option value="">선택</option>' + Object.keys(policeData).map((k) => `<option>${esc(k)}</option>`).join('');
      const fillStations = () => {
        const list = policeData[sido.value] || [];
        station.disabled = !list.length;
        station.innerHTML = '<option value="">선택</option>' + list.map((s) => `<option>${esc(s.name)}</option>`).join('');
      };
      sido.addEventListener('change', fillStations);
      if (party.station) {
        const found = Object.keys(policeData).find((k) => policeData[k].some((s) => s.name === party.station));
        if (found) { sido.value = found; fillStations(); station.value = party.station; }
      }
    } catch (e) { toast('경찰서 목록을 불러오지 못했습니다.', 'error'); }

    $('#genBtn').addEventListener('click', () => {
      const get = (id) => ($(`#${id}`) ? $(`#${id}`).value.trim() : '');
      const person = (p) => {
        const r1 = get(`${p}_rrn1`), r2 = get(`${p}_rrn2`);
        return {
          name: get(`${p}_name`), rrn: r1 || r2 ? `${r1}-${r2}` : '',
          address: [get(`${p}_addr1`), get(`${p}_addr2`)].filter(Boolean).join(' '),
          job: get(`${p}_job`), phone: get(`${p}_phone`), email: get(`${p}_email`),
        };
      };
      const body = { complainant: person('c'), suspect: person('s'), station: station.value, filing_date: get('filingDate'), keep_rrn: true };
      const errs = [];
      const mark = (id, bad) => { const el = $(`#${id}`); if (el) el.setAttribute('aria-invalid', String(!!bad)); if (bad) errs.push(id); };
      mark('c_name', !body.complainant.name);
      mark('c_addr1', !get('c_addr1'));
      mark('c_phone', body.complainant.phone.replace(/\D/g, '').length < 9);
      const needRrn = !(comp.has_rrn && !get('c_rrn1') && !get('c_rrn2'));
      mark('c_rrn1', needRrn && !/^\d{6}$/.test(get('c_rrn1')));
      mark('c_rrn2', needRrn && !/^\d{7}$/.test(get('c_rrn2')));
      if (!needRrn) body.complainant.rrn = '';
      const sr = [get('s_rrn1'), get('s_rrn2')];
      if (sr.some(Boolean)) { mark('s_rrn1', !/^\d{6}$/.test(sr[0])); mark('s_rrn2', !/^\d{7}$/.test(sr[1])); }
      mark('sido', !sido.value);
      mark('station', !station.value);
      if (errs.length) {
        $(`#${errs[0]}`).scrollIntoView({ behavior: 'smooth', block: 'center' });
        return toast('빨간색으로 표시된 칸을 확인해 주세요.', 'error');
      }
      if (!$('#agree1').checked || !$('#agree2').checked) return toast('안내 사항 두 가지에 동의해 주세요.', 'error');
      S.pendingParty = body;
      go(`#/generating/${c.id}`);
    });
  }

  // ── 생성 진행 ────────────────────────────────────────────────────────────
  const GEN_STEPS = [
    ['research', '관련 법령·판례 찾기'],
    ['analyze', '사기죄 구성요건 검토'],
    ['draft', '고소장 초안 작성'],
    ['review', '수사관 시각으로 교차 검토'],
    ['render', '경찰청 표준 양식 문서 만들기'],
  ];

  async function renderGenerating() {
    const c = S.case;
    if (!S.pendingParty) {
      // 새로고침 등으로 입력값이 없어졌다면 결과 또는 입력 화면으로
      return go(c.files ? `#/result/${c.id}` : `#/party/${c.id}`);
    }
    const party = S.pendingParty;
    app.innerHTML = `<div class="container view"><div class="gen-wrap"><div class="card gen-card" style="text-align:center">
      <div class="gen-orb">${icon('spark')}</div>
      <h1 class="page-title">고소장을 만들고 있어요</h1>
      <p class="page-sub">법령과 판례를 검토하며 작성하느라 1~2분 정도 걸립니다. 이 화면을 닫지 말아 주세요.</p>
      <ul class="gen-steps" style="text-align:left">${GEN_STEPS.map(([k, t]) => `<li class="wait" data-step="${k}"><span class="ic">${icon('clock')}</span><div><b>${t}</b><small></small></div></li>`).join('')}</ul>
      <div class="tiny muted" id="elapsed" style="margin-top:14px"></div>
      <div id="genErr"></div></div></div></div>`;
    const t0 = Date.now();
    const timer = setInterval(() => { const e = $('#elapsed'); if (!e) return clearInterval(timer); e.textContent = `${Math.floor((Date.now() - t0) / 1000)}초 경과`; }, 1000);
    const setStep = (k, cls, detail) => {
      const li = $(`[data-step="${k}"]`);
      if (!li) return;
      li.className = cls;
      li.querySelector('.ic').innerHTML = cls === 'run' ? '<span class="spin"></span>' : cls === 'ok' ? icon('check') : cls === 'fail' ? icon('x') : icon('clock');
      if (detail != null) li.querySelector('small').textContent = detail;
    };
    let done = false;
    let running = null;
    const fail = (msg) => {
      if (running) setStep(running, 'fail');
      $('#genErr').innerHTML = `<div class="issue error" style="margin-top:18px;text-align:left"><span class="i">${icon('alert')}</span><div>${esc(msg)}</div></div>
        <div class="row" style="justify-content:center;margin-top:14px"><a class="btn btn-outline" href="#/party/${c.id}">정보 수정</a><button class="btn btn-primary" id="retry">${icon('refresh')}다시 시도</button></div>`;
      $('#retry').addEventListener('click', () => { S.pendingParty = party; renderGenerating(); });
    };
    try {
      await ndjson(`/cases/${c.id}/generate`, party, (ev) => {
        if (ev.type === 'step') {
          if (ev.status === 'start') { running = ev.step; setStep(ev.step, 'run'); } else setStep(ev.step, 'ok', ev.detail || '');
        } else if (ev.type === 'result') {
          done = true;
          Object.assign(c, { analysis: ev.analysis, draft: ev.draft, review: ev.review, files: ev.files });
        } else if (ev.type === 'error') {
          fail(ev.message);
        }
      });
    } catch (e) {
      fail(e.message);
    }
    clearInterval(timer);
    if (done) {
      S.pendingParty = null;
      toast('고소장 초안이 완성되었습니다.', 'ok');
      setTimeout(() => go(`#/result/${c.id}`), 500);
    }
  }

  // ── 결과 ────────────────────────────────────────────────────────────────
  const SECTION_LABELS = { suspect_other: '피고소인 기타사항', purpose: '3. 고소취지', facts: '4. 범죄사실', reasons: '5. 고소이유', evidence: '6. 증거자료', others: '8. 기타' };
  const STATUS_BADGE = { '충족': 'badge-success', '보완필요': 'badge-warn', '불명확': '' };

  function renderResult(tab) {
    const c = S.case;
    if (!c.files || !c.draft) return go(`#/party/${c.id}`);
    tab = tab || sessionStorage.getItem('resultTab') || 'doc';
    const a = c.analysis || {};
    const issues = (c.review && c.review.issues) || [];
    const fileUrl = (k, dl) => `/api/files/${c.id}/${k}?v=${encodeURIComponent(c.files.token)}${dl ? '&download=1' : ''}`;
    app.innerHTML = `<div class="container page view">
      <div class="card result-hero">
        <div class="ok">${icon('check')}</div>
        <div class="grow"><h1 class="page-title" style="font-size:22px">고소장 초안이 완성되었습니다</h1>
          <div class="muted small">${esc(a.offense || '')} · ${esc(c.state.crime_label || '')} · 고소인 서명·날인 후 제출하세요</div></div>
        <div class="row wrap">
          ${c.files.pdf ? `<a class="btn btn-primary" href="${fileUrl('pdf', true)}">${icon('download')}PDF</a>` : ''}
          <a class="btn btn-outline" href="${fileUrl('docx', true)}">${icon('download')}Word</a>
          <button class="btn btn-outline" id="mailBtn">${icon('mail')}메일로 받기</button>
        </div>
      </div>
      <div class="tabs" role="tablist">
        <button role="tab" data-tab="doc" aria-selected="${tab === 'doc'}">${icon('form')}고소장</button>
        <button role="tab" data-tab="legal" aria-selected="${tab === 'legal'}">${icon('scale')}법률 검토</button>
        <button role="tab" data-tab="guide" aria-selected="${tab === 'guide'}">${icon('list')}제출 안내</button>
      </div>
      <div id="tabBody"></div>
    </div>`;
    $$('[data-tab]', app).forEach((b) => b.addEventListener('click', () => { sessionStorage.setItem('resultTab', b.dataset.tab); renderResult(b.dataset.tab); }));
    $('#mailBtn').addEventListener('click', mailSheet);
    const body = $('#tabBody');
    if (tab === 'legal') return renderLegal(body, a);
    if (tab === 'guide') return renderGuide(body, a);

    // 고소장 탭
    const errs = issues.filter((i) => i.level === 'error');
    body.innerHTML = `<div class="result-grid">
      <div>
        ${issues.length ? `<div class="card card-pad" style="margin-bottom:16px"><h3 style="font-size:15.5px;font-weight:800;margin-bottom:12px">확인이 필요한 부분 ${issues.length}건</h3>
          ${issues.map((i) => `<div class="issue ${i.level === 'error' ? 'error' : ''}"><span class="i">${icon('alert')}</span><div><b>${esc(i.section)}</b> — ${esc(i.problem)}${i.fix ? `<div class="muted small">${esc(i.fix)}</div>` : ''}</div></div>`).join('')}</div>` : ''}
        <div class="card" id="docCard">
          <div class="card-head"><h3>${icon('form')}고소장 내용</h3><button class="btn btn-soft btn-sm" id="editBtn">${icon('pencil')}문장 고치기</button></div>
          ${Object.keys(SECTION_LABELS).map((k) => `<div class="doc-section" data-sec="${k}"><h4>${SECTION_LABELS[k]}</h4><div class="doc-text ${c.draft[k] ? '' : 'empty'}">${c.draft[k] ? esc(c.draft[k]) : '(비어 있음)'}</div></div>`).join('')}
          <div class="card-body" id="editActions" hidden style="border-top:1px solid var(--line)"><div class="row between wrap"><span class="muted small">고친 내용으로 Word·PDF 문서를 다시 만듭니다. AI는 다시 호출하지 않아요.</span>
            <div class="row"><button class="btn btn-outline" id="cancelEdit">취소</button><button class="btn btn-primary" id="saveEdit">${icon('refresh')}문서 다시 만들기</button></div></div></div>
        </div>
        <div class="row wrap" style="margin-top:16px">
          <a class="btn btn-ghost" href="#/party/${c.id}">${icon('user')}당사자 정보 수정 후 다시 생성</a>
          <a class="btn btn-ghost" href="${c.mode === 'chat' ? `#/chat/${c.id}` : `#/form/${c.id}/facts`}">${icon('chat')}사건 내용 보완하기</a>
          <button class="btn btn-ghost" id="newBtn">${icon('plus')}새 고소장</button>
        </div>
      </div>
      <div class="card preview-frame">${c.files.pdf ? `<iframe title="고소장 미리보기" src="${fileUrl('pdf')}#view=FitH"></iframe>` : `<div class="card-body muted">PDF 미리보기를 만들지 못했습니다. Word 파일을 받아 확인해 주세요.</div>`}</div>
    </div>`;
    if (errs.length) $('#docCard').scrollIntoView({ block: 'nearest' });

    $('#editBtn').addEventListener('click', () => {
      $$('.doc-section', body).forEach((sec) => {
        const k = sec.dataset.sec;
        sec.querySelector('.doc-text').outerHTML = `<textarea class="textarea" data-edit="${k}" rows="${Math.max(3, Math.min(18, (c.draft[k] || '').split('\n').length + 2))}">${esc(c.draft[k] || '')}</textarea>`;
      });
      $('#editActions').hidden = false;
      $('#editBtn').hidden = true;
    });
    $('#cancelEdit') && $('#cancelEdit').addEventListener('click', () => renderResult('doc'));
    $('#saveEdit') && $('#saveEdit').addEventListener('click', async (e) => {
      const sections = {};
      $$('[data-edit]', body).forEach((t) => { sections[t.dataset.edit] = t.value; });
      e.target.disabled = true;
      try {
        const r = await api(`/cases/${c.id}/render`, { method: 'POST', body: { sections } });
        Object.assign(c, { files: r.files, review: r.review, draft: r.draft });
        toast('고친 내용으로 문서를 다시 만들었습니다.', 'ok');
        renderResult('doc');
      } catch (err) { toast(err.message, 'error'); e.target.disabled = false; }
    });
    $('#newBtn').addEventListener('click', async () => {
      if (!(await confirmSheet({ title: '새 고소장을 작성할까요?', message: '지금 고소장은 보존 기간 동안 서버에 남아 있지만, 이 기기에서 바로 이어서 열 수는 없게 됩니다. 필요하면 먼저 파일을 받아 두세요.', ok: '새로 작성' }))) return;
      store.clear();
      S.case = null;
      go('#/');
    });
  }

  function renderLegal(body, a) {
    const st = S.case.state;
    body.innerHTML = `<div class="stack" style="max-width:860px">
      <div class="card"><div class="card-head"><h3>${icon('scale')}적용 법조</h3></div><div class="card-body">
        ${(a.applicable || []).map((x) => {
          const full = (a.statutes || []).find((s) => s.id === x.id) || {};
          return `<details class="law-card" open><summary><div class="t"><b>${esc(x.label)} <span>(${esc(x.title)})</span></b><span>${esc(x.why)}</span></div>${icon('down').replace('class="i"', 'class="i chev"')}</summary>
            <div class="law-text">${esc(full.text || '')}<div class="law-meta"><span>시행 ${esc(fmtDate(full.effective))}</span><a href="${esc(x.url)}" target="_blank" rel="noopener">국가법령정보센터 원문 ${icon('ext')}</a></div></div></details>`;
        }).join('') || '<p class="muted">적용 법조를 정하지 못했습니다.</p>'}
      </div></div>
      <div class="card"><div class="card-head"><h3>${icon('list')}구성요건 검토</h3></div><div class="card-body" style="overflow-x:auto">
        <table class="el-table"><thead><tr><th>요건</th><th>판단</th><th>근거</th><th>보완 방법</th></tr></thead><tbody>
        ${(a.elements || []).map((e) => `<tr><td>${esc(e.name)}</td><td><span class="badge ${STATUS_BADGE[e.status] || ''}">${esc(e.status)}</span></td><td>${esc(e.basis || '-')}</td><td class="muted">${esc(e.advice || '-')}</td></tr>`).join('')}
        </tbody></table></div></div>
      ${a.civil_risk ? `<div class="callout warn"><span class="i">${icon('alert')}</span><div><b>민사 사건으로 판단될 위험</b><div>${esc(a.civil_risk)}</div></div></div>` : ''}
      <div class="grid-2">
        <div class="card card-pad"><h3 style="font-size:15px;font-weight:800;margin-bottom:10px;color:var(--success)">유리한 사정</h3><ul class="list-clean small">${(a.strengths || []).map((x) => `<li>${esc(x)}</li>`).join('') || '<li class="muted">-</li>'}</ul></div>
        <div class="card card-pad"><h3 style="font-size:15px;font-weight:800;margin-bottom:10px;color:var(--warn)">보완할 사정</h3><ul class="list-clean small">${(a.weaknesses || []).map((x) => `<li>${esc(x)}</li>`).join('') || '<li class="muted">-</li>'}</ul></div>
      </div>
      <div class="card card-pad"><h3 style="font-size:15px;font-weight:800;margin-bottom:10px">${icon('list')} 준비하면 좋은 증거</h3><ul class="list-clean">${(a.evidence_tips || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>
      ${a.limitation ? `<div class="callout"><span class="i">${icon('clock')}</span><div><b>공소시효 (참고)</b><div>${esc(a.limitation)}</div></div></div>` : ''}
      <div class="card"><div class="card-head"><h3>${icon('book')}참고 판례</h3><span class="muted tiny">국가법령정보센터 원문</span></div><div class="card-body">${lawCards(a.precedents || [], 'prec')}</div></div>
      <p class="tiny muted">이 검토는 입력한 사실관계를 바탕으로 AI가 작성한 참고 자료이며, 법률 자문을 대신하지 않습니다. 사건이 복잡하거나 피해액이 크다면 변호사 또는 대한법률구조공단(국번 없이 132)의 상담을 받아 보세요.</p>
    </div>`;
  }

  function renderGuide(body, a) {
    const party = S.case.party || {};
    const proc = (a.procedure || []).concat(a.statutes || []);
    const law = (id) => proc.find((s) => s.id === id);
    const card = (s, sub) => s ? `<details class="law-card"><summary><div class="t"><b>${esc(s.label)} <span>(${esc(s.title)})</span></b><span>${esc(sub)}</span></div>${icon('down').replace('class="i"', 'class="i chev"')}</summary><div class="law-text">${esc(s.text)}<div class="law-meta"><span>시행 ${esc(fmtDate(s.effective))}</span><a href="${esc(s.url)}" target="_blank" rel="noopener">원문 ${icon('ext')}</a></div></div></details>` : '';
    body.innerHTML = `<div class="stack" style="max-width:860px">
      <div class="card card-pad"><h3 class="section-title">제출 순서</h3><ol class="guide-steps">
        <li><b>내용 확인·수정</b><p>‘고소장’ 탭에서 사실관계와 날짜·금액을 다시 확인하세요. Word 파일로 받아 직접 고쳐도 됩니다.</p></li>
        <li><b>출력 후 서명·날인</b><p>고소인 란에 직접 서명하거나 도장을 찍어야 합니다. 제출일도 확인하세요.</p></li>
        <li><b>증거자료 준비</b><p>‘6. 증거자료’에 적은 자료의 사본(이체확인증, 대화 캡처 출력물 등)을 함께 준비하세요. 원본은 본인이 보관합니다.</p></li>
        <li><b>경찰서 제출</b><p>${party.station ? `선택한 <b>${esc(party.station)}</b> 또는 ` : ''}가까운 경찰서 민원실에 신분증을 지참해 방문 제출하세요. 온라인 거래 사기 등 사이버 범죄는 경찰청 사이버범죄 신고시스템(ECRM)으로 신고할 수도 있습니다.</p></li>
        <li><b>접수 후 진행</b><p>접수 후 담당 수사관이 배정되며, 고소인 진술 조사를 위해 연락이 올 수 있습니다.</p></li>
      </ol></div>
      <div class="card"><div class="card-head"><h3>${icon('book')}관련 절차 법령</h3><span class="muted tiny">국가법령정보센터 원문</span></div><div class="card-body">
        ${card(law('001671-237'), '고소는 서면 또는 구술로 합니다')}
        ${card(law('001671-257'), '고소 사건의 처리 기간')}
        ${card(law('001671-249'), '공소시효 기간')}
        ${card(law('001215-25'), '형사재판에서 피해 배상을 명령하는 제도')}
        ${card(law('001215-26'), '배상명령을 신청하는 방법')}
        ${card(law('001692-156'), '허위 고소에 대한 처벌')}
      </div></div>
      <div class="callout"><span class="i">${icon('info')}</span><div><b>피해금 돌려받기</b><div>형사재판에서 법원에 배상명령을 신청하면 별도 민사소송 없이 피해금 배상 판결을 받을 수도 있습니다(소송촉진 등에 관한 특례법 제25조·제26조). 보이스피싱 피해라면 즉시 112와 송금한 은행에 지급정지를 요청하세요.</div></div></div>
      <div class="callout warn"><span class="i">${icon('alert')}</span><div><b>무고죄 주의</b><div>사실과 다른 내용으로 고소하면 형법 제156조의 무고죄로 처벌받을 수 있습니다. 모르는 부분은 추측하지 말고 ‘불상’ 또는 ‘모름’으로 적으세요.</div></div></div>
      <div class="card card-pad row between wrap"><div><b>개인정보 삭제</b><div class="muted small">입력한 정보와 문서는 72시간 후 자동으로 삭제됩니다. 지금 바로 지울 수도 있어요.</div></div>
        <button class="btn btn-danger-ghost" id="delBtn">${icon('trash')}지금 삭제</button></div>
    </div>`;
    $('#delBtn').addEventListener('click', async () => {
      if (!(await confirmSheet({ title: '모든 정보를 삭제할까요?', message: '대화·사건 정리·당사자 정보·생성된 문서가 서버에서 즉시 삭제되며 되돌릴 수 없습니다.', ok: '삭제', danger: true }))) return;
      try { await api(`/cases/${S.case.id}`, { method: 'DELETE' }); } catch (e) {}
      store.clear();
      S.case = null;
      toast('삭제했습니다.', 'ok');
      go('#/');
    });
  }

  function mailSheet() {
    const c = S.case;
    const email = (c.party && c.party.complainant && c.party.complainant.email) || '';
    openSheet(`<h3>메일로 받기</h3><p class="muted small" style="margin:0 0 16px">Word 파일을 첨부해 보내 드립니다.</p>
      <label class="field"><span class="field-label">받는 주소</span><input class="input" id="mailTo" type="email" value="${esc(email)}" placeholder="name@example.com"></label>
      <div class="field"><span class="field-label">용도</span><div class="seg" id="mailKind" data-choice="k"><button type="button" aria-pressed="true" data-v="self">본인 보관용</button><button type="button" aria-pressed="false" data-v="submit">제출용(기관 등)</button></div></div>
      <div class="sheet-actions"><button class="btn btn-outline" data-a="no">취소</button><button class="btn btn-primary" data-a="send">${icon('send')}보내기</button></div>`, {
      onMount: (s) => {
        wireChoices(s);
        s.addEventListener('click', async (e) => {
          const a = e.target.closest('[data-a]');
          if (!a) return;
          if (a.dataset.a === 'no') return closeSheet();
          a.disabled = true;
          try {
            await api(`/cases/${c.id}/email`, { method: 'POST', body: { to: $('#mailTo', s).value.trim(), kind: readChoice($('#mailKind', s)) } });
            closeSheet();
            toast('메일을 보냈습니다.', 'ok');
          } catch (err) { toast(err.message, 'error'); a.disabled = false; }
        });
      },
    });
  }

  route();
})();
