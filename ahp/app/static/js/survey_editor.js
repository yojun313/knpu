(function () {
  'use strict';

  const projectId = location.pathname.split('/')[2];
  let survey = null;
  let diagramLoaded = false;
  let projectSettings = {};

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
      projectSettings = project.settings || {};
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

    const demoOn = projectSettings.collect_demographics === 'on';
    document.getElementById('demographicsCard').hidden = !demoOn;
    if (demoOn) {
      demoFields = JSON.parse(JSON.stringify(survey.demographics || []));
      renderDemoFields();
      if (!demoWired) { wireDemographics(); demoWired = true; }
    }
  }

  // ── 인구통계 설계 패널 ────────────────────────────────────────────────────
  const DEMO_TYPES = [
    { v: 'single', label: '단일선택' },
    { v: 'multi', label: '복수선택' },
    { v: 'number', label: '숫자' },
    { v: 'text', label: '단답형' },
  ];
  let demoFields = [];
  let demoWired = false;

  function renderDemoFields() {
    const box = document.getElementById('demoFieldList');
    if (!demoFields.length) {
      box.innerHTML = '<p class="muted" style="font-size:12px">추가된 항목이 없습니다.</p>';
      return;
    }
    box.innerHTML = demoFields.map(function (f, i) {
      const typeOpts = DEMO_TYPES.map(function (t) {
        return '<option value="' + t.v + '"' + (t.v === f.type ? ' selected' : '') + '>' + t.label + '</option>';
      }).join('');
      const isChoice = f.type === 'single' || f.type === 'multi';
      const optsHtml = isChoice ? (
        '<div class="demo-opts-editor">' +
        (f.options || []).map(function (o, j) {
          return '<div class="demo-opt-row">' +
            '<input class="demo-opt-label" data-fi="' + i + '" data-oi="' + j + '" placeholder="보기(예: 남)" value="' + ahpEsc(o.label || '') + '">' +
            '<input class="demo-opt-code" data-fi="' + i + '" data-oi="' + j + '" placeholder="코드" value="' + ahpEsc(o.code || '') + '">' +
            '<button type="button" class="btn sm" data-act="del-opt" data-fi="' + i + '" data-oi="' + j + '">×</button></div>';
        }).join('') +
        '<button type="button" class="btn sm" data-act="add-opt" data-fi="' + i + '">＋ 보기 추가</button></div>'
      ) : '';
      return '<div class="demo-field-card">' +
        '<div class="demo-field-head">' +
        '<input class="demo-field-label" data-fi="' + i + '" placeholder="항목 이름(예: 성별)" value="' + ahpEsc(f.label || '') + '">' +
        '<select class="demo-field-type" data-fi="' + i + '">' + typeOpts + '</select>' +
        '<label class="demo-req-check"><input type="checkbox" class="demo-field-req" data-fi="' + i + '"' + (f.required ? ' checked' : '') + '> 필수</label>' +
        '<button type="button" class="btn sm" data-act="del-field" data-fi="' + i + '">삭제</button>' +
        '</div>' + optsHtml + '</div>';
    }).join('');
  }

  function syncDemoFromDom() {
    document.querySelectorAll('.demo-field-label').forEach(function (el) {
      demoFields[+el.dataset.fi].label = el.value;
    });
    document.querySelectorAll('.demo-field-req').forEach(function (el) {
      demoFields[+el.dataset.fi].required = el.checked;
    });
    document.querySelectorAll('.demo-opt-label').forEach(function (el) {
      const f = demoFields[+el.dataset.fi];
      f.options[+el.dataset.oi] = f.options[+el.dataset.oi] || {};
      f.options[+el.dataset.oi].label = el.value;
    });
    document.querySelectorAll('.demo-opt-code').forEach(function (el) {
      const f = demoFields[+el.dataset.fi];
      f.options[+el.dataset.oi] = f.options[+el.dataset.oi] || {};
      f.options[+el.dataset.oi].code = el.value;
    });
  }

  async function saveDemographics() {
    syncDemoFromDom();
    try {
      const res = await ahpApi('/api/projects/' + projectId + '/survey', {
        method: 'PUT', body: { demographics: demoFields },
      });
      survey.demographics = res.demographics || [];
      demoFields = JSON.parse(JSON.stringify(survey.demographics));
      renderDemoFields();
      ahpToast('인구통계 설계를 저장했습니다');
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    }
  }

  function wireDemographics() {
    document.getElementById('addDemoFieldBtn').addEventListener('click', function () {
      syncDemoFromDom();
      demoFields.push({ label: '', type: 'single', required: false, options: [{ label: '', code: '1' }] });
      renderDemoFields();
    });
    document.getElementById('saveDemoBtn').addEventListener('click', saveDemographics);
    const list = document.getElementById('demoFieldList');
    list.addEventListener('change', function (e) {
      if (!e.target.classList.contains('demo-field-type')) return;
      syncDemoFromDom();
      const f = demoFields[+e.target.dataset.fi];
      f.type = e.target.value;
      if ((f.type === 'single' || f.type === 'multi') && !(f.options && f.options.length)) {
        f.options = [{ label: '', code: '1' }];
      }
      renderDemoFields();
    });
    list.addEventListener('click', function (e) {
      const btn = e.target.closest('button[data-act]');
      if (!btn) return;
      syncDemoFromDom();
      const fi = +btn.dataset.fi;
      const act = btn.dataset.act;
      if (act === 'del-field') demoFields.splice(fi, 1);
      else if (act === 'add-opt') demoFields[fi].options.push({ label: '', code: String((demoFields[fi].options || []).length + 1) });
      else if (act === 'del-opt') demoFields[fi].options.splice(+btn.dataset.oi, 1);
      renderDemoFields();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
