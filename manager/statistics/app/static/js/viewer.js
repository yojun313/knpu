(function () {
  'use strict';

  function parseProjectId() {
    var m = location.pathname.match(/^\/viewer\/([^\/]+)\/?$/);
    return m ? decodeURIComponent(m[1]) : null;
  }
  var projectId = parseProjectId();
  var LAST_PROJECT_KEY = 'sv_last_project'; // 마지막으로 열었던 프로젝트 — 사이트를 새로 열 때 자동 선택

  var currentMeta = null;
  var base = null;              // /api/projects/{id}/base 응답: metadata,description,tables,graphs
  var searchQuery = '';
  var chartsById = {};          // table.id -> Chart.js 인스턴스(프로젝트 전환 시 정리, PNG 내보내기에 재사용)
  var heatmapTables = {};       // table.id -> table (히트맵은 Chart.js가 아니라 캔버스에 직접 그려서 별도 보관)
  var exportTargetId = null;    // PNG 내보내기 모달이 현재 대상으로 하는 table.id

  // ---------------------------------------------------------------
  // 공통 유틸
  // ---------------------------------------------------------------
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }

  function api(path) {
    return fetch(path).then(function (res) {
      if (!res.ok) return res.json().then(function (b) { throw new Error(b.detail || res.statusText); });
      return res.json();
    });
  }

  function railApi(path, opts) {
    return fetch(path, opts).then(function (res) {
      if (res.status === 401) { location.href = '/login'; return Promise.reject(new Error('unauthorized')); }
      return res.json().then(function (b) {
        if (!res.ok) throw new Error(b.detail || res.statusText);
        return b;
      });
    });
  }

  function postJson(path, obj) {
    return railApi(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(obj),
    });
  }

  // fetch()는 업로드 진행률을 알려주지 않으므로, 진행률 표시가 필요한 업로드는 XHR로 보낸다.
  function uploadWithProgress(path, formData, onProgress) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', path);
      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable && onProgress) onProgress(Math.round(e.loaded / e.total * 100));
      };
      xhr.onload = function () {
        if (xhr.status === 401) { location.href = '/login'; return; }
        var body = {};
        try { body = JSON.parse(xhr.responseText); } catch (e) { /* noop */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body);
        else reject(new Error(body.detail || xhr.statusText || ('HTTP ' + xhr.status)));
      };
      xhr.onerror = function () { reject(new Error('네트워크 오류로 업로드에 실패했습니다.')); };
      xhr.send(formData);
    });
  }

  function toast(msg) {
    var t = document.getElementById('__toast');
    if (!t) {
      t = document.createElement('div'); t.id = '__toast';
      t.style.cssText = 'position:fixed;bottom:24px;left:calc(50% - 168px);transform:translateX(-50%);background:rgba(27,38,52,.96);color:#fff;padding:10px 18px;border-radius:10px;font-size:13px;z-index:99;box-shadow:0 6px 20px rgba(0,0,0,.35);transition:opacity .3s;pointer-events:none;opacity:0';
      document.body.appendChild(t);
    }
    t.innerText = msg; t.style.opacity = '1';
    clearTimeout(t.__tm); t.__tm = setTimeout(function () { t.style.opacity = '0'; }, 1500);
  }

  function fmtDate(iso) {
    try {
      var d = new Date(iso);
      return d.getFullYear() + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + String(d.getDate()).padStart(2, '0')
        + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    } catch (e) { return iso; }
  }

  function fmtCell(v) {
    if (v == null) return '';
    if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3).replace(/\.?0+$/, '');
    return String(v);
  }

  // ---------------------------------------------------------------
  // 대시보드(표 + 차트) 렌더링
  // ---------------------------------------------------------------
  function destroyCharts() {
    Object.keys(chartsById).forEach(function (id) {
      try { chartsById[id].destroy(); } catch (e) { }
    });
    chartsById = {};
    heatmapTables = {};
  }

  function cssVar(name) { return getComputedStyle(document.body).getPropertyValue(name).trim(); }

  function hexToRgb(hex) {
    var m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
    return m ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) } : { r: 44, g: 127, b: 184 };
  }

  // 요일×시간대(또는 상관행렬) 히트맵을 캔버스에 직접 그린다. 온스크린 렌더와 PNG
  // 내보내기(임의 배율)에서 같은 함수를 재사용한다.
  function drawHeatmap(canvas, table, opts) {
    opts = opts || {};
    var scale = opts.scale || (window.devicePixelRatio || 1);
    var background = opts.background || 'theme';
    var cssWidth = opts.width || canvas.clientWidth || 600;
    var cssHeight = opts.height || canvas.clientHeight || 220;

    var rowLabels = table.rows.map(function (r) { return fmtCell(r[0]); });
    var colLabels = table.columns.slice(1);
    var values = table.rows.map(function (r) {
      return r.slice(1).map(function (v) { return typeof v === 'number' ? v : 0; });
    });
    var maxVal = 1;
    values.forEach(function (row) { row.forEach(function (v) { if (v > maxVal) maxVal = v; }); });

    var labelW = Math.min(70, cssWidth * 0.14);
    var headerH = 20;
    var cellW = (cssWidth - labelW) / Math.max(1, colLabels.length);
    var cellH = (cssHeight - headerH) / Math.max(1, rowLabels.length);

    canvas.width = Math.round(cssWidth * scale);
    canvas.height = Math.round(cssHeight * scale);
    canvas.style.width = cssWidth + 'px';
    canvas.style.height = cssHeight + 'px';
    var ctx = canvas.getContext('2d');
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    if (background !== 'transparent') {
      ctx.fillStyle = background === 'white' ? '#ffffff' : cssVar('--sidebar-bg');
      ctx.fillRect(0, 0, cssWidth, cssHeight);
    }

    var accent = hexToRgb(cssVar('--series-1'));
    var textColor = background === 'white' ? '#33414f' : cssVar('--sidebar-text');
    var mutedColor = background === 'white' ? '#7c8896' : cssVar('--sidebar-muted');

    // 열 머리글(시간대 등) — 너무 많으면 겹치지 않도록 일부만 표시
    ctx.fillStyle = mutedColor;
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    var labelStep = cellW < 22 ? Math.ceil(22 / cellW) : 1;
    colLabels.forEach(function (label, ci) {
      if (ci % labelStep !== 0) return;
      ctx.fillText(label, labelW + ci * cellW + cellW / 2, headerH / 2);
    });

    rowLabels.forEach(function (rowLabel, ri) {
      ctx.fillStyle = textColor;
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(rowLabel, labelW - 6, headerH + ri * cellH + cellH / 2);

      values[ri].forEach(function (v, ci) {
        var t = maxVal > 0 ? v / maxVal : 0;
        var x = labelW + ci * cellW, y = headerH + ri * cellH;
        ctx.fillStyle = 'rgba(' + accent.r + ',' + accent.g + ',' + accent.b + ',' + (0.08 + t * 0.85) + ')';
        ctx.fillRect(x + 1, y + 1, Math.max(0, cellW - 2), Math.max(0, cellH - 2));
        if (cellW > 26 && cellH > 16) {
          ctx.fillStyle = t > 0.55 ? '#ffffff' : textColor;
          ctx.font = Math.max(8, Math.round(cellH * 0.32)) + 'px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(String(v), x + cellW / 2, y + cellH / 2);
        }
      });
    });
  }

  // 표 컬럼 구성을 보고 라인/막대 차트로 그릴만한 표인지 판단한다.
  // - Date가 포함된 열이 있으면 라인 차트(시계열)
  // - 문자열 카테고리 열(고유값 <= 40) + 숫자 열이 있으면 막대 차트
  // - 그 외(기초통계 describe, 상관행렬처럼 넓은 요약표)는 표만 표시
  function planChart(table) {
    if (table.id === 'basic_stats' || table.id.indexOf('corr') !== -1) return null;
    var cols = table.columns, rows = table.rows;
    if (!rows.length) return null;

    function isNumericCol(i) {
      return rows.every(function (r) { return r[i] == null || typeof r[i] === 'number'; })
        && rows.some(function (r) { return typeof r[i] === 'number'; });
    }

    var dateIdx = cols.findIndex(function (c) { return /date/i.test(c); });
    var mode, labelIdx;
    if (dateIdx !== -1 && !isNumericCol(dateIdx)) {
      mode = 'line'; labelIdx = dateIdx;
    } else {
      labelIdx = cols.findIndex(function (c, i) { return !isNumericCol(i); });
      if (labelIdx === -1) {
        // 모든 열이 숫자인 경우(예: "시간대(0~23시)별 집계"처럼 카테고리 자체가
        // 숫자인 표) — 첫 열이 행 수만큼 서로 다른 값을 가지는 소규모 카테고리처럼
        // 보이면 그 열을 x축으로 사용한다.
        var firstColUnique = {};
        rows.forEach(function (r) { firstColUnique[r[0]] = true; });
        var firstUniqueCount = Object.keys(firstColUnique).length;
        if (firstUniqueCount === rows.length && firstUniqueCount <= 40) {
          labelIdx = 0;
        } else {
          return null;
        }
      }
      mode = 'bar';
      if (rows.length > 50) return null; // 카테고리가 너무 많으면 막대 대신 표만
    }

    var numericIdxs = [];
    cols.forEach(function (c, i) { if (i !== labelIdx && isNumericCol(i)) numericIdxs.push(i); });
    if (!numericIdxs.length) return null;
    numericIdxs = numericIdxs.slice(0, 3);

    return { mode: mode, labelIdx: labelIdx, numericIdxs: numericIdxs };
  }

  function buildChart(canvas, table, plan) {
    var seriesColors = [cssVar('--series-1'), cssVar('--series-2'), cssVar('--series-3')];
    var labels = table.rows.map(function (r) { return fmtCell(r[plan.labelIdx]); });
    var datasets = plan.numericIdxs.map(function (idx, si) {
      var color = seriesColors[si % seriesColors.length];
      return {
        label: table.columns[idx],
        data: table.rows.map(function (r) { return r[idx]; }),
        borderColor: color,
        backgroundColor: plan.mode === 'line' ? color : color + 'cc',
        borderWidth: plan.mode === 'line' ? 2 : 0,
        borderRadius: plan.mode === 'bar' ? 4 : 0,
        pointRadius: plan.mode === 'line' ? (labels.length > 60 ? 0 : 2) : 0,
        tension: 0.25,
        fill: false,
      };
    });

    return new Chart(canvas, {
      type: plan.mode,
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: datasets.length > 1, labels: { color: cssVar('--sidebar-text'), boxWidth: 12, font: { size: 11 } } },
          tooltip: { mode: 'index', intersect: false },
        },
        scales: {
          x: { ticks: { color: cssVar('--sidebar-muted'), font: { size: 10 }, maxRotation: 45, autoSkipPadding: 12 }, grid: { display: false } },
          y: { ticks: { color: cssVar('--sidebar-muted'), font: { size: 10 } }, grid: { color: cssVar('--sidebar-panel2') } },
        },
      },
    });
  }

  function buildTableCard(table) {
    var card = document.createElement('div');
    card.className = 'table-card';
    card.setAttribute('data-search', (table.title + ' ' + table.columns.join(' ')).toLowerCase());

    var head = document.createElement('div');
    head.className = 'tc-head';
    head.innerHTML = '<span class="tc-head-main"><span class="tc-title">' + esc(table.title) + '</span>'
      + '<span class="tc-meta">' + table.row_count + '행 · ' + table.columns.length + '열</span></span>';
    card.appendChild(head);

    function addExportButton() {
      var actions = document.createElement('span');
      actions.className = 'tc-head-actions';
      var pngBtn = document.createElement('button');
      pngBtn.className = 'tc-png-btn';
      pngBtn.title = 'PNG로 저장';
      pngBtn.innerHTML = '&#8681;';
      pngBtn.addEventListener('click', function () { openExportModal(table.id, table.title); });
      actions.appendChild(pngBtn);
      head.appendChild(actions);
    }

    if (table.is_heatmap) {
      var heatmapWrap = document.createElement('div');
      heatmapWrap.className = 'tc-chart';
      var heatmapCanvas = document.createElement('canvas');
      heatmapWrap.appendChild(heatmapCanvas);
      card.appendChild(heatmapWrap);
      heatmapTables[table.id] = table;
      drawHeatmap(heatmapCanvas, table);
      addExportButton();
    } else {
      var plan = planChart(table);
      if (plan) {
        var chartWrap = document.createElement('div');
        chartWrap.className = 'tc-chart';
        var canvas = document.createElement('canvas');
        chartWrap.appendChild(canvas);
        card.appendChild(chartWrap);
        chartsById[table.id] = buildChart(canvas, table, plan);
        addExportButton();
      }
    }

    if (table.description) {
      var desc = document.createElement('div');
      desc.className = 'tc-desc';
      desc.textContent = table.description;
      card.appendChild(desc);
    }

    var tableWrap = document.createElement('div');
    tableWrap.className = 'tc-table-wrap';
    var html = '<table class="tc-table"><thead><tr>';
    table.columns.forEach(function (c) { html += '<th>' + esc(c) + '</th>'; });
    html += '</tr></thead><tbody>';
    table.rows.forEach(function (r) {
      html += '<tr>' + r.map(function (v) { return '<td>' + esc(fmtCell(v)) + '</td>'; }).join('') + '</tr>';
    });
    html += '</tbody></table>';
    tableWrap.innerHTML = html;
    card.appendChild(tableWrap);

    if (table.truncated) {
      var trunc = document.createElement('div');
      trunc.className = 'tc-truncated';
      trunc.textContent = '표가 너무 커서 처음 ' + table.row_count + '행만 표시합니다. 전체 데이터는 원본 zip 다운로드에서 확인하세요.';
      card.appendChild(trunc);
    }

    return card;
  }

  function applyTableSearch() {
    var q = searchQuery;
    document.querySelectorAll('.table-card').forEach(function (card) {
      var match = !q || card.getAttribute('data-search').indexOf(q) !== -1;
      card.classList.toggle('hidden-by-search', !match);
    });
    document.querySelectorAll('.section-title').forEach(function (h) {
      var el = h.nextElementSibling, anyVisible = false;
      while (el && !el.classList.contains('section-title')) {
        if (!el.classList.contains('hidden-by-search')) anyVisible = true;
        el = el.nextElementSibling;
      }
      h.classList.toggle('hidden-by-search', !anyVisible);
    });
  }

  // ---------------------------------------------------------------
  // 차트 PNG 내보내기 (배율/배경/범례·제목 표시 옵션)
  // ---------------------------------------------------------------
  function openExportModal(tableId, title) {
    exportTargetId = tableId;
    document.getElementById('exportTargetTitle').textContent = title;
    document.getElementById('exportModal').hidden = false;
  }
  function closeExportModal() {
    document.getElementById('exportModal').hidden = true;
    exportTargetId = null;
  }

  function selectedOptionValue(rowId) {
    var active = document.querySelector('#' + rowId + ' .option-btn.active');
    return active ? active.getAttribute('data-value') : null;
  }

  // src 캔버스(이미 background/scale까지 반영해 그려진 상태) 위에 제목 캡션을 붙이고
  // 다운로드 URL을 만든다. 차트/히트맵 내보내기가 공통으로 사용한다.
  function compositeWithTitle(src, scale, background, showTitleCaption, titleText) {
    var titleH = showTitleCaption ? Math.round(28 * scale) : 0;
    var out = document.createElement('canvas');
    out.width = src.width;
    out.height = src.height + titleH;
    var ctx = out.getContext('2d');

    if (titleH && background !== 'transparent') {
      ctx.fillStyle = background === 'white' ? '#ffffff' : cssVar('--sidebar-bg');
      ctx.fillRect(0, 0, out.width, titleH);
    }
    if (showTitleCaption) {
      ctx.fillStyle = background === 'white' ? '#111111' : cssVar('--text-strong');
      ctx.font = 'bold ' + Math.round(14 * scale) + 'px sans-serif';
      ctx.textBaseline = 'middle';
      ctx.fillText(titleText, Math.round(12 * scale), titleH / 2);
    }
    ctx.drawImage(src, 0, titleH);
    return out.toDataURL('image/png');
  }

  function triggerDownload(url, filename) {
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function downloadChartPng() {
    var scale = parseInt(selectedOptionValue('exportScaleRow'), 10) || 2;
    var background = selectedOptionValue('exportBgRow') || 'theme';
    var showLegend = document.getElementById('exportShowLegend').checked;
    var showTitleCaption = document.getElementById('exportShowTitle').checked;
    var titleText = document.getElementById('exportTargetTitle').textContent;

    var heatmapTable = heatmapTables[exportTargetId];
    if (heatmapTable) {
      // 히트맵은 Chart.js 인스턴스가 없으므로, 요청한 배율/배경으로 다시 한번 그려서
      // 그 결과를 그대로 내보낸다("범례 표시" 옵션은 히트맵에는 해당하지 않는다).
      var hCanvas = document.createElement('canvas');
      drawHeatmap(hCanvas, heatmapTable, { scale: scale, background: background, width: 640, height: 260 });
      var hUrl = compositeWithTitle(hCanvas, scale, background, showTitleCaption, titleText);
      triggerDownload(hUrl, exportTargetId + '.png');
      closeExportModal();
      return;
    }

    var chart = chartsById[exportTargetId];
    if (!chart) { closeExportModal(); return; }

    // Chart.js는 devicePixelRatio를 기준으로 캔버스 실제 픽셀 수를 정하므로, 배율을 이
    // 값에 반영해 resize하면 별도 캔버스 없이 고해상도로 다시 그려진다.
    var originalRatio = chart.options.devicePixelRatio;
    var originalLegendDisplay = chart.options.plugins.legend.display;
    chart.options.devicePixelRatio = scale;
    chart.options.plugins.legend.display = showLegend && chart.data.datasets.length > 1;
    chart.resize();
    chart.update('none');

    var url = compositeWithTitle(chart.canvas, scale, background, showTitleCaption, titleText);

    // 원상복구
    chart.options.devicePixelRatio = originalRatio;
    chart.options.plugins.legend.display = originalLegendDisplay;
    chart.resize();
    chart.update('none');

    triggerDownload(url, exportTargetId + '.png');
    closeExportModal();
  }

  var SECTION_ORDER = [
    '핵심 지표', '기술통계', '빈도분석', '교차분석 (카이제곱)', '평균 비교 (t-검정/분산분석)',
    '상관분석', '회귀분석', '요인분석 (PCA)', '신뢰도분석', '군집분석', '고급 통계',
  ];

  function renderDashboard() {
    var meta = base.metadata || {};
    document.getElementById('dashSource').textContent = meta.source_filename || currentMeta.name || '-';
    document.getElementById('dashPlatform').textContent = meta.platform || currentMeta.platform || '-';
    document.getElementById('dashCategory').textContent = meta.category || currentMeta.category || '-';
    document.getElementById('dashGenerated').textContent = meta.generated_at ? fmtDate(meta.generated_at) : '';
    document.getElementById('dashRows').textContent = meta.row_count != null ? ('원본 ' + meta.row_count + '행') : '';

    destroyCharts();
    var grid = document.getElementById('tableGrid');
    grid.innerHTML = '';

    var tables = base.tables || [];
    var bySection = {};
    tables.forEach(function (table) {
      var sec = table.section || '핵심 지표';
      (bySection[sec] = bySection[sec] || []).push(table);
    });
    var sections = Object.keys(bySection).sort(function (a, b) {
      var ia = SECTION_ORDER.indexOf(a); if (ia === -1) ia = SECTION_ORDER.length;
      var ib = SECTION_ORDER.indexOf(b); if (ib === -1) ib = SECTION_ORDER.length;
      return ia - ib;
    });
    sections.forEach(function (sec) {
      if (sections.length > 1) {
        var h = document.createElement('div');
        h.className = 'section-title';
        h.textContent = sec;
        grid.appendChild(h);
      }
      bySection[sec].forEach(function (table) { grid.appendChild(buildTableCard(table)); });
    });
    applyTableSearch();
  }

  // ---------------------------------------------------------------
  // 프로젝트 로드
  // ---------------------------------------------------------------
  function resetViewState() {
    searchQuery = '';
    document.getElementById('search').value = '';
  }

  function loadProject(id) {
    document.getElementById('loading').classList.remove('hide');
    return Promise.all([
      api('/api/projects/' + id + '/meta'),
      api('/api/projects/' + id + '/base'),
    ]).then(function (res) {
      currentMeta = res[0];
      base = res[1];

      document.getElementById('projectName').textContent = currentMeta.name || 'Statistics Analyzer';
      document.title = (currentMeta.name || 'Statistics Analyzer') + ' · Statistics Analyzer';
      document.getElementById('emptyProject').hidden = true;
      document.getElementById('dashboard').hidden = false;
      highlightActiveRailItem();
      localStorage.setItem(LAST_PROJECT_KEY, id);
      resetViewState();
      renderDashboard();
      document.getElementById('loading').classList.add('hide');
    }).catch(function (err) {
      document.getElementById('loading').innerHTML =
        '<div style="color:#e08a52;font-weight:700">불러오기 실패</div><div>' + esc(err.message) + '</div>';
    });
  }

  function showProjectProperties(p) {
    document.getElementById('propsTitle').textContent = p.name + ' · 속성';
    var html = '';
    html += '<div class="stat"><span>이름</span><span>' + esc(p.name) + '</span></div>';
    html += '<div class="stat"><span>생성일</span><span>' + esc(fmtDate(p.created_at)) + '</span></div>';
    if (p.updated_at && p.updated_at !== p.created_at) {
      html += '<div class="stat"><span>수정일</span><span>' + esc(fmtDate(p.updated_at)) + '</span></div>';
    }
    if (p.platform) html += '<div class="stat"><span>플랫폼</span><span>' + esc(p.platform) + '</span></div>';
    if (p.category) html += '<div class="stat"><span>분석 종류</span><span>' + esc(p.category) + '</span></div>';
    var s = p.summary || {};
    if (s.table_count != null) html += '<div class="stat"><span>표 개수</span><span>' + s.table_count + '</span></div>';
    if (s.row_count != null) html += '<div class="stat"><span>원본 행 수</span><span>' + s.row_count + '</span></div>';
    document.getElementById('propsBody').innerHTML = html;
    closeMobileDrawers();
    document.getElementById('propsModal').hidden = false;
  }

  // ---------------------------------------------------------------
  // 왼쪽 프로젝트 레일
  // ---------------------------------------------------------------
  var railProjects = [];
  var PALETTE_LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
  var PALETTE_DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'];
  function railDotColor(i) {
    var pal = document.body.classList.contains('dark-theme') ? PALETTE_DARK : PALETTE_LIGHT;
    return pal[((i % pal.length) + pal.length) % pal.length];
  }
  function railInitial(name) { return (name || '?').trim().charAt(0).toUpperCase(); }

  var ADMIN_ALL_KEY = 'sv_admin_all_projects';
  var isAdmin = false;

  function loadMe() {
    return railApi('/api/me').then(function (me) {
      document.getElementById('railUserName').textContent = me.name || '';
      document.getElementById('railUserName').title = me.name || '';
      isAdmin = me.role === 'admin';
      var toggleEl = document.getElementById('railAdminAllToggle');
      var chk = document.getElementById('railAdminAllChk');
      toggleEl.hidden = !isAdmin;
      if (isAdmin) {
        chk.checked = localStorage.getItem(ADMIN_ALL_KEY) === '1';
        chk.addEventListener('change', function () {
          localStorage.setItem(ADMIN_ALL_KEY, chk.checked ? '1' : '0');
          loadRailProjects();
        });
      }
    }).catch(function () { });
  }

  var railFolders = [];
  var COLLAPSED_FOLDERS_KEY = 'sv_collapsed_folders';
  var collapsedFolders = (function () {
    try { return new Set(JSON.parse(localStorage.getItem(COLLAPSED_FOLDERS_KEY) || '[]')); }
    catch (e) { return new Set(); }
  })();
  var expandedAdminUsers = new Set(); // 관리자 "모든 사용자 보기" 그룹 펼침 상태 — 새로고침 전까지만 유지

  function isAdminAllMode() { return isAdmin && localStorage.getItem(ADMIN_ALL_KEY) === '1'; }

  function loadRailProjects() {
    var showAll = isAdminAllMode();
    var qs = showAll ? '?all=true' : '';
    return Promise.all([
      railApi('/api/projects' + qs),
      railApi('/api/folders' + qs).catch(function () { return { folders: [] }; }),
    ]).then(function (results) {
      railProjects = results[0].projects || [];
      railFolders = results[1].folders || [];
      renderRail();
    }).catch(function (err) {
      if (err.message !== 'unauthorized') toast('프로젝트 목록을 불러오지 못했습니다.');
    });
  }

  var railColorCounter = 0;

  function buildProjectItem(p, interactive) {
    var idx = railColorCounter++;
    var item = document.createElement('div');
    item.className = 'rail-item' + (p.project_id === projectId ? ' active' : '');
    item.setAttribute('data-id', p.project_id);
    item.title = p.name;
    var meta = [p.owner_name, p.platform, p.category].filter(Boolean).join(' · ');
    var actionsHtml = !interactive ? '' :
      '<span class="ri-actions">'
      + '<button class="ri-btn" data-act="props" title="속성">ℹ</button>'
      + '<button class="ri-btn" data-act="move" title="폴더로 이동">📁</button>'
      + '<button class="ri-btn" data-act="rename" title="이름 변경">✎</button>'
      + '<button class="ri-btn danger" data-act="delete" title="삭제">🗑</button>'
      + '</span>';
    item.innerHTML =
      '<span class="ri-dot" style="background:' + railDotColor(idx) + '">' + esc(railInitial(p.name)) + '</span>'
      + '<span class="ri-main"><span class="ri-name">' + esc(p.name) + '</span>'
      + '<span class="ri-meta">' + esc(meta) + '</span></span>'
      + actionsHtml;
    item.addEventListener('click', function (e) {
      if (e.target.closest('[data-act]')) return;
      switchProject(p.project_id);
      closeMobileDrawers();
    });

    if (interactive) {
      item.addEventListener('contextmenu', function (e) {
        e.preventDefault(); e.stopPropagation();
        openRailCtxMenu(e.clientX, e.clientY, p, item);
      });
      item.querySelector('[data-act="props"]').addEventListener('click', function (e) { e.stopPropagation(); showProjectProperties(p); });
      item.querySelector('[data-act="move"]').addEventListener('click', function (e) { e.stopPropagation(); openMoveFolderMenu(e.clientX, e.clientY, p); });
      item.querySelector('[data-act="rename"]').addEventListener('click', function (e) { e.stopPropagation(); startRailRename(item, p); });
      item.querySelector('[data-act="delete"]').addEventListener('click', function (e) { e.stopPropagation(); deleteRailProject(p); });

      item.draggable = true;
      item.addEventListener('dragstart', function (e) {
        e.stopPropagation();
        e.dataTransfer.setData('text/plain', p.project_id);
        e.dataTransfer.effectAllowed = 'move';
        item.classList.add('dragging');
      });
      item.addEventListener('dragend', function () { item.classList.remove('dragging'); });
    }
    return item;
  }

  function buildFolderGroup(f, projects, interactive) {
    var group = document.createElement('div');
    group.className = 'folder-group' + (collapsedFolders.has(f.folder_id) ? ' collapsed' : '');
    group.setAttribute('data-folder-id', f.folder_id);

    var header = document.createElement('div');
    header.className = 'folder-header';
    header.innerHTML =
      '<span class="fh-chevron">▸</span>'
      + '<span class="fh-icon">📁</span>'
      + '<span class="fh-name">' + esc(f.name) + '</span>'
      + '<span class="fh-count">' + projects.length + '</span>'
      + (!interactive ? '' :
        '<span class="fh-actions">'
        + '<button class="ri-btn" data-act="folder-rename" title="이름 변경">✎</button>'
        + '<button class="ri-btn danger" data-act="folder-delete" title="삭제">🗑</button>'
        + '</span>');
    header.addEventListener('click', function (e) {
      if (e.target.closest('[data-act]')) return;
      group.classList.toggle('collapsed');
      if (group.classList.contains('collapsed')) collapsedFolders.add(f.folder_id);
      else collapsedFolders.delete(f.folder_id);
      localStorage.setItem(COLLAPSED_FOLDERS_KEY, JSON.stringify(Array.from(collapsedFolders)));
    });

    var body = document.createElement('div');
    body.className = 'folder-body';
    projects.forEach(function (p) { body.appendChild(buildProjectItem(p, interactive)); });

    if (interactive) {
      header.querySelector('[data-act="folder-rename"]').addEventListener('click', function (e) { e.stopPropagation(); startFolderRename(group, f); });
      header.querySelector('[data-act="folder-delete"]').addEventListener('click', function (e) { e.stopPropagation(); deleteFolder(f); });

      [header, body].forEach(function (el) {
        el.addEventListener('dragover', function (e) {
          e.preventDefault(); e.stopPropagation();
          e.dataTransfer.dropEffect = 'move';
          header.classList.add('drag-over');
        });
        el.addEventListener('dragleave', function (e) { e.stopPropagation(); header.classList.remove('drag-over'); });
        el.addEventListener('drop', function (e) {
          e.preventDefault(); e.stopPropagation();
          header.classList.remove('drag-over');
          var pid = e.dataTransfer.getData('text/plain');
          if (pid) moveProjectToFolder(pid, f.folder_id);
        });
      });
    }

    group.appendChild(header);
    group.appendChild(body);
    return group;
  }

  // projects/folders를 폴더별로 묶어 container에 렌더링한다. interactive=false면
  // 관리자 "모든 사용자 보기"에서 다른 사용자 그룹을 읽기 전용(드래그·컨텍스트메뉴 없음)으로 보여줄 때 쓴다.
  function renderProjectTree(container, projects, folders, interactive) {
    var byFolder = {};
    folders.forEach(function (f) { byFolder[f.folder_id] = []; });
    var unfiled = [];
    projects.forEach(function (p) {
      if (p.folder_id && byFolder[p.folder_id]) byFolder[p.folder_id].push(p);
      else unfiled.push(p);
    });
    folders.forEach(function (f) {
      container.appendChild(buildFolderGroup(f, byFolder[f.folder_id], interactive));
    });
    unfiled.forEach(function (p) { container.appendChild(buildProjectItem(p, interactive)); });
  }

  function renderAdminGroupedRail(container) {
    var groups = {}; // owner_uid -> { name, projects: [] }
    railProjects.forEach(function (p) {
      var uid = p.owner_uid;
      if (!groups[uid]) groups[uid] = { name: p.owner_name || uid, projects: [] };
      groups[uid].projects.push(p);
    });
    var foldersByOwner = {};
    railFolders.forEach(function (f) {
      (foldersByOwner[f.owner_uid] = foldersByOwner[f.owner_uid] || []).push(f);
    });

    var uids = Object.keys(groups).sort(function (a, b) {
      return groups[a].name.localeCompare(groups[b].name, 'ko');
    });
    uids.forEach(function (uid) {
      var g = groups[uid];
      var userGroup = document.createElement('div');
      userGroup.className = 'user-group' + (expandedAdminUsers.has(uid) ? '' : ' collapsed');

      var header = document.createElement('div');
      header.className = 'user-header';
      header.innerHTML =
        '<span class="fh-chevron">▸</span>'
        + '<span class="uh-avatar">' + esc(railInitial(g.name)) + '</span>'
        + '<span class="uh-name">' + esc(g.name) + '</span>'
        + '<span class="fh-count">' + g.projects.length + '</span>';
      header.addEventListener('click', function () {
        userGroup.classList.toggle('collapsed');
        if (userGroup.classList.contains('collapsed')) expandedAdminUsers.delete(uid);
        else expandedAdminUsers.add(uid);
      });

      var body = document.createElement('div');
      body.className = 'user-body';
      renderProjectTree(body, g.projects, foldersByOwner[uid] || [], false);

      userGroup.appendChild(header);
      userGroup.appendChild(body);
      container.appendChild(userGroup);
    });
  }

  function renderRail() {
    var listEl = document.getElementById('railList');
    var emptyEl = document.getElementById('railEmpty');
    listEl.innerHTML = '';
    emptyEl.hidden = railProjects.length > 0;
    railColorCounter = 0;

    if (isAdminAllMode()) {
      renderAdminGroupedRail(listEl);
    } else {
      renderProjectTree(listEl, railProjects, railFolders, true);
    }
  }

  function highlightActiveRailItem() {
    document.querySelectorAll('.rail-item').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-id') === projectId);
    });
  }

  function startRailRename(item, p) {
    var nameEl = item.querySelector('.ri-name');
    var input = document.createElement('input');
    input.className = 'ri-name-input';
    input.value = p.name;
    nameEl.replaceWith(input);
    input.focus(); input.select();

    function commit() {
      var newName = input.value.trim();
      if (!newName || newName === p.name) { renderRail(); return; }
      railApi('/api/projects/' + p.project_id, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newName })
      }).then(function () {
        loadRailProjects();
        if (p.project_id === projectId) {
          document.getElementById('projectName').textContent = newName;
          document.title = newName + ' · Statistics Analyzer';
        }
      }).catch(function () { toast('이름 변경에 실패했습니다.'); renderRail(); });
    }
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') input.blur();
      if (e.key === 'Escape') { input.value = p.name; input.blur(); }
    });
    input.addEventListener('click', function (e) { e.stopPropagation(); });
  }

  function deleteRailProject(p) {
    if (!confirm('"' + p.name + '" 프로젝트를 삭제할까요? 되돌릴 수 없습니다.')) return;
    railApi('/api/projects/' + p.project_id, { method: 'DELETE' }).then(function () {
      var wasCurrent = p.project_id === projectId;
      if (wasCurrent) localStorage.removeItem(LAST_PROJECT_KEY);
      loadRailProjects().then(function () {
        if (wasCurrent) {
          projectId = null;
          base = null;
          destroyCharts();
          history.pushState(null, '', '/viewer');
          document.getElementById('projectName').textContent = 'Statistics Analyzer';
          document.title = 'Statistics Analyzer';
          document.getElementById('dashboard').hidden = true;
          document.getElementById('emptyProject').hidden = false;
        }
      });
    }).catch(function () { toast('삭제에 실패했습니다.'); });
  }

  // ---------------------------------------------------------------
  // 폴더
  // ---------------------------------------------------------------
  function createFolder() {
    var name = prompt('새 폴더 이름을 입력하세요');
    if (name === null) return;
    name = name.trim();
    if (!name) return;
    postJson('/api/folders', { name: name }).then(function () {
      loadRailProjects();
    }).catch(function () { toast('폴더 생성에 실패했습니다.'); });
  }

  function startFolderRename(group, f) {
    var nameEl = group.querySelector('.fh-name');
    var input = document.createElement('input');
    input.className = 'ri-name-input';
    input.value = f.name;
    nameEl.replaceWith(input);
    input.focus(); input.select();

    function commit() {
      var newName = input.value.trim();
      if (!newName || newName === f.name) { renderRail(); return; }
      railApi('/api/folders/' + f.folder_id, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newName })
      }).then(function () {
        loadRailProjects();
      }).catch(function () { toast('이름 변경에 실패했습니다.'); renderRail(); });
    }
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') input.blur();
      if (e.key === 'Escape') { input.value = f.name; input.blur(); }
    });
    input.addEventListener('click', function (e) { e.stopPropagation(); });
  }

  function deleteFolder(f) {
    if (!confirm('"' + f.name + '" 폴더를 삭제할까요?\n안에 있던 프로젝트는 삭제되지 않고 미분류로 이동합니다.')) return;
    railApi('/api/folders/' + f.folder_id, { method: 'DELETE' }).then(function () {
      collapsedFolders.delete(f.folder_id);
      loadRailProjects();
    }).catch(function () { toast('폴더 삭제에 실패했습니다.'); });
  }

  function moveProjectToFolder(projectIdToMove, folderId) {
    railApi('/api/projects/' + projectIdToMove + '/folder', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ folder_id: folderId || null })
    }).then(function () {
      loadRailProjects();
    }).catch(function () { toast('폴더 이동에 실패했습니다.'); });
  }

  function closeMoveFolderMenu() { document.getElementById('moveFolderMenu').hidden = true; }

  function openMoveFolderMenu(x, y, p) {
    var menu = document.getElementById('moveFolderMenu');
    var html = '<button class="ctx-item" data-folder="">📄 미분류</button>';
    if (railFolders.length) {
      html += '<div class="ctx-sep"></div>';
      html += railFolders.map(function (f) {
        return '<button class="ctx-item" data-folder="' + esc(f.folder_id) + '">📁 ' + esc(f.name) + '</button>';
      }).join('');
    }
    menu.innerHTML = html;
    menu.hidden = false; menu.style.left = '-9999px'; menu.style.top = '-9999px';
    var pad = 8, mw = menu.offsetWidth, mh = menu.offsetHeight;
    var left = Math.max(pad, Math.min(x, window.innerWidth - mw - pad));
    var top = Math.max(pad, Math.min(y, window.innerHeight - mh - pad));
    menu.style.left = left + 'px'; menu.style.top = top + 'px';

    menu.querySelectorAll('[data-folder]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        closeMoveFolderMenu();
        moveProjectToFolder(p.project_id, btn.getAttribute('data-folder') || null);
      });
    });
  }

  function switchProject(id, replace) {
    if (!id || id === projectId) return;
    projectId = id;
    if (replace) history.replaceState(null, '', '/viewer/' + encodeURIComponent(id));
    else history.pushState(null, '', '/viewer/' + encodeURIComponent(id));
    highlightActiveRailItem();
    loadProject(id);
  }

  // ---------------------------------------------------------------
  // 업로드 모달 : zip 업로드 / 원본 CSV 새 분석
  // ---------------------------------------------------------------
  function setModalStatus(msg, cls) {
    var el = document.getElementById('modalStatus');
    el.textContent = msg || '';
    el.className = 'modal-status' + (cls ? ' ' + cls : '');
  }

  function switchModalTab(tab) {
    document.getElementById('tabBtnZip').classList.toggle('active', tab === 'zip');
    document.getElementById('tabBtnAnalyze').classList.toggle('active', tab === 'analyze');
    document.getElementById('tabBtnCrawl').classList.toggle('active', tab === 'crawl');
    document.getElementById('tabZip').classList.toggle('active', tab === 'zip');
    document.getElementById('tabAnalyze').classList.toggle('active', tab === 'analyze');
    document.getElementById('tabCrawl').classList.toggle('active', tab === 'crawl');
    document.querySelector('#uploadModal .modal-card').classList.toggle('wide', tab === 'crawl');
    if (tab === 'crawl') loadCrawlDbList('');
  }

  var zipStage = null;
  var analyzeStage = null;
  var crawlAnalyzeStage = null;
  var analyzeOptions = null; // { platforms: {platform: [category,...]}, common_category }

  function loadAnalyzeOptions() {
    if (analyzeOptions) return Promise.resolve(analyzeOptions);
    return api('/api/analyze/options').then(function (res) {
      analyzeOptions = res;
      var platformSel = document.getElementById('optPlatform');
      platformSel.innerHTML = '';
      Object.keys(res.platforms).forEach(function (p) {
        var opt = document.createElement('option');
        opt.value = p; opt.textContent = p;
        platformSel.appendChild(opt);
      });
      updateCategoryOptions();
      return res;
    });
  }

  function updateCategoryOptions() {
    if (!analyzeOptions) return;
    var platform = document.getElementById('optPlatform').value;
    var categories = (analyzeOptions.platforms[platform] || []).concat([analyzeOptions.common_category]);
    var categorySel = document.getElementById('optCategory');
    categorySel.innerHTML = '';
    categories.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      categorySel.appendChild(opt);
    });
  }

  function updateCrawlCategoryOptions() {
    if (!analyzeOptions) return;
    var platform = document.getElementById('crawlOptPlatform').value;
    var categories = (analyzeOptions.platforms[platform] || []).concat([analyzeOptions.common_category]);
    var categorySel = document.getElementById('crawlOptCategory');
    categorySel.innerHTML = '';
    categories.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      categorySel.appendChild(opt);
    });
  }

  function populateCrawlPlatformSelect(guessedPlatform, guessedCategory) {
    return loadAnalyzeOptions().then(function (res) {
      var platformSel = document.getElementById('crawlOptPlatform');
      platformSel.innerHTML = '';
      Object.keys(res.platforms).forEach(function (p) {
        var opt = document.createElement('option');
        opt.value = p; opt.textContent = p;
        platformSel.appendChild(opt);
      });
      if (guessedPlatform && res.platforms[guessedPlatform]) platformSel.value = guessedPlatform;
      updateCrawlCategoryOptions();
      if (guessedCategory) {
        var categorySel = document.getElementById('crawlOptCategory');
        if (Array.from(categorySel.options).some(function (o) { return o.value === guessedCategory; })) {
          categorySel.value = guessedCategory;
        }
      }
    });
  }

  // 크롤 DB 이름 접두사(navernews_.../navercafe_.../youtube_...) -> 통계분석 플랫폼 이름
  var CRAWL_NAME_PREFIX_TO_PLATFORM = { navernews: 'Naver News', navercafe: 'Naver Cafe', youtube: 'Google YouTube' };
  // 원본 파일명 접미사(_article/_reply/_rereply/_statistics) -> 분석 종류
  var CRAWL_FILE_SUFFIX_TO_CATEGORY = { article: 'article 분석', rereply: 'rereply 분석', reply: 'reply 분석', statistics: 'statistics 분석' };

  function guessPlatformFromDbName(dbName) {
    var prefix = (dbName || '').split('_')[0];
    return CRAWL_NAME_PREFIX_TO_PLATFORM[prefix] || null;
  }
  function guessCategoryFromFilename(filename) {
    var base = (filename || '').replace(/\.(csv|parquet)$/i, '');
    var suffixes = Object.keys(CRAWL_FILE_SUFFIX_TO_CATEGORY);
    for (var i = 0; i < suffixes.length; i++) {
      if (base.endsWith('_' + suffixes[i])) return CRAWL_FILE_SUFFIX_TO_CATEGORY[suffixes[i]];
    }
    return null;
  }

  function resetUploadModalState() {
    zipStage = null;
    analyzeStage = null;
    crawlAnalyzeStage = null;
    setModalStatus('');
    document.getElementById('zipProgress').hidden = true;
    document.getElementById('zipConfirm').hidden = true;
    document.getElementById('analyzeStatus').textContent = '';
    document.getElementById('analyzeProgress').hidden = true;
    document.getElementById('analyzeForm').hidden = true;
    document.getElementById('analyzeFileLabel').textContent = '원본 CSV 파일을 선택하세요';
    document.getElementById('crawlStatus').textContent = '';
    document.getElementById('crawlProgress').hidden = true;
    document.getElementById('crawlAnalyzeForm').hidden = true;
    document.getElementById('crawlDbStep').hidden = false;
    document.getElementById('crawlFileStep').hidden = true;
    document.getElementById('crawlDbSearch').value = '';
  }

  function openUploadModal() {
    closeMobileDrawers();
    document.getElementById('uploadModal').hidden = false;
    resetUploadModalState();
    switchModalTab('zip');
    loadAnalyzeOptions().catch(function () { });
  }
  function closeUploadModal() { document.getElementById('uploadModal').hidden = true; }

  function uploadToRail(file) {
    if (!file) return;
    if (!/\.zip$/i.test(file.name)) { setModalStatus('zip 파일만 업로드할 수 있습니다.', 'err'); return; }
    setModalStatus('');
    document.getElementById('zipConfirm').hidden = true;
    var progEl = document.getElementById('zipProgress');
    var fillEl = document.getElementById('zipProgressFill');
    var labelEl = document.getElementById('zipProgressLabel');
    progEl.hidden = false; fillEl.style.width = '0%'; labelEl.textContent = '업로드 중... 0%';

    var fd = new FormData();
    fd.append('file', file);
    uploadWithProgress('/api/projects/upload-zip', fd, function (pct) {
      fillEl.style.width = pct + '%'; labelEl.textContent = '업로드 중... ' + pct + '%';
    }).then(function (res) {
      progEl.hidden = true;
      zipStage = res.stage_id;
      document.getElementById('zipProjectName').value = res.suggested_name || '';
      document.getElementById('zipConfirm').hidden = false;
    }).catch(function (err) { progEl.hidden = true; setModalStatus(err.message || String(err), 'err'); });
  }

  function confirmZipProject() {
    if (!zipStage) return;
    var name = document.getElementById('zipProjectName').value.trim();
    setModalStatus('프로젝트 생성 중...');
    postJson('/api/projects/finalize-zip', { stage_id: zipStage, name: name }).then(function (project) {
      setModalStatus('완료!', 'ok');
      zipStage = null;
      loadRailProjects();
      switchProject(project.project_id);
      setTimeout(closeUploadModal, 400);
    }).catch(function (err) { setModalStatus(err.message || String(err), 'err'); });
  }

  function onAnalyzeFileSelected(file) {
    var statusEl = document.getElementById('analyzeStatus');
    statusEl.textContent = '';
    if (!file) return;
    if (!/\.csv$/i.test(file.name)) { statusEl.textContent = 'CSV 파일만 업로드할 수 있습니다.'; return; }
    document.getElementById('analyzeForm').hidden = true;
    document.getElementById('analyzeFileLabel').textContent = file.name;

    var progEl = document.getElementById('analyzeProgress');
    var fillEl = document.getElementById('analyzeProgressFill');
    var labelEl = document.getElementById('analyzeProgressLabel');
    progEl.hidden = false; fillEl.style.width = '0%'; labelEl.textContent = '업로드 중... 0%';

    var fd = new FormData();
    fd.append('file', file);
    uploadWithProgress('/api/projects/analyze/upload', fd, function (pct) {
      fillEl.style.width = pct + '%'; labelEl.textContent = '업로드 중... ' + pct + '%';
    }).then(function (res) {
      progEl.hidden = true;
      analyzeStage = res.stage_id;
      document.getElementById('analyzeProjectName').value = res.suggested_name || '';
      document.getElementById('analyzeForm').hidden = false;
      return loadAnalyzeOptions();
    }).catch(function (err) { progEl.hidden = true; statusEl.textContent = err.message || String(err); });
  }

  function startAnalyze() {
    if (!analyzeStage) return;
    var statusEl = document.getElementById('analyzeStatus');
    var name = document.getElementById('analyzeProjectName').value.trim();
    var platform = document.getElementById('optPlatform').value;
    var category = document.getElementById('optCategory').value;
    var btn = document.getElementById('btnStartAnalyze');
    statusEl.textContent = ''; btn.disabled = true;
    postJson('/api/projects/analyze/start', { stage_id: analyzeStage, name: name, platform: platform, category: category }).then(function (res) {
      btn.disabled = false;
      analyzeStage = null;
      closeUploadModal();
      openProgressModal(res.pid);
    }).catch(function (err) { btn.disabled = false; statusEl.textContent = err.message || String(err); });
  }

  // ---------------------------------------------------------------
  // 크롤링 DB에서 선택 (이 서버 자신의 API를 통해 크롤러와 서버 간 통신 — CORS 불필요)
  // ---------------------------------------------------------------
  var CRAWL_OBJECTS = { 1: 'Naver News', 2: 'Naver Blog', 3: 'Naver Cafe', 4: 'YouTube', 5: 'ChinaDaily', 6: 'ChinaSina' };
  function formatCrawlDate(d) { if (!d || d.length !== 8) return d || '-'; return d.slice(0, 4) + '.' + d.slice(4, 6) + '.' + d.slice(6, 8); }
  function formatCrawlSize(bytes) {
    if (!bytes) return '-';
    if (bytes > 1024 * 1024 * 1024) return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB';
    if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    return (bytes / 1024).toFixed(1) + ' KB';
  }

  var crawlDbSearchTimer = null;
  var crawlDbCurrentQ = '';
  var crawlDbCurrentPage = 1;
  function renderCrawlDbPager(data) {
    var pagerEl = document.getElementById('crawlDbPager');
    if (!pagerEl) return;
    var total = data.total || 0;
    var perPage = data.per_page || 30;
    var page = data.page || 1;
    var totalPages = Math.max(1, Math.ceil(total / perPage));
    if (totalPages <= 1) { pagerEl.innerHTML = ''; return; }
    pagerEl.innerHTML = '<button class="btn" id="crawlDbPrev" type="button"' + (page <= 1 ? ' disabled' : '') + '>← 이전</button>'
      + '<span class="crawl-pager-info">' + page + ' / ' + totalPages + '</span>'
      + '<button class="btn" id="crawlDbNext" type="button"' + (page >= totalPages ? ' disabled' : '') + '>다음 →</button>';
    var prevBtn = document.getElementById('crawlDbPrev');
    var nextBtn = document.getElementById('crawlDbNext');
    if (prevBtn) prevBtn.addEventListener('click', function () { if (page > 1) loadCrawlDbList(crawlDbCurrentQ, page - 1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { if (page < totalPages) loadCrawlDbList(crawlDbCurrentQ, page + 1); });
  }
  function loadCrawlDbList(q, page) {
    crawlDbCurrentQ = q || '';
    crawlDbCurrentPage = page || 1;
    var wrapEl = document.getElementById('crawlDbList');
    wrapEl.innerHTML = '<div class="crawl-db-empty">불러오는 중...</div>';
    var pagerElInit = document.getElementById('crawlDbPager');
    if (pagerElInit) pagerElInit.innerHTML = '';
    railApi('/api/crawl-dbs?q=' + encodeURIComponent(crawlDbCurrentQ) + '&page=' + crawlDbCurrentPage).then(function (data) {
      var items = data.items || [];
      if (!items.length) { wrapEl.innerHTML = '<div class="crawl-db-empty">검색된 크롤링 DB가 없습니다.</div>'; renderCrawlDbPager(data); return; }
      var uidMap = {};
      var rows = items.map(function (it) {
        uidMap[it.uid] = it;
        return '<tr data-uid="' + esc(it.uid) + '">'
          + '<td class="ct-main" data-label="키워드">' + esc(it.keyword || it.name) + '</td>'
          + '<td class="ct-muted" data-label="크롤러">' + esc(CRAWL_OBJECTS[it.crawlObject] || '-') + '</td>'
          + '<td class="ct-muted" data-label="요청자">' + esc(it.requester || '-') + '</td>'
          + '<td class="ct-muted" data-label="기간">' + formatCrawlDate(it.startDate) + ' ~ ' + formatCrawlDate(it.endDate) + '</td>'
          + '<td class="ct-muted" data-label="크기">' + formatCrawlSize(it.dbSize) + '</td>'
          + '</tr>';
      }).join('');
      wrapEl.innerHTML = '<table class="crawl-table"><thead><tr>'
        + '<th>키워드</th><th>크롤러</th><th>요청자</th><th>기간</th><th>크기</th>'
        + '</tr></thead><tbody>' + rows + '</tbody></table>';
      Array.prototype.forEach.call(wrapEl.querySelectorAll('tbody tr'), function (tr) {
        tr.addEventListener('click', function () {
          var it = uidMap[tr.dataset.uid];
          openCrawlDbFiles(it.uid, it.name, it.keyword);
        });
      });
      renderCrawlDbPager(data);
    }).catch(function (err) { wrapEl.innerHTML = '<div class="crawl-db-empty">' + esc(err.message || String(err)) + '</div>'; });
  }

  function openCrawlDbFiles(uid, dbName, keyword) {
    document.getElementById('crawlDbStep').hidden = true;
    document.getElementById('crawlFileStep').hidden = false;
    document.getElementById('crawlFileDbName').textContent = keyword || dbName;
    var wrapEl = document.getElementById('crawlFileList');
    wrapEl.innerHTML = '<div class="crawl-db-empty">불러오는 중...</div>';
    railApi('/api/crawl-dbs/' + encodeURIComponent(uid) + '/files').then(function (data) {
      var files = data.files || [];
      if (!files.length) { wrapEl.innerHTML = '<div class="crawl-db-empty">원본 파일이 없습니다.</div>'; return; }
      var rows = files.map(function (f, i) {
        return '<tr data-idx="' + i + '">'
          + '<td class="ct-main" data-label="파일명">' + esc(f.csv_name) + '</td>'
          + '<td data-label="종류"><span class="ct-filetype ' + esc(f.type) + '">' + (f.type === 'token' ? '토큰화' : '원본') + '</span></td>'
          + '<td class="ct-muted" data-label="크기">' + formatCrawlSize(f.size) + '</td>'
          + '</tr>';
      }).join('');
      wrapEl.innerHTML = '<table class="crawl-table"><thead><tr>'
        + '<th>파일명</th><th>종류</th><th>크기</th>'
        + '</tr></thead><tbody>' + rows + '</tbody></table>';
      Array.prototype.forEach.call(wrapEl.querySelectorAll('tbody tr'), function (tr) {
        tr.addEventListener('click', function () { selectCrawlFile(uid, dbName, files[+tr.dataset.idx]); });
      });
    }).catch(function (err) { wrapEl.innerHTML = '<div class="crawl-db-empty">' + esc(err.message || String(err)) + '</div>'; });
  }

  function selectCrawlFile(uid, dbName, file) {
    var statusEl = document.getElementById('crawlStatus');
    statusEl.textContent = '';
    var progEl = document.getElementById('crawlProgress');
    var labelEl = document.getElementById('crawlProgressLabel');
    progEl.hidden = false; labelEl.textContent = '불러오는 중...';
    document.getElementById('crawlAnalyzeForm').hidden = true;

    postJson('/api/crawl-dbs/' + encodeURIComponent(uid) + '/select', { name: file.name }).then(function (res) {
      crawlAnalyzeStage = res.stage_id;
      document.getElementById('crawlProjectName').value = res.suggested_name || '';
      return populateCrawlPlatformSelect(guessPlatformFromDbName(dbName), guessCategoryFromFilename(file.name));
    }).then(function () {
      progEl.hidden = true;
      document.getElementById('crawlAnalyzeForm').hidden = false;
    }).catch(function (err) { progEl.hidden = true; statusEl.textContent = err.message || String(err); });
  }

  function startCrawlAnalyze() {
    if (!crawlAnalyzeStage) return;
    var statusEl = document.getElementById('crawlStatus');
    var name = document.getElementById('crawlProjectName').value.trim();
    var platform = document.getElementById('crawlOptPlatform').value;
    var category = document.getElementById('crawlOptCategory').value;
    var btn = document.getElementById('btnCrawlStartAnalyze');
    statusEl.textContent = ''; btn.disabled = true;
    postJson('/api/projects/analyze/start', { stage_id: crawlAnalyzeStage, name: name, platform: platform, category: category }).then(function (res) {
      btn.disabled = false;
      crawlAnalyzeStage = null;
      closeUploadModal();
      openProgressModal(res.pid);
    }).catch(function (err) { btn.disabled = false; statusEl.textContent = err.message || String(err); });
  }

  // ---------------------------------------------------------------
  // 진행 상황 모달
  // ---------------------------------------------------------------
  var progressWs = null;
  var progressPollTimer = null;

  function appendProgressLine(text, cls) {
    var log = document.getElementById('progressLog');
    var div = document.createElement('div');
    div.className = 'pl-line' + (cls ? ' ' + cls : '');
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }
  function closeProgressWs() { if (progressWs) { try { progressWs.close(); } catch (e) { } progressWs = null; } }
  function closeProgressModal() {
    document.getElementById('progressModal').hidden = true;
    closeProgressWs();
    if (progressPollTimer) { clearInterval(progressPollTimer); progressPollTimer = null; }
  }
  function openProgressModal(pid) {
    document.getElementById('progressLog').innerHTML = '';
    document.getElementById('progressModalClose').hidden = true;
    document.getElementById('progressSpin').style.display = '';
    document.getElementById('progressModal').hidden = false;
    appendProgressLine('분석을 시작합니다...');

    railApi('/api/progress-config').then(function (cfg) {
      try {
        progressWs = new WebSocket(cfg.ws_url + '/ws/' + pid);
        progressWs.onmessage = function (ev) {
          try {
            var msg = JSON.parse(ev.data);
            if (msg.type === 'message' && msg.text) appendProgressLine(msg.text);
          } catch (e) { }
        };
      } catch (e) { }
    }).catch(function () { });

    progressPollTimer = setInterval(function () {
      railApi('/api/projects/analyze/' + pid + '/status').then(function (job) {
        if (job.status === 'done') {
          clearInterval(progressPollTimer); progressPollTimer = null;
          appendProgressLine('완료! 프로젝트로 저장했습니다.', 'pl-ok');
          closeProgressWs();
          document.getElementById('progressSpin').style.display = 'none';
          document.getElementById('progressModalClose').hidden = false;
          loadRailProjects();
          setTimeout(function () {
            closeProgressModal();
            if (job.project_id) switchProject(job.project_id);
          }, 900);
        } else if (job.status === 'error') {
          clearInterval(progressPollTimer); progressPollTimer = null;
          appendProgressLine('오류: ' + (job.error || '알 수 없는 오류'), 'pl-err');
          closeProgressWs();
          document.getElementById('progressSpin').style.display = 'none';
          document.getElementById('progressModalClose').hidden = false;
        }
      }).catch(function () { });
    }, 2000);
  }

  // ---------------------------------------------------------------
  // 모바일 드로어 / 우클릭 메뉴
  // ---------------------------------------------------------------
  function closeMobileDrawers() {
    document.getElementById('rail').classList.remove('mobile-open');
    document.getElementById('mobileBackdrop').classList.remove('show');
  }
  function openMobileDrawer(id) {
    closeMobileDrawers();
    document.getElementById(id).classList.add('mobile-open');
    document.getElementById('mobileBackdrop').classList.add('show');
  }

  var ctxMenuProject = null, ctxMenuItem = null;
  function closeRailCtxMenu() {
    document.getElementById('railCtxMenu').hidden = true;
    ctxMenuProject = null; ctxMenuItem = null;
  }
  function openRailCtxMenu(x, y, p, item) {
    var menu = document.getElementById('railCtxMenu');
    ctxMenuProject = p; ctxMenuItem = item;
    menu.hidden = false; menu.style.left = '-9999px'; menu.style.top = '-9999px';
    var pad = 8, mw = menu.offsetWidth, mh = menu.offsetHeight;
    var left = Math.max(pad, Math.min(x, window.innerWidth - mw - pad));
    var top = Math.max(pad, Math.min(y, window.innerHeight - mh - pad));
    menu.style.left = left + 'px'; menu.style.top = top + 'px';
  }

  // ---------------------------------------------------------------
  // 이벤트 바인딩
  // ---------------------------------------------------------------
  var RAIL_MIN_WIDTH = 180, RAIL_MAX_WIDTH = 440, RAIL_DEFAULT_WIDTH = 236;
  var mobileQuery = window.matchMedia('(max-width:1100px)');

  function bindEvents() {
    var rail = document.getElementById('rail');
    var toggle = document.getElementById('railToggle');

    var collapsed = localStorage.getItem('sv_rail_collapsed') === '1';
    var savedWidth = parseInt(localStorage.getItem('sv_rail_width'), 10);
    if (!savedWidth || isNaN(savedWidth)) savedWidth = RAIL_DEFAULT_WIDTH;
    savedWidth = Math.max(RAIL_MIN_WIDTH, Math.min(RAIL_MAX_WIDTH, savedWidth));
    if (!mobileQuery.matches) {
      if (!collapsed) rail.style.width = savedWidth + 'px';
      rail.classList.toggle('collapsed', collapsed);
    }

    toggle.addEventListener('click', function () {
      if (mobileQuery.matches) { closeMobileDrawers(); return; }
      var isCollapsed = rail.classList.toggle('collapsed');
      localStorage.setItem('sv_rail_collapsed', isCollapsed ? '1' : '0');
      if (!isCollapsed) rail.style.width = savedWidth + 'px';
    });

    document.getElementById('mobileRailBtn').addEventListener('click', function () { openMobileDrawer('rail'); });
    document.getElementById('mobileBackdrop').addEventListener('click', closeMobileDrawers);

    var mqHandler = function () {
      rail.classList.remove('collapsed');
      rail.style.width = mobileQuery.matches ? '' : savedWidth + 'px';
      closeMobileDrawers();
    };
    if (mobileQuery.addEventListener) mobileQuery.addEventListener('change', mqHandler);
    else mobileQuery.addListener(mqHandler);

    var resizer = document.getElementById('railResizer');
    var draggingRail = false;
    resizer.addEventListener('mousedown', function (e) {
      if (rail.classList.contains('collapsed') || mobileQuery.matches) return;
      draggingRail = true; rail.classList.add('resizing'); resizer.classList.add('active');
      document.body.style.userSelect = 'none'; e.preventDefault();
    });
    window.addEventListener('mousemove', function (e) {
      if (!draggingRail) return;
      var w = Math.max(RAIL_MIN_WIDTH, Math.min(RAIL_MAX_WIDTH, e.clientX));
      rail.style.width = w + 'px'; savedWidth = w;
    });
    window.addEventListener('mouseup', function () {
      if (!draggingRail) return;
      draggingRail = false; rail.classList.remove('resizing'); resizer.classList.remove('active');
      document.body.style.userSelect = '';
      localStorage.setItem('sv_rail_width', String(savedWidth));
    });

    var ctxMenu = document.getElementById('railCtxMenu');
    ctxMenu.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-act]');
      if (!btn || !ctxMenuProject) return;
      var p = ctxMenuProject, item = ctxMenuItem, act = btn.getAttribute('data-act');
      var x = parseInt(ctxMenu.style.left, 10), y = parseInt(ctxMenu.style.top, 10);
      closeRailCtxMenu();
      if (act === 'props') showProjectProperties(p);
      else if (act === 'rename') startRailRename(item, p);
      else if (act === 'move') openMoveFolderMenu(x, y, p);
      else if (act === 'delete') deleteRailProject(p);
    });
    var moveFolderMenu = document.getElementById('moveFolderMenu');
    document.addEventListener('click', function (e) {
      if (!ctxMenu.hidden && !ctxMenu.contains(e.target)) closeRailCtxMenu();
      if (!moveFolderMenu.hidden && !moveFolderMenu.contains(e.target)) closeMoveFolderMenu();
    });
    document.addEventListener('contextmenu', function (e) {
      if (!ctxMenu.hidden && !ctxMenu.contains(e.target) && !e.target.closest('.rail-item')) closeRailCtxMenu();
      if (!moveFolderMenu.hidden && !moveFolderMenu.contains(e.target)) closeMoveFolderMenu();
    });
    window.addEventListener('resize', function () { closeRailCtxMenu(); closeMoveFolderMenu(); });
    window.addEventListener('scroll', function () { closeRailCtxMenu(); closeMoveFolderMenu(); }, true);
    window.addEventListener('blur', function () { closeRailCtxMenu(); closeMoveFolderMenu(); });

    document.getElementById('propsModalClose').addEventListener('click', function () { document.getElementById('propsModal').hidden = true; });
    document.getElementById('propsModal').addEventListener('click', function (e) { if (e.target.id === 'propsModal') document.getElementById('propsModal').hidden = true; });

    document.getElementById('railNewFolderBtn').addEventListener('click', createFolder);

    // 폴더 밖(목록의 빈 공간)에 드롭하면 미분류로 뺀다 — 폴더 헤더/본문의 drop 핸들러가
    // stopPropagation()하므로, 여기까지 버블링되는 건 폴더 안이 아닌 곳에 놓은 경우뿐이다.
    var railListEl = document.getElementById('railList');
    railListEl.addEventListener('dragover', function (e) {
      if (isAdminAllMode()) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    });
    railListEl.addEventListener('drop', function (e) {
      if (isAdminAllMode()) return;
      e.preventDefault();
      var pid = e.dataTransfer.getData('text/plain');
      if (pid) moveProjectToFolder(pid, null);
    });

    document.getElementById('railUploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('emptyUploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('uploadModalClose').addEventListener('click', closeUploadModal);
    document.getElementById('uploadModal').addEventListener('click', function (e) { if (e.target.id === 'uploadModal') closeUploadModal(); });

    document.getElementById('exportModalClose').addEventListener('click', closeExportModal);
    document.getElementById('exportModal').addEventListener('click', function (e) { if (e.target.id === 'exportModal') closeExportModal(); });
    document.getElementById('btnDownloadPng').addEventListener('click', downloadChartPng);
    ['exportScaleRow', 'exportBgRow'].forEach(function (rowId) {
      document.getElementById(rowId).addEventListener('click', function (e) {
        var btn = e.target.closest('.option-btn');
        if (!btn) return;
        this.querySelectorAll('.option-btn').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
      });
    });

    window.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (!moveFolderMenu.hidden) closeMoveFolderMenu();
      else if (!ctxMenu.hidden) closeRailCtxMenu();
      else if (!document.getElementById('exportModal').hidden) closeExportModal();
      else if (!document.getElementById('propsModal').hidden) document.getElementById('propsModal').hidden = true;
      else if (!document.getElementById('uploadModal').hidden) closeUploadModal();
      else closeMobileDrawers();
    });

    var fileInput = document.getElementById('modalFileInput');
    var dropzone = document.getElementById('modalDropzone');
    fileInput.addEventListener('change', function () { uploadToRail(fileInput.files[0]); fileInput.value = ''; });
    ['dragenter', 'dragover'].forEach(function (evt) { dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.add('drag'); }); });
    ['dragleave', 'drop'].forEach(function (evt) { dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.remove('drag'); }); });
    dropzone.addEventListener('drop', function (e) { uploadToRail(e.dataTransfer.files && e.dataTransfer.files[0]); });
    document.getElementById('btnConfirmZip').addEventListener('click', confirmZipProject);

    document.getElementById('tabBtnZip').addEventListener('click', function () { switchModalTab('zip'); });
    document.getElementById('tabBtnAnalyze').addEventListener('click', function () { switchModalTab('analyze'); });
    document.getElementById('tabBtnCrawl').addEventListener('click', function () { switchModalTab('crawl'); });

    var analyzeInput = document.getElementById('analyzeFileInput');
    var analyzeDropzone = document.getElementById('analyzeDropzone');
    analyzeInput.addEventListener('change', function () { onAnalyzeFileSelected(analyzeInput.files[0]); analyzeInput.value = ''; });
    ['dragenter', 'dragover'].forEach(function (evt) { analyzeDropzone.addEventListener(evt, function (e) { e.preventDefault(); analyzeDropzone.classList.add('drag'); }); });
    ['dragleave', 'drop'].forEach(function (evt) { analyzeDropzone.addEventListener(evt, function (e) { e.preventDefault(); analyzeDropzone.classList.remove('drag'); }); });
    analyzeDropzone.addEventListener('drop', function (e) { onAnalyzeFileSelected(e.dataTransfer.files && e.dataTransfer.files[0]); });
    document.getElementById('btnStartAnalyze').addEventListener('click', startAnalyze);
    document.getElementById('optPlatform').addEventListener('change', updateCategoryOptions);

    document.getElementById('crawlDbSearch').addEventListener('input', function () {
      var q = this.value;
      clearTimeout(crawlDbSearchTimer);
      crawlDbSearchTimer = setTimeout(function () { loadCrawlDbList(q); }, 300);
    });
    document.getElementById('btnCrawlBack').addEventListener('click', function () {
      document.getElementById('crawlFileStep').hidden = true;
      document.getElementById('crawlDbStep').hidden = false;
      document.getElementById('crawlAnalyzeForm').hidden = true;
      document.getElementById('crawlStatus').textContent = '';
    });
    document.getElementById('btnCrawlStartAnalyze').addEventListener('click', startCrawlAnalyze);
    document.getElementById('crawlOptPlatform').addEventListener('change', updateCrawlCategoryOptions);

    document.getElementById('progressModalClose').addEventListener('click', closeProgressModal);

    document.getElementById('railLogout').addEventListener('click', function () {
      // 로그인은 knpu.re.kr 중앙 로그인이 전담하므로, 로그아웃도 그쪽 세션(쿠키)을 지운다
      fetch('https://knpu.re.kr/api/auth/logout', { method: 'POST', credentials: 'include' })
        .then(function () { location.href = 'https://knpu.re.kr/login?redirect=' + encodeURIComponent(window.location.href); });
    });

    document.getElementById('btnTheme').addEventListener('click', function () {
      var dark = document.body.classList.toggle('dark-theme');
      localStorage.setItem('sv_theme', dark ? 'dark' : 'light');
      renderRail();
      if (base) renderDashboard();
    });

    document.getElementById('search').addEventListener('input', function (e) {
      searchQuery = e.target.value.trim().toLowerCase();
      applyTableSearch();
    });

    document.getElementById('btnDownloadRaw').addEventListener('click', function () {
      if (!projectId) return;
      window.open('/api/projects/' + projectId + '/download', '_blank');
    });

    window.addEventListener('popstate', function () {
      var id = parseProjectId();
      if (id === projectId) return;
      projectId = id;
      if (id) {
        document.getElementById('emptyProject').hidden = true;
        loadProject(id);
      } else {
        base = null;
        destroyCharts();
        document.getElementById('dashboard').hidden = true;
        document.getElementById('emptyProject').hidden = false;
        document.getElementById('projectName').textContent = 'Statistics Analyzer';
      }
      highlightActiveRailItem();
    });
  }

  // ---------------------------------------------------------------
  // 초기화
  // ---------------------------------------------------------------
  if (localStorage.getItem('sv_theme') === 'dark') document.body.classList.add('dark-theme');

  bindEvents();
  loadMe().then(function () {
    if (projectId) {
      loadRailProjects();
      loadProject(projectId);
    } else {
      // URL에 프로젝트가 지정되지 않았으면(사이트를 그냥 열었으면) 마지막으로 열어봤던
      // 프로젝트를 자동으로 선택한다. 그 프로젝트가 삭제되었거나 접근 권한이 없으면
      // 조용히 포기하고 빈 화면을 보여준다.
      loadRailProjects().then(function () {
        var lastId = localStorage.getItem(LAST_PROJECT_KEY);
        var exists = lastId && railProjects.some(function (p) { return p.project_id === lastId; });
        if (exists) {
          switchProject(lastId, true);
        } else {
          if (lastId) localStorage.removeItem(LAST_PROJECT_KEY);
          document.getElementById('loading').classList.add('hide');
          document.getElementById('emptyProject').hidden = false;
        }
      });
    }
  });
})();
