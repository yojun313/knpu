(function () {
  'use strict';

  const accessToken = location.pathname.split('/')[2];
  const STORAGE_TOKEN_KEY = 'ahp_respondent_token_' + accessToken;
  const STORAGE_QUEUE_KEY = 'ahp_queue_' + accessToken;
  const STORAGE_SEQ_KEY = 'ahp_seq_' + accessToken;
  const STORAGE_SUBMITTED_KEY = 'ahp_submitted_' + accessToken;

  let landing = null;
  let respondentToken = localStorage.getItem(STORAGE_TOKEN_KEY);
  let pendingReopenGroupId = null;
  let questions = [];            // 평탄한 쌍 목록(리뷰·이름조회용)
  let activeMatrices = [];       // 현재 흐름에서 보여줄 기준(matrix) 뷰 목록
  let currentMatrixIndex = 0;
  // answers 키 = groupId + '::' + pairId  — 대안 비교 행렬은 matrix_id만 다르고
  // child_uuids(대안 uuid)는 모든 leaf에서 같아서, pairId 하나로만 keying하면
  // 첫 대안 평가가 나머지에 그대로 복사된다(이 파일 이전 버전의 버그).
  let answers = {};
  let respondentAttributes = {};
  let demographicsDone = false;
  let everSubmitted = localStorage.getItem(STORAGE_SUBMITTED_KEY) === '1';
  let matrixCrCache = {};
  let clientSeq = Number(localStorage.getItem(STORAGE_SEQ_KEY) || 0);
  let revisionGroupId = null;
  let revisionWorst = [];        // 진행자가 재조정 요청 시 함께 받은 문제 쌍

  const STORAGE_SECTIONS_DONE_KEY = 'ahp_sections_done_' + accessToken;
  function loadSectionsDone() {
    try { return JSON.parse(localStorage.getItem(STORAGE_SECTIONS_DONE_KEY) || '{}'); } catch (e) { return {}; }
  }
  function markSectionDone(groupId) {
    const done = loadSectionsDone();
    done[landing.collection.round + ':' + groupId] = true;
    localStorage.setItem(STORAGE_SECTIONS_DONE_KEY, JSON.stringify(done));
  }
  function isSectionDone(groupId) {
    return !!loadSectionsDone()[landing.collection.round + ':' + groupId];
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
  function answerKey(groupId, a, b) { return groupId + '::' + pairId(a, b); }
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
          matrixCrCache[item.group_id] = { complete: data.complete, cr: data.cr };
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
    landing.survey.groups.forEach(function (m) {
      m.pairs.forEach(function (p) {
        const a = m.children.find(function (c) { return c.uuid === p.uuid_a; });
        const b = m.children.find(function (c) { return c.uuid === p.uuid_b; });
        questions.push({
          group_id: m.group_id, parent_name: m.parent_name, parent_description: m.parent_description,
          question_text: m.question_text, uuid_a: p.uuid_a, uuid_b: p.uuid_b,
          name_a: a ? a.name : p.uuid_a, name_b: b ? b.name : p.uuid_b,
          desc_a: (a && a.description) || '', desc_b: (b && b.description) || '',
          is_alternative: !!m.is_alternative,
        });
      });
    });
  }

  function matrixView(groupId) {
    return landing.survey.groups.find(function (m) { return m.group_id === groupId; });
  }
  function pairsOfMatrix(groupId) {
    return questions.filter(function (q) { return q.group_id === groupId; });
  }

  function mergeServerAnswers(serverAnswers) {
    // serverAnswers: { group_id: { pair_id: value } } — 표시 방향으로 이미 해석돼 옴.
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
      activeMatrices = landing.survey.groups.slice();
      return;
    }
    const targetId = revisionGroupId || landing.collection.active_group_id;
    activeMatrices = landing.survey.groups.filter(function (m) { return m.group_id === targetId; });
  }

  function pairValue(q) {
    const k = answerKey(q.group_id, q.uuid_a, q.uuid_b);
    return (k in answers) ? answers[k] : null;
  }
  function matrixComplete(m) {
    return rendererFor(m).isComplete(m);
  }
  function firstIncompleteMatrixIndex() {
    const i = activeMatrices.findIndex(function (m) { return !matrixComplete(m); });
    return i === -1 ? Math.max(0, activeMatrices.length - 1) : i;
  }

  // ── 실시간 흐름 ──────────────────────────────────────────────────────────
  function enterRealtimeFlow() {
    buildActiveMatrices();
    if (!landing.collection.session_started) { showWaitStart(); return; }
    const targetId = revisionGroupId || landing.collection.active_group_id;
    if (!targetId) { finishSurvey(); return; }
    if (!revisionGroupId && isSectionDone(targetId)) { showSectionWait(); return; }
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

  // q: {group_id, uuid_a, uuid_b, name_a, name_b, desc_a, desc_b, is_alternative}
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
    return '<div class="pair-row' + (opts.worst ? ' worst' : '') + '" data-mid="' + q.group_id +
      '" data-a="' + q.uuid_a + '" data-b="' + q.uuid_b + '">' +
      '<div class="pair-names"><span>' + esc(q.name_a) + '</span><span>' + esc(q.name_b) + '</span></div>' +
      descLine + badge +
      '<div class="pair-dir"><span>◀ ‘' + esc(q.name_a) + '’이 더 중요</span>' +
      '<span>‘' + esc(q.name_b) + '’이 더 중요 ▶</span></div>' +
      '<div class="scale">' + cells + '</div></div>';
  }

  // ── BWM 렌더러 보조 ───────────────────────────────────────────────────
  function bwmVal(gid, itemId) {
    const k = gid + '::' + itemId;
    return (k in answers) ? answers[k] : null;
  }
  function bwmNames(group) {
    const nm = {};
    (group.children || []).forEach(function (c) { nm[c.uuid] = c.name; });
    return nm;
  }
  function bwmScaleRow(gid, itemId, cur) {
    let cells = '';
    for (let n = 1; n <= 9; n++) {
      cells += '<button type="button" class="bwm-scale-cell' +
        (cur === n ? ' on' : '') + '" data-v="' + n + '">' + n + '</button>';
    }
    return '<div class="scale bwm-scale">' + cells + '</div>';
  }
  function bwmRenderBody(group, worstSet) {
    worstSet = worstSet || {};
    const gid = group.group_id, nm = bwmNames(group);
    const kids = (group.children || []).map(function (c) { return c.uuid; });
    const best = bwmVal(gid, 'best'), worst = bwmVal(gid, 'worst');
    let h = '';

    // 1) Best 선택
    h += '<div class="bwm-step"><div class="bwm-q">가장 <b>중요한</b> 항목</div><div class="bwm-pick-row">' +
      kids.map(function (u) {
        return '<button type="button" class="bwm-pick' + (best === u ? ' on' : '') +
          '" data-item="best" data-v="' + u + '">' + esc(nm[u] || u) + '</button>';
      }).join('') + '</div></div>';

    // 2) Worst 선택 (Best 고른 뒤)
    if (best) {
      h += '<div class="bwm-step"><div class="bwm-q">가장 <b>덜 중요한</b> 항목</div><div class="bwm-pick-row">' +
        kids.filter(function (u) { return u !== best; }).map(function (u) {
          return '<button type="button" class="bwm-pick' + (worst === u ? ' on' : '') +
            '" data-item="worst" data-v="' + u + '">' + esc(nm[u] || u) + '</button>';
        }).join('') + '</div></div>';
    } else {
      h += '<p class="bwm-hint">먼저 가장 중요한 항목을 고르세요.</p>';
    }

    // 3) Best-to-Others · 4) Others-to-Worst 벡터 (Best·Worst 모두 고른 뒤)
    if (best && worst && best !== worst) {
      h += '<div class="bwm-vecs"><div class="bwm-q">‘' + esc(nm[best]) +
        '’이(가) 각 항목보다 얼마나 더 중요합니까? <span class="bwm-note">1=비슷 · 9=압도적</span></div>';
      kids.filter(function (u) { return u !== best; }).forEach(function (u) {
        const it = 'BO:' + u;
        h += '<div class="bwm-vrow' + (worstSet[it] ? ' worst' : '') + '" data-item="' + it + '">' +
          '<span class="bwm-vlabel">‘' + esc(nm[best]) + '’ vs ‘' + esc(nm[u]) + '’</span>' +
          bwmScaleRow(gid, it, bwmVal(gid, it)) + '</div>';
      });
      h += '<div class="bwm-q" style="margin-top:14px">각 항목이 ‘' + esc(nm[worst]) +
        '’보다 얼마나 더 중요합니까?</div>';
      kids.filter(function (u) { return u !== worst; }).forEach(function (u) {
        const it = 'OW:' + u;
        h += '<div class="bwm-vrow' + (worstSet[it] ? ' worst' : '') + '" data-item="' + it + '">' +
          '<span class="bwm-vlabel">‘' + esc(nm[u]) + '’ vs ‘' + esc(nm[worst]) + '’</span>' +
          bwmScaleRow(gid, it, bwmVal(gid, it)) + '</div>';
      });
      h += '</div>';
    }
    return h;
  }
  function bwmComplete(group) {
    const gid = group.group_id;
    const b = bwmVal(gid, 'best'), w = bwmVal(gid, 'worst');
    if (!b || !w || b === w) return false;
    return (group.children || []).every(function (c) {
      if (c.uuid !== b && bwmVal(gid, 'BO:' + c.uuid) == null) return false;
      if (c.uuid !== w && bwmVal(gid, 'OW:' + c.uuid) == null) return false;
      return true;
    });
  }
  function bwmAnswered(group) {
    const p = group.group_id + '::';
    return Object.keys(answers).filter(function (k) { return k.indexOf(p) === 0; }).length;
  }
  function bwmOverrides(group) {
    const gid = group.group_id, out = [];
    ['best', 'worst'].forEach(function (it) {
      const v = bwmVal(gid, it); if (v != null) out.push({ item_id: it, value: v });
    });
    (group.children || []).forEach(function (c) {
      ['BO:' + c.uuid, 'OW:' + c.uuid].forEach(function (it) {
        const v = bwmVal(gid, it); if (v != null) out.push({ item_id: it, value: v });
      });
    });
    return out;
  }

  // ── kind별 렌더러 레지스트리 ──────────────────────────────────────────
  //   renderBody(group, worstSet)  : #pairList / #reviewPairs 본문 HTML
  //   isComplete(group)            : 이 그룹 응답이 완료됐는가
  //   answered(group) / total(group): 진행률
  //   overrides(group)             : group-eval what-if 페이로드
  const RENDERERS = {
    pairwise: {
      renderBody: function (group, worstSet) {
        worstSet = worstSet || {};
        return pairsOfMatrix(group.group_id).map(function (q) {
          const w = worstSet[pairId(q.uuid_a, q.uuid_b)];
          return renderPairScaleRow(q, w ? {
            worst: true, suggestBadge: true,
            given: w.given_label || fmtValue(pairValue(q)), suggest: w.suggested_label,
          } : {});
        }).join('');
      },
      isComplete: function (group) {
        return pairsOfMatrix(group.group_id).every(function (q) { return pairValue(q) !== null; });
      },
      answered: function (group) {
        return pairsOfMatrix(group.group_id).filter(function (q) { return pairValue(q) !== null; }).length;
      },
      total: function (group) { return pairsOfMatrix(group.group_id).length; },
      overrides: function (group) {
        return pairsOfMatrix(group.group_id).map(function (q) {
          const v = pairValue(q);
          return v == null ? null : { uuid_a: q.uuid_a, uuid_b: q.uuid_b, value_a_over_b: v };
        }).filter(Boolean);
      },
    },
    bwm: {
      renderBody: bwmRenderBody,
      isComplete: bwmComplete,
      answered: bwmAnswered,
      total: function (group) { return 2 * (group.children || []).length; },
      overrides: bwmOverrides,
    },
  };
  function rendererFor(group) {
    return (group && RENDERERS[group.kind]) || RENDERERS.pairwise;
  }

  function renderMatrixPage() {
    const m = activeMatrices[currentMatrixIndex];
    if (!m) return;
    document.getElementById('qParentName').textContent = (m.is_alternative ? '대안 비교 · ' : '') + m.parent_name;
    document.getElementById('qParentDesc').textContent = m.parent_description || '';
    document.getElementById('qParentDesc').hidden = !m.parent_description;
    document.getElementById('qQuestionText').textContent = m.question_text;
    document.getElementById('pairList').innerHTML = rendererFor(m).renderBody(m);
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
      const R = rendererFor(m);
      total += R.total(m); done += R.answered(m);
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
    const info = matrixCrCache[m.group_id];
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

  // 모든 질문 그룹의 children(uuid→name) 병합 맵. 쌍대비교는 questions 로 이름을
  // 얻지만 BWM 등은 pairs 가 없어 questions 에 안 들어온다 — 방법 무관 폴백.
  function groupChildNameMap() {
    const m = {};
    ((landing && landing.survey && landing.survey.groups) || []).forEach(function (g) {
      (g.children || []).forEach(function (c) { if (c && c.uuid) m[c.uuid] = c.name; });
    });
    return m;
  }
  function nodeNameByUuid(uuid) {
    for (let i = 0; i < questions.length; i++) {
      if (questions[i].uuid_a === uuid) return questions[i].name_a;
      if (questions[i].uuid_b === uuid) return questions[i].name_b;
    }
    return groupChildNameMap()[uuid] || uuid;
  }

  function groupKind(groupId) {
    const g = ((landing && landing.survey && landing.survey.groups) || [])
      .find(function (x) { return x.group_id === groupId; });
    return (g && g.kind) || 'pairwise';
  }

  function renderSectionWaitResults(msg, isIndividual) {
    if (document.getElementById('viewSectionWait').hidden) return;
    if (msg.group_id !== (revisionGroupId || landing.collection.active_group_id)) return;
    const box = document.getElementById('sectionWaitResults');
    const cr = isIndividual ? msg.cr : msg.avg_cr;
    const crLine = (cr == null) ? '' : '<div class="swr-cr">CR ' + cr.toFixed(3) + '</div>';
    const view = window.MCDMViews.for(msg.kind || groupKind(msg.group_id));
    const rows = view.revealRows(msg.weights || {}, nodeNameByUuid)
      .map(function (r) {
        return '<div class="swr-row"><span>' + esc(r.name) + '</span>' +
          '<span>' + r.pct + '%</span></div>';
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
    landing.survey.groups = msg.groups;
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
      revisionGroupId = null;
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
    landing.collection.active_group_id = msg.group_id;
    revisionGroupId = null;
    showNotice('연구자가 설문을 시작했습니다.');
    if (document.getElementById('viewWaitStart').hidden === false) enterRealtimeFlow();
  }

  function handleSectionAdvanced(msg) {
    landing.collection.active_group_id = msg.group_id;
    revisionGroupId = null;
    if (msg.done) { showNotice('모든 섹션이 끝났습니다. 제출을 마무리합니다.'); finishSurvey(); return; }
    showNotice('다음 섹션이 열렸습니다.');
    const waiting = ['viewSectionWait', 'viewWaitStart'].some(function (id) {
      return document.getElementById(id).hidden === false;
    });
    if (waiting) enterRealtimeFlow();
  }

  function handleRevisionRequested(msg) {
    revisionGroupId = msg.group_id;
    revisionWorst = msg.worst_pairs || [];
    showNotice('연구자가 이 항목의 응답을 다시 확인해 달라고 요청했습니다.');
    enterRealtimeFlow();
  }

  function handleSectionUnlock(msg) {
    const q = pairsOfMatrix(msg.group_id)[0];
    const name = q ? q.parent_name : '이 항목';
    if (landing.collection.mode === 'realtime') {
      revisionGroupId = msg.group_id;
      revisionWorst = [];
      showNotice('연구자가 "' + name + '" 항목을 전원에게 다시 열었습니다. 이어서 응답해 주세요.');
      enterRealtimeFlow();
      return;
    }
    pendingReopenGroupId = msg.group_id;
    const onDone = document.getElementById('viewDone').hidden === false;
    showNotice('연구자가 "' + name + '" 항목을 다시 열었습니다. ' +
      (onDone ? '아래 항목을 눌러 조정해 주세요.' : '이어서 응답해 주세요.'));
  }

  // 진행자가 콘솔에서 이 참여자 답을 고침 → 로컬에 즉시 반영(원복 방지).
  function handleAnswerOverride(msg) {
    const q = pairsOfMatrix(msg.group_id).find(function (x) {
      return pairId(x.uuid_a, x.uuid_b) === pairId(msg.uuid_a, msg.uuid_b);
    });
    if (!q) return;
    // msg.value_a_over_b 는 msg.uuid_a 기준. 이 화면 질문의 a 기준으로 방향 맞춤.
    const v = (q.uuid_a === msg.uuid_a) ? msg.value_a_over_b : (1 / msg.value_a_over_b);
    answers[answerKey(q.group_id, q.uuid_a, q.uuid_b)] = v;
    matrixCrCache[msg.group_id] = { complete: !!msg.complete, cr: msg.cr };
    showNotice('연구자가 함께 확인한 값으로 응답이 조정되었습니다.');
    if (!document.getElementById('viewSurvey').hidden) renderMatrixPage();
    if (!document.getElementById('viewReview').hidden && reviewGroupId === msg.group_id) refreshReview();
  }

  // ── 네비게이션 ──────────────────────────────────────────────────────────
  function crWarningIfNeeded(groupId) {
    const info = matrixCrCache[groupId];
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
        const warn = crWarningIfNeeded(m.group_id);
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
      if (revisionGroupId === m.group_id) revisionGroupId = null;
      else markSectionDone(m.group_id);
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

  // 제출 완료 화면에 응답자 본인의 결과(전역 가중치 + 대안 순위)를 그린다.
  function weightBars(weights, names) {
    const ent = Object.keys(weights || {})
      .map(function (k) { return [k, weights[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
    if (!ent.length) return '';
    const max = ent[0][1] || 1;
    return ent.map(function (e) {
      const pct = (e[1] * 100).toFixed(1);
      return '<div class="mr-row"><span class="mr-name">' + esc((names && names[e[0]]) || e[0]) + '</span>' +
        '<span class="mr-bar"><span style="width:' + (100 * e[1] / max) + '%"></span></span>' +
        '<span class="mr-pct">' + pct + '%</span></div>';
    }).join('');
  }
  function renderMyResult(mr) {
    const box = document.getElementById('myResult');
    if (!mr || (!Object.keys(mr.global_weights || {}).length && !Object.keys(mr.alt_scores || {}).length)) {
      box.hidden = true; box.innerHTML = ''; return;
    }
    let h = '<h3>내 응답 결과</h3>';
    const gw = weightBars(mr.global_weights, mr.node_names);
    if (gw) h += '<div class="mr-block"><h4>기준 종합 가중치</h4>' + gw + '</div>';
    const alt = weightBars(mr.alt_scores, mr.alt_names);
    if (alt) h += '<div class="mr-block"><h4>대안 평가 순위</h4>' + alt + '</div>';
    h += '<p class="small muted">이 결과는 귀하의 응답만으로 계산한 것으로, 전체 집계 결과와 다를 수 있습니다.</p>';
    box.innerHTML = h;
    box.hidden = false;
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
      renderMyResult(data.my_result);
      const anyBad = data.items.some(function (it) {
        return it.cr != null && it.cr > data.cr_threshold;
      });
      document.getElementById('crExplain').hidden = !anyBad;
      if (!data.items.length) { box.innerHTML = ''; return; }
      box.innerHTML = data.items.map(function (it) {
        const cls = (it.cr == null) ? '' : (it.cr <= data.cr_threshold ? 'ok' : 'bad');
        const crText = (it.cr == null) ? '-' : ('CR ' + it.cr.toFixed(3));
        return '<button type="button" class="cr-summary-row ' + cls + '" data-matrix="' + it.group_id + '">' +
          '<span class="csr-name">' + esc(it.parent_name) + '</span>' +
          '<span class="csr-cr">' + crText + '</span></button>';
      }).join('');
    } catch (e) {
      box.innerHTML = '';
      document.getElementById('crExplain').hidden = true;
      document.getElementById('myResult').hidden = true;
    }
  }

  // ── 수정 화면 — what-if 가중치 차트 + 응답형 추천 ─────────────────────────
  let reviewGroupId = null;
  let reviewWorstPids = {};      // pid -> {given_label, suggested_label}
  let reviewEval = null;         // 최근 group-eval 결과
  let rankFocus = 0;            // 좌우 화살표 포커스 (ranking 인덱스)
  let evalTimer = null;

  function enterReview(groupId) {
    reviewGroupId = groupId;
    rankFocus = 0;
    reviewWorstPids = {};
    const m = matrixView(groupId);
    if (revisionGroupId === groupId && (!m || m.kind !== 'bwm')) {
      revisionWorst.forEach(function (w) {
        reviewWorstPids[pairId(w.uuid_a, w.uuid_b)] = w;
      });
    }
    document.getElementById('reviewTitle').textContent =
      (m && m.is_alternative ? '대안 비교 · ' : '') + (m ? m.parent_name : '');
    renderReviewPairs();
    show('viewReview');
    refreshReview();
  }

  function renderReviewPairs() {
    const m = matrixView(reviewGroupId) || { group_id: reviewGroupId, children: [] };
    document.getElementById('reviewPairs').innerHTML =
      rendererFor(m).renderBody(m, reviewWorstPids);
  }

  function currentOverrides() {
    const m = matrixView(reviewGroupId) || { group_id: reviewGroupId, children: [] };
    return rendererFor(m).overrides(m);
  }

  function refreshReview() {
    clearTimeout(evalTimer);
    evalTimer = setTimeout(async function () {
      try {
        const res = await fetch('/api/respond/' + accessToken + '/group-eval', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + respondentToken, 'Content-Type': 'application/json' },
          body: JSON.stringify({ group_id: reviewGroupId, overrides: currentOverrides() }),
        });
        if (!res.ok) return;
        reviewEval = await res.json();
        // worst 힌트를 서버 최신값으로 갱신
        reviewWorstPids = {};
        const rm = matrixView(reviewGroupId);
        if (rm && rm.kind === 'bwm') {
          (reviewEval.locus || []).forEach(function (iid) { reviewWorstPids[iid] = true; });
        } else {
          (reviewEval.worst_pairs || []).slice(0, 1).forEach(function (w) {
            reviewWorstPids[w.pair_id] = w;
          });
        }
        renderReviewPairs();
        renderReviewChart();
      } catch (e) { /* ignore */ }
    }, 250);
  }

  function renderReviewChart() {
    const el = document.getElementById('reviewChart');
    const crBar = document.getElementById('reviewCrBar');
    if (!reviewEval || reviewEval.incomplete) {
      el.innerHTML = '<p class="muted" style="font-size:12.5px">모든 항목에 응답하면 가중치·CR이 표시됩니다.</p>';
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
      queueAnswer({ group_id: mid, kind: 'pairwise', uuid_a: a, uuid_b: b, value: v, client_seq: clientSeq });
      onPick();
    });
  }

  // BWM 위젯 클릭(Best/Worst 선택 · 1~9 눈금). onPick(rerender) — rerender면 화면
  // 전체를 다시 그려야 한다(다음 단계가 열리므로).
  function bwmClickHandler(container, onPick) {
    container.addEventListener('click', function (e) {
      const gid = container.id === 'reviewPairs'
        ? reviewGroupId
        : (activeMatrices[currentMatrixIndex] || {}).group_id;
      if (!gid) return;

      const pick = e.target.closest('.bwm-pick');
      if (pick && container.contains(pick)) {
        const item = pick.dataset.item;                 // 'best' | 'worst'
        const uuid = pick.dataset.v;
        if (answers[gid + '::' + item] === uuid) return;
        answers[gid + '::' + item] = uuid;
        // Best/Worst가 바뀌면 벡터 응답 무효화(서버도 put_answer에서 동일 처리)
        Object.keys(answers).forEach(function (k) {
          if (k.indexOf(gid + '::BO:') === 0 || k.indexOf(gid + '::OW:') === 0) delete answers[k];
        });
        clientSeq += 1; localStorage.setItem(STORAGE_SEQ_KEY, String(clientSeq));
        queueAnswer({
          group_id: gid, kind: item === 'best' ? 'pick_best' : 'pick_worst',
          value: uuid, client_seq: clientSeq,
        });
        onPick(true);
        return;
      }

      const cell = e.target.closest('.bwm-scale-cell');
      const row = e.target.closest('.bwm-vrow');
      if (cell && row && container.contains(row)) {
        const item = row.dataset.item;                  // 'BO:<uuid>' | 'OW:<uuid>'
        const v = Number(cell.dataset.v);
        row.querySelectorAll('.bwm-scale-cell').forEach(function (c) { c.classList.toggle('on', c === cell); });
        answers[gid + '::' + item] = v;
        clientSeq += 1; localStorage.setItem(STORAGE_SEQ_KEY, String(clientSeq));
        queueAnswer({ group_id: gid, kind: 'vector', item_id: item, value: v, client_seq: clientSeq });
        onPick(false);
      }
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
    bwmClickHandler(document.getElementById('pairList'), function (rerender) {
      if (rerender) renderMatrixPage();
      else { updateProgress(); updateNav(); refreshCrBar(); }
    });
    bwmClickHandler(document.getElementById('reviewPairs'), function (rerender) {
      if (rerender) renderReviewPairs();
      refreshReview();
    });

    document.getElementById('nextBtn').addEventListener('click', goNext);
    document.getElementById('prevBtn').addEventListener('click', goPrev);
    document.getElementById('submitBtn').addEventListener('click', onSubmitBtn);
    document.getElementById('demoSubmitBtn').addEventListener('click', submitDemographics);

    document.getElementById('editAnswersBtn').addEventListener('click', function () {
      buildActiveMatrices();
      if (pendingReopenGroupId) {
        const i = activeMatrices.findIndex(function (m) { return m.group_id === pendingReopenGroupId; });
        currentMatrixIndex = i !== -1 ? i : 0;
        pendingReopenGroupId = null;
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
