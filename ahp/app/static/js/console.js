(function () {
  'use strict';

  const collectionId = location.pathname.split('/')[2];
  let projectId = null;
  let respondents = [];
  let ws = null;
  let backoff = 1000;

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
        '<span></span></div>';
    }).join('');
  }

  function patchRespondent(id, patch) {
    const r = respondents.find(function (x) { return x.id === id; });
    if (r) Object.assign(r, patch);
    renderTable();
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
        loadRespondents();
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

  async function loadLiveMatrices() {
    const survey = await ahpApi('/api/projects/' + projectId + '/survey');
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
        '<h4>' + ahpEsc(nodeNamesCache[m.matrix_id] || m.matrix_id) + '</h4>' +
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
    if (window.AHPShell) window.AHPShell.setActiveProject(projectId);

    try {
      const hierarchy = await ahpApi('/api/projects/' + projectId + '/hierarchy');
      nodeNamesCache = {};
      hierarchy.nodes.forEach(function (n) { nodeNamesCache[n.uuid] = n.name; });
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
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
