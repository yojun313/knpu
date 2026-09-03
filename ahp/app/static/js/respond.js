(function () {
  'use strict';

  const accessToken = location.pathname.split('/')[2];
  const STORAGE_TOKEN_KEY = 'ahp_respondent_token_' + accessToken;
  const STORAGE_QUEUE_KEY = 'ahp_queue_' + accessToken;
  const STORAGE_SEQ_KEY = 'ahp_seq_' + accessToken;
  const STORAGE_SUBMITTED_KEY = 'ahp_submitted_' + accessToken;

  let landing = null;
  let respondentToken = localStorage.getItem(STORAGE_TOKEN_KEY);
  let pendingReopenMatrixId = null;
  let questions = [];            // 평탄한 쌍 목록(리뷰·이름조회용)
  let activeMatrices = [];       // 현재 흐름에서 보여줄 기준(matrix) 뷰 목록
  let currentMatrixIndex = 0;
  // answers 키 = matrixId + '::' + pairId  — 대안 비교 행렬은 matrix_id만 다르고
  // child_uuids(대안 uuid)는 모든 leaf에서 같아서, pairId 하나로만 keying하면
  // 첫 대안 평가가 나머지에 그대로 복사된다(이 파일 이전 버전의 버그).
  let answers = {};
  let respondentAttributes = {};
  let demographicsDone = false;
  let everSubmitted = localStorage.getItem(STORAGE_SUBMITTED_KEY) === '1';
  let matrixCrCache = {};
  let clientSeq = Number(localStorage.getItem(STORAGE_SEQ_KEY) || 0);
  let revisionMatrixId = null;
  let revisionWorst = [];        // 진행자가 재조정 요청 시 함께 받은 문제 쌍

  const STORAGE_SECTIONS_DONE_KEY = 'ahp_sections_done_' + accessToken;
  function loadSectionsDone() {
    try { return JSON.parse(localStorage.getItem(STORAGE_SECTIONS_DONE_KEY) || '{}'); } catch (e) { return {}; }
  }
  function markSectionDone(matrixId) {
    const done = loadSectionsDone();
    done[landing.collection.round + ':' + matrixId] = true;
    localStorage.setItem(STORAGE_SECTIONS_DONE_KEY, JSON.stringify(done));
  }
  function isSectionDone(matrixId) {
    return !!loadSectionsDone()[landing.collection.round + ':' + matrixId];
  }

  function views() {
    return ['viewLoading', 'viewError', 'viewConsent', 'viewCode', 'viewSurvey', 'viewDone',
      'viewReview', 'viewWaitStart', 'viewSectionWait', 'viewDemographics'];
  }
  function show(id) { views().forEach(function (v) { document.getElementById(v).hidden = (v !== id); }); }
  function showError(title, msg) {
    document.getElementById('errorTitle').textContent = title;
    document.getElementById('errorMessage').textContent = msg || '';
    show('viewError');
  }
  function pairId(a, b) { return [a, b].sort().join(':'); }
  function answerKey(matrixId, a, b) { return matrixId + '::' + pairId(a, b); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  // A-over-B 값(예: 3, 1/3)을 사람이 읽는 응답형 문자열로.
  function fmtValue(v) {
    if (v == null) return '';
    if (Math.abs(v - 1) < 1e-9) return '1';
    if (v > 1) return String(Math.round(v));
    return '1/' + String(Math.round(1 / v));
  }

  // ── 저장 큐 ──────────────────────────────────────────────────────────────
  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(STORAGE_QUEUE_KEY) || '[]'); } catch (e) { return []; }
  }
  function saveQueue(q) { localStorage.setItem(STORAGE_QUEUE_KEY, JSON.stringify(q)); }

  let flushing = false;
  let backoff = 1000;
  function setConnBanner(state) {
    const bar = document.getElementById('connBar');
    const text = document.getElementById('connText');
    if (state === 'ok') { bar.hidden = true; bar.classList.remove('reconnecting'); return; }
    bar.hidden = false;
    bar.classList.toggle('reconnecting', state === 'retrying');
    text.textContent = '저장 재시도 중입니다… 입력하신 내용은 안전하게 보관되고 있습니다.';
  }

  async function flushQueue() {
    if (flushing) return;
    flushing = true;
    try {
      let queue = loadQueue();
      while (queue.length) {
        const item = queue[0];
        try {
          const res = await fetch('/api/respond/' + accessToken + '/answer', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + respondentToken },
            body: JSON.stringify(item),
          });
          if (res.status === 401) { await handleTokenExpired(); return; }
          if (!res.ok) throw new Error('save failed');
          const data = await res.json();
          matrixCrCache[item.matrix_id] = { complete: data.complete, cr: data.cr };
          queue.shift();
          saveQueue(queue);
          backoff = 1000;
          setConnBanner('ok');
        } catch (e) {
          setConnBanner('retrying');
          await new Promise(function (r) { setTimeout(r, backoff); });
          backoff = Math.min(backoff * 2, 15000);
        }
      }
    } finally {
      flushing = false;
      refreshCrBar();
    }
  }

  function queueAnswer(item) {
    const queue = loadQueue();
    queue.push(item);
    saveQueue(queue);
    flushQueue();
  }

  async function handleTokenExpired() {
    localStorage.removeItem(STORAGE_TOKEN_KEY);
    respondentToken = null;
    show('viewCode');
  }

  // ── 초기 로드 ──────────────────────────────────────────────────────────
  async function loadLanding() {
    const res = await fetch('/api/respond/' + accessToken);
    if (!res.ok) {
      if (res.status === 404) showError('링크를 찾을 수 없습니다', '주소가 정확한지 확인해 주세요.');
      else showError('연결할 수 없습니다', '잠시 후 다시 시도해 주세요.');
      throw new Error('landing failed');
    }
    landing = await res.json();
    if (landing.collection.status !== 'open') {
      showError('마감된 설문입니다', '이 설문은 더 이상 응답을 받지 않습니다.');
      throw new Error('closed');
    }
    buildQuestions();
  }

  function buildQuestions() {
    questions = [];
    landing.survey.matrices.forEach(function (m) {
      m.pairs.forEach(function (p) {
        const a = m.children.find(function (c) { return c.uuid === p.uuid_a; });
        const b = m.children.find(function (c) { return c.uuid === p.uuid_b; });
        questions.push({
          matrix_id: m.matrix_id, parent_name: m.parent_name, parent_description: m.parent_description,
          question_text: m.question_text, uuid_a: p.uuid_a, uuid_b: p.uuid_b,
          name_a: a ? a.name : p.uuid_a, name_b: b ? b.name : p.uuid_b,
          desc_a: (a && a.description) || '', desc_b: (b && b.description) || '',
          is_alternative: !!m.is_alternative,
        });
      });
    });
  }

  function matrixView(matrixId) {
    return landing.survey.matrices.find(function (m) { return m.matrix_id === matrixId; });
  }
  function pairsOfMatrix(matrixId) {
    return questions.filter(function (q) { return q.matrix_id === matrixId; });
  }

  function mergeServerAnswers(serverAnswers) {
    // serverAnswers: { matrix_id: { pair_id: value } } — 표시 방향으로 이미 해석돼 옴.
    Object.keys(serverAnswers || {}).forEach(function (mid) {
      Object.keys(serverAnswers[mid]).forEach(function (pid) {
        answers[mid + '::' + pid] = serverAnswers[mid][pid];
      });
    });
  }

  function renderConsent() {
    document.getElementById('consentTitle').textContent = landing.survey.title;
    document.getElementById('consentIntro').textContent = landing.survey.intro_text;
    document.getElementById('consentText').textContent = landing.survey.consent_text;
    show('viewConsent');
  }

  async function tryResume() {
    if (!respondentToken) { renderConsent(); return; }
    try {
      const res = await fetch('/api/respond/' + accessToken + '/me', {
        headers: { 'Authorization': 'Bearer ' + respondentToken },
      });
      if (res.status === 401) { await handleTokenExpired(); renderConsent(); return; }
      if (!res.ok) throw new Error('resume failed');
      const me = await res.json();
      answers = {};
      mergeServerAnswers(me.answers);
      clientSeq = me.client_seq || clientSeq;
      respondentAttributes = me.respondent.attributes || {};
      if (me.respondent.status === 'submitted' || Object.keys(respondentAttributes).length) {
        demographicsDone = true;
      }
      if (me.respondent.status === 'submitted') { everSubmitted = true; localStorage.setItem(STORAGE_SUBMITTED_KEY, '1'); }
      if (me.respondent.status === 'submitted') { await showDone(); return; }
      if (landing.collection.mode === 'realtime') { enterRealtimeFlow(); return; }
      buildActiveMatrices();
      currentMatrixIndex = firstIncompleteMatrixIndex();
      startSurvey();
    } catch (e) {
      renderConsent();
    }
  }

  function buildActiveMatrices() {
    if (landing.collection.mode !== 'realtime') {
      activeMatrices = landing.survey.matrices.slice();
      return;
    }
    const targetId = revisionMatrixId || landing.collection.active_matrix_id;
    activeMatrices = landing.survey.matrices.filter(function (m) { return m.matrix_id === targetId; });
  }

  function pairValue(q) {
    const k = answerKey(q.matrix_id, q.uuid_a, q.uuid_b);
    return (k in answers) ? answers[k] : null;
  }
  function matrixComplete(m) {
    return pairsOfMatrix(m.matrix_id).every(function (q) { return pairValue(q) !== null; });
  }
  function firstIncompleteMatrixIndex() {
    const i = activeMatrices.findIndex(function (m) { return !matrixComplete(m); });
    return i === -1 ? Math.max(0, activeMatrices.length - 1) : i;
  }

  // ── 실시간 흐름 ──────────────────────────────────────────────────────────
  function enterRealtimeFlow() {
    buildActiveMatrices();
    if (!landing.collection.session_started) { showWaitStart(); return; }
    const targetId = revisionMatrixId || landing.collection.active_matrix_id;
    if (!targetId) { finishSurvey(); return; }
    if (!revisionMatrixId && isSectionDone(targetId)) { showSectionWait(); return; }
    currentMatrixIndex = 0;
    startSurvey();
  }

  async function submitCode(code) {
    const btn = document.getElementById('codeSubmitBtn');
    const errEl = document.getElementById('codeError');
    errEl.hidden = true;
    btn.disabled = true;
    try {
      const res = await fetch('/api/respond/' + accessToken + '/verify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code, consent: true }),
      });
      if (!res.ok) {
        const d = await res.json().catch(function () { return {}; });
        errEl.textContent = d.detail || '코드를 확인할 수 없습니다';
        errEl.hidden = false;
        return;
      }
      const data = await res.json();
      respondentToken = data.token;
      localStorage.setItem(STORAGE_TOKEN_KEY, respondentToken);
      answers = {};
      if (landing.collection.mode === 'realtime') { enterRealtimeFlow(); return; }
      buildActiveMatrices();
      currentMatrixIndex = 0;
      startSurvey();
    } catch (e) {
      errEl.textContent = '연결에 실패했습니다. 다시 시도해 주세요';
      errEl.hidden = false;
    } finally {
      btn.disabled = false;
    }
  }

  // ── 설문 화면 ──────────────────────────────────────────────────────────
  function startSurvey() {
    show('viewSurvey');
    renderHierarchyOnce();
    renderMatrixPage();
    connectRealtimeIfNeeded();
  }

  let hierarchyRendered = false;
  function renderHierarchyOnce() {
    if (hierarchyRendered) return;
    const nodes = (landing.survey.hierarchy_nodes || []);
    if (!nodes.length || !window.AHPHierarchyDiagram) { document.querySelector('.hd-card').hidden = true; return; }
    window.AHPHierarchyDiagram.render(document.getElementById('hdCanvas'), nodes);
    hierarchyRendered = true;
  }

  // 17칸 가로 눈금: 왼쪽 9..2 = A가 n배(value=n), 가운데 1, 오른쪽 2..9 = B가 n배(value=1/n).
  function scaleCells() {
    const out = [];
    for (let n = 9; n >= 2; n--) out.push({ v: n, txt: String(n), side: 'a' });
    out.push({ v: 1, txt: '1', side: 'eq' });
    for (let n = 2; n <= 9; n++) out.push({ v: 1 / n, txt: String(n), side: 'b' });
    return out;
  }
  const SCALE_CELLS = scaleCells();

  // q: {matrix_id, uuid_a, uuid_b, name_a, name_b, desc_a, desc_b, is_alternative}
  function renderPairScaleRow(q, opts) {
    opts = opts || {};
    const cur = opts.value !== undefined ? opts.value : pairValue(q);
    const cells = SCALE_CELLS.map(function (c) {
      const on = cur != null && Math.abs(c.v - cur) < 1e-9;
      return '<button type="button" class="scale-cell' + (c.side === 'eq' ? ' eq' : '') +
        (on ? ' on' : '') + '" data-v="' + c.v + '">' + c.txt + '</button>';
    }).join('');
    const descLine = (q.desc_a || q.desc_b)
      ? '<div class="pair-desc"><span>' + (q.desc_a ? esc(q.name_a) + ': ' + esc(q.desc_a) : '') + '</span>' +
        '<span>' + (q.desc_b ? esc(q.name_b) + ': ' + esc(q.desc_b) : '') + '</span></div>'
      : '';
    const badge = opts.suggestBadge
      ? '<div class="pair-suggest">⚠ 가장 모순적인 응답 · 추천 ' +
        (opts.given ? esc(opts.given) + ' → ' : '') + '<b>' + esc(opts.suggest) + '</b></div>'
      : '';
    return '<div class="pair-row' + (opts.worst ? ' worst' : '') + '" data-mid="' + q.matrix_id +
      '" data-a="' + q.uuid_a + '" data-b="' + q.uuid_b + '">' +
      '<div class="pair-names"><span>' + esc(q.name_a) + '</span><span>' + esc(q.name_b) + '</span></div>' +
      descLine + badge +
      '<div class="pair-dir"><span>◀ ‘' + esc(q.name_a) + '’이 더 중요</span>' +
      '<span>‘' + esc(q.name_b) + '’이 더 중요 ▶</span></div>' +
      '<div class="scale">' + cells + '</div></div>';
  }

  function renderMatrixPage() {
    const m = activeMatrices[currentMatrixIndex];
    if (!m) return;
    document.getElementById('qParentName').textContent = (m.is_alternative ? '대안 비교 · ' : '') + m.parent_name;
    document.getElementById('qParentDesc').textContent = m.parent_description || '';
    document.getElementById('qParentDesc').hidden = !m.parent_description;
    document.getElementById('qQuestionText').textContent = m.question_text;
    document.getElementById('pairList').innerHTML = pairsOfMatrix(m.matrix_id)
      .map(function (q) { return renderPairScaleRow(q); }).join('');
    document.getElementById('qCounter').textContent =
      (currentMatrixIndex + 1) + ' / ' + activeMatrices.length + ' 기준';
    document.getElementById('prevBtn').disabled = currentMatrixIndex === 0;
    updateNav();
    updateProgress();
    refreshCrBar();
  }

  function updateNav() {
    const isRealtime = landing.collection.mode === 'realtime';
    const isLast = currentMatrixIndex === activeMatrices.length - 1;
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');
    nextBtn.hidden = isLast && !isRealtime;
    nextBtn.textContent = isLast ? (isRealtime ? '완료' : '다음') : '다음';
    submitBtn.hidden = isRealtime;
    if (!isRealtime) {
      const allDone = activeMatrices.every(matrixComplete);
      submitBtn.disabled = !allDone;
      submitBtn.classList.toggle('ready', allDone);
    }
  }

  function updateProgress() {
    let total = 0, done = 0;
    activeMatrices.forEach(function (m) {
      pairsOfMatrix(m.matrix_id).forEach(function (q) { total += 1; if (pairValue(q) !== null) done += 1; });
    });
    const pct = total ? Math.round(100 * done / total) : 100;
    document.getElementById('progressFill').style.width = pct + '%';
    document.getElementById('progressText').textContent = pct + '% 완료';
  }

  function crState(cr) {
    const th = landing.survey.cr_threshold || 0.1;
    if (cr == null) return { cls: '', txt: '-' };
    return { cls: cr <= th ? 'ok' : 'bad', txt: 'CR ' + cr.toFixed(3) + (cr <= th ? ' · 양호' : ' · 주의') };
  }
  function refreshCrBar() { renderCrBar(document.getElementById('matrixCrBar')); }
  function renderCrBar(el) {
    if (!el) return;
    if (document.getElementById('viewSurvey').hidden) { el.hidden = true; return; }
    const m = activeMatrices[currentMatrixIndex];
    if (!m || m.children.length < 3) { el.hidden = true; return; }
    if (!everSubmitted) {
      el.hidden = false; el.className = 'cr-bar muted';
      el.textContent = '일관성(CR)은 제출 후 공개됩니다';
      return;
    }
    const info = matrixCrCache[m.matrix_id];
    const s = crState(info && info.complete ? info.cr : null);
    el.hidden = false;
    el.className = 'cr-bar ' + s.cls;
    el.textContent = '이 기준 ' + (info && info.complete ? s.txt : 'CR: 응답 완료 후 표시');
  }

  function showWaitStart() { show('viewWaitStart'); connectRealtimeIfNeeded(); }
  function showSectionWait() {
    const box = document.getElementById('sectionWaitResults');
    box.innerHTML = ''; box.hidden = true;
    show('viewSectionWait');
    connectRealtimeIfNeeded();
  }

  function nodeNameByUuid(uuid) {
    for (let i = 0; i < questions.length; i++) {
      if (questions[i].uuid_a === uuid) return questions[i].name_a;
      if (questions[i].uuid_b === uuid) return questions[i].name_b;
    }
    return uuid;
  }

  function renderSectionWaitResults(msg, isIndividual) {
    if (document.getElementById('viewSectionWait').hidden) return;
    if (msg.matrix_id !== (revisionMatrixId || landing.collection.active_matrix_id)) return;
    const box = document.getElementById('sectionWaitResults');
    const cr = isIndividual ? msg.cr : msg.avg_cr;
    const crLine = (cr == null) ? '' : '<div class="swr-cr">CR ' + cr.toFixed(3) + '</div>';
    const rows = Object.keys(msg.weights || {})
      .sort(function (a, b) { return msg.weights[b] - msg.weights[a]; })
      .map(function (uuid) {
        return '<div class="swr-row"><span>' + esc(nodeNameByUuid(uuid)) + '</span>' +
          '<span>' + (msg.weights[uuid] * 100).toFixed(1) + '%</span></div>';
      }).join('');
    box.innerHTML = '<h3>' + (isIndividual ? '나의 결과' : '그룹 결과') + '</h3>' + crLine + rows;
    box.hidden = false;
  }

  // ── 실시간 수신 소켓 ──────────────────────────────────────────────────────
  let realtimeSocket = null;

  function showNotice(msg) {
    const el = document.getElementById('patchNotice');
    document.getElementById('patchNoticeText').textContent = msg;
    el.hidden = false;
    setTimeout(function () { el.hidden = true; }, 3200);
  }

  function connectRealtimeIfNeeded() {
    if (landing.collection.mode !== 'realtime' || realtimeSocket) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(proto + '//' + location.host + '/ws/respond/' + accessToken);
    realtimeSocket = ws;
    ws.addEventListener('open', function () { ws.send(JSON.stringify({ type: 'auth', token: respondentToken })); });
    ws.addEventListener('message', function (e) {
      let msg;
      try { msg = JSON.parse(e.data); } catch (err) { return; }
      if (msg.event === 'survey.patch') handleSurveyPatch(msg);
      else if (msg.event === 'round.advanced') handleRoundAdvanced(msg);
      else if (msg.event === 'section.unlock') handleSectionUnlock(msg);
      else if (msg.event === 'session.started') handleSessionStarted(msg);
      else if (msg.event === 'section.advanced') handleSectionAdvanced(msg);
      else if (msg.event === 'section.results') renderSectionWaitResults(msg, false);
      else if (msg.event === 'section.individual_result') renderSectionWaitResults(msg, true);
      else if (msg.event === 'section.revision_requested') handleRevisionRequested(msg);
      else if (msg.event === 'answer.override') handleAnswerOverride(msg);
    });
    ws.addEventListener('close', function () {
      realtimeSocket = null;
      setTimeout(function () {
        const still = ['viewSurvey', 'viewWaitStart', 'viewSectionWait', 'viewReview', 'viewDone']
          .some(function (id) { return document.getElementById(id).hidden === false; });
        if (still) connectRealtimeIfNeeded();
      }, 2000);
    });
  }

  async function handleSurveyPatch(msg) {
    landing.survey.matrices = msg.matrices;
    landing.survey.node_descriptions = msg.node_descriptions;
    showNotice('연구자가 설문 문항을 수정했습니다. 최신 내용으로 갱신합니다.');
    try {
      const res = await fetch('/api/respond/' + accessToken + '/me', {
        headers: { 'Authorization': 'Bearer ' + respondentToken },
      });
      if (res.ok) { const me = await res.json(); answers = {}; mergeServerAnswers(me.answers); }
    } catch (e) { /* keep local */ }
    buildQuestions();
    if (document.getElementById('viewSurvey').hidden) return;
    buildActiveMatrices();
    currentMatrixIndex = Math.min(currentMatrixIndex, activeMatrices.length - 1);
    renderMatrixPage();
  }

  async function handleRoundAdvanced(msg) {
    showNotice((msg.round) + '라운드가 시작되었습니다. 이어서 응답해 주세요.');
    if (landing.collection.mode === 'realtime') {
      try {
        const res = await fetch('/api/respond/' + accessToken);
        if (res.ok) { landing = await res.json(); buildQuestions(); }
      } catch (e) { /* keep */ }
      revisionMatrixId = null;
      const waiting = ['viewDone', 'viewWaitStart', 'viewSectionWait', 'viewSurvey', 'viewReview']
        .some(function (id) { return document.getElementById(id).hidden === false; });
      if (waiting) enterRealtimeFlow();
      return;
    }
    if (!document.getElementById('viewDone').hidden) {
      buildActiveMatrices();
      currentMatrixIndex = 0;
      startSurvey();
    }
  }

  function handleSessionStarted(msg) {
    landing.collection.session_started = true;
    landing.collection.active_matrix_id = msg.matrix_id;
    revisionMatrixId = null;
    showNotice('연구자가 설문을 시작했습니다.');
    if (document.getElementById('viewWaitStart').hidden === false) enterRealtimeFlow();
  }

  function handleSectionAdvanced(msg) {
    landing.collection.active_matrix_id = msg.matrix_id;
    revisionMatrixId = null;
    if (msg.done) { showNotice('모든 섹션이 끝났습니다. 제출을 마무리합니다.'); finishSurvey(); return; }
    showNotice('다음 섹션이 열렸습니다.');
    const waiting = ['viewSectionWait', 'viewWaitStart'].some(function (id) {
      return document.getElementById(id).hidden === false;
    });
    if (waiting) enterRealtimeFlow();
  }

  function handleRevisionRequested(msg) {
    revisionMatrixId = msg.matrix_id;
    revisionWorst = msg.worst_pairs || [];
    showNotice('연구자가 이 항목의 응답을 다시 확인해 달라고 요청했습니다.');
    enterRealtimeFlow();
  }

  function handleSectionUnlock(msg) {
    const q = pairsOfMatrix(msg.matrix_id)[0];
    const name = q ? q.parent_name : '이 항목';
    if (landing.collection.mode === 'realtime') {
      revisionMatrixId = msg.matrix_id;
      revisionWorst = [];
      showNotice('연구자가 "' + name + '" 항목을 전원에게 다시 열었습니다. 이어서 응답해 주세요.');
      enterRealtimeFlow();
      return;
    }
    pendingReopenMatrixId = msg.matrix_id;
    const onDone = document.getElementById('viewDone').hidden === false;
    showNotice('연구자가 "' + name + '" 항목을 다시 열었습니다. ' +
      (onDone ? '아래 항목을 눌러 조정해 주세요.' : '이어서 응답해 주세요.'));
  }

  // 진행자가 콘솔에서 이 참여자 답을 고침 → 로컬에 즉시 반영(원복 방지).
  function handleAnswerOverride(msg) {
    const q = pairsOfMatrix(msg.matrix_id).find(function (x) {
      return pairId(x.uuid_a, x.uuid_b) === pairId(msg.uuid_a, msg.uuid_b);
    });
    if (!q) return;
    // msg.value_a_over_b 는 msg.uuid_a 기준. 이 화면 질문의 a 기준으로 방향 맞춤.
    const v = (q.uuid_a === msg.uuid_a) ? msg.value_a_over_b : (1 / msg.value_a_over_b);
    answers[answerKey(q.matrix_id, q.uuid_a, q.uuid_b)] = v;
    matrixCrCache[msg.matrix_id] = { complete: !!msg.complete, cr: msg.cr };
    showNotice('연구자가 함께 확인한 값으로 응답이 조정되었습니다.');
    if (!document.getElementById('viewSurvey').hidden) renderMatrixPage();
    if (!document.getElementById('viewReview').hidden && reviewMatrixId === msg.matrix_id) refreshReview();
  }

  // ── 네비게이션 ──────────────────────────────────────────────────────────
  function crWarningIfNeeded(matrixId) {
    const info = matrixCrCache[matrixId];
    if (!info || !info.complete) return null;
    const th = landing.survey.cr_threshold || 0.1;
    return info.cr > th ? info : null;
  }

  async function leaveCurrentMatrix() {
    // 현재 기준을 떠나기 전 저장 flush.
    await flushQueue();
    // CR 경고/차단은 "최초 제출 이후"에만 — 그 전에는 가중치·CR을 아직 보여주지
    // 않았으므로 CR을 이유로 진행을 막으면 참가자에게 혼란만 준다. 최초 제출 후
    // 마지막 화면에서 이유를 설명한 뒤부터 수정을 요청한다.
    if (everSubmitted) {
      const m = activeMatrices[currentMatrixIndex];
      if (m && matrixComplete(m)) {
        const warn = crWarningIfNeeded(m.matrix_id);
        if (warn) {
          const msg = '이 기준의 응답이 다소 일관되지 않습니다 (CR ' + warn.cr.toFixed(2) + ').';
          if (landing.survey.cr_action === 'block') { alert(msg + ' 아래에서 다시 조정해 주세요.'); return false; }
          if (!confirm(msg + ' 계속 진행할까요?')) return false;
        }
      }
    }
    return true;
  }

  async function goNext() {
    if (!(await leaveCurrentMatrix())) return;
    if (currentMatrixIndex < activeMatrices.length - 1) {
      currentMatrixIndex += 1;
      renderMatrixPage();
      document.getElementById('viewSurvey').scrollTo && window.scrollTo(0, 0);
    } else if (landing.collection.mode === 'realtime') {
      const m = activeMatrices[currentMatrixIndex];
      if (revisionMatrixId === m.matrix_id) revisionMatrixId = null;
      else markSectionDone(m.matrix_id);
      enterRealtimeFlow();
    } else {
      await finishSurvey();
    }
  }

  function goPrev() {
    if (currentMatrixIndex === 0) return;
    currentMatrixIndex -= 1;
    renderMatrixPage();
    window.scrollTo(0, 0);
  }

  async function onSubmitBtn() {
    if (!activeMatrices.every(matrixComplete)) return;
    if (!(await leaveCurrentMatrix())) return;
    // 남은 기준 중 CR 경고가 있으면 한 번 더 확인
    await finishSurvey();
  }

  function needsDemographics() {
    return landing.survey.collect_demographics &&
      (landing.survey.demographics || []).length && !demographicsDone;
  }

  async function finishSurvey() {
    if (needsDemographics()) { renderDemographics(); show('viewDemographics'); return; }
    await flushQueue();
    try {
      const res = await fetch('/api/respond/' + accessToken + '/submit', {
        method: 'POST', headers: { 'Authorization': 'Bearer ' + respondentToken },
      });
      if (res.status === 401) { await handleTokenExpired(); return; }
      if (!res.ok && res.status !== 409) throw new Error('submit failed');
      everSubmitted = true;
      localStorage.setItem(STORAGE_SUBMITTED_KEY, '1');
      await showDone();
    } catch (e) {
      alert('제출 중 문제가 발생했습니다. 다시 시도해 주세요.');
    }
  }

  // ── 인구통계 화면 ──────────────────────────────────────────────────────────
  function renderDemographics() {
    const fields = landing.survey.demographics || [];
    document.getElementById('demoForm').innerHTML = fields.map(function (f) {
      const saved = respondentAttributes[f.id];
      let control = '';
      if (f.type === 'single') {
        control = (f.options || []).map(function (o) {
          const on = String(saved) === String(o.code) ? ' checked' : '';
          return '<label class="demo-choice"><input type="radio" name="demo_' + f.id + '" value="' + esc(o.code) + '"' + on + '> ' + esc(o.label) + '</label>';
        }).join('');
      } else if (f.type === 'multi') {
        const set = Array.isArray(saved) ? saved.map(String) : [];
        control = (f.options || []).map(function (o) {
          const on = set.indexOf(String(o.code)) !== -1 ? ' checked' : '';
          return '<label class="demo-choice"><input type="checkbox" name="demo_' + f.id + '" value="' + esc(o.code) + '"' + on + '> ' + esc(o.label) + '</label>';
        }).join('');
      } else if (f.type === 'number') {
        control = '<input type="number" class="demo-input" data-fid="' + f.id + '" value="' + (saved != null ? esc(saved) : '') + '">';
      } else {
        control = '<input type="text" class="demo-input" data-fid="' + f.id + '" value="' + (saved != null ? esc(saved) : '') + '">';
      }
      return '<div class="demo-field" data-fid="' + f.id + '" data-type="' + f.type + '">' +
        '<div class="demo-q">' + esc(f.label) + (f.required ? ' <span class="demo-req">*</span>' : '') + '</div>' +
        control + '</div>';
    }).join('');
    document.getElementById('demoError').hidden = true;
  }

  function collectDemoAnswers() {
    const out = {};
    document.querySelectorAll('#demoForm .demo-field').forEach(function (el) {
      const fid = el.dataset.fid, type = el.dataset.type;
      if (type === 'single') {
        const r = el.querySelector('input[type=radio]:checked');
        if (r) out[fid] = r.value;
      } else if (type === 'multi') {
        const vals = Array.prototype.map.call(el.querySelectorAll('input[type=checkbox]:checked'), function (c) { return c.value; });
        if (vals.length) out[fid] = vals;
      } else {
        const v = el.querySelector('.demo-input').value.trim();
        if (v) out[fid] = v;
      }
    });
    return out;
  }

  async function submitDemographics() {
    const answersOut = collectDemoAnswers();
    const btn = document.getElementById('demoSubmitBtn');
    btn.disabled = true;
    try {
      const res = await fetch('/api/respond/' + accessToken + '/demographics', {
        method: 'PUT',
        headers: { 'Authorization': 'Bearer ' + respondentToken, 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: answersOut }),
      });
      if (res.status === 401) { await handleTokenExpired(); return; }
      const d = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        const el = document.getElementById('demoError');
        el.textContent = d.detail || d.message || '저장에 실패했습니다.';
        el.hidden = false;
        return;
      }
      respondentAttributes = d.attributes || {};
      demographicsDone = true;
      await finishSurvey();
    } catch (e) {
      const el = document.getElementById('demoError');
      el.textContent = '네트워크 오류로 저장하지 못했습니다.';
      el.hidden = false;
    } finally {
      btn.disabled = false;
    }
  }

  // ── 제출 완료 화면 ──────────────────────────────────────────────────────────
  async function showDone() {
    show('viewDone');
    const box = document.getElementById('crSummaryList');
    box.innerHTML = '<p class="muted">CR을 불러오는 중입니다…</p>';
    try {
      const res = await fetch('/api/respond/' + accessToken + '/summary', {
        headers: { 'Authorization': 'Bearer ' + respondentToken },
      });
      if (!res.ok) throw new Error('summary failed');
      const data = await res.json();
      const anyBad = data.items.some(function (it) {
        return it.cr != null && it.cr > data.cr_threshold;
      });
      document.getElementById('crExplain').hidden = !anyBad;
      if (!data.items.length) { box.innerHTML = ''; return; }
      box.innerHTML = data.items.map(function (it) {
        const cls = (it.cr == null) ? '' : (it.cr <= data.cr_threshold ? 'ok' : 'bad');
        const crText = (it.cr == null) ? '-' : ('CR ' + it.cr.toFixed(3));
        return '<button type="button" class="cr-summary-row ' + cls + '" data-matrix="' + it.matrix_id + '">' +
          '<span class="csr-name">' + esc(it.parent_name) + '</span>' +
          '<span class="csr-cr">' + crText + '</span></button>';
      }).join('');
    } catch (e) {
      box.innerHTML = '';
      document.getElementById('crExplain').hidden = true;
    }
  }

  // ── 수정 화면 — what-if 가중치 차트 + 응답형 추천 ─────────────────────────
  let reviewMatrixId = null;
  let reviewWorstPids = {};      // pid -> {given_label, suggested_label}
  let reviewEval = null;         // 최근 matrix-eval 결과
  let rankFocus = 0;            // 좌우 화살표 포커스 (ranking 인덱스)
  let evalTimer = null;

  function enterReview(matrixId) {
    reviewMatrixId = matrixId;
    rankFocus = 0;
    reviewWorstPids = {};
    (revisionMatrixId === matrixId ? revisionWorst : []).forEach(function (w) {
      reviewWorstPids[pairId(w.uuid_a, w.uuid_b)] = w;
    });
    const qs = pairsOfMatrix(matrixId);
    document.getElementById('reviewTitle').textContent =
      (qs[0] && qs[0].is_alternative ? '대안 비교 · ' : '') + (qs[0] ? qs[0].parent_name : '');
    renderReviewPairs();
    show('viewReview');
    refreshReview();
  }

  function renderReviewPairs() {
    const qs = pairsOfMatrix(reviewMatrixId);
    document.getElementById('reviewPairs').innerHTML = qs.map(function (q) {
      const pid = pairId(q.uuid_a, q.uuid_b);
      const w = reviewWorstPids[pid];
      return renderPairScaleRow(q, {
        worst: !!w,
        suggestBadge: !!w,
        given: w ? (w.given_label || fmtValue(pairValue(q))) : '',
        suggest: w ? w.suggested_label : '',
      });
    }).join('');
  }

  function currentOverrides() {
    return pairsOfMatrix(reviewMatrixId).map(function (q) {
      const v = pairValue(q);
      return v == null ? null : { uuid_a: q.uuid_a, uuid_b: q.uuid_b, value_a_over_b: v };
    }).filter(Boolean);
  }

  function refreshReview() {
    clearTimeout(evalTimer);
    evalTimer = setTimeout(async function () {
      try {
        const res = await fetch('/api/respond/' + accessToken + '/matrix-eval', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + respondentToken, 'Content-Type': 'application/json' },
          body: JSON.stringify({ matrix_id: reviewMatrixId, overrides: currentOverrides() }),
        });
        if (!res.ok) return;
        reviewEval = await res.json();
        // worst 힌트를 서버 최신값으로 갱신(응답형 라벨 포함)
        reviewWorstPids = {};
        (reviewEval.worst_pairs || []).slice(0, 1).forEach(function (w) {
          reviewWorstPids[w.pair_id] = w;
        });
        renderReviewPairs();
        renderReviewChart();
      } catch (e) { /* ignore */ }
    }, 250);
  }

  function renderReviewChart() {
    const el = document.getElementById('reviewChart');
    const crBar = document.getElementById('reviewCrBar');
    if (!reviewEval || reviewEval.incomplete) {
      el.innerHTML = '<p class="muted" style="font-size:12.5px">모든 쌍을 응답하면 가중치·CR이 표시됩니다.</p>';
      crBar.hidden = true;
      document.getElementById('rankFocusLabel').textContent = '';
      return;
    }
    const s = crState(reviewEval.cr);
    crBar.hidden = false; crBar.className = 'cr-bar ' + s.cls;
    crBar.textContent = s.txt;

    const ranking = reviewEval.ranking || [];
    if (rankFocus >= ranking.length) rankFocus = ranking.length - 1;
    if (rankFocus < 0) rankFocus = 0;
    const maxW = Math.max.apply(null, ranking.map(function (u) { return reviewEval.weights[u] || 0; }).concat([1e-6]));
    el.innerHTML = ranking.map(function (u, i) {
      const w = reviewEval.weights[u] || 0;
      const focus = i === rankFocus;
      const near = i === rankFocus - 1 || i === rankFocus + 1;
      return '<div class="wc-row' + (focus ? ' focus' : (near ? ' near' : '')) + '">' +
        '<span class="wc-name">' + esc(reviewEval.names[u] || u) + '</span>' +
        '<span class="wc-bar"><span style="width:' + (w / maxW * 100).toFixed(1) + '%"></span></span>' +
        '<span class="wc-val">' + (w * 100).toFixed(1) + '%</span></div>';
    }).join('');

    const focusU = ranking[rankFocus];
    document.getElementById('rankFocusLabel').textContent = focusU
      ? (rankFocus + 1) + '위 ' + (reviewEval.names[focusU] || focusU) + ' · ' + (reviewEval.weights[focusU] * 100).toFixed(1) + '%'
      : '';
  }

  // ── 초기화 ──────────────────────────────────────────────────────────────
  function scaleClickHandler(container, onPick) {
    container.addEventListener('click', function (e) {
      const cell = e.target.closest('.scale-cell');
      if (!cell) return;
      const row = e.target.closest('.pair-row');
      if (!row) return;
      const v = Number(cell.dataset.v);
      row.querySelectorAll('.scale-cell').forEach(function (c) { c.classList.toggle('on', c === cell); });
      const mid = row.dataset.mid, a = row.dataset.a, b = row.dataset.b;
      answers[answerKey(mid, a, b)] = v;
      clientSeq += 1;
      localStorage.setItem(STORAGE_SEQ_KEY, String(clientSeq));
      queueAnswer({ matrix_id: mid, uuid_a: a, uuid_b: b, value: v, client_seq: clientSeq });
      onPick();
    });
  }

  function init() {
    document.getElementById('consentCheck').addEventListener('change', function (e) {
      document.getElementById('consentNextBtn').disabled = !e.target.checked;
    });
    document.getElementById('consentNextBtn').addEventListener('click', function () { show('viewCode'); });

    document.getElementById('codeInput').addEventListener('input', function (e) { e.target.value = e.target.value.toUpperCase(); });
    document.getElementById('codeInput').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') submitCode(document.getElementById('codeInput').value);
    });
    document.getElementById('codeSubmitBtn').addEventListener('click', function () {
      submitCode(document.getElementById('codeInput').value);
    });

    document.getElementById('hdToggle').addEventListener('click', function () {
      const box = document.getElementById('hdBox');
      box.hidden = !box.hidden;
      document.getElementById('hdToggleIcon').textContent = box.hidden ? '▸' : '▾';
    });
    document.getElementById('hdZoom').addEventListener('click', function (e) {
      e.stopPropagation();
      document.getElementById('hdBox').classList.toggle('fit');
    });

    scaleClickHandler(document.getElementById('pairList'), function () {
      updateProgress(); updateNav(); refreshCrBar();
    });
    scaleClickHandler(document.getElementById('reviewPairs'), function () {
      refreshReview();
    });

    document.getElementById('nextBtn').addEventListener('click', goNext);
    document.getElementById('prevBtn').addEventListener('click', goPrev);
    document.getElementById('submitBtn').addEventListener('click', onSubmitBtn);
    document.getElementById('demoSubmitBtn').addEventListener('click', submitDemographics);

    document.getElementById('editAnswersBtn').addEventListener('click', function () {
      buildActiveMatrices();
      if (pendingReopenMatrixId) {
        const i = activeMatrices.findIndex(function (m) { return m.matrix_id === pendingReopenMatrixId; });
        currentMatrixIndex = i !== -1 ? i : 0;
        pendingReopenMatrixId = null;
      } else {
        currentMatrixIndex = 0;
      }
      startSurvey();
    });

    document.getElementById('crSummaryList').addEventListener('click', function (e) {
      const row = e.target.closest('.cr-summary-row');
      if (row) enterReview(row.dataset.matrix);
    });
    document.getElementById('reviewBackBtn').addEventListener('click', function () { showDone(); });
    document.getElementById('reviewDoneBtn').addEventListener('click', async function () {
      await flushQueue();
      await showDone();
    });
    document.getElementById('rankPrevBtn').addEventListener('click', function () { rankFocus -= 1; renderReviewChart(); });
    document.getElementById('rankNextBtn').addEventListener('click', function () { rankFocus += 1; renderReviewChart(); });

    window.addEventListener('online', flushQueue);
    run();
  }

  async function run() {
    show('viewLoading');
    try { await loadLanding(); } catch (e) { return; }
    await tryResume();
  }

  init();
})();
