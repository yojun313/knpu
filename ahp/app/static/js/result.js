(function () {
  'use strict';

  const projectId = location.pathname.split('/')[2];
  const MODE_LABEL = { offline: '오프라인', online: '온라인', realtime: '실시간' };
  let results = null;
  let hierarchyNodes = [];
  let altNames = {};
  let collectionsWithRounds = [];
  // scopeMode 'all' = 응답자별 최신 라운드로 전체 합산(기존 기본 동작).
  // 'custom'이면 scopeSelection에 담긴 collection_ids(+선택된 round만) 조합만 본다.
  let scopeMode = 'all';
  let scopeSelection = { collectionIds: [], roundMap: {} };

  function renderWeightChart(container, weights, nodeNames, opts) {
    opts = opts || {};
    const sorted = Object.entries(weights).sort(function (a, b) { return b[1] - a[1]; });
    const max = Math.max.apply(null, sorted.map(function (e) { return e[1]; }).concat([0.0001]));
    container.innerHTML = sorted.map(function (e) {
      const name = nodeNames[e[0]] || e[0];
      const pct = (e[1] * 100).toFixed(1);
      const width = (e[1] / max) * 100;
      return '<div class="wc-row"><span class="wc-name">' + ahpEsc(name) + '</span>' +
        '<div class="wc-track"><div class="wc-fill' + (opts.adjusted ? ' adjusted' : '') + '" style="width:' + width + '%"></div></div>' +
        '<span class="wc-pct">' + pct + '%</span></div>';
    }).join('');
  }

  function renderConsensus() {
    const box = document.getElementById('consensusList');
    const matrixIds = Object.keys(results.consensus || {});
    if (!matrixIds.length) {
      box.innerHTML = '<p style="padding:14px;font-size:12px;color:var(--sidebar-muted)">응답자가 2명 이상이어야 합의도를 계산합니다.</p>';
      return;
    }
    box.innerHTML = matrixIds.map(function (mid) {
      const c = results.consensus[mid];
      const outliers = (results.outliers || {})[mid] || [];
      const outlierText = outliers.length
        ? outliers.map(function (o) { return o.outlier_respondents.length + '명 의견이 크게 다른 쌍 발견'; }).join(', ')
        : '극단값 없음';
      return '<div class="consensus-item"><div class="ci-head"><span>' + ahpEsc(results.node_names[matrixIdToParent(mid)] || mid) + '</span>' +
        '<span class="ci-w">Kendall W ' + c.kendalls_w.toFixed(2) + '</span></div>' +
        '<div class="ci-outliers">' + ahpEsc(outlierText) + '</div></div>';
    }).join('');
  }

  let matrixParentMap = {};
  function matrixIdToParent(mid) { return matrixParentMap[mid] || mid; }

  function renderCrTable() {
    const table = document.getElementById('crTable');
    const rows = [];
    Object.entries(results.per_respondent_cr || {}).forEach(function (entry) {
      const rid = entry[0], perMatrix = entry[1];
      Object.entries(perMatrix).forEach(function (mEntry) {
        const mid = mEntry[0], cr = mEntry[1];
        rows.push({ rid: rid, parent: results.node_names[matrixIdToParent(mid)] || mid, cr: cr });
      });
    });
    if (!rows.length) {
      table.innerHTML = '<tr><td style="padding:14px;color:var(--sidebar-muted);font-size:12px">아직 계산할 수 있는 CR이 없습니다.</td></tr>';
      return;
    }
    table.innerHTML = '<thead><tr><th>응답자</th><th>기준</th><th>CR</th></tr></thead><tbody>' +
      rows.map(function (r) {
        const cls = r.cr === null ? '' : (r.cr <= (results.cr_threshold || 0.1) ? 'cr-ok' : 'cr-bad');
        return '<tr><td>' + ahpEsc(r.rid.slice(0, 8)) + '</td><td>' + ahpEsc(r.parent) + '</td>' +
          '<td class="' + cls + '">' + (r.cr === null ? '미완료' : r.cr.toFixed(3)) + '</td></tr>';
      }).join('') + '</tbody>';
  }

  function renderStats() {
    document.getElementById('statRespondents').textContent = results.respondent_count;
    const allCrs = [];
    Object.values(results.per_respondent_cr || {}).forEach(function (m) {
      Object.values(m).forEach(function (cr) { if (cr !== null && cr !== undefined) allCrs.push(cr); });
    });
    document.getElementById('statAvgCr').textContent = allCrs.length
      ? (allCrs.reduce(function (a, b) { return a + b; }, 0) / allCrs.length).toFixed(3) : '-';
    document.getElementById('statBadCr').textContent = allCrs.filter(function (c) { return c > (results.cr_threshold || 0.1); }).length;
  }

  // 현재 선택 범위를 쿼리스트링으로 — get_results/get_sensitivity가 공유하는
  // collection_id(단일, 레거시)/collection_ids(복수)/rounds(cid:round 쌍) 규약을 그대로 따른다.
  function buildScopeQuery() {
    if (scopeMode === 'all') return '';
    const params = new URLSearchParams();
    if (scopeSelection.collectionIds.length) {
      params.set('collection_ids', scopeSelection.collectionIds.join(','));
    }
    const roundPairs = Object.keys(scopeSelection.roundMap).map(function (cid) {
      return cid + ':' + scopeSelection.roundMap[cid];
    });
    if (roundPairs.length) params.set('rounds', roundPairs.join(','));
    const qs = params.toString();
    return qs ? ('?' + qs) : '';
  }

  async function loadResults() {
    document.getElementById('resultError').hidden = true;
    try {
      results = await ahpApi('/api/projects/' + projectId + '/results' + buildScopeQuery());
    } catch (e) {
      // 성공이든 실패든 반드시 화면을 갱신한다 — 예외를 그냥 던지면 직전 범위의
      // 렌더가 그대로 남아 "필터를 바꿔도 안 바뀐다"는 문제로 이어진다.
      document.getElementById('resultEmpty').hidden = true;
      document.getElementById('resultContent').hidden = true;
      document.getElementById('resultError').hidden = false;
      ahpToast(e.message || '결과를 불러오는 중 오류가 발생했습니다', true);
      return;
    }

    matrixParentMap = {};
    // matrices 정보가 결과에 직접 없으므로 hierarchy 기반으로 부모=matrix_id 관계를 유추
    // (survey_service의 규칙: matrix_id는 항상 parent_uuid와 같다)
    Object.keys(results.local_weights || {}).forEach(function (mid) { matrixParentMap[mid] = mid; });

    document.getElementById('resultEmpty').hidden = results.respondent_count > 0;
    document.getElementById('resultContent').hidden = results.respondent_count === 0;
    if (!results.respondent_count) return;

    renderStats();
    renderWeightChart(document.getElementById('globalWeightsChart'), results.global_weights, results.node_names);
    renderConsensus();
    renderCrTable();

    const altScores = results.alternative_scores || {};
    const hasAlts = Object.keys(altScores).length > 0;
    document.getElementById('altRankCard').hidden = !hasAlts;
    if (hasAlts) {
      renderWeightChart(document.getElementById('altRankChart'), altScores, altNames);
    }

    const proj = await ahpApi('/api/projects/' + projectId);
    document.getElementById('statAgg').textContent = proj.settings.aggregation;
  }

  function updateScopeButtonLabel() {
    const btn = document.getElementById('scopeBtn');
    if (scopeMode === 'all') { btn.textContent = '결과 범위: 전체 합산 ▾'; return; }
    const n = scopeSelection.collectionIds.length;
    btn.textContent = '결과 범위: ' + n + '개 선택 ▾';
  }

  function renderScopeList() {
    const box = document.getElementById('scopeCollectionsList');
    if (!collectionsWithRounds.length) {
      box.innerHTML = '<p class="muted" style="font-size:11.5px">아직 제출된 수집이 없습니다.</p>';
      return;
    }
    box.innerHTML = collectionsWithRounds.map(function (c) {
      const roundOpts = ['<option value="">최신 라운드</option>'].concat(
        c.rounds.map(function (r) { return '<option value="' + r + '">' + r + '라운드</option>'; })
      ).join('');
      return '<div class="scope-coll-row" data-id="' + c.id + '">' +
        '<label><input type="checkbox" class="scope-coll-check" data-id="' + c.id + '">' +
        '<span>' + ahpEsc(c.label) + ' · ' + (MODE_LABEL[c.mode] || c.mode) + '</span></label>' +
        '<select class="scope-round-select" data-id="' + c.id + '">' + roundOpts + '</select></div>';
    }).join('');
  }

  async function loadCollectionsFilter() {
    collectionsWithRounds = await ahpApi('/api/projects/' + projectId + '/collections/rounds');
    renderScopeList();
  }

  function applyScopeSelection() {
    const allChecked = document.getElementById('scopeAllToggle').checked;
    if (allChecked) {
      scopeMode = 'all';
      scopeSelection = { collectionIds: [], roundMap: {} };
    } else {
      const collectionIds = [];
      const roundMap = {};
      document.querySelectorAll('.scope-coll-check:checked').forEach(function (cb) {
        const cid = cb.dataset.id;
        collectionIds.push(cid);
        const roundSel = document.querySelector('.scope-round-select[data-id="' + cid + '"]');
        if (roundSel && roundSel.value) roundMap[cid] = Number(roundSel.value);
      });
      if (!collectionIds.length) {
        ahpToast('최소 한 개 이상 선택하거나 "전체 합산"을 유지해 주세요', true);
        return;
      }
      scopeMode = 'custom';
      scopeSelection = { collectionIds: collectionIds, roundMap: roundMap };
    }
    updateScopeButtonLabel();
    document.getElementById('scopePanel').hidden = true;
    loadResults();
  }

  async function loadSensNodeOptions() {
    const h = await ahpApi('/api/projects/' + projectId + '/hierarchy');
    hierarchyNodes = h.nodes;
    altNames = {};
    (h.alternatives || []).forEach(function (a) { altNames[a.uuid] = a.name; });
    const sel = document.getElementById('sensNode');
    sel.innerHTML = hierarchyNodes
      .filter(function (n) { return n.parent_id !== null; })
      .map(function (n) { return '<option value="' + n.uuid + '">' + '　'.repeat(n.level - 1) + ahpEsc(n.name) + '</option>'; })
      .join('');
  }

  async function runSensitivity() {
    const target = document.getElementById('sensNode').value;
    const delta = Number(document.getElementById('sensDelta').value);
    const base = buildScopeQuery();
    const sep = base ? '&' : '?';
    const qs = base + sep + new URLSearchParams({ target_node: target, delta_pct: delta }).toString();
    try {
      const res = await ahpApi('/api/projects/' + projectId + '/results/sensitivity' + qs);
      renderWeightChart(document.getElementById('sensResult'), res.adjusted, results.node_names, { adjusted: true });
    } catch (e) {
      ahpToast(e.message || '민감도 분석에 실패했습니다', true);
    }
  }

  function wireExportLinks() {
    document.getElementById('exportDocx').href = '/api/export/' + projectId + '/survey.docx';
    document.getElementById('exportXlsx').href = '/api/export/' + projectId + '/package.xlsx';
    document.getElementById('exportCsv').href = '/api/export/' + projectId + '/responses.csv';
  }

  async function init() {
    try {
      const project = await ahpApi('/api/projects/' + projectId);
      document.getElementById('projTitle').textContent = project.title + ' · 결과 분석';
      if (window.AHPShell) window.AHPShell.setActiveProject(projectId);
    } catch (e) {
      ahpToast('프로젝트를 불러오지 못했습니다', true);
      return;
    }

    wireExportLinks();
    await loadCollectionsFilter();
    await loadSensNodeOptions();
    await loadResults();

    document.querySelectorAll('#stageTabs .stage-tab').forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        e.preventDefault();
        const stage = tab.dataset.stage;
        if (stage === 'result') return;
        location.href = '/' + stage + '/' + projectId;
      });
    });

    document.getElementById('scopeBtn').addEventListener('click', function (e) {
      e.stopPropagation();
      document.getElementById('scopePanel').hidden = !document.getElementById('scopePanel').hidden;
    });
    document.getElementById('scopePanel').addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function () {
      document.getElementById('scopePanel').hidden = true;
    });
    document.getElementById('scopeApplyBtn').addEventListener('click', applyScopeSelection);
    document.getElementById('sensRunBtn').addEventListener('click', runSensitivity);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
