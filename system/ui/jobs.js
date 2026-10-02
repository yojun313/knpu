/* KNPU 분석 작업 관리 UI — 작업 목록 · 진행 상황 창 · 예약 선택 · 완료 알림.
 *
 * 서버: 각 분석 서비스의 /api/jobs/* (system/jobs/routes.py). 상태는 모두 서버(DB)에 있으므로
 * 어느 브라우저·기기에서 들어와도 같은 목록과 진행 로그가 보인다.
 *
 *   KNPUJobs.init({ service: 'statistics', anchor: el, onOpenResult(job), onJobDone(job) })
 *   KNPUJobs.open(jobId, { autoOpenResult: true })   // 진행 상황 창
 *   KNPUJobs.openList()                               // 작업 목록
 *   var picker = KNPUJobs.schedulePicker(hostEl, { button: startBtn })
 *   picker.value()  → 예약 시각(ms) 또는 null(바로 실행),  picker.validate() → 오류 문구 또는 ''
 */
(function () {
  'use strict';
  if (window.KNPUJobs) return;

  var API = '/api/jobs';
  var ACTIVE = { scheduled: 1, queued: 1, starting: 1, running: 1, cancelling: 1 };
  var RUNNING = { starting: 1, running: 1, cancelling: 1 };
  var STATUS = {
    scheduled: ['예약됨', 'violet'],
    queued: ['대기 중', 'slate'],
    starting: ['시작 중', 'blue'],
    running: ['실행 중', 'blue'],
    cancelling: ['중단 중', 'amber'],
    done: ['완료', 'green'],
    error: ['실패', 'red'],
    cancelled: ['중단됨', 'gray'],
    interrupted: ['끊김', 'amber']
  };
  var SERVICE_LABEL = { statistics: 'Statistics', kemkim: 'KEMKIM', network: 'Network' };
  var FILTERS = [
    ['all', '전체'],
    ['active', '진행·대기'],
    ['scheduled', '예약'],
    ['done', '완료'],
    ['failed', '실패·중단']
  ];

  var S = {
    service: null,
    opts: {},
    scope: 'service',
    filter: 'all',
    listTimer: null,
    summaryTimer: null,
    detail: null, // { id, since, timer, auto, job }
    seen: null,   // 이미 알림을 띄운(또는 페이지를 열 때 이미 끝나 있던) 작업 id
    badge: null,
    navHost: null
  };

  // ------------------------------------------------------------ 유틸 ---
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function api(path, opt) {
    opt = opt || {};
    var init = { method: opt.method || 'GET', credentials: 'same-origin', cache: 'no-store', headers: {} };
    if (opt.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opt.body); }
    return fetch(API + path, init).then(function (r) {
      return r.text().then(function (t) {
        var data = null;
        try { data = t ? JSON.parse(t) : {}; } catch (e) { data = null; }
        if (!r.ok) {
          var msg = (data && (data.detail || data.message)) || ('요청 실패 (HTTP ' + r.status + ')');
          throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        }
        if (data === null) throw new Error('서버 응답을 읽지 못했습니다.');
        return data;
      });
    });
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function fmtTime(ts, withDate) {
    if (!ts) return '—';
    var d = new Date(ts * 1000), now = new Date();
    var t = pad(d.getHours()) + ':' + pad(d.getMinutes());
    var sameDay = d.toDateString() === now.toDateString();
    if (!withDate && sameDay) return t;
    return (d.getMonth() + 1) + '.' + pad(d.getDate()) + ' ' + t;
  }
  function fmtClock(ts) {
    var d = new Date(ts * 1000);
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }
  function fmtDur(sec) {
    if (sec == null || !isFinite(sec) || sec < 0) return '—';
    sec = Math.round(sec);
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    if (h) return h + '시간 ' + m + '분';
    if (m) return m + '분 ' + s + '초';
    return s + '초';
  }
  function fmtSize(b) {
    if (!b) return '';
    if (b > 1048576) return (b / 1048576).toFixed(1) + ' MB';
    return Math.max(1, Math.round(b / 1024)) + ' KB';
  }
  function relUntil(ts) {
    var sec = ts - Date.now() / 1000;
    if (sec <= 0) return '곧 실행';
    var h = Math.floor(sec / 3600), m = Math.ceil((sec % 3600) / 60);
    if (m === 60) { h += 1; m = 0; }
    return (h ? h + '시간 ' : '') + (m ? m + '분' : '') + ' 후';
  }
  function pill(status) {
    var s = STATUS[status] || [status, 'gray'];
    return '<span class="kj-pill kj-' + s[1] + (RUNNING[status] ? ' kj-live' : '') + '">' + esc(s[0]) + '</span>';
  }
  function duration(j, now) {
    if (!j.started_ts) return null;
    return (j.finished_ts || now || Date.now() / 1000) - j.started_ts;
  }
  function pct(j) {
    var p = j.progress;
    if (p && p.total > 0) return Math.max(0, Math.min(100, Math.round((p.current / p.total) * 100)));
    return null;
  }
  function serviceUrl(service, path) {
    var cfg = window.KNPU_SERVICES;
    if (service === S.service || !cfg || !cfg.services || !cfg.services[service]) return path;
    var svc = cfg.services[service];
    var host = cfg.isDev ? svc.devDomain : svc.prodDomain;
    return 'https://' + host + (svc.publicPath || '') + path;
  }
  function icon(name) {
    var P = {
      list: '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
      stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
      retry: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
      open: '<path d="M14 3h7v7"/><path d="M10 14 21 3"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/>',
      trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>',
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
      play: '<path d="M7 4v16l13-8z"/>',
      back: '<path d="M15 18l-6-6 6-6"/>'
    };
    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (P[name] || '') + '</svg>';
  }

  // ------------------------------------------------------------ 모달 뼈대 ---
  function overlay(id) {
    var el = document.getElementById(id);
    if (el) return el;
    el = document.createElement('div');
    el.id = id;
    el.className = 'kj-overlay';
    el.hidden = true;
    el.addEventListener('mousedown', function (e) { if (e.target === el) close(id); });
    document.body.appendChild(el);
    return el;
  }
  function close(id) {
    var el = document.getElementById(id);
    if (el) el.hidden = true;
    if (id === 'kjList' && S.listTimer) { clearInterval(S.listTimer); S.listTimer = null; }
    if (id === 'kjDetail' && S.detail) { clearTimeout(S.detail.timer); S.detail = null; renderNav(); }
  }
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var d = document.getElementById('kjDetail'), l = document.getElementById('kjList');
    if (d && !d.hidden) { close('kjDetail'); e.stopPropagation(); }
    else if (l && !l.hidden) { close('kjList'); e.stopPropagation(); }
  }, true);

  // ------------------------------------------------------------ 목록 ---
  function openList() {
    var el = overlay('kjList');
    el.innerHTML =
      '<div class="kj-modal kj-list-modal" role="dialog" aria-label="작업 목록">' +
      '<div class="kj-head"><div><h3>작업 목록</h3><p class="kj-sub">분석은 서버에서 실행됩니다 — 창을 닫거나 다른 기기에서 들어와도 이어서 확인할 수 있습니다.</p></div>' +
      '<button class="kj-x" type="button" data-close title="닫기">×</button></div>' +
      '<div class="kj-toolbar"><div class="kj-seg" data-filter>' +
      FILTERS.map(function (f) { return '<button type="button" data-v="' + f[0] + '"' + (S.filter === f[0] ? ' class="on"' : '') + '>' + f[1] + '</button>'; }).join('') +
      '</div><label class="kj-scope"><input type="checkbox" data-scope' + (S.scope === 'all' ? ' checked' : '') + '> 모든 분석 사이트</label></div>' +
      '<div class="kj-list-body" data-body><div class="kj-empty">불러오는 중…</div></div>' +
      '<div class="kj-foot kj-foot-note" data-note></div>' +
      '</div>';
    el.hidden = false;
    el.querySelector('[data-close]').onclick = function () { close('kjList'); };
    el.querySelector('[data-filter]').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-v]');
      if (!b) return;
      S.filter = b.getAttribute('data-v');
      Array.prototype.forEach.call(this.children, function (c) { c.classList.toggle('on', c === b); });
      renderList();
    });
    el.querySelector('[data-scope]').onchange = function () { S.scope = this.checked ? 'all' : 'service'; loadList(); };
    loadList();
    if (S.listTimer) clearInterval(S.listTimer);
    S.listTimer = setInterval(function () { if (!document.hidden) loadList(true); }, 3000);
  }

  var listData = null;
  function loadList(quiet) {
    return api('?scope=' + S.scope + '&limit=100').then(function (data) {
      listData = data;
      renderList();
    }).catch(function (err) {
      if (quiet) return;
      var body = document.querySelector('#kjList [data-body]');
      if (body) body.innerHTML = '<div class="kj-empty kj-err">' + esc(err.message) + '</div>';
    });
  }
  function matches(j) {
    switch (S.filter) {
      case 'active': return j.status in ACTIVE && j.status !== 'scheduled';
      case 'scheduled': return j.status === 'scheduled';
      case 'done': return j.status === 'done';
      case 'failed': return j.status === 'error' || j.status === 'cancelled' || j.status === 'interrupted';
      default: return true;
    }
  }
  function renderList() {
    var el = document.getElementById('kjList');
    if (!el || el.hidden || !listData) return;
    var body = el.querySelector('[data-body]');
    var items = (listData.items || []).filter(matches);
    var now = listData.now || Date.now() / 1000;
    if (!items.length) {
      body.innerHTML = '<div class="kj-empty">' + (S.filter === 'all' ? '아직 작업이 없습니다. 새 프로젝트 → 분석을 시작하면 여기에 표시됩니다.' : '해당하는 작업이 없습니다.') + '</div>';
    } else {
      var scroll = body.scrollTop;
      body.innerHTML = items.map(function (j) {
        var p = pct(j);
        var when;
        if (j.status === 'scheduled') when = icon('clock') + ' ' + esc(fmtTime(j.scheduled_ts, true)) + ' <span class="kj-dim">(' + esc(relUntil(j.scheduled_ts)) + ')</span>';
        else if (j.status in RUNNING) when = '경과 ' + esc(fmtDur(duration(j, now)));
        else if (j.finished_ts) when = esc(fmtTime(j.finished_ts)) + (j.started_ts ? ' · ' + esc(fmtDur(duration(j))) : '');
        else when = esc(fmtTime(j.created_ts));
        var bar = '';
        if (j.status in RUNNING) {
          bar = '<div class="kj-bar' + (p == null ? ' kj-indet' : '') + '"><i style="width:' + (p == null ? 35 : p) + '%"></i></div>';
        }
        return '<button type="button" class="kj-row kj-st-' + esc(j.status) + '" data-id="' + esc(j.id) + '">' +
          '<div class="kj-row-top">' + pill(j.status) +
          '<span class="kj-row-title">' + esc(j.title || '(이름 없음)') + '</span>' +
          (S.scope === 'all' ? '<span class="kj-svc">' + esc(SERVICE_LABEL[j.service] || j.service) + '</span>' : '') +
          '<span class="kj-row-when">' + when + '</span></div>' +
          '<div class="kj-row-sub"><span class="kj-kind">' + esc(j.kind_label || j.kind) + '</span>' +
          '<span class="kj-stage">' + esc(j.status === 'error' || j.status === 'interrupted' ? (j.error || '').split('\n')[0] : (j.stage || '')) + '</span>' +
          (p != null && j.status in RUNNING ? '<span class="kj-pct">' + p + '%</span>' : '') + '</div>' +
          bar + '</button>';
      }).join('');
      body.scrollTop = scroll;
      Array.prototype.forEach.call(body.querySelectorAll('.kj-row'), function (row) {
        row.onclick = function () { open(row.getAttribute('data-id')); };
      });
    }
    var active = (listData.items || []).filter(function (j) { return j.status in RUNNING; }).length;
    var note = el.querySelector('[data-note]');
    note.textContent = '동시 실행 ' + active + ' / ' + (listData.max_concurrent || '-') + ' (이 사이트 기준) · 나머지는 차례로 대기합니다. 끝난 작업의 입력 파일은 14일간 보관되어 다시 실행할 수 있습니다.';
  }

  // ------------------------------------------------------------ 상세(진행 상황 창) ---
  function open(id, opt) {
    opt = opt || {};
    if (S.detail) clearTimeout(S.detail.timer);
    var el = overlay('kjDetail');
    var listEl = document.getElementById('kjList');
    var overList = !!(listEl && !listEl.hidden);
    el.classList.toggle('kj-over-list', overList);
    el.innerHTML =
      '<div class="kj-modal kj-detail-modal" role="dialog" aria-label="작업 진행 상황">' +
      '<div class="kj-head"><div class="kj-head-main">' +
      (overList ? '<button type="button" class="kj-back" data-back title="목록으로">' + icon('back') + '</button>' : '') +
      '<div><div class="kj-title-row"><span data-pill></span><h3 data-title>불러오는 중…</h3></div><p class="kj-sub" data-kind></p></div></div>' +
      '<button class="kj-x" type="button" data-close title="닫기 (작업은 계속 실행됩니다)">×</button></div>' +
      '<div class="kj-detail-body">' +
      '<div class="kj-meta" data-meta></div>' +
      '<div class="kj-progress"><div class="kj-stage-line"><span data-stage></span><b data-pct></b></div>' +
      '<div class="kj-bar kj-bar-lg" data-bar><i></i></div><div class="kj-warn" data-warn hidden></div></div>' +
      '<div class="kj-error" data-error hidden></div>' +
      '<div class="kj-sched-edit" data-sched hidden></div>' +
      '<div class="kj-log-head"><span>진행 로그</span><label><input type="checkbox" data-follow checked> 자동 스크롤</label></div>' +
      '<div class="kj-log" data-log></div>' +
      '</div>' +
      '<div class="kj-foot" data-actions></div>' +
      '</div>';
    el.hidden = false;
    el.querySelector('[data-close]').onclick = function () { close('kjDetail'); };
    var back = el.querySelector('[data-back]');
    if (back) back.onclick = function () { close('kjDetail'); loadList(); };
    S.detail = { id: id, since: 0, timer: null, auto: !!opt.autoOpenResult, job: null, lastStatus: null };
    renderNav();   // 사이드바에서 지금 보고 있는 작업을 바로 강조
    pollDetail();
  }

  function pollDetail() {
    var d = S.detail;
    if (!d) return;
    api('/' + encodeURIComponent(d.id) + '?since=' + d.since).then(function (j) {
      if (S.detail !== d) return;
      renderDetail(j);
      d.job = j;
      if (j.status in ACTIVE) d.timer = setTimeout(pollDetail, j.status === 'scheduled' ? 5000 : 1500);
    }).catch(function (err) {
      if (S.detail !== d) return;
      var t = document.querySelector('#kjDetail [data-title]');
      if (t && !d.job) t.textContent = err.message;
      d.timer = setTimeout(pollDetail, 4000);
    });
  }

  function renderDetail(j) {
    var el = document.getElementById('kjDetail');
    var d = S.detail;
    if (!el || !d) return;
    var now = j.now || Date.now() / 1000;
    el.querySelector('[data-pill]').innerHTML = pill(j.status);
    el.querySelector('[data-title]').textContent = j.title || '(이름 없음)';
    el.querySelector('[data-kind]').textContent = (j.kind_label || j.kind) + ' · ' + (SERVICE_LABEL[j.service] || j.service) + (j.retry_of ? ' · 다시 실행한 작업' : '');

    var meta = [
      ['입력 파일', j.input ? esc(j.input.filename || '-') + (j.input.size ? ' <span class="kj-dim">' + fmtSize(j.input.size) + '</span>' : '') : '—'],
      ['등록', esc(fmtTime(j.created_ts, true))]
    ];
    if (j.scheduled_ts) meta.push(['예약 시각', esc(fmtTime(j.scheduled_ts, true)) + (j.status === 'scheduled' ? ' <span class="kj-dim">(' + esc(relUntil(j.scheduled_ts)) + ')</span>' : '')]);
    if (j.started_ts) meta.push(['시작', esc(fmtTime(j.started_ts, true))]);
    if (j.finished_ts) meta.push(['종료', esc(fmtTime(j.finished_ts, true))]);
    if (j.started_ts) meta.push([j.finished_ts ? '소요 시간' : '경과', esc(fmtDur(duration(j, now)))]);
    el.querySelector('[data-meta]').innerHTML = meta.map(function (m) { return '<div><span>' + m[0] + '</span><b>' + m[1] + '</b></div>'; }).join('');

    var stage = j.stage || (STATUS[j.status] || [j.status])[0];
    if (j.status === 'queued' && j.queue_ahead) stage = '대기 중 — 먼저 등록된 대기 작업 ' + j.queue_ahead + '개';
    el.querySelector('[data-stage]').textContent = stage;
    var p = pct(j);
    var bar = el.querySelector('[data-bar]');
    bar.className = 'kj-bar kj-bar-lg kj-bar-' + j.status + (j.status in RUNNING && p == null ? ' kj-indet' : '');
    var w = j.status === 'done' ? 100 : (p != null ? p : (j.status in RUNNING ? 35 : (j.status in { error: 1, cancelled: 1, interrupted: 1 } ? 100 : 0)));
    bar.firstChild.style.width = w + '%';
    el.querySelector('[data-pct]').textContent = p != null && j.status in RUNNING ? p + '%' : '';

    var warn = el.querySelector('[data-warn]');
    var stale = j.status === 'running' && j.heartbeat_ts && now - j.heartbeat_ts > 30;
    warn.hidden = !stale;
    if (stale) warn.textContent = '작업 프로세스에서 ' + fmtDur(now - j.heartbeat_ts) + ' 동안 응답이 없습니다. 무거운 계산 중일 수 있습니다.';

    var errEl = el.querySelector('[data-error]');
    errEl.hidden = !j.error || j.status === 'done';
    if (j.error) errEl.textContent = j.error;

    // 로그 (since 이후 줄만 받아 덧붙인다)
    var log = el.querySelector('[data-log]');
    var follow = el.querySelector('[data-follow]').checked;
    (j.log || []).forEach(function (line) {
      var div = document.createElement('div');
      div.className = 'kj-line kj-l-' + (line.level || 'info');
      div.innerHTML = '<time>' + fmtClock(line.t) + '</time><span></span>';
      div.lastChild.textContent = line.text;
      log.appendChild(div);
      d.since = Math.max(d.since, line.n || 0);
    });
    if (!log.childNodes.length) log.innerHTML = '<div class="kj-line kj-dim kj-placeholder"><span>' + (j.status === 'scheduled' ? '예약 시각이 되면 자동으로 시작합니다.' : '아직 로그가 없습니다.') + '</span></div>';
    else { var ph = log.querySelector('.kj-placeholder'); if (ph) ph.remove(); }
    if (follow) log.scrollTop = log.scrollHeight;

    renderSchedEdit(el, j);
    renderActions(el, j);

    // 방금 시작한 작업이 끝나면 결과 프로젝트를 바로 연다(예전 진행 창과 같은 흐름)
    if (d.lastStatus && d.lastStatus !== j.status && j.status === 'done') {
      if (j.service === S.service && S.opts.onJobDone) S.opts.onJobDone(j);
      markSeen(j.id);
      if (d.auto && j.service === S.service && j.result && j.result.project_id && S.opts.onOpenResult) {
        setTimeout(function () {
          if (S.detail !== d) return;
          close('kjDetail'); close('kjList');
          S.opts.onOpenResult(j);
        }, 900);
      }
    }
    d.lastStatus = j.status;
  }

  function renderSchedEdit(el, j) {
    var box = el.querySelector('[data-sched]');
    if (j.status !== 'scheduled') { box.hidden = true; box.innerHTML = ''; return; }
    if (!box.hidden && box.firstChild) return; // 입력 중인 값 유지
    box.hidden = false;
    box.innerHTML = '<span>예약 시각 변경</span><input type="datetime-local" data-dt><button type="button" class="kj-btn" data-save>저장</button>';
    box.querySelector('[data-dt]').value = toLocalInput(new Date(j.scheduled_ts * 1000));
    box.querySelector('[data-save]').onclick = function () {
      var v = box.querySelector('[data-dt]').value;
      var ms = v ? new Date(v).getTime() : NaN;
      if (!isFinite(ms) || ms < Date.now() + 30000) { toast('예약 시각은 지금 이후로 지정해 주세요.', 'err'); return; }
      act('PATCH', '', { scheduled_at: ms }, '예약 시각을 바꿨습니다.');
    };
  }

  function renderActions(el, j) {
    var box = el.querySelector('[data-actions]');
    var h = [];
    if (j.status === 'scheduled') h.push(btn('runnow', 'play', '지금 실행', 'primary'));
    if (j.status in ACTIVE && j.status !== 'cancelling') h.push(btn('cancel', 'stop', j.status in RUNNING ? '작업 중단' : '예약/대기 취소', 'danger'));
    if (j.status === 'done' && j.result && j.result.project_id) h.push(btn('result', 'open', j.service === S.service ? '결과 열기' : (SERVICE_LABEL[j.service] || j.service) + '에서 결과 열기', 'primary'));
    if (!(j.status in ACTIVE)) {
      if (j.input === null || (j.input && j.input.available)) h.push(btn('retry', 'retry', '다시 실행', j.status === 'done' ? '' : 'primary'));
      h.push(btn('delete', 'trash', '기록 삭제', 'ghost'));
    }
    h.push('<span class="kj-foot-hint">' + (j.status in ACTIVE ? '창을 닫아도 작업은 서버에서 계속됩니다.' : '') + '</span>');
    box.innerHTML = h.join('');
    Array.prototype.forEach.call(box.querySelectorAll('[data-act]'), function (b) {
      b.onclick = function () { onAction(b.getAttribute('data-act'), j, b); };
    });
  }
  function btn(act, ic, label, kind) {
    return '<button type="button" class="kj-btn' + (kind ? ' kj-' + kind : '') + '" data-act="' + act + '">' + icon(ic) + '<span>' + esc(label) + '</span></button>';
  }

  function act(method, suffix, body, okMsg) {
    var d = S.detail;
    if (!d) return Promise.resolve();
    return api('/' + encodeURIComponent(d.id) + suffix, { method: method, body: body }).then(function (res) {
      if (okMsg) toast(okMsg, 'ok');
      if (S.detail === d) { clearTimeout(d.timer); var s = el('[data-sched]'); if (s) { s.hidden = true; s.innerHTML = ''; } pollDetail(); }
      refreshSummary();
      loadList(true);
      return res;
    }).catch(function (err) { toast(err.message, 'err'); });
    function el(sel) { return document.querySelector('#kjDetail ' + sel); }
  }

  function onAction(a, j, b) {
    if (a === 'cancel') {
      var running = j.status in RUNNING;
      if (!confirm(running ? '실행 중인 분석을 중단할까요?\n분석 프로세스와 하위 프로세스를 모두 종료하고 자원을 회수합니다.' : '이 작업을 취소할까요?')) return;
      b.disabled = true;
      act('POST', '/cancel', {}, running ? '중단 요청을 보냈습니다 — 프로세스를 정리하는 중입니다.' : '작업을 취소했습니다.');
    } else if (a === 'runnow') {
      b.disabled = true;
      act('PATCH', '', { run_now: true }, '대기열에 넣었습니다.');
    } else if (a === 'retry') {
      b.disabled = true;
      api('/' + encodeURIComponent(j.id) + '/retry', { method: 'POST', body: {} }).then(function (nj) {
        toast('같은 설정으로 다시 실행합니다.', 'ok');
        refreshSummary();
        open(nj.id, { autoOpenResult: true });
      }).catch(function (err) { b.disabled = false; toast(err.message, 'err'); });
    } else if (a === 'delete') {
      if (!confirm('이 작업 기록을 삭제할까요? (만들어진 결과 프로젝트는 그대로 남습니다)')) return;
      api('/' + encodeURIComponent(j.id), { method: 'DELETE' }).then(function () {
        close('kjDetail');
        loadList(true);
      }).catch(function (err) { toast(err.message, 'err'); });
    } else if (a === 'result') {
      openResult(j);
    }
  }

  function openResult(j) {
    if (j.service === S.service && S.opts.onOpenResult) {
      close('kjDetail'); close('kjList');
      S.opts.onOpenResult(j);
    } else {
      window.open(serviceUrl(j.service, '/viewer/' + encodeURIComponent(j.result.project_id)), '_blank', 'noopener');
    }
  }

  // ------------------------------------------------------------ 배지 · 알림 ---
  function seenKey() { return 'kj_seen_' + S.service; }
  function loadSeen() {
    if (S.seen) return S.seen;
    S.seen = {};
    try { (JSON.parse(sessionStorage.getItem(seenKey()) || '[]') || []).forEach(function (id) { S.seen[id] = 1; }); } catch (e) { }
    return S.seen;
  }
  function markSeen(id) {
    loadSeen()[id] = 1;
    try { sessionStorage.setItem(seenKey(), JSON.stringify(Object.keys(S.seen).slice(-100))); } catch (e) { }
  }

  var firstSummary = true;
  function refreshSummary() {
    return api('/summary').then(function (s) {
      setBadge(s.running, s.scheduled);
      var seen = loadSeen();
      (s.recent || []).forEach(function (j) {
        if (seen[j.id]) return;
        markSeen(j.id);
        if (firstSummary) return; // 페이지를 열기 전에 끝난 작업은 알리지 않는다
        if (S.detail && S.detail.id === j.id) return;
        if (j.status === 'done') {
          if (S.opts.onJobDone) S.opts.onJobDone(j);
          toast('분석 완료 — ' + (j.title || ''), 'ok', { label: '결과 열기', fn: function () { openResult(j); } });
        } else if (j.status === 'error' || j.status === 'interrupted') {
          toast('분석 ' + (STATUS[j.status] || [''])[0] + ' — ' + (j.title || ''), 'err', { label: '자세히', fn: function () { open(j.id); } });
        }
      });
      firstSummary = false;
    }).catch(function () { });
  }
  function setBadge(running, scheduled) {
    var b = S.badge;
    if (!b) return;
    var n = (running || 0) + (scheduled || 0);
    b.hidden = !n;
    b.textContent = n > 99 ? '99+' : String(n);
    b.classList.toggle('kj-badge-live', !!running);
    var host = b.closest('.kj-rail-head');
    if (host) host.title = '작업' + (n ? ' — 실행·대기 ' + (running || 0) + '개, 예약 ' + (scheduled || 0) + '개' : '');
  }
  function scheduleSummary() {
    if (S.summaryTimer) clearTimeout(S.summaryTimer);
    S.summaryTimer = setTimeout(function () {
      refreshNav();
      refreshSummary().then(scheduleSummary);
    }, document.hidden ? 30000 : 5000);
  }

  function toast(text, kind, action) {
    var stack = document.getElementById('kjToasts');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'kjToasts';
      stack.className = 'kj-toasts';
      document.body.appendChild(stack);
    }
    var t = document.createElement('div');
    t.className = 'kj-toast kj-toast-' + (kind || 'info');
    t.innerHTML = '<span></span>';
    t.firstChild.textContent = text;
    if (action) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = action.label;
      b.onclick = function () { t.remove(); action.fn(); };
      t.appendChild(b);
    }
    var x = document.createElement('button');
    x.type = 'button'; x.className = 'kj-toast-x'; x.textContent = '×';
    x.onclick = function () { t.remove(); };
    t.appendChild(x);
    stack.appendChild(t);
    setTimeout(function () { t.classList.add('kj-out'); setTimeout(function () { t.remove(); }, 300); }, action ? 12000 : 4500);
  }

  // ------------------------------------------------------------ 예약 선택 ---
  function toLocalInput(d) {
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function schedulePicker(host, opt) {
    opt = opt || {};
    var btnEl = opt.button || null;
    var btnText = btnEl ? btnEl.textContent : '';
    var wrap = document.createElement('div');
    wrap.className = 'kj-sched';
    wrap.innerHTML =
      '<span class="kj-sched-label">실행 시점</span>' +
      '<div class="kj-seg kj-seg-sm"><button type="button" data-v="now" class="on">바로 실행</button><button type="button" data-v="later">' + icon('clock') + ' 예약</button></div>' +
      '<input type="datetime-local" data-dt hidden>' +
      '<p class="kj-sched-hint" data-hint>서버에서 실행되므로 창을 닫아도 계속됩니다. 진행 상황은 작업 목록에서 볼 수 있습니다.</p>';
    if (btnEl && btnEl.parentNode === host) host.insertBefore(wrap, btnEl);
    else host.appendChild(wrap);
    var mode = 'now';
    var dt = wrap.querySelector('[data-dt]');
    var hint = wrap.querySelector('[data-hint]');
    function sync() {
      Array.prototype.forEach.call(wrap.querySelectorAll('[data-v]'), function (b) { b.classList.toggle('on', b.getAttribute('data-v') === mode); });
      dt.hidden = mode !== 'later';
      if (mode === 'later') {
        var ms = dt.value ? new Date(dt.value).getTime() : NaN;
        hint.textContent = isFinite(ms) ? (ms > Date.now() ? relUntil(ms / 1000) + ' 자동으로 시작합니다. 예약은 작업 목록에서 바꾸거나 취소할 수 있습니다.' : '지금 이후의 시각을 골라 주세요.') : '';
      } else {
        hint.textContent = '서버에서 실행되므로 창을 닫아도 계속됩니다. 진행 상황은 작업 목록에서 볼 수 있습니다.';
      }
      if (btnEl) btnEl.textContent = mode === 'later' ? '예약 등록' : btnText;
    }
    wrap.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-v]');
      if (!b) return;
      mode = b.getAttribute('data-v');
      if (mode === 'later' && !dt.value) {
        var d = new Date(Date.now() + 60 * 60 * 1000);
        d.setMinutes(Math.ceil(d.getMinutes() / 10) * 10, 0, 0);
        dt.value = toLocalInput(d);
      }
      sync();
    });
    dt.addEventListener('input', sync);
    return {
      value: function () {
        if (mode !== 'later') return null;
        var ms = dt.value ? new Date(dt.value).getTime() : NaN;
        return isFinite(ms) ? ms : null;
      },
      validate: function () {
        if (mode !== 'later') return '';
        var ms = dt.value ? new Date(dt.value).getTime() : NaN;
        if (!isFinite(ms)) return '예약 시각을 입력해 주세요.';
        if (ms < Date.now() + 30000) return '예약 시각은 지금 이후로 지정해 주세요.';
        return '';
      },
      reset: function () { mode = 'now'; dt.value = ''; sync(); },
      isScheduled: function () { return mode === 'later'; }
    };
  }

  // ------------------------------------------------------------ 사이드바 작업 목록 ---
  // 모달을 열지 않고 사이드바에 바로 보여 준다. 항목을 누르면 진행 상황 창이 바로 열린다.
  var NAV_LIMIT = 8;
  var navData = null;

  function mountRail(anchor) {
    if (!anchor || document.querySelector('.kj-rail')) return;
    var wrap = document.createElement('div');
    wrap.className = 'kj-rail';
    wrap.innerHTML =
      '<div class="kj-rail-head">' +
      '<span class="kj-nav-icon">' + icon('list') + '</span>' +
      '<span class="kj-rail-title sb-label">작업</span>' +
      '<span class="kj-badge" hidden></span>' +
      '<button type="button" class="kj-rail-all sb-label" data-all title="작업 목록 전체 보기">전체</button>' +
      '</div>' +
      '<div class="kj-rail-list" data-nav></div>';
    anchor.parentNode.insertBefore(wrap, anchor.nextSibling);
    wrap.querySelector('[data-all]').onclick = openList;
    S.badge = wrap.querySelector('.kj-badge');
    S.navHost = wrap;
    renderNav();
  }

  // 진행·대기·예약을 먼저, 그 다음 최근 끝난 것 — 사이드바는 좁으니 NAV_LIMIT 개까지만
  function navItems() {
    var all = (navData && navData.items) || [];
    var rank = function (j) {
      if (j.status in RUNNING) return 0;
      if (j.status === 'queued') return 1;
      if (j.status === 'scheduled') return 2;
      return 3;
    };
    return all.slice().sort(function (a, b) {
      var d = rank(a) - rank(b);
      if (d) return d;
      return (b.finished_ts || b.created_ts || 0) - (a.finished_ts || a.created_ts || 0);
    }).slice(0, NAV_LIMIT);
  }

  function navMeta(j, now) {
    var label = (STATUS[j.status] || [j.status])[0];
    if (j.status === 'scheduled') return label + ' · ' + fmtTime(j.scheduled_ts, true);
    if (j.status in RUNNING) {
      var p = pct(j);
      return (j.stage || label) + (p != null ? ' · ' + p + '%' : '');
    }
    if (j.status === 'queued') return j.stage || label;
    if (j.status === 'error' || j.status === 'interrupted') {
      return label + ' · ' + ((j.error || '').split('\n')[0] || '');
    }
    return label + (j.finished_ts ? ' · ' + fmtTime(j.finished_ts) : '');
  }

  function renderNav() {
    if (!S.navHost) return;
    var body = S.navHost.querySelector('[data-nav]');
    if (!body) return;
    var items = navItems();
    if (!items.length) {
      body.innerHTML = '<div class="kj-rail-empty">' +
        (navData ? '진행 중인 작업이 없습니다.' : '불러오는 중…') + '</div>';
      return;
    }
    var now = (navData && navData.now) || Date.now() / 1000;
    var openId = S.detail && S.detail.id;
    body.innerHTML = items.map(function (j) {
      var p = pct(j);
      var bar = '';
      if (j.status in RUNNING) {
        bar = '<span class="kj-rail-bar' + (p == null ? ' kj-indet' : '') +
          '"><i style="width:' + (p == null ? 35 : p) + '%"></i></span>';
      }
      return '<button type="button" class="kj-rail-item kj-st-' + esc(j.status) +
        (openId === j.id ? ' on' : '') + '" data-id="' + esc(j.id) + '"' +
        ' title="' + esc((j.title || '') + ' — ' + navMeta(j, now)) + '">' +
        '<span class="kj-rail-dot"></span>' +
        '<span class="kj-rail-main">' +
        '<span class="kj-rail-name">' + esc(j.title || '(이름 없음)') + '</span>' +
        '<span class="kj-rail-meta">' + esc(navMeta(j, now)) + '</span>' +
        '</span>' + bar + '</button>';
    }).join('');
    Array.prototype.forEach.call(body.querySelectorAll('.kj-rail-item'), function (row) {
      // 바로 진행 상황 창으로 — 목록 모달을 거치지 않는다
      row.onclick = function () { open(row.getAttribute('data-id'), { autoOpenResult: false }); };
    });
  }

  function refreshNav() {
    return api('?scope=service&limit=' + NAV_LIMIT * 3).then(function (data) {
      navData = data;
      renderNav();
    }).catch(function () { });
  }

  function init(opts) {
    S.opts = opts || {};
    S.service = S.opts.service;
    mountRail(S.opts.anchor);
    refreshSummary().then(scheduleSummary);
    refreshNav();
    document.addEventListener('visibilitychange', function () { if (!document.hidden) { refreshSummary(); scheduleSummary(); } });
  }

  window.KNPUJobs = {
    init: init,
    open: open,
    openList: openList,
    schedulePicker: schedulePicker,
    refresh: function () { refreshNav(); return refreshSummary(); },
    toast: toast
  };
})();
