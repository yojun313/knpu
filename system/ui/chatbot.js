// KNPU 연구실 챗봇 위젯 — 오른쪽 아래 동그라미 버튼 (모든 사이트 공용, 고소장 생성기 제외)
//  - 홈페이지: "홈페이지 안내"(외부인용) 기본, 구성원이 로그인하면 "구성원용"으로 토글
//  - 그 밖의 사이트: 구성원용만 (로그인 필요 — 공통 로그인 모듈의 세션 쿠키로 확인)
//  - 로그인하면: 대화를 여러 개 만들고 전환할 수 있고 모두 서버에 저장된다(다른 사이트 · 기기에서도 이어짐).
//  - 로그인하지 않으면: 대화는 이 브라우저에만 남는다.
(function () {
  'use strict';
  if (window.__knpuChatbot) return;
  window.__knpuChatbot = true;
  var API = '/shared-ui/chatbot/api';
  var ANON_KEY = 'knpu_chatbot_public_v1', MODE_KEY = 'knpu_chatbot_mode', OPEN_KEY = 'knpu_chatbot_open', ACTIVE_KEY = 'knpu_chatbot_active_';

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { } }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  var ICON = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/><path d="M8.5 11h.01M12 11h.01M15.5 11h.01"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    spark: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.9 5.6L19.5 9.5l-5.6 1.9L12 17l-1.9-5.6L4.5 9.5l5.6-1.9z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" opacity=".7"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
    list: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>',
  };
  var SUGGEST = {
    public: ['연구원은 어떤 연구를 하나요?', '대학원 입학 지원 자격과 일정 알려줘', '최근 발표한 논문을 알려줘', '연구실에서 운영하는 시스템은 뭐가 있어?'],
    member: ['KEMKIM에서 약한 신호 AI 해석은 어떻게 써?', '크롤러에서 새 수집 작업을 추가하는 방법', '통계 분석 AI 리포트는 어떤 근거로 만들어져?', '새 서비스를 PM2에 등록하려면?'],
  };

  var state = {
    cfg: null, mode: 'public', open: false, view: 'chat',
    convs: [],          // 로그인: 현재 모드의 대화 목록
    active: null,       // 로그인: 열어 둔 대화 {id, title, messages}
    anon: [],           // 비로그인: 브라우저에 저장된 대화
    pollTimer: null, tick: null,
  };
  try { state.anon = JSON.parse(lsGet(ANON_KEY) || '[]') || []; } catch (e) { state.anon = []; }

  // ── DOM ─────────────────────────────────────────────────────────────────
  var root = el('div', 'kcb');
  root.innerHTML =
    '<button type="button" class="kcb-fab" aria-label="연구실 AI 챗봇 열기" aria-expanded="false">' + ICON.chat + '<span class="kcb-dot"></span></button>' +
    '<div class="kcb-panel" role="dialog" aria-label="연구실 AI 챗봇" hidden>' +
      '<div class="kcb-head"><div class="kcb-avatar">' + ICON.spark + '</div>' +
        '<div class="kcb-title"><b data-title>FPEI AI 도우미</b><span data-sub></span></div>' +
        '<button type="button" class="kcb-hbtn" data-list title="대화 목록" aria-label="대화 목록">' + ICON.list + '</button>' +
        '<button type="button" class="kcb-hbtn" data-new title="새 대화" aria-label="새 대화">' + ICON.plus + '</button>' +
        '<button type="button" class="kcb-hbtn" data-close title="닫기" aria-label="닫기">' + ICON.close + '</button></div>' +
      '<div class="kcb-modes" role="tablist" hidden><button type="button" data-mode="public">홈페이지 안내</button><button type="button" data-mode="member">구성원용</button></div>' +
      '<div class="kcb-log" aria-live="polite"></div>' +
      '<form class="kcb-compose"><textarea rows="1" maxlength="2000" placeholder="무엇이든 물어보세요" title="Enter 전송 · Shift+Enter 줄바꿈" aria-label="질문"></textarea>' +
        '<button type="submit" class="kcb-send" aria-label="보내기">' + ICON.send + '</button></form>' +
      '<div class="kcb-foot" data-foot></div>' +
    '</div>';
  var fab = root.querySelector('.kcb-fab'), panel = root.querySelector('.kcb-panel'), log = root.querySelector('.kcb-log');
  var input = root.querySelector('textarea'), sendBtn = root.querySelector('.kcb-send'), form = root.querySelector('form');
  var modes = root.querySelector('.kcb-modes'), listBtn = root.querySelector('[data-list]');

  function loggedIn() { return !!(state.cfg && state.cfg.user); }
  function homepageOrigin() {
    if (state.cfg && state.cfg.public) return '';
    var s = window.KNPU_SERVICES && window.KNPU_SERVICES.services && window.KNPU_SERVICES.services.homepage;
    return 'https://' + ((s && s.prodDomain) || 'knpu.re.kr');
  }
  function loginUrl() {
    try { if (window.KNPU && KNPU.loginUrl) return KNPU.loginUrl(); } catch (e) { }
    return homepageOrigin() + '/login?redirect=' + encodeURIComponent(location.href);
  }

  // ── 간단한 마크다운 (먼저 전부 이스케이프하고 형식만 되살린다) ─────────────────
  function inline(s) {
    return s.replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|\/[^)\s]*)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }
  function md(text) {
    var lines = esc(text).split('\n'), html = '', list = null, para = [], code = null;
    function fp() { if (para.length) { html += '<p>' + inline(para.join('<br>')) + '</p>'; para = []; } }
    function fl() { if (list) { html += '</' + list + '>'; list = null; } }
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i], m;
      if (/^\s*```/.test(line)) {
        if (code === null) { fp(); fl(); code = []; } else { html += '<pre><code>' + code.join('\n') + '</code></pre>'; code = null; }
        continue;
      }
      if (code !== null) { code.push(line); continue; }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        fp(); fl();
        var cells = function (l) { return l.trim().replace(/^\||\|$/g, '').split('|').map(function (c) { return inline(c.trim()); }); };
        html += '<table><thead><tr>' + cells(line).map(function (c) { return '<th>' + c + '</th>'; }).join('') + '</tr></thead><tbody>';
        i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { html += '<tr>' + cells(lines[i]).map(function (c) { return '<td>' + c + '</td>'; }).join('') + '</tr>'; i++; }
        i--; html += '</tbody></table>'; continue;
      }
      if ((m = line.match(/^\s*#{1,4}\s+(.*)$/))) { fp(); fl(); html += '<h4>' + inline(m[1]) + '</h4>'; continue; }
      if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) { fp(); if (list !== 'ul') { fl(); html += '<ul>'; list = 'ul'; } html += '<li>' + inline(m[1]) + '</li>'; continue; }
      if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) { fp(); if (list !== 'ol') { fl(); html += '<ol>'; list = 'ol'; } html += '<li>' + inline(m[1]) + '</li>'; continue; }
      if (!line.trim() || /^\s*(---|\*\*\*)\s*$/.test(line)) { fp(); fl(); continue; }
      fl(); para.push(line);
    }
    if (code !== null) html += '<pre><code>' + code.join('\n') + '</code></pre>';
    fp(); fl();
    return html;
  }

  function elapsed(iso) {
    var s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    return s < 60 ? s + '초' : Math.floor(s / 60) + '분 ' + (s % 60) + '초';
  }
  function ago(iso) {
    var s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
    if (!(s >= 0)) return '';
    if (s < 60) return '방금'; if (s < 3600) return Math.floor(s / 60) + '분 전';
    if (s < 86400) return Math.floor(s / 3600) + '시간 전'; if (s < 604800) return Math.floor(s / 86400) + '일 전';
    var d = new Date(iso); return (d.getMonth() + 1) + '/' + d.getDate();
  }

  // ── 상태 도우미 ──────────────────────────────────────────────────────────────
  function messages() { return loggedIn() ? (state.active ? state.active.messages : []) : state.anon; }
  function isBusy() { return messages().some(function (m) { return m.pending; }); }
  function anyBusy() { return isBusy() || state.convs.some(function (c) { return c.pending; }); }
  function activeKey() { return ACTIVE_KEY + state.mode; }

  // ── 그리기 ─────────────────────────────────────────────────────────────────
  function renderMsg(m) {
    if (m.role === 'user') return el('div', 'kcb-msg user', m.content);
    var box = el('div', 'kcb-msg bot' + (m.error ? ' err' : ''));
    if (m.pending) {
      var st = el('div', 'kcb-status');
      st.appendChild(el('span', 'kcb-spin'));
      st.appendChild(el('span', null, m.stage || '답변을 준비하는 중'));
      var t = el('span', 't', elapsed(m.created_at)); t.setAttribute('data-elapsed', m.created_at); st.appendChild(t);
      box.appendChild(st);
      if ((m.steps || []).length) {
        var ul = el('ul', 'kcb-trail');
        m.steps.slice(-4).forEach(function (s) { ul.appendChild(el('li', null, s)); });
        box.appendChild(ul);
      }
      return box;
    }
    if (m.error) { box.textContent = m.content || '답변을 만들지 못했어요.'; return box; }
    var body = el('div', 'kcb-md'); body.innerHTML = md(m.content || ''); box.appendChild(body);
    if ((m.sources || []).length) {
      var refs = el('div', 'kcb-refs');
      m.sources.forEach(function (s) {
        var a;
        if (s.type === 'page') {
          a = el('a', 'kcb-ref', '📄 ' + (s.title || s.url)); a.href = homepageOrigin() + (s.url || '/'); a.target = '_blank'; a.rel = 'noopener';
        } else {
          a = el('span', 'kcb-ref', '‹/› ' + s.path + (s.lines ? ':' + s.lines : '')); a.title = s.path;
        }
        refs.appendChild(a);
      });
      box.appendChild(refs);
    }
    var meta = el('div', 'kcb-meta'), llm = m.llm || {};
    if (llm.used || llm.model) meta.appendChild(el('span', null, [llm.used, llm.model].filter(Boolean).join(' · ') + (llm.cost_usd ? ' · $' + Number(llm.cost_usd).toFixed(4) : '')));
    if ((m.steps || []).length) {
      var d = el('details'); d.appendChild(el('summary', null, '조회 과정 ' + m.steps.length + '단계'));
      var ol = el('ol'); m.steps.forEach(function (s) { ol.appendChild(el('li', null, s)); }); d.appendChild(ol); meta.appendChild(d);
    }
    if (meta.childNodes.length) box.appendChild(meta);
    return box;
  }

  function renderHeader() {
    var cfg = state.cfg || {};
    root.querySelector('[data-title]').textContent = state.view === 'list' ? '대화 목록'
      : (loggedIn() && state.active && state.active.title && state.active.title !== '새 대화' ? state.active.title : 'FPEI AI 도우미');
    root.querySelector('[data-sub]').textContent = state.mode === 'member'
      ? (cfg.user ? cfg.user.name + '님 · 연구 시스템 도우미' : '연구실 구성원 전용')
      : (cfg.user ? cfg.user.name + '님 · 홈페이지 안내' : '미래치안공학연구원 홈페이지 안내');
    root.querySelector('[data-foot]').textContent = loggedIn()
      ? (state.mode === 'member' ? '연구실 코드를 직접 찾아 읽고 답해요. ' : '') + '대화는 모두 계정에 저장돼 다른 기기에서도 이어져요.'
      : state.mode === 'member' ? '연구실 구성원 계정으로 로그인하면 쓸 수 있어요.'
      : 'AI 답변은 홈페이지 정보를 바탕으로 하며 틀릴 수 있어요. 로그인하지 않으면 대화는 이 브라우저에만 저장돼요.';
    modes.hidden = !(cfg.public && cfg.member);
    modes.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-mode') === state.mode); });
    listBtn.hidden = !loggedIn();
    root.querySelector('[data-new]').hidden = state.mode === 'member' && !loggedIn();
    listBtn.classList.toggle('on', state.view === 'list');
  }

  function renderList() {
    var add = el('button', 'kcb-newconv'); add.type = 'button'; add.innerHTML = ICON.plus + '<span>새 대화 시작</span>';
    add.addEventListener('click', function () { newConversation(); });
    log.appendChild(add);
    if (!state.convs.length) { log.appendChild(el('div', 'kcb-empty', '저장된 대화가 없어요.')); return; }
    state.convs.forEach(function (c) {
      var row = el('div', 'kcb-conv' + (state.active && state.active.id === c.id ? ' on' : ''));
      var main = el('button', 'kcb-conv-main'); main.type = 'button';
      main.appendChild(el('span', 'kcb-conv-title', c.title || '새 대화'));
      var sub = el('span', 'kcb-conv-sub', ago(c.updated_at) + ' · 질문 ' + (c.count || 0) + '개');
      if (c.pending) { var p = el('span', 'kcb-conv-busy', ' · 답변 중'); sub.appendChild(p); }
      main.appendChild(sub);
      main.addEventListener('click', function () { openConversation(c.id); });
      var del = el('button', 'kcb-conv-del'); del.type = 'button'; del.title = '대화 삭제'; del.innerHTML = ICON.trash;
      var armed = null;
      del.addEventListener('click', function () {
        if (!armed) { del.classList.add('armed'); del.title = '한 번 더 누르면 삭제'; armed = setTimeout(function () { armed = null; del.classList.remove('armed'); }, 2500); return; }
        clearTimeout(armed);
        api('/conversations/' + c.id, { method: 'DELETE' }).then(function () {
          if (state.active && state.active.id === c.id) { state.active = null; lsSet(activeKey(), null); }
          loadList();
        }).catch(function (e) { flash(e.message); });
      });
      row.appendChild(main); row.appendChild(del);
      log.appendChild(row);
    });
  }

  function flash(text) {
    var n = el('div', 'kcb-msg bot err', text); log.appendChild(n); log.scrollTop = log.scrollHeight;
    setTimeout(function () { n.remove(); }, 4000);
  }

  function render() {
    var atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
    renderHeader();
    log.innerHTML = '';
    if (state.mode === 'member' && !loggedIn()) {
      var box = el('div', 'kcb-login');
      box.innerHTML = '<b>구성원 로그인이 필요해요</b><p>연구 시스템 도우미는 연구실 구성원만 쓸 수 있어요. 로그인하면 코드 · 사용법 질문에 답해 드리고, 대화도 계정에 저장돼요.</p>';
      var a = el('a', null, '로그인하기'); a.href = loginUrl(); box.appendChild(a);
      log.appendChild(box);
      form.style.display = 'none';
      return;
    }
    if (state.view === 'list') { form.style.display = 'none'; renderList(); log.scrollTop = 0; fab.classList.toggle('busy', anyBusy()); return; }
    form.style.display = '';
    var list = messages();
    if (!list.length) {
      var w = el('div', 'kcb-welcome');
      w.innerHTML = state.mode === 'member'
        ? '<b>무엇을 도와드릴까요?</b>연구실 소프트웨어(크롤러 · 통계 · KEMKIM · 네트워크 · Whisper · PolyDecision · MANAGER 등) 사용법이나 동작 원리를 물어보세요. 코드를 직접 찾아 읽고 근거와 함께 답해요.'
        : '<b>안녕하세요! 미래치안공학연구원입니다.</b>연구 분야, 구성원, 논문, 소식, 대학원 입학 안내 등 홈페이지 정보를 바탕으로 답해 드려요.';
      var sg = el('div', 'kcb-suggest');
      SUGGEST[state.mode].forEach(function (q) {
        var b = el('button', null, q); b.type = 'button';
        b.addEventListener('click', function () { ask(q); });
        sg.appendChild(b);
      });
      w.appendChild(sg);
      log.appendChild(w);
    }
    list.forEach(function (m) { log.appendChild(renderMsg(m)); });
    if (atBottom || isBusy()) log.scrollTop = log.scrollHeight;
    sendBtn.disabled = isBusy();
    fab.classList.toggle('busy', anyBusy());
    ensureTick();
  }

  function ensureTick() {
    if (state.tick || !isBusy()) return;
    state.tick = setInterval(function () {
      if (!isBusy()) { clearInterval(state.tick); state.tick = null; return; }
      root.querySelectorAll('[data-elapsed]').forEach(function (e) { e.textContent = elapsed(e.getAttribute('data-elapsed')); });
    }, 1000);
  }

  // ── 서버 ─────────────────────────────────────────────────────────────────
  function api(path, opts) {
    return fetch(API + path, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opts || {})).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (b) {
        if (!r.ok) throw new Error(typeof b.detail === 'string' ? b.detail : '요청이 실패했어요 (' + r.status + ')');
        return b;
      });
    });
  }
  function post(path, body) { return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }); }

  function loadList() {
    if (!loggedIn()) return Promise.resolve();
    return api('/conversations?mode=' + state.mode).then(function (r) {
      state.convs = r.conversations || [];
      // 이 사이트에서 열어 둔 대화가 없으면(다른 사이트 · 기기에서 대화한 경우) 가장 최근 대화를 이어서 연다.
      // 답변 중인 대화가 있으면 그것을 우선한다. '새 대화'를 누른 뒤에는 자동으로 열지 않는다.
      if (state.autoResume && !state.active && state.convs.length) {
        var pick = state.convs.filter(function (c) { return c.pending; })[0] || state.convs[0];
        state.autoResume = false;
        openConversation(pick.id);
        return;
      }
      state.autoResume = false;
      render(); schedule();
    }).catch(function () { });
  }

  function loadActive() {
    if (!loggedIn() || !state.active || !state.active.id) return Promise.resolve();
    var id = state.active.id;
    return api('/conversations/' + id).then(function (c) {
      if (state.active && state.active.id === id) { state.active = c; render(); }
      schedule();
    }).catch(function () { state.active = null; lsSet(activeKey(), null); render(); });
  }

  function openConversation(id) {
    state.view = 'chat';
    state.active = { id: id, title: '', messages: [] };
    lsSet(activeKey(), id);
    render();
    loadActive();
  }

  function newConversation() {
    state.view = 'chat';
    state.autoResume = false;
    if (loggedIn()) { state.active = null; lsSet(activeKey(), null); }
    else { state.anon = []; saveAnon(); }
    render();
    if (form.style.display !== 'none') input.focus();
  }

  function schedule() {
    clearTimeout(state.pollTimer);
    if (!loggedIn()) return;
    var busy = isBusy() || state.convs.some(function (c) { return c.pending; });
    if (busy || state.open) {
      state.pollTimer = setTimeout(function () {
        (state.view === 'list' ? loadList() : (state.active ? loadActive() : loadList()));
      }, busy ? 1500 : 20000);
    }
  }

  function saveAnon() { lsSet(ANON_KEY, JSON.stringify(state.anon.filter(function (m) { return !m.pending; }).slice(-40))); }

  function pollAnon(jobId, pending) {
    api('/jobs/' + jobId).then(function (j) {
      pending.stage = j.stage; pending.steps = j.steps || [];
      if (j.status === 'running') { render(); setTimeout(function () { pollAnon(jobId, pending); }, 1200); return; }
      var i = state.anon.indexOf(pending);
      var msg = j.status === 'done'
        ? { role: 'assistant', content: j.result.answer, sources: j.result.sources, steps: j.result.steps, llm: j.result.llm, created_at: new Date().toISOString() }
        : { role: 'assistant', error: true, content: j.error || '답변을 만들지 못했어요.' };
      if (i >= 0) state.anon[i] = msg;
      saveAnon(); render();
    }).catch(function (e) {
      var i = state.anon.indexOf(pending);
      if (i >= 0) state.anon[i] = { role: 'assistant', error: true, content: e.message };
      saveAnon(); render();
    });
  }

  function ask(question) {
    question = String(question || '').trim();
    if (!question || isBusy()) return;
    var now = new Date().toISOString();
    if (loggedIn()) {
      if (!state.active) state.active = { id: null, title: '', messages: [] };
      var conv = state.active;
      conv.messages.push({ role: 'user', content: question, created_at: now }, { role: 'assistant', pending: true, stage: '질문을 보내는 중', created_at: now });
      render();
      post('/ask', { mode: state.mode, question: question, conversation_id: conv.id || undefined })
        .then(function (r) {
          conv.id = r.conversation_id; lsSet(activeKey(), r.conversation_id);
          loadActive(); loadList();
        })
        .catch(function (e) { conv.messages.pop(); conv.messages.push({ role: 'assistant', error: true, content: e.message }); render(); });
      return;
    }
    if (state.mode === 'member') return;
    var history = state.anon.filter(function (m) { return !m.pending && !m.error; }).slice(-8).map(function (m) { return { role: m.role, content: m.content }; });
    var pending = { role: 'assistant', pending: true, stage: '질문을 보내는 중', created_at: now };
    state.anon.push({ role: 'user', content: question, created_at: now }, pending);
    saveAnon(); render();
    post('/ask', { mode: 'public', question: question, history: history })
      .then(function (r) { pollAnon(r.job_id, pending); })
      .catch(function (e) { var i = state.anon.indexOf(pending); if (i >= 0) state.anon[i] = { role: 'assistant', error: true, content: e.message }; saveAnon(); render(); });
  }

  function setOpen(open) {
    state.open = open;
    panel.hidden = !open;
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
    fab.innerHTML = (open ? ICON.close : ICON.chat) + '<span class="kcb-dot"></span>';
    lsSet(OPEN_KEY, open ? '1' : '0');
    if (open) {
      render();
      if (loggedIn()) { loadList(); loadActive(); }
      setTimeout(function () { if (form.style.display !== 'none') input.focus(); log.scrollTop = log.scrollHeight; }, 30);
    }
    schedule();
  }

  function setMode(mode) {
    if (!state.cfg) return;
    if (mode === 'public' && !state.cfg.public) mode = 'member';
    state.mode = mode;
    state.view = 'chat';
    lsSet(MODE_KEY, mode);
    state.convs = [];
    var saved = loggedIn() ? lsGet(activeKey()) : null;
    state.active = saved ? { id: saved, title: '', messages: [] } : null;
    state.autoResume = !saved;
    render();
    if (loggedIn()) { loadList(); loadActive(); }
  }

  // ── 시작 ─────────────────────────────────────────────────────────────────
  function boot() {
    document.body.appendChild(root);
    fab.addEventListener('click', function () { setOpen(!state.open); });
    root.querySelector('[data-close]').addEventListener('click', function () { setOpen(false); });
    root.querySelector('[data-new]').addEventListener('click', function () { if (!isBusy() || loggedIn()) newConversation(); });
    listBtn.addEventListener('click', function () {
      state.view = state.view === 'list' ? 'chat' : 'list';
      render();
      if (state.view === 'list') loadList();
    });
    modes.addEventListener('click', function (e) { var b = e.target.closest('[data-mode]'); if (b) setMode(b.getAttribute('data-mode')); });
    form.addEventListener('submit', function (e) { e.preventDefault(); var q = input.value; input.value = ''; input.style.height = ''; ask(q); });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
    input.addEventListener('input', function () { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px'; });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && state.open) setOpen(false); });
    document.addEventListener('visibilitychange', function () { if (!document.hidden && loggedIn()) { loadList(); loadActive(); } });

    api('/config').then(function (cfg) {
      state.cfg = cfg;
      var saved = lsGet(MODE_KEY);
      setMode(cfg.public ? (saved === 'member' && cfg.member ? 'member' : 'public') : 'member');
      if (lsGet(OPEN_KEY) === '1' && window.innerWidth > 640) setOpen(true);
    }).catch(function () { root.remove(); }); // 챗봇 API 가 없는 사이트면 버튼을 숨긴다
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
