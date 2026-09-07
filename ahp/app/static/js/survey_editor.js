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

  const WEIGHT_METHODS = [
    { v: 'ahp', label: 'AHP — 모든 쌍을 1:1 비교' },
    { v: 'bwm', label: 'BWM — 가장/가장 덜 중요한 것 기준 비교' },
  ];
  const METHOD_LABEL = { ahp: 'AHP', bwm: 'BWM' };
  const METHOD_DOCS = {
    ahp: 'AHP(Analytic Hierarchy Process) — 항목을 두 개씩 모두 짝지어 상대 중요도를 ' +
      '1~9로 매기고, 고유벡터로 가중치를 얻습니다. 판단의 논리적 일관성을 CR로 점검합니다. ' +
      '문항 수는 n(n-1)/2 로 늘어납니다.',
    bwm: 'BWM(Best-Worst Method) — 먼저 가장 중요한 항목과 가장 덜 중요한 항목을 고른 뒤, ' +
      '그 둘을 기준으로만 나머지를 비교합니다(문항 2n-3개). 선형계획으로 가중치를 얻고 ' +
      '입력 일관성(CR^I)과 순서 일관성(OR)으로 점검합니다.',
  };

  function enabledMethods() {
    const en = survey.methods && survey.methods.enabled;
    return Array.isArray(en) && en.length ? en.slice() : ['ahp'];
  }
  function methodOf(nodeUuid) {
    return (survey.methods && survey.methods.criteria && survey.methods.criteria[nodeUuid]) ||
      'ahp';
  }
  // 모든 기준 노드에 배정된 방법이 하나로 통일돼 있으면 그 값, 아니면 null(=혼합).
  function commonCriteriaMethod() {
    const parents = survey.groups.filter(function (m) { return !m.is_alternative; })
      .map(function (m) { return m.parent_uuid; });
    if (!parents.length) return enabledMethods()[0];
    const vals = parents.map(methodOf);
    return vals.every(function (v) { return v === vals[0]; }) ? vals[0] : null;
  }

  let perNodeMode = false;

  function renderMethodsCard() {
    const en = enabledMethods();
    // 활용 분석 체크박스
    document.getElementById('enabledMethods').innerHTML = WEIGHT_METHODS.map(function (o) {
      const on = en.indexOf(o.v) !== -1;
      return '<label class="em-chip' + (on ? ' on' : '') + '" data-m="' + o.v + '">' +
        '<input type="checkbox" class="em-check" value="' + o.v + '"' + (on ? ' checked' : '') + '> ' +
        ahpEsc(o.label) + '</label>';
    }).join('');
    updateMethodDoc(en[0]);

    // 기준 가중치 방법(전체) + 고급 토글
    const common = commonCriteriaMethod();
    perNodeMode = common === null;
    const master = document.getElementById('criteriaMethodMaster');
    master.innerHTML = en.map(function (m) {
      return '<option value="' + m + '"' + (m === (common || en[0]) ? ' selected' : '') + '>' +
        (METHOD_LABEL[m] || m) + '</option>';
    }).join('');
    master.disabled = perNodeMode;
    document.getElementById('criteriaPerNodeToggle').checked = perNodeMode;

    // 대안 평가 방법 (대안 계층을 쓸 때만)
    const altField = document.getElementById('altMethodField');
    altField.hidden = projectSettings.alt_layer !== 'on';
    if (!altField.hidden) {
      const cur = (survey.methods && survey.methods.alternatives) || 'ahp';
      document.getElementById('altMethodSelect').innerHTML = en.map(function (m) {
        return '<option value="' + m + '"' + (m === cur ? ' selected' : '') + '>' +
          (METHOD_LABEL[m] || m) + '</option>';
      }).join('');
    }
    applyPerNodeVisibility();
  }

  function updateMethodDoc(m) {
    document.getElementById('methodDoc').textContent = METHOD_DOCS[m] || '';
  }
  function applyPerNodeVisibility() {
    document.querySelectorAll('#matricesList .method-field').forEach(function (el) {
      el.hidden = !perNodeMode;
    });
  }
  // 체크박스에서 방법을 빼면 master/alt 셀렉트 선택지도 즉시 반영.
  function checkedMethods() {
    return Array.prototype.map.call(
      document.querySelectorAll('.em-check:checked'), function (el) { return el.value; }
    );
  }
  function refreshMethodSelects() {
    const en = checkedMethods().length ? checkedMethods() : ['ahp'];
    [['criteriaMethodMaster'], ['altMethodSelect']].forEach(function (p) {
      const sel = document.getElementById(p[0]);
      if (!sel) return;
      const keep = en.indexOf(sel.value) !== -1 ? sel.value : en[0];
      sel.innerHTML = en.map(function (m) {
        return '<option value="' + m + '"' + (m === keep ? ' selected' : '') + '>' +
          (METHOD_LABEL[m] || m) + '</option>';
      }).join('');
    });
  }

  let methodsWired = false;
  function wireMethodsCard() {
    if (methodsWired) return;
    methodsWired = true;
    const card = document.getElementById('methodsCard');
    card.addEventListener('change', function (e) {
      if (e.target.classList.contains('em-check')) {
        const chip = e.target.closest('.em-chip');
        if (chip) chip.classList.toggle('on', e.target.checked);
        if (e.target.checked) updateMethodDoc(e.target.value);
        refreshMethodSelects();
      } else if (e.target.id === 'criteriaPerNodeToggle') {
        perNodeMode = e.target.checked;
        document.getElementById('criteriaMethodMaster').disabled = perNodeMode;
        applyPerNodeVisibility();
      }
    });
    card.addEventListener('mouseover', function (e) {
      const chip = e.target.closest('.em-chip');
      if (chip) updateMethodDoc(chip.dataset.m);
    });
    document.getElementById('saveMethodsBtn').addEventListener('click', saveMethods);
  }

  function renderMatrices(nodesByUuid) {
    const box = document.getElementById('matricesList');
    if (!survey.groups.length) {
      box.innerHTML = '<div class="empty-state"><div class="es-icon">📋</div>' +
        '<h2>비교할 항목이 없습니다</h2><p>계층 설계에서 최상위 기준을 2개 이상 추가해 주세요.</p></div>';
      return;
    }
    box.innerHTML = survey.groups.map(function (m) {
      const parentDesc = survey.node_descriptions[m.parent_uuid] || '';
      const childrenHtml = m.child_uuids.map(function (cid) {
        const desc = survey.node_descriptions[cid] || '';
        return '<div class="matrix-child-row">' +
          '<div class="mc-name">' + ahpEsc(nodeName(cid, nodesByUuid)) + '</div>' +
          '<textarea class="node-desc-input" data-node="' + cid + '" placeholder="응답자에게 보여줄 설명(선택)">' +
          ahpEsc(desc) + '</textarea></div>';
      }).join('');
      // 노드별 방법 — "고급: 기준마다 다른 방법" 토글일 때만 보인다. 선택지는
      // "활용 분석"에서 선언한 방법으로 제한.
      const cur = m.is_alternative ? ((survey.methods && survey.methods.alternatives) || 'ahp')
        : methodOf(m.parent_uuid);
      const opts = enabledMethods();
      const methodHtml = m.is_alternative ? '' : (
        '<div class="field method-field" style="margin-top:10px" hidden><label>이 기준의 가중치 산출 방법</label>' +
        '<select class="method-input" data-node="' + m.parent_uuid + '">' +
        opts.map(function (v) {
          const o = WEIGHT_METHODS.find(function (w) { return w.v === v; }) || { v: v, label: v };
          return '<option value="' + o.v + '"' + (o.v === cur ? ' selected' : '') + '>' +
            o.label + '</option>';
        }).join('') + '</select></div>'
      );
      return '<div class="table-card matrix-block">' +
        '<div class="matrix-parent">' +
        '<div class="mp-name">' + (m.is_alternative ? '<span class="badge ok" style="margin-right:6px">대안 비교</span>' :
          (cur === 'bwm' ? '<span class="badge" style="margin-right:6px">BWM</span>' : '')) +
        ahpEsc(nodeName(m.parent_uuid, nodesByUuid)) + '</div>' +
        methodHtml +
        '<div class="field" style="margin-top:10px"><label>이 기준 자체에 대한 설명(선택)</label>' +
        '<textarea class="node-desc-input" data-node="' + m.parent_uuid + '">' + ahpEsc(parentDesc) + '</textarea></div>' +
        '<div class="field" style="margin-top:10px"><label>비교 질문 문구</label>' +
        '<textarea class="question-input" data-matrix="' + m.group_id + '">' + ahpEsc(m.question_text) + '</textarea></div>' +
        '</div>' +
        '<div class="matrix-children">' + childrenHtml + '</div>' +
        '</div>';
    }).join('');
  }

  async function saveMethods() {
    const enabled = Array.prototype.map.call(
      document.querySelectorAll('.em-check:checked'), function (el) { return el.value; }
    );
    if (!enabled.length) { ahpToast('활용할 분석을 최소 하나 선택해 주세요', true); return; }

    const parents = survey.groups.filter(function (m) { return !m.is_alternative; })
      .map(function (m) { return m.parent_uuid; });
    const criteria = {};
    if (perNodeMode) {
      document.querySelectorAll('.method-input').forEach(function (el) {
        criteria[el.dataset.node] = enabled.indexOf(el.value) !== -1 ? el.value : enabled[0];
      });
    } else {
      const master = document.getElementById('criteriaMethodMaster').value || enabled[0];
      parents.forEach(function (uuid) { criteria[uuid] = master; });
    }
    const altField = document.getElementById('altMethodField');
    const alternatives = altField.hidden
      ? ((survey.methods && survey.methods.alternatives) || 'ahp')
      : document.getElementById('altMethodSelect').value;

    if (survey.status === 'published' &&
      !confirm('이미 발행된 설문입니다. 방법을 바꾼 항목의 기존 응답은 초기화됩니다. 계속할까요?')) {
      await init();
      return;
    }
    try {
      const res = await ahpApi('/api/projects/' + projectId + '/survey', {
        method: 'PUT',
        body: { methods: { criteria: criteria, alternatives: alternatives, enabled: enabled } },
      });
      const cleared = res.cleared_answers || 0;
      const savedEnabled = (res.methods && res.methods.enabled) || enabled;
      const kept = savedEnabled.filter(function (m) { return enabled.indexOf(m) === -1; });
      let msg = cleared > 0
        ? '방법을 저장했습니다. 형식이 바뀐 항목의 응답 ' + cleared + '건이 초기화됐습니다.'
        : '방법을 저장했습니다.';
      if (kept.length) {
        msg += ' (' + kept.map(function (m) { return METHOD_LABEL[m] || m; }).join(', ') +
          '은(는) 사용 중이라 해제되지 않았습니다)';
      }
      ahpToast(msg);
      await init();
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    }
  }

  async function saveMatrixEdits() {
    const nodeDescriptions = {};
    document.querySelectorAll('.node-desc-input').forEach(function (el) {
      nodeDescriptions[el.dataset.node] = el.value.trim();
    });
    const groupQuestions = {};
    document.querySelectorAll('.question-input').forEach(function (el) {
      groupQuestions[el.dataset.matrix] = el.value.trim();
    });
    try {
      await ahpApi('/api/projects/' + projectId + '/survey', {
        method: 'PUT',
        body: { node_descriptions: nodeDescriptions, group_questions: groupQuestions },
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
    renderMethodsCard();
    wireMethodsCard();

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
