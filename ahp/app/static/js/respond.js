(function () {
  'use strict';

  const accessToken = location.pathname.split('/')[2];
  const STORAGE_TOKEN_KEY = 'ahp_respondent_token_' + accessToken;
  const STORAGE_QUEUE_KEY = 'ahp_queue_' + accessToken;
  const STORAGE_SEQ_KEY = 'ahp_seq_' + accessToken;

  // 5점 축약형은 "최대 강도를 5로 낮춘 다른 척도"가 아니라, 같은 1~9 비율
  // 척도에서 선택지 수만 줄인 것이다(홀수 지점만 제시). 최대 강도는 여전히
  // 9이고, 그래야 CI/CR·RI 표 등 계산 계층이 흔들리지 않는다.
  const INTENSITY_LEVELS_BY_SCALE = { 9: [2, 3, 4, 5, 6, 7, 8, 9], 5: [3, 5, 7, 9] };
  const INTENSITY_LABELS = {
    2: '약간~보통 사이', 3: '약간 더 중요', 4: '보통~강함 사이', 5: '강하게 중요',
    6: '강함~매우 사이', 7: '매우 중요', 8: '매우~절대 사이', 9: '절대적으로 중요',
  };

  let landing = null;
  let respondentToken = localStorage.getItem(STORAGE_TOKEN_KEY);
  let pendingReopenMatrixId = null;
  let questions = [];
  let currentIndex = 0;
  let answers = {};
  let matrixCrCache = {};
  let clientSeq = Number(localStorage.getItem(STORAGE_SEQ_KEY) || 0);
  let pendingSide = null;
  let pendingIntensity = null;

  function views() { return ['viewLoading', 'viewError', 'viewConsent', 'viewCode', 'viewSurvey', 'viewDone']; }
  function show(id) { views().forEach(function (v) { document.getElementById(v).hidden = (v !== id); }); }
  function showError(title, msg) {
    document.getElementById('errorTitle').textContent = title;
    document.getElementById('errorMessage').textContent = msg || '';
    show('viewError');
  }
  function pairId(a, b) { return [a, b].sort().join(':'); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ── 저장 큐(네트워크 문제에도 입력을 잃지 않는다, PLAN.md 4.6) ─────────────
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
          is_alternative: !!m.is_alternative,
          is_last_in_matrix: false,
        });
      });
    });
    const seen = {};
    for (let i = questions.length - 1; i >= 0; i--) {
      if (!seen[questions[i].matrix_id]) { questions[i].is_last_in_matrix = true; seen[questions[i].matrix_id] = true; }
    }
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
      Object.keys(me.answers).forEach(function (mid) { Object.assign(answers, me.answers[mid]); });
      clientSeq = me.client_seq || clientSeq;
      if (me.respondent.status === 'submitted') { await showDone(); return; }
      currentIndex = questions.findIndex(function (q) { return !(pairId(q.uuid_a, q.uuid_b) in answers); });
      if (currentIndex === -1) currentIndex = questions.length ? questions.length - 1 : 0;
      startSurvey();
    } catch (e) {
      renderConsent();
    }
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
      currentIndex = 0;
      answers = {};
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
    renderQuestion();
    connectRealtimeIfNeeded();
  }

  // ── 실시간 수신 전용 소켓 (PLAN.md 7.2) ────────────────────────────────
  // 응답 저장은 여기서 하지 않는다 — 이미 검증된 HTTP 저장 경로를 그대로 쓰고,
  // 이 소켓은 관리자가 문항을 실시간으로 고쳤을 때 그 사실만 받아서 반영한다.
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

    ws.addEventListener('open', function () {
      ws.send(JSON.stringify({ type: 'auth', token: respondentToken }));
    });
    ws.addEventListener('message', function (e) {
      let msg;
      try { msg = JSON.parse(e.data); } catch (err) { return; }
      if (msg.event === 'survey.patch') handleSurveyPatch(msg);
      else if (msg.event === 'round.advanced') handleRoundAdvanced(msg);
      else if (msg.event === 'section.unlock') handleSectionUnlock(msg);
    });
    ws.addEventListener('close', function () {
      realtimeSocket = null;
      // 재연결(지수 백오프) — 응답 저장 자체는 HTTP라 끊겨도 입력을 잃지 않지만,
      // 문항 실시간 반영 채널은 계속 살려 둔다.
      setTimeout(function () { if (document.getElementById('viewSurvey').hidden === false) connectRealtimeIfNeeded(); }, 2000);
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
      if (res.ok) {
        const me = await res.json();
        answers = {};
        Object.keys(me.answers).forEach(function (mid) { Object.assign(answers, me.answers[mid]); });
      }
    } catch (e) { /* 서버 재조회 실패해도 로컬 답은 유지하고 계속 진행 */ }
    buildQuestions();
    currentIndex = questions.findIndex(function (q) { return !(pairId(q.uuid_a, q.uuid_b) in answers); });
    if (currentIndex === -1) currentIndex = questions.length ? questions.length - 1 : 0;
    renderQuestion();
  }

  function handleRoundAdvanced(msg) {
    showNotice((msg.round) + '라운드가 시작되었습니다. 이어서 응답해 주세요.');
    if (!document.getElementById('viewDone').hidden) {
      currentIndex = 0;
      startSurvey();
    }
  }

  // 연구자가 콘솔에서 특정 섹션(계층 매트릭스)만 다시 열었을 때 — 이미 제출을
  // 마친 응답자도 이 항목만 다시 조정할 수 있게 안내한다(PLAN.md 3절: 델파이는
  // 계층 하나하나가 곧 라운드이기도 하다).
  function handleSectionUnlock(msg) {
    const q = questions.find(function (qq) { return qq.matrix_id === msg.matrix_id; });
    const name = q ? q.parent_name : '이 항목';
    pendingReopenMatrixId = msg.matrix_id;
    const onDone = document.getElementById('viewDone').hidden === false;
    showNotice(
      '연구자가 "' + name + '" 항목을 다시 열었습니다. ' +
      (onDone ? '아래 "답변 수정하기"를 눌러 조정해 주세요.' : '이어서 응답해 주세요.')
    );
  }

  function currentValueForQuestion(q) {
    const pid = pairId(q.uuid_a, q.uuid_b);
    return (pid in answers) ? answers[pid] : null;
  }

  function renderQuestion() {
    const q = questions[currentIndex];
    document.getElementById('qParentName').textContent = (q.is_alternative ? '대안 비교 · ' : '') + q.parent_name;
    document.getElementById('qParentDesc').textContent = q.parent_description || '';
    document.getElementById('qParentDesc').hidden = !q.parent_description;
    document.getElementById('qQuestionText').textContent = q.question_text;
    document.getElementById('labelA').textContent = q.name_a;
    document.getElementById('labelB').textContent = q.name_b;
    document.getElementById('sideBtnAName').textContent = q.name_a;
    document.getElementById('sideBtnBName').textContent = q.name_b;
    document.getElementById('qCounter').textContent = (currentIndex + 1) + ' / ' + questions.length;
    document.getElementById('prevBtn').disabled = currentIndex === 0;

    const current = currentValueForQuestion(q);
    if (current === null) { pendingSide = null; pendingIntensity = null; }
    else if (Math.abs(current - 1) < 1e-9) { pendingSide = 'eq'; pendingIntensity = 1; }
    else if (current > 1) { pendingSide = 'a'; pendingIntensity = Math.round(current); }
    else { pendingSide = 'b'; pendingIntensity = Math.round(1 / current); }

    renderSideButtons();
    renderIntensity();
    updateProgress();
    updateNextButtonState();
  }

  function renderSideButtons() {
    document.querySelectorAll('.side-btn').forEach(function (btn) {
      btn.classList.toggle('selected', btn.dataset.side === pendingSide);
    });
    document.getElementById('intensityWrap').hidden = (pendingSide === 'eq' || pendingSide === null);
  }

  function renderIntensity() {
    const row = document.getElementById('intensityRow');
    if (pendingSide === null || pendingSide === 'eq') { row.innerHTML = ''; return; }
    const levels = INTENSITY_LEVELS_BY_SCALE[landing.survey.scale] || INTENSITY_LEVELS_BY_SCALE[9];
    row.innerHTML = levels.map(function (n) {
      return '<button type="button" class="intensity-chip' + (pendingIntensity === n ? ' selected' : '') +
        '" data-n="' + n + '">' + n + '</button>';
    }).join('');
    document.getElementById('intensityHint').textContent =
      pendingIntensity ? (INTENSITY_LABELS[pendingIntensity] || '') : '정도를 선택해 주세요';
  }

  function updateProgress() {
    const answeredCount = questions.filter(function (q) { return currentValueForQuestion(q) !== null; }).length;
    const pct = questions.length ? Math.round(100 * answeredCount / questions.length) : 100;
    document.getElementById('progressFill').style.width = pct + '%';
    document.getElementById('progressText').textContent = pct + '% 완료';
  }

  function updateNextButtonState() {
    const ready = pendingSide === 'eq' || (pendingSide && pendingIntensity);
    document.getElementById('nextBtn').disabled = !ready;
    document.getElementById('nextBtn').textContent = currentIndex === questions.length - 1 ? '제출' : '다음';
  }

  function commitAnswer() {
    const q = questions[currentIndex];
    let value;
    if (pendingSide === 'eq') value = 1;
    else if (pendingSide === 'a') value = pendingIntensity;
    else if (pendingSide === 'b') value = 1 / pendingIntensity;
    else return false;

    const pid = pairId(q.uuid_a, q.uuid_b);
    answers[pid] = value;
    clientSeq += 1;
    localStorage.setItem(STORAGE_SEQ_KEY, String(clientSeq));
    queueAnswer({ matrix_id: q.matrix_id, uuid_a: q.uuid_a, uuid_b: q.uuid_b, value: value, client_seq: clientSeq });
    updateProgress();
    return true;
  }

  function crWarningIfNeeded(matrixId) {
    const info = matrixCrCache[matrixId];
    if (!info || !info.complete) return null;
    const threshold = landing.survey.cr_threshold || 0.1;
    return info.cr > threshold ? info : null;
  }

  async function goNext() {
    if (!commitAnswer()) return;
    const q = questions[currentIndex];

    if (q.is_last_in_matrix) {
      await flushQueue();
      const warn = crWarningIfNeeded(q.matrix_id);
      if (warn) {
        const msg = '이 항목 그룹의 응답이 다소 일관되지 않습니다 (CR ' + warn.cr.toFixed(2) + ').';
        if (landing.survey.cr_action === 'block') {
          alert(msg + ' 이전 문항으로 돌아가 다시 생각해 주세요.');
          return;
        }
        if (!confirm(msg + ' 계속 진행할까요?')) return;
      }
    }

    if (currentIndex < questions.length - 1) {
      currentIndex += 1;
      renderQuestion();
    } else {
      await finishSurvey();
    }
  }

  function goPrev() {
    if (currentIndex === 0) return;
    currentIndex -= 1;
    renderQuestion();
  }

  async function finishSurvey() {
    await flushQueue();
    try {
      const res = await fetch('/api/respond/' + accessToken + '/submit', {
        method: 'POST', headers: { 'Authorization': 'Bearer ' + respondentToken },
      });
      if (res.status === 401) { await handleTokenExpired(); return; }
      if (!res.ok && res.status !== 409) throw new Error('submit failed');
      await showDone();
    } catch (e) {
      alert('제출 중 문제가 발생했습니다. 다시 시도해 주세요.');
    }
  }

  // ── 제출 완료 화면 — 기준별 CR 요약 + 재조정 진입점 ─────────────────────────
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
      if (!data.items.length) { box.innerHTML = ''; return; }
      box.innerHTML = data.items.map(function (it) {
        const cls = (it.cr === null || it.cr === undefined) ? '' : (it.cr <= data.cr_threshold ? 'ok' : 'bad');
        const crText = (it.cr === null || it.cr === undefined) ? '-' : ('CR ' + it.cr.toFixed(3));
        return '<div class="cr-summary-row ' + cls + '"><span class="csr-name">' + esc(it.parent_name) + '</span>' +
          '<span class="csr-cr">' + crText + '</span></div>';
      }).join('');
    } catch (e) {
      box.innerHTML = '';
    }
  }

  // ── 초기화 ──────────────────────────────────────────────────────────────
  function init() {
    document.getElementById('consentCheck').addEventListener('change', function (e) {
      document.getElementById('consentNextBtn').disabled = !e.target.checked;
    });
    document.getElementById('consentNextBtn').addEventListener('click', function () { show('viewCode'); });

    document.getElementById('codeInput').addEventListener('input', function (e) {
      e.target.value = e.target.value.toUpperCase();
    });
    document.getElementById('codeInput').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') submitCode(document.getElementById('codeInput').value);
    });
    document.getElementById('codeSubmitBtn').addEventListener('click', function () {
      submitCode(document.getElementById('codeInput').value);
    });

    document.getElementById('sideButtons').addEventListener('click', function (e) {
      const btn = e.target.closest('.side-btn');
      if (!btn) return;
      pendingSide = btn.dataset.side;
      if (pendingSide !== 'eq' && !pendingIntensity) {
        const levels = INTENSITY_LEVELS_BY_SCALE[landing.survey.scale] || INTENSITY_LEVELS_BY_SCALE[9];
        pendingIntensity = levels[0];
      }
      renderSideButtons();
      renderIntensity();
      updateNextButtonState();
    });
    document.getElementById('intensityRow').addEventListener('click', function (e) {
      const chip = e.target.closest('.intensity-chip');
      if (!chip) return;
      pendingIntensity = Number(chip.dataset.n);
      renderIntensity();
      updateNextButtonState();
    });

    document.getElementById('nextBtn').addEventListener('click', goNext);
    document.getElementById('prevBtn').addEventListener('click', goPrev);
    document.getElementById('editAnswersBtn').addEventListener('click', function () {
      if (pendingReopenMatrixId) {
        const idx = questions.findIndex(function (q) { return q.matrix_id === pendingReopenMatrixId; });
        currentIndex = idx !== -1 ? idx : 0;
        pendingReopenMatrixId = null;
      } else {
        currentIndex = 0;
      }
      startSurvey();
    });
    window.addEventListener('online', flushQueue);

    run();
  }

  async function run() {
    show('viewLoading');
    try {
      await loadLanding();
    } catch (e) {
      return;
    }
    await tryResume();
  }

  init();
})();
