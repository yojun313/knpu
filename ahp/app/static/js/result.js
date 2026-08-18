(function () {
  'use strict';

  const projectId = location.pathname.split('/')[2];
  let results = null;
  let hierarchyNodes = [];

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

  async function loadResults() {
    const collectionId = document.getElementById('collectionFilter').value;
    const qs = collectionId ? ('?collection_id=' + collectionId) : '';
    results = await ahpApi('/api/projects/' + projectId + '/results' + qs);

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

    const proj = await ahpApi('/api/projects/' + projectId);
    document.getElementById('statAgg').textContent = proj.settings.aggregation;
  }

  async function loadCollectionsFilter() {
    const collections = await ahpApi('/api/projects/' + projectId + '/collections');
    const sel = document.getElementById('collectionFilter');
    collections.forEach(function (c) {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.label + ' (' + c.mode + ')';
      sel.appendChild(opt);
    });
  }

  async function loadSensNodeOptions() {
    const h = await ahpApi('/api/projects/' + projectId + '/hierarchy');
    hierarchyNodes = h.nodes;
    const sel = document.getElementById('sensNode');
    sel.innerHTML = hierarchyNodes
      .filter(function (n) { return n.parent_id !== null; })
      .map(function (n) { return '<option value="' + n.uuid + '">' + '　'.repeat(n.level - 1) + ahpEsc(n.name) + '</option>'; })
      .join('');
  }

  async function runSensitivity() {
    const target = document.getElementById('sensNode').value;
    const delta = Number(document.getElementById('sensDelta').value);
    const collectionId = document.getElementById('collectionFilter').value;
    const qs = new URLSearchParams({ target_node: target, delta_pct: delta });
    if (collectionId) qs.set('collection_id', collectionId);
    try {
      const res = await ahpApi('/api/projects/' + projectId + '/results/sensitivity?' + qs.toString());
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

    document.getElementById('collectionFilter').addEventListener('change', loadResults);
    document.getElementById('sensRunBtn').addEventListener('click', runSensitivity);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
