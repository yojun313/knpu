(function () {
  'use strict';

  const collectionId = location.pathname.split('/')[2];
  let projectId = null;
  let respondents = [];
  let ws = null;
  let backoff = 1000;
  let sessionStarted = false;
  let activeSectionIndex = 0;
  let totalSections = 0;

  function fmtCr(v) {
    if (v === null || v === undefined) return '-';
    return 'CR ' + v.toFixed(2);
  }

  function renderTable() {
    const box = document.getElementById('respondentTable');
    document.getElementById('respCountMeta').textContent =
      respondents.length + '명 · 제출 완료 ' + respondents.filter(function (r) { return r.status === 'submitted'; }).length;
    if (!respondents.length) {
      box.innerHTML = '<p style="padding:14px;font-size:12px;color:var(--sidebar-muted)">아직 참여자가 없습니다.</p>';
      return;
    }
    const sorted = respondents.slice().sort(function (a, b) { return a.label.localeCompare(b.label); });
    box.innerHTML = sorted.map(function (r) {
      const crCls = r.worst_cr === null || r.worst_cr === undefined ? '' : (r.worst_cr <= 0.1 ? 'ok' : 'bad');
      return '<div class="resp-row" data-id="' + r.id + '">' +
        '<span class="rr-dot' + (r.online ? ' online' : '') + '"></span>' +
        '<div><div class="rr-name">' + ahpEsc(r.label) + '</div>' +
        '<div class="rr-status">' + (r.status === 'submitted' ? '제출 완료' : r.status === 'in_progress' ? '응답 중' : '시작 전') + '</div>' +
        '<div class="rr-progress"><div class="rr-progress-fill" style="width:' + (r.progress || 0) + '%"></div></div></div>' +
        '<span class="rr-cr ' + crCls + '">' + fmtCr(r.worst_cr) + '</span>' +
        '<div class="rr-actions">' +
        (r.source === 'web'
          ? '<button class="rr-act" data-act="reissue" data-id="' + r.id + '" title="코드 재발급">↻</button>'
          : '') +
        '<button class="rr-act" data-act="delete" data-id="' + r.id + '" title="삭제">×</button></div></div>';
    }).join('');
  }

  function patchRespondent(id, patch) {
    const r = respondents.find(function (x) { return x.id === id; });
    if (r) Object.assign(r, patch);
    renderTable();
  }

  function activeSectionMatrix() {
    return surveyMatricesCache[activeSectionIndex] || null;
  }

  function renderPhaseBadge() {
    const badge = document.getElementById('sessionPhaseBadge');
    const startBtn = document.getElementById('startSessionBtn');
    if (!sessionStarted) {
      badge.textContent = '시작 전';
      badge.className = 'badge muted';
      startBtn.hidden = false;
      return;
    }
    startBtn.hidden = true;
    if (activeSectionIndex >= totalSections) {
      badge.textContent = '모든 섹션 완료 — 라운드 결정 대기';
      badge.className = 'badge ok';
      return;
    }
    const m = activeSectionMatrix();
    const name = m ? (m.is_alternative ? '[대안] ' : '') + nodeNameFromHierarchy(m.parent_uuid) : '';
    badge.textContent = '섹션 ' + (activeSectionIndex + 1) + '/' + totalSections + ' 진행 중 — ' + name;
    badge.className = 'badge ok';
  }

  // 진행 중인 섹션이 바뀔 때마다(시작·다음 섹션·라운드 진행) 아래 섹션 그리드가
  // 자동으로 그 섹션을 보여주게 한다 — 예전엔 관리자가 드롭다운을 직접 바꾸거나
  // 새로고침해야 지금 무슨 섹션이 열려 있는지 알 수 있었다(요청사항).
  function syncSectionToActive() {
    const m = activeSectionMatrix();
    if (!sessionStarted || !m) return;
    const sel = document.getElementById('sectionMatrixSelect');
    if (sel.value !== m.matrix_id) sel.value = m.matrix_id;
    loadSectionSnapshot();
  }

  function setWsStatus(state) {
    const el = document.getElementById('wsStatus');
    if (state === 'connected') { el.textContent = '실시간 연결됨'; el.className = 'badge ok'; }
    else if (state === 'connecting') { el.textContent = '연결 중…'; el.className = 'badge muted'; }
    else { el.textContent = '재연결 중'; el.className = 'badge warn'; }
  }

  function connectWs() {
    setWsStatus('connecting');
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(proto + '//' + location.host + '/ws/console/' + collectionId);

    ws.addEventListener('open', function () { backoff = 1000; setWsStatus('connected'); });
    ws.addEventListener('message', function (e) {
      let msg;
      try { msg = JSON.parse(e.data); } catch (err) { return; }
      if (msg.event === 'snapshot') {
        respondents = msg.respondents;
        document.getElementById('roundNum').textContent = msg.round;
        renderTable();
      } else if (msg.event === 'progress') {
        patchRespondent(msg.respondent_id, {
          progress: msg.progress, worst_cr: msg.complete ? msg.cr : undefined, status: 'in_progress',
        });
      } else if (msg.event === 'presence') {
        patchRespondent(msg.respondent_id, { online: msg.online });
      } else if (msg.event === 'round.advanced') {
        document.getElementById('roundNum').textContent = msg.round;
        sessionStarted = true;
        activeSectionIndex = 0;
        renderPhaseBadge();
        syncSectionToActive();
        loadRespondents();
      } else if (msg.event === 'session.started') {
        sessionStarted = true;
        activeSectionIndex = 0;
        renderPhaseBadge();
        syncSectionToActive();
      } else if (msg.event === 'section.advanced') {
        activeSectionIndex = msg.section_index;
        renderPhaseBadge();
        syncSectionToActive();
      }
    });
    ws.addEventListener('close', function () {
      setWsStatus('retrying');
      setTimeout(connectWs, backoff);
      backoff = Math.min(backoff * 2, 15000);
    });
  }

  async function loadRespondents() {
    respondents = await ahpApi('/api/collections/' + collectionId + '/respondents');
    renderTable();
  }

  function nodeName(uuid, m) {
    const c = m.children.find(function (x) { return x.uuid === uuid; });
    return c ? c.name : uuid;
  }

  let surveyMatricesCache = [];

  async function loadLiveMatrices() {
    const survey = await ahpApi('/api/projects/' + projectId + '/survey');
    surveyMatricesCache = survey.matrices;
    totalSections = survey.matrices.length;
    renderPhaseBadge();
    populateSectionMatrixSelect(survey.matrices);
    const box = document.getElementById('liveMatricesList');
    if (!survey.matrices.length) {
      box.innerHTML = '<p style="color:var(--sidebar-muted);font-size:12.5px">비교할 항목이 없습니다.</p>';
      return;
    }
    box.innerHTML = survey.matrices.map(function (m) {
      const childrenHtml = m.child_uuids.map(function (cid) {
        const desc = survey.node_descriptions[cid] || '';
        return '<div class="field"><label>' + ahpEsc(nodeNameFromHierarchy(cid)) + '</label>' +
          '<textarea class="live-desc-input" data-node="' + cid + '">' + ahpEsc(desc) + '</textarea></div>';
      }).join('');
      return '<div class="live-matrix" data-matrix="' + m.matrix_id + '">' +
        '<h4>' + (m.is_alternative ? '[대안] ' : '') + ahpEsc(nodeNameFromHierarchy(m.parent_uuid)) + '</h4>' +
        '<div class="field"><label>질문 문구</label>' +
        '<textarea class="live-question-input" data-matrix="' + m.matrix_id + '">' + ahpEsc(m.question_text) + '</textarea></div>' +
        childrenHtml + '</div>';
    }).join('');
  }

  // 콘솔은 hierarchy를 따로 불러오지 않고 survey.matrices만으로 그리므로,
  // 자식 이름은 매트릭스가 몰라도 node_descriptions 키(uuid)만으로 라벨을 못 만든다 —
  // 그래서 uuid를 그대로 짧게 보여주는 대신 최초 1회 계층을 함께 불러와 이름을 채운다.
  let nodeNamesCache = null;
  function nodeNameFromHierarchy(uuid) {
    return (nodeNamesCache && nodeNamesCache[uuid]) || uuid;
  }

  async function saveLiveEdits() {
    const nodeDescriptions = {};
    document.querySelectorAll('.live-desc-input').forEach(function (el) {
      nodeDescriptions[el.dataset.node] = el.value.trim();
    });
    const matrixQuestions = {};
    document.querySelectorAll('.live-question-input').forEach(function (el) {
      matrixQuestions[el.dataset.matrix] = el.value.trim();
    });
    try {
      await ahpApi('/api/projects/' + projectId + '/survey', {
        method: 'PUT', body: { node_descriptions: nodeDescriptions, matrix_questions: matrixQuestions },
      });
      ahpToast('저장했습니다 — 접속 중인 응답자 화면에 반영됩니다');
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    }
  }

  // ── 섹션(계층 매트릭스) 단위 델파이 진행 ─────────────────────────────────
  function populateSectionMatrixSelect(matrices) {
    const sel = document.getElementById('sectionMatrixSelect');
    const prev = sel.value;
    sel.innerHTML = matrices.map(function (m) {
      const label = (m.is_alternative ? '[대안] ' : '') + nodeNameFromHierarchy(m.parent_uuid);
      return '<option value="' + m.matrix_id + '">' + ahpEsc(label) + '</option>';
    }).join('');
    if (prev && matrices.some(function (m) { return m.matrix_id === prev; })) sel.value = prev;
  }

  function currentSectionMatrix() {
    const mid = document.getElementById('sectionMatrixSelect').value;
    return surveyMatricesCache.find(function (m) { return m.matrix_id === mid; });
  }

  function scaleOptionsHtml(nameA, nameB, currentAOverB) {
    const opts = [];
    for (let n = 9; n >= 2; n--) opts.push({ v: n, label: nameA + '가(이) ' + n + '배 더 중요' });
    opts.push({ v: 1, label: '동일하게 중요' });
    for (let n = 2; n <= 9; n++) opts.push({ v: 1 / n, label: nameB + '가(이) ' + n + '배 더 중요' });
    return opts.map(function (o) {
      const sel = currentAOverB != null && Math.abs(o.v - currentAOverB) < 1e-6 ? ' selected' : '';
      return '<option value="' + o.v + '"' + sel + '>' + o.label + '</option>';
    }).join('');
  }

  function resolveDisplayValue(a, b, answers) {
    const sorted = [a, b].sort();
    const pid = sorted.join(':');
    if (!(pid in answers)) return null;
    const v = answers[pid];
    return a === sorted[0] ? v : 1 / v;
  }

  function renderSectionTable(snap) {
    const matrix = currentSectionMatrix();
    const box = document.getElementById('sectionTable');
    if (!matrix || matrix.child_uuids.length < 2) {
      box.innerHTML = '<p class="muted" style="font-size:11.5px">이 항목은 비교할 하위가 2개 미만이라 표시할 게 없습니다.</p>';
      document.getElementById('sectionWorstPairs').innerHTML = '';
      return;
    }
    const pairs = [];
    for (let i = 0; i < matrix.child_uuids.length; i++) {
      for (let j = i + 1; j < matrix.child_uuids.length; j++) pairs.push([matrix.child_uuids[i], matrix.child_uuids[j]]);
    }
    const outlierSet = {};
    (snap.outliers || []).forEach(function (o) {
      o.outlier_respondents.forEach(function (rid) { outlierSet[o.pair_id + '|' + rid] = true; });
    });

    const header = '<tr><th>참여자</th><th>CR</th>' + pairs.map(function (p) {
      return '<th>' + ahpEsc(nodeNameFromHierarchy(p[0])) + ' vs ' + ahpEsc(nodeNameFromHierarchy(p[1])) + '</th>';
    }).join('') + '<th>개별 진행</th></tr>';

    const rows = (snap.respondents || []).map(function (r) {
      const crCls = r.cr === null || r.cr === undefined ? '' : (r.cr <= 0.1 ? 'ok' : 'bad');
      const cells = pairs.map(function (p) {
        const pid = [p[0], p[1]].sort().join(':');
        const current = resolveDisplayValue(p[0], p[1], r.answers || {});
        const cls = outlierSet[pid + '|' + r.respondent_id] ? 'section-outlier' : '';
        return '<td class="' + cls + '"><select data-rid="' + r.respondent_id + '" data-a="' + p[0] + '" data-b="' + p[1] + '">' +
          '<option value="">(미응답)</option>' +
          scaleOptionsHtml(nodeNameFromHierarchy(p[0]), nodeNameFromHierarchy(p[1]), current) + '</select></td>';
      }).join('');
      const actions = '<td><div class="section-row-actions">' +
        '<button class="sr-act" data-act="reveal-individual" data-rid="' + r.respondent_id + '">개별 공개</button>' +
        '<button class="sr-act" data-act="request-revision" data-rid="' + r.respondent_id + '">재조정 요청</button>' +
        '</div></td>';
      return '<tr><td>' + ahpEsc(r.label) + ' <span class="muted">(' + r.answered_pairs + '/' + r.total_pairs + ')</span></td>' +
        '<td class="' + crCls + '">' + (r.cr === null || r.cr === undefined ? '-' : r.cr.toFixed(3)) + '</td>' + cells + actions + '</tr>';
    }).join('');

    box.innerHTML = rows
      ? '<table class="section-grid"><thead>' + header + '</thead><tbody>' + rows + '</tbody></table>'
      : '<p class="muted" style="font-size:11.5px">아직 참여자가 없습니다.</p>';

    document.getElementById('sectionWorstPairs').innerHTML = (snap.worst_pairs || []).length
      ? snap.worst_pairs.map(function (w) {
        return '<div class="warn-item">⚠ ' + ahpEsc(nodeNameFromHierarchy(w.uuid_a)) + ' vs ' + ahpEsc(nodeNameFromHierarchy(w.uuid_b)) +
          ' — 응답값 ' + w.given_value.toFixed(2) + ', 그룹 관점 권장값 ' + w.suggested_value.toFixed(2) + '</div>';
      }).join('')
      : '';
  }

  async function loadSectionSnapshot() {
    const mid = document.getElementById('sectionMatrixSelect').value;
    if (!mid) { document.getElementById('sectionTable').innerHTML = ''; return; }
    try {
      const snap = await ahpApi('/api/collections/' + collectionId + '/sections/' + mid + '/snapshot');
      document.getElementById('sectionRoundNum').textContent = snap.round;
      renderSectionTable(snap);
    } catch (e) {
      ahpToast(e.message || '섹션 정보를 불러오지 못했습니다', true);
    }
  }

  async function saveSectionCell(rid, a, b, value) {
    const matrix = currentSectionMatrix();
    try {
      await ahpApi('/api/entry/' + collectionId + '/answers', {
        method: 'PUT',
        body: { respondent_id: rid, matrix_id: matrix.matrix_id, uuid_a: a, uuid_b: b, value: value },
      });
      ahpToast('저장했습니다');
      await loadSectionSnapshot();
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    }
  }

  async function init() {
    let collection;
    try {
      collection = await ahpApi('/api/collections/' + collectionId);
    } catch (e) {
      ahpToast('수집 정보를 불러오지 못했습니다', true);
      return;
    }
    projectId = collection.project_id;
    document.getElementById('collLabel').textContent = collection.label + ' · 실시간 콘솔';
    document.getElementById('roundNum').textContent = collection.round;
    document.getElementById('backToCollect').href = '/collect/' + projectId;
    sessionStarted = !!collection.session_started;
    activeSectionIndex = collection.active_section_index || 0;
    renderPhaseBadge();
    if (window.AHPShell) window.AHPShell.setActiveProject(projectId);

    try {
      const hierarchy = await ahpApi('/api/projects/' + projectId + '/hierarchy');
      nodeNamesCache = {};
      hierarchy.nodes.forEach(function (n) { nodeNamesCache[n.uuid] = n.name; });
      (hierarchy.alternatives || []).forEach(function (a) { nodeNamesCache[a.uuid] = a.name; });
    } catch (e) { nodeNamesCache = {}; }

    await loadRespondents();
    await loadLiveMatrices();
    connectWs();

    document.getElementById('liveMatricesList').addEventListener('blur', function (e) {
      if (e.target.classList.contains('live-desc-input') || e.target.classList.contains('live-question-input')) {
        saveLiveEdits();
      }
    }, true);

    document.getElementById('advanceRoundBtn').addEventListener('click', async function () {
      if (!confirm('다음 라운드를 시작할까요? 제출 완료된 참여자도 다시 응답할 수 있게 됩니다.')) return;
      try {
        await ahpApi('/api/collections/' + collectionId + '/advance-round', { method: 'POST' });
      } catch (e) {
        ahpToast(e.message || '라운드 진행에 실패했습니다', true);
      }
    });

    // 콘솔을 열었을 때(또는 새로고침 후) 이미 세션이 진행 중이면 처음부터
    // 현재 열려 있는 섹션을 보여준다 — 매번 드롭다운에서 직접 찾을 필요 없게.
    if (sessionStarted) syncSectionToActive();
    else await loadSectionSnapshot();
    document.getElementById('sectionMatrixSelect').addEventListener('change', loadSectionSnapshot);
    document.getElementById('sectionRefreshBtn').addEventListener('click', loadSectionSnapshot);
    document.getElementById('sectionUnlockBtn').addEventListener('click', async function () {
      const matrix = currentSectionMatrix();
      if (!matrix) return;
      if (!confirm('"' + nodeNameFromHierarchy(matrix.parent_uuid) + '" 섹션을 다시 열까요? 이미 제출한 참여자도 이 항목만 다시 응답할 수 있게 됩니다.')) return;
      try {
        await ahpApi('/api/collections/' + collectionId + '/sections/' + matrix.matrix_id + '/unlock', { method: 'POST' });
        ahpToast('섹션을 다시 열었습니다');
        await loadSectionSnapshot();
      } catch (e) {
        ahpToast(e.message || '섹션 재오픈에 실패했습니다', true);
      }
    });
    document.getElementById('sectionTable').addEventListener('change', function (e) {
      if (e.target.tagName !== 'SELECT') return;
      const el = e.target;
      if (el.value === '') return;
      if (!confirm('응답자와 확인한 값입니까?')) { loadSectionSnapshot(); return; }
      saveSectionCell(el.dataset.rid, el.dataset.a, el.dataset.b, Number(el.value));
    });
    document.getElementById('sectionTable').addEventListener('click', async function (e) {
      const btn = e.target.closest('.sr-act');
      if (!btn) return;
      const matrix = currentSectionMatrix();
      if (!matrix) return;
      const rid = btn.dataset.rid;
      const path = '/api/collections/' + collectionId + '/sections/' + matrix.matrix_id + '/' + btn.dataset.act + '/' + rid;
      if (btn.dataset.act === 'request-revision' &&
        !confirm('이 참여자에게만 이 섹션을 다시 조정하도록 요청할까요?')) return;
      try {
        await ahpApi(path, { method: 'POST' });
        ahpToast(btn.dataset.act === 'reveal-individual' ? '이 참여자에게 결과를 공개했습니다' : '재조정을 요청했습니다');
      } catch (e2) {
        ahpToast(e2.message || '처리에 실패했습니다', true);
      }
    });

    // ── 실시간 세션 진행 제어 ──────────────────────────────────────────
    document.getElementById('startSessionBtn').addEventListener('click', async function () {
      if (!confirm('설문을 시작할까요? 대기 중인 참여자에게 첫 섹션이 열립니다.')) return;
      try {
        await ahpApi('/api/collections/' + collectionId + '/session/start', { method: 'POST' });
        sessionStarted = true;
        activeSectionIndex = 0;
        renderPhaseBadge();
        syncSectionToActive();
      } catch (e) {
        ahpToast(e.message || '세션 시작에 실패했습니다', true);
      }
    });

    document.getElementById('advanceSectionBtn').addEventListener('click', async function () {
      const isLast = activeSectionIndex >= totalSections - 1;
      if (!confirm(isLast ? '마지막 섹션입니다. 진행하면 라운드가 종료됩니다. 계속할까요?' : '다음 섹션을 열까요?')) return;
      try {
        const res = await ahpApi('/api/collections/' + collectionId + '/sections/advance', { method: 'POST' });
        activeSectionIndex = res.section_index;
        renderPhaseBadge();
        syncSectionToActive();
        await loadRespondents();
      } catch (e) {
        ahpToast(e.message || '섹션 진행에 실패했습니다', true);
      }
    });

    document.getElementById('revealGroupBtn').addEventListener('click', async function () {
      const matrix = currentSectionMatrix();
      if (!matrix) return;
      try {
        await ahpApi('/api/collections/' + collectionId + '/sections/' + matrix.matrix_id + '/reveal-group', { method: 'POST' });
        ahpToast('그룹 결과를 공개했습니다');
      } catch (e) {
        ahpToast(e.message || '공개에 실패했습니다', true);
      }
    });

    // ── 참여자 관리(입장 현황과 함께 콘솔에서 바로) ──────────────────────
    document.getElementById('addParticipantBtn').addEventListener('click', async function () {
      const count = Number(prompt('발급할 인원 수', '1') || '0');
      if (!count || count < 1) return;
      try {
        const res = await ahpApi('/api/collections/' + collectionId + '/codes', {
          method: 'POST', body: { count: count },
        });
        ahpToast(res.issued.length + '명의 코드를 발급했습니다 — "수집 관리"에서 확인/인쇄할 수 있습니다');
        await loadRespondents();
      } catch (e) {
        ahpToast(e.message || '발급에 실패했습니다', true);
      }
    });

    document.getElementById('respondentTable').addEventListener('click', async function (e) {
      const btn = e.target.closest('.rr-act');
      if (!btn) return;
      const rid = btn.dataset.id;
      if (btn.dataset.act === 'reissue') {
        try {
          const res = await ahpApi('/api/collections/' + collectionId + '/respondents/' + rid + '/reissue-code', { method: 'POST' });
          alert('새 코드: ' + res.code);
        } catch (e2) {
          ahpToast(e2.message || '재발급에 실패했습니다', true);
        }
        return;
      }
      if (btn.dataset.act === 'delete') {
        if (!confirm('이 참여자를 삭제할까요? 지금까지의 응답도 함께 삭제됩니다.')) return;
        try {
          await ahpApi('/api/collections/' + collectionId + '/respondents/' + rid, { method: 'DELETE' });
          await loadRespondents();
        } catch (e2) {
          ahpToast(e2.message || '삭제에 실패했습니다', true);
        }
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
