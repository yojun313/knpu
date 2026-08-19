(function () {
  'use strict';

  const projectId = location.pathname.split('/')[2];
  let survey = null;
  let diagramLoaded = false;

  const STATUS_LABEL = { draft: '초안', published: '발행됨' };
  const STATUS_BADGE = { draft: 'muted', published: 'ok' };

  // 계층도는 다른 단계에서도 참고할 수 있어야 한다는 요청사항 — design.html의
  // hierarchy_diagram.js를 그대로 재사용, 접이식 카드로 두고 처음 펼칠 때만 불러온다.
  function wireDiagramToggle() {
    const toggle = document.getElementById('diagramToggle');
    if (!toggle) return;
    toggle.addEventListener('click', async function () {
      const box = document.getElementById('diagramContainer');
      const icon = document.getElementById('diagramToggleIcon');
      box.hidden = !box.hidden;
      icon.textContent = box.hidden ? '▸ 펼치기' : '▾ 접기';
      if (box.hidden || diagramLoaded) return;
      diagramLoaded = true;
      try {
        const h = await ahpApi('/api/projects/' + projectId + '/hierarchy');
        window.AHPHierarchyDiagram.render(box, h.nodes);
      } catch (e) {
        box.innerHTML = '<p class="muted" style="padding:16px;font-size:12px">계층도를 불러오지 못했습니다.</p>';
      }
    });
  }

  function nodeName(uuid, nodesByUuid) {
    return (nodesByUuid[uuid] && nodesByUuid[uuid].name) || uuid;
  }

  async function loadHierarchyNodes() {
    const h = await ahpApi('/api/projects/' + projectId + '/hierarchy');
    const map = {};
    h.nodes.forEach(function (n) { map[n.uuid] = n; });
    (h.alternatives || []).forEach(function (a) { map[a.uuid] = a; });
    return map;
  }

  function renderStatus() {
    const badge = document.getElementById('surveyStatusBadge');
    badge.className = 'badge ' + (STATUS_BADGE[survey.status] || 'muted');
    badge.textContent = STATUS_LABEL[survey.status] || survey.status;
    document.getElementById('publishBtn').disabled = survey.status === 'published';
    document.getElementById('publishBtn').textContent = survey.status === 'published' ? '발행됨' : '발행';
  }

  function renderMatrices(nodesByUuid) {
    const box = document.getElementById('matricesList');
    if (!survey.matrices.length) {
      box.innerHTML = '<div class="empty-state"><div class="es-icon">📋</div>' +
        '<h2>비교할 항목이 없습니다</h2><p>계층 설계에서 최상위 기준을 2개 이상 추가해 주세요.</p></div>';
      return;
    }
    box.innerHTML = survey.matrices.map(function (m) {
      const parentDesc = survey.node_descriptions[m.parent_uuid] || '';
      const childrenHtml = m.child_uuids.map(function (cid) {
        const desc = survey.node_descriptions[cid] || '';
        return '<div class="matrix-child-row">' +
          '<div class="mc-name">' + ahpEsc(nodeName(cid, nodesByUuid)) + '</div>' +
          '<textarea class="node-desc-input" data-node="' + cid + '" placeholder="응답자에게 보여줄 설명(선택)">' +
          ahpEsc(desc) + '</textarea></div>';
      }).join('');
      return '<div class="table-card matrix-block">' +
        '<div class="matrix-parent">' +
        '<div class="mp-name">' + (m.is_alternative ? '<span class="badge ok" style="margin-right:6px">대안 비교</span>' : '') +
        ahpEsc(nodeName(m.parent_uuid, nodesByUuid)) + '</div>' +
        '<div class="field"><label>이 기준 자체에 대한 설명(선택)</label>' +
        '<textarea class="node-desc-input" data-node="' + m.parent_uuid + '">' + ahpEsc(parentDesc) + '</textarea></div>' +
        '<div class="field" style="margin-top:10px"><label>비교 질문 문구</label>' +
        '<textarea class="question-input" data-matrix="' + m.matrix_id + '">' + ahpEsc(m.question_text) + '</textarea></div>' +
        '</div>' +
        '<div class="matrix-children">' + childrenHtml + '</div>' +
        '</div>';
    }).join('');
  }

  async function saveMatrixEdits() {
    const nodeDescriptions = {};
    document.querySelectorAll('.node-desc-input').forEach(function (el) {
      nodeDescriptions[el.dataset.node] = el.value.trim();
    });
    const matrixQuestions = {};
    document.querySelectorAll('.question-input').forEach(function (el) {
      matrixQuestions[el.dataset.matrix] = el.value.trim();
    });
    try {
      await ahpApi('/api/projects/' + projectId + '/survey', {
        method: 'PUT',
        body: { node_descriptions: nodeDescriptions, matrix_questions: matrixQuestions },
      });
      ahpToast('저장했습니다');
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    }
  }

  async function resync() {
    const btn = document.getElementById('resyncBtn');
    btn.disabled = true;
    try {
      const res = await ahpApi('/api/projects/' + projectId + '/survey/resync', { method: 'POST' });
      const notice = document.getElementById('resyncNotice');
      if (!res.changed) {
        notice.innerHTML = '<div class="warn-item" style="background:var(--overlay-hover);color:var(--sidebar-muted);border-color:var(--sidebar-border)">계층 변경 사항이 없습니다.</div>';
      } else if (!res.impact) {
        notice.innerHTML = '<div class="warn-item" style="background:rgba(76,175,80,.1);color:var(--success);border-color:rgba(76,175,80,.3)">✓ v' + res.version + '로 갱신했습니다. 응답에 영향 없는 변경입니다.</div>';
      } else if (res.pruned_responses === 0) {
        notice.innerHTML = '<div class="warn-item" style="background:rgba(76,175,80,.1);color:var(--success);border-color:rgba(76,175,80,.3)">✓ v' + res.version + '로 갱신했습니다. 아직 정리할 기존 응답이 없습니다.</div>';
      } else {
        notice.innerHTML = '<div class="warn-item">⚠ v' + res.version + '로 갱신했습니다. 구조가 바뀌어 응답 ' + res.pruned_responses + '건이 정리됐습니다(무효화된 쌍만 제거, 유효한 응답은 유지).</div>';
      }
      await init();
    } catch (e) {
      ahpToast(e.message || '새로고침에 실패했습니다', true);
    } finally {
      btn.disabled = false;
    }
  }

  async function publish() {
    if (!confirm('설문지를 발행하면 수집(온라인/실시간 배포, 오프라인 입력)을 시작할 수 있습니다. 계속할까요?')) return;
    try {
      await ahpApi('/api/projects/' + projectId + '/survey/publish', { method: 'POST' });
      ahpToast('발행했습니다');
      await init();
    } catch (e) {
      ahpToast(e.message || '발행에 실패했습니다', true);
    }
  }

  async function init() {
    try {
      const project = await ahpApi('/api/projects/' + projectId);
      document.getElementById('projTitle').textContent = project.title + ' · 설문지';
      if (window.AHPShell) window.AHPShell.setActiveProject(projectId);
    } catch (e) {
      ahpToast('프로젝트를 불러오지 못했습니다', true);
      return;
    }

    let nodesByUuid;
    try {
      nodesByUuid = await loadHierarchyNodes();
      survey = await ahpApi('/api/projects/' + projectId + '/survey');
    } catch (e) {
      ahpToast(e.message || '설문지를 불러오지 못했습니다', true);
      return;
    }

    document.getElementById('surveyTitle').value = survey.title;
    document.getElementById('surveyIntro').value = survey.intro_text;
    document.getElementById('surveyConsent').value = survey.consent_text;
    renderStatus();
    renderMatrices(nodesByUuid);

    document.querySelectorAll('#stageTabs .stage-tab').forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        e.preventDefault();
        const stage = tab.dataset.stage;
        if (stage === 'survey') return;
        location.href = '/' + stage + '/' + projectId;
      });
    });

    document.getElementById('saveIntroBtn').addEventListener('click', async function () {
      try {
        await ahpApi('/api/projects/' + projectId + '/survey', {
          method: 'PUT',
          body: {
            title: document.getElementById('surveyTitle').value,
            intro_text: document.getElementById('surveyIntro').value,
            consent_text: document.getElementById('surveyConsent').value,
          },
        });
        ahpToast('저장했습니다');
      } catch (e) {
        ahpToast(e.message || '저장에 실패했습니다', true);
      }
    });

    document.getElementById('matricesList').addEventListener('blur', function (e) {
      if (e.target.classList.contains('node-desc-input') || e.target.classList.contains('question-input')) {
        saveMatrixEdits();
      }
    }, true);

    document.getElementById('resyncBtn').addEventListener('click', resync);
    document.getElementById('previewBtn').addEventListener('click', function () {
      window.open('/print/' + survey.id, '_blank');
    });
    document.getElementById('publishBtn').addEventListener('click', publish);
    wireDiagramToggle();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
