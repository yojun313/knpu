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
      if (res.status === 401) { location.href = KNPU.loginUrl(); return Promise.reject(new Error('unauthorized')); }
      return res.text().then(function (txt) {
        var b = null;
        try { b = txt ? JSON.parse(txt) : {}; } catch (e) { b = null; }
        if (b === null) {
          // nginx 504 같은 HTML 오류 페이지 — JSON 파싱 오류 대신 알아볼 수 있는 문구로.
          throw new Error(res.status === 504 || res.status === 502
            ? '서버 응답이 늦어 게이트웨이가 요청을 끊었습니다(' + res.status + '). 잠시 후 다시 시도해 주세요.'
            : '서버 응답을 해석하지 못했습니다(' + res.status + ').');
        }
        if (!res.ok) throw new Error(typeof b.detail === 'string' ? b.detail : res.statusText);
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
        if (xhr.status === 401) { location.href = KNPU.loginUrl(); return; }
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

  // 상단 네비게이션의 MANAGER 버튼: PC에 데스크톱 MANAGER 앱이 설치되어 있으면
  // (설치 프로그램이 knpumanager:// URL 프로토콜을 등록해둔다) 바로 그 앱을 실행하고,
  // 설치되어 있지 않으면(=페이지가 포커스를 잃지 않으면) 잠시 후 웹 버전으로 이동한다.
  function openManagerApp(e) {
    e.preventDefault();
    var fallbackUrl = e.currentTarget.href;
    var appOpened = false;
    var onBlur = function () { appOpened = true; };
    window.addEventListener('blur', onBlur, { once: true });
    window.location.href = 'knpumanager://open';
    setTimeout(function () {
      window.removeEventListener('blur', onBlur);
      if (!appOpened) window.location.href = fallbackUrl;
    }, 1000);
    return false;
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
    card.setAttribute('data-table-id', table.id);
    card.setAttribute('data-search', (table.title + ' ' + table.columns.join(' ')).toLowerCase());

    var head = document.createElement('div');
    head.className = 'tc-head';
    head.innerHTML = '<span class="tc-head-main"><span class="tc-title">' + esc(table.title) + '</span>'
      + '<span class="tc-meta">' + table.row_count + '행 · ' + table.columns.length + '열</span></span>';
    card.appendChild(head);

    function addHeaderActions() {
      var actions = document.createElement('span');
      actions.className = 'tc-head-actions';
      if (table.is_heatmap || planChart(table)) {
        var pngBtn = document.createElement('button');
        pngBtn.className = 'tc-png-btn';
        pngBtn.title = 'PNG로 저장';
        pngBtn.innerHTML = '&#8681;';
        pngBtn.addEventListener('click', function () { openExportModal(table.id, table.title); });
        actions.appendChild(pngBtn);
      }
      var privateTable = /writer|user_activity|top_10_percent_users|top_10_articles|top_10_videos|top_10_liked|top_controversial|top_articles_by_demographic|reply_text|rereply_text/i.test(table.id || '');
      var privateColumn = (table.columns || []).some(function (name) { return /text|content|본문|제목|title|url|link|작성자|사용자|user|writer|author|name|이름|닉네임|아이디|계정|email|전화|주소|ip/i.test(name); });
      if (!privateTable && !privateColumn) {
        var aiBtn = document.createElement('button');
        aiBtn.className = 'tc-ai-btn'; aiBtn.type = 'button'; aiBtn.textContent = '✦ AI 해석'; aiBtn.title = '이 표를 AI로 해석';
        aiBtn.setAttribute('data-table', table.id);
        aiBtn.addEventListener('click', function () { runAiReport('table', table.id, ''); });
        actions.appendChild(aiBtn);
      }
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
    } else {
      var plan = planChart(table);
      if (plan) {
        var chartWrap = document.createElement('div');
        chartWrap.className = 'tc-chart';
        var canvas = document.createElement('canvas');
        chartWrap.appendChild(canvas);
        card.appendChild(chartWrap);
        chartsById[table.id] = buildChart(canvas, table, plan);
      }
    }
    addHeaderActions();

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

    // 워드클라우드 PNG (graphs/wordcloud_*.png) — 표보다 위에 이미지 카드로 보여준다
    var graphGrid = document.getElementById('graphGrid');
    graphGrid.innerHTML = '';
    var wcGraphs = (base.graphs || []).filter(function (g) { return /^wordcloud_/i.test(g); });
    graphGrid.hidden = !wcGraphs.length;
    wcGraphs.forEach(function (g) {
      var card = document.createElement('div');
      card.className = 'graph-card';
      var title = g.replace(/^wordcloud_/i, '').replace(/\.png$/i, '').replace(/_/g, ' ');
      var head = document.createElement('div');
      head.className = 'gc-title';
      head.textContent = '워드클라우드 — ' + title;
      var img = document.createElement('img');
      img.loading = 'lazy';
      img.alt = title;
      img.src = '/api/projects/' + encodeURIComponent(currentMeta.project_id) + '/graphs/' + encodeURIComponent(g);
      card.appendChild(head);
      card.appendChild(img);
      graphGrid.appendChild(card);
    });

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
      aiSetProject(currentMeta);

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
  function isDarkMode() { return document.documentElement.getAttribute('data-ui-theme-mode') === 'dark'; }
  function railDotColor(i) {
    var pal = isDarkMode() ? PALETTE_DARK : PALETTE_LIGHT;
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
    // 사이드바 Overview 통계
    var statP = document.getElementById('statProjects'), statF = document.getElementById('statFolders');
    if (statP) statP.textContent = railProjects.length;
    if (statF) statF.textContent = railFolders.length;
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
    applyAiActivity();
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
          currentMeta = null;
          aiSetProject(null);
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

  function commonCategories() {
    if (!analyzeOptions) return [];
    return analyzeOptions.common_categories || [analyzeOptions.common_category];
  }

  function isWcCategory(c) {
    return !!c && c.indexOf('워드클라우드') !== -1;
  }

  function updateWcVisibility() {
    document.getElementById('wcOptions').hidden = !isWcCategory(document.getElementById('optCategory').value);
  }

  function updateCrawlWcVisibility() {
    document.getElementById('crawlWcOptions').hidden = !isWcCategory(document.getElementById('crawlOptCategory').value);
  }

  function collectWcOptions(periodId, maxId, exclId) {
    return {
      wc_period: document.getElementById(periodId).value || 'total',
      wc_max_words: parseInt(document.getElementById(maxId).value, 10) || 100,
      wc_exclude: (document.getElementById(exclId).value || '')
        .split(',').map(function (w) { return w.trim(); }).filter(Boolean),
    };
  }

  function updateCategoryOptions() {
    if (!analyzeOptions) return;
    var platform = document.getElementById('optPlatform').value;
    var categories = (analyzeOptions.platforms[platform] || []).concat(commonCategories());
    var categorySel = document.getElementById('optCategory');
    categorySel.innerHTML = '';
    categories.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      categorySel.appendChild(opt);
    });
    updateWcVisibility();
  }

  function updateCrawlCategoryOptions() {
    if (!analyzeOptions) return;
    var platform = document.getElementById('crawlOptPlatform').value;
    var categories = (analyzeOptions.platforms[platform] || []).concat(commonCategories());
    var categorySel = document.getElementById('crawlOptCategory');
    categorySel.innerHTML = '';
    categories.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      categorySel.appendChild(opt);
    });
    updateCrawlWcVisibility();
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
      updateCrawlWcVisibility();
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
    // 토큰화 파일(token_*)은 워드클라우드 분석용
    if (base.indexOf('token_') === 0) return '워드클라우드 분석';
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
    var payload = { stage_id: analyzeStage, name: name, platform: platform, category: category };
    if (isWcCategory(category)) payload.options = collectWcOptions('wcPeriod', 'wcMaxWords', 'wcExclude');
    postJson('/api/projects/analyze/start', payload).then(function (res) {
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
    var payload = { stage_id: crawlAnalyzeStage, name: name, platform: platform, category: category };
    if (isWcCategory(category)) payload.options = collectWcOptions('crawlWcPeriod', 'crawlWcMaxWords', 'crawlWcExclude');
    postJson('/api/projects/analyze/start', payload).then(function (res) {
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
    document.getElementById('side').classList.remove('mobile-open');
    document.getElementById('mobileBackdrop').classList.remove('show');
    if (document.getElementById('aiSideBtn')) syncSideToggle();
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
  var RAIL_MIN_WIDTH = 220, RAIL_MAX_WIDTH = 440, RAIL_DEFAULT_WIDTH = 256;
  var mobileQuery = window.matchMedia('(max-width:1100px)');
  // ---------------------------------------------------------------
  // AI 통계 분석 — 오른쪽 사이드바
  //   * 작업·대화·결과는 모두 서버(프로젝트 폴더)에 저장된다. 이 화면은 서버 상태를
  //     보여 주기만 하므로, 다른 페이지로 갔다 오거나 다른 기기·브라우저에서 같은
  //     계정으로 들어와도 진행 중인 작업이 그대로 이어서 보인다.
  //   * 진행 중인 작업이 있으면 2초마다, 없으면 20초마다 상태를 다시 읽는다.
  // ---------------------------------------------------------------
  var AI_KIND = { overview: '전체 요약', findings: '핵심 발견', relationships: '변수 관계·가설', methods: '방법·한계 점검', table: '표 해석', question: '질문' };
  function aiChip(mode) { return mode === 'table' ? '표' : mode === 'question' ? '질문' : '리포트'; }
  var AI_SIDE_KEY = 'sv_ai_side_open', AI_SIDE_W_KEY = 'sv_ai_side_width', AI_TAB_KEY = 'sv_ai_side_tab';
  var aiResults = [], aiJobs = [], chatLog = [], aiOpen = {}, aiEpoch = 0;
  var aiResultsVersion = null, aiPollTimer = null, aiTickTimer = null, aiActivityTimer = null;
  var aiPromptCache = {}, aiActivity = [];

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { } }
  function projectApi(sub) { return '/api/projects/' + encodeURIComponent(currentMeta.project_id) + sub; }

  function friendlyAiError(msg) {
    msg = String(msg || '');
    if (/^not found$/i.test(msg)) return '서버에 AI 분석 기능이 아직 반영되지 않았습니다. 서비스를 재시작한 뒤 다시 시도해 주세요.';
    if (/unexpected token|not valid json|<html/i.test(msg)) return '서버 응답이 올바르지 않습니다(시간 초과 또는 게이트웨이 오류). 잠시 후 다시 시도해 주세요.';
    if (/failed to fetch|networkerror/i.test(msg)) return '서버에 연결하지 못했습니다. 네트워크를 확인해 주세요.';
    return msg || 'AI 분석에 실패했습니다.';
  }

  function fmtClock(iso) {
    var d = iso ? new Date(iso) : new Date();
    if (isNaN(d)) return '';
    var now = new Date(), pad = function (n) { return (n < 10 ? '0' : '') + n; };
    var t = pad(d.getHours()) + ':' + pad(d.getMinutes());
    return d.toDateString() === now.toDateString() ? t : (d.getMonth() + 1) + '/' + d.getDate() + ' ' + t;
  }

  function elapsedText(iso) {
    var s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    return s < 60 ? s + '초' : Math.floor(s / 60) + '분 ' + (s % 60) + '초';
  }

  function tableTitle(id) {
    var t = base && (base.tables || []).filter(function (x) { return x.id === id; })[0];
    return t ? t.title : id;
  }

  function isMobileLayout() { return mobileQuery.matches; }

  // ---- 사이드바 열기/닫기/탭 ----
  function setSideTab(tab) {
    tab = tab === 'chat' ? 'chat' : 'report';
    lsSet(AI_TAB_KEY, tab);
    document.querySelectorAll('.side-tab').forEach(function (b) {
      var on = b.getAttribute('data-side-tab') === tab;
      b.classList.toggle('active', on); b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    var hasProject = !!(currentMeta && base);
    document.getElementById('paneReport').hidden = !hasProject || tab !== 'report';
    document.getElementById('paneChat').hidden = !hasProject || tab !== 'chat';
    document.getElementById('sideEmpty').hidden = hasProject;
    if (hasProject && tab === 'chat') {
      var log = document.getElementById('aiChatMessages'); log.scrollTop = log.scrollHeight;
    }
  }

  function syncSideToggle() {
    var side = document.getElementById('side');
    var open = isMobileLayout() ? side.classList.contains('mobile-open') : !side.classList.contains('collapsed');
    document.getElementById('aiSideBtn').setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function resizeCharts() {
    Object.keys(chartsById).forEach(function (k) { if (chartsById[k] && chartsById[k].resize) chartsById[k].resize(); });
  }

  function openAiSide(tab) {
    var side = document.getElementById('side');
    if (isMobileLayout()) openMobileDrawer('side');
    else { side.classList.remove('collapsed'); lsSet(AI_SIDE_KEY, '1'); setTimeout(resizeCharts, 50); }
    if (tab) setSideTab(tab);
    syncSideToggle();
  }

  function closeAiSide() {
    var side = document.getElementById('side');
    if (isMobileLayout()) closeMobileDrawers();
    else { side.classList.add('collapsed'); lsSet(AI_SIDE_KEY, '0'); setTimeout(resizeCharts, 50); }
    syncSideToggle();
  }

  function refreshModelLine() {
    var line = document.getElementById('aiModelLine');
    railApi('/api/llm-settings').then(function (s) {
      var u = s.usage || {};
      var money = '$' + Number(u.cost_usd || 0).toFixed(2) + ' / $' + Number(s.monthly_limit_usd || 0).toFixed(2);
      line.textContent = s.mode === 'openai' ? '내 GPT API · ' + s.model + ' · 이번 달 ' + money
        : s.mode === 'local_then_openai' ? '로컬 LLM 우선 → ' + s.model + ' · ' + money
        : '로컬 LLM (연구실 서버) · 설정 변경';
    }).catch(function () { line.textContent = 'AI 모델 설정'; });
  }

  function openLlmSettings() {
    var btn = document.getElementById('themeSettingsBtn');
    if (!btn) return;
    btn.click();
    setTimeout(function () {
      var sec = document.getElementById('llmSettings');
      if (sec && !sec.hidden) sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 350);
  }

  // ---- 서버 상태 동기화 ----
  function hasRunning() { return aiJobs.some(function (j) { return j.status === 'running'; }); }

  function schedulePoll(ms) {
    clearTimeout(aiPollTimer);
    aiPollTimer = setTimeout(pollAiState, ms);
  }

  function loadAiResults(epoch) {
    return railApi(projectApi('/ai-results')).then(function (r) {
      if (epoch !== aiEpoch) return;
      aiResults = r.results || [];
      if (aiResults[0] && !Object.keys(aiOpen).length) aiOpen[aiResults[0].id] = true;
      renderAiResults();
    });
  }

  function applyAiState(state, epoch) {
    if (epoch !== aiEpoch) return;
    var before = {};
    aiJobs.forEach(function (j) { before[j.id] = j.status; });
    aiJobs = state.jobs || [];
    // 방금 끝난 리포트는 펼쳐서 보여 준다
    aiJobs.forEach(function (j) {
      if (j.status === 'done' && before[j.id] === 'running' && j.result_id) aiOpen[j.result_id] = true;
    });
    var chatChanged = JSON.stringify(state.chat || []) !== JSON.stringify(chatLog);
    chatLog = state.chat || [];
    if (state.results_version !== aiResultsVersion) {
      aiResultsVersion = state.results_version;
      loadAiResults(epoch);
    } else {
      renderAiResults();
    }
    if (chatChanged) renderChat(); else updateChatStage();
    var busy = chatBusy();
    document.getElementById('aiChatSend').disabled = busy;
    ensureTick();
  }

  function pollAiState() {
    if (!currentMeta) return;
    var epoch = aiEpoch;
    railApi(projectApi('/ai-state')).then(function (state) {
      applyAiState(state, epoch);
    }).catch(function () { }).then(function () {
      if (epoch !== aiEpoch) return;
      schedulePoll(hasRunning() ? 2000 : (document.hidden ? 60000 : 20000));
    });
  }

  function ensureTick() {
    if (aiTickTimer || !hasRunning()) return;
    aiTickTimer = setInterval(function () {
      if (!hasRunning()) { clearInterval(aiTickTimer); aiTickTimer = null; return; }
      document.querySelectorAll('[data-elapsed]').forEach(function (e) { e.textContent = elapsedText(e.getAttribute('data-elapsed')); });
    }, 1000);
  }

  // 다른 프로젝트에서 돌고 있는 작업도 왼쪽 목록에 표시한다
  function pollAiActivity() {
    clearTimeout(aiActivityTimer);
    railApi('/api/ai-activity').then(function (r) {
      aiActivity = r.running || [];
      applyAiActivity();
      aiActivityTimer = setTimeout(pollAiActivity, aiActivity.length ? 4000 : 20000);
    }).catch(function () { aiActivityTimer = setTimeout(pollAiActivity, 30000); });
  }

  function applyAiActivity() {
      var running = {};
      aiActivity.forEach(function (a) { running[a.project_id] = (running[a.project_id] || 0) + 1; });
      document.querySelectorAll('.rail-item').forEach(function (item) {
        var id = item.getAttribute('data-id'), badge = item.querySelector('.ri-ai');
        if (running[id]) {
          if (!badge) {
            badge = document.createElement('span'); badge.className = 'ri-ai'; badge.title = 'AI 분석 진행 중';
            badge.innerHTML = '<span class="ri-ai-dot"></span>AI';
            var main = item.querySelector('.ri-main'); if (main) main.after(badge);
          }
        } else if (badge) badge.remove();
      });
  }

  // ---- 프로젝트 전환 ----
  function aiSetProject(meta) {
    aiEpoch++;
    clearTimeout(aiPollTimer);
    aiResults = []; aiJobs = []; chatLog = []; aiOpen = {}; aiResultsVersion = null;
    renderChat(); renderAiResults(); setSideTab(lsGet(AI_TAB_KEY));
    if (!meta) return;
    document.getElementById('aiResults').innerHTML = '<div class="ai-results-empty">저장된 결과와 진행 중인 작업을 불러오는 중…</div>';
    pollAiState();
  }

  // ---- 작업 시작 ----
  function startAiJob(payload) {
    return postJson(projectApi('/ai-analysis'), payload).then(function (r) {
      if (r.job && !aiJobs.some(function (j) { return j.id === r.job.id; })) aiJobs.unshift(r.job);
      schedulePoll(600);
      pollAiActivity();
      return r;
    });
  }

  function runAiReport(mode, tableId, question) {
    if (!currentMeta || !currentMeta.project_id) return;
    openAiSide('report');
    startAiJob({ mode: mode, table_id: tableId || undefined, question: question || '' }).then(function () {
      renderAiResults(); ensureTick();
      document.getElementById('reportScroll').scrollTop = 0;
    }).catch(function (err) { toast(friendlyAiError(err.message)); });
  }

  function dismissJob(job) {
    aiJobs = aiJobs.filter(function (j) { return j.id !== job.id; });
    renderAiResults();
    railApi(projectApi('/ai-jobs/' + encodeURIComponent(job.id)), { method: 'DELETE' }).catch(function () { });
  }

  // ---- 결과 렌더링 ----
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // 프롬프트는 크기가 커서 펼칠 때 서버에서 받아 온다
  function promptDetails(url) {
    var d = el('details', 'ai-prompt');
    d.appendChild(el('summary', null, 'AI에 보낸 프롬프트 보기'));
    var pre = el('pre', null, '불러오는 중…');
    d.appendChild(pre);
    d.addEventListener('toggle', function () {
      if (!d.open) return;
      if (aiPromptCache[url]) { pre.textContent = aiPromptCache[url]; return; }
      railApi(url).then(function (r) { aiPromptCache[url] = r.prompt || '(비어 있음)'; pre.textContent = aiPromptCache[url]; })
        .catch(function (e) { pre.textContent = e.message || '프롬프트를 불러오지 못했습니다.'; });
    });
    return d;
  }

  function focusTable(tableId) {
    var card = document.querySelector('.table-card[data-table-id="' + (window.CSS && CSS.escape ? CSS.escape(tableId) : tableId) + '"]');
    if (!card) { toast('해당 표를 화면에서 찾지 못했습니다.'); return; }
    if (card.classList.contains('hidden-by-search')) {
      document.getElementById('search').value = ''; searchQuery = ''; applyTableSearch();
    }
    if (isMobileLayout()) closeMobileDrawers();
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.classList.remove('ai-flash'); void card.offsetWidth; card.classList.add('ai-flash');
  }

  function jobTitle(j) {
    return j.mode === 'table' ? (j.label || tableTitle(j.table_id)) : j.mode === 'question' ? (j.question || j.label) : (AI_KIND[j.mode] || j.label || 'AI 분석');
  }

  function buildJobCard(j) {
    var failed = j.status === 'error';
    var card = el('article', 'ai-card open' + (failed ? ' is-error' : ' is-pending'));
    var head = el('div', 'ai-card-head');
    head.appendChild(el('span', 'ai-card-kind', aiChip(j.mode)));
    head.appendChild(el('span', 'ai-card-title', jobTitle(j)));
    head.appendChild(el('span', 'ai-card-time', fmtClock(j.created_at)));
    card.appendChild(head);
    if (failed) {
      card.appendChild(el('div', 'ai-error', friendlyAiError(j.error)));
      var acts = el('div', 'ai-error-actions');
      var retry = el('button', null, '다시 시도'); retry.type = 'button';
      retry.addEventListener('click', function () { dismissJob(j); runAiReport(j.mode, j.table_id, j.question); });
      var dismiss = el('button', null, '닫기'); dismiss.type = 'button';
      dismiss.addEventListener('click', function () { dismissJob(j); });
      acts.appendChild(retry); acts.appendChild(dismiss);
      if (/모델|LLM|한도|API/.test(j.error || '')) {
        var cfg = el('button', null, 'AI 모델 설정'); cfg.type = 'button';
        cfg.addEventListener('click', openLlmSettings); acts.appendChild(cfg);
      }
      card.appendChild(acts);
      return card;
    }
    var p = el('div', 'ai-pending');
    p.appendChild(el('div', 'spin'));
    var txt = el('div', 'ai-pending-text');
    txt.appendChild(el('b', null, '분석 중'));
    txt.appendChild(el('span', null, j.stage || '대기 중'));
    p.appendChild(txt);
    var time = el('span', 'ai-pending-time', elapsedText(j.created_at));
    time.setAttribute('data-elapsed', j.created_at);
    p.appendChild(time);
    card.appendChild(p);
    var note = el('div', 'ai-pending-note', '다른 페이지로 이동하거나 창을 닫아도 서버에서 계속 진행되고, 다시 열면 이어서 보입니다.');
    card.appendChild(note);
    if (j.has_prompt) {
      var body = el('div', 'ai-card-body');
      body.appendChild(promptDetails('/api/ai-jobs/' + encodeURIComponent(j.id) + '/prompt'));
      card.appendChild(body);
    }
    return card;
  }

  function buildEvidence(ev) {
    var b = el('button', 'ai-ev ' + (ev.status || 'unknown_table')); b.type = 'button';
    b.appendChild(el('span', 'ai-ev-mark', ev.status === 'verified' ? '✓' : '!'));
    var body = el('span', 'ai-ev-body');
    body.appendChild(el('span', 'ai-ev-table', ev.table_title || ev.table_id || '표 미지정'));
    body.appendChild(document.createTextNode(ev.value || ''));
    if (ev.status === 'unverified') body.appendChild(el('span', 'ai-ev-note', '원자료에서 찾지 못한 수치: ' + (ev.unmatched || []).join(', ') + ' (계산값이거나 오류일 수 있음)'));
    if (ev.status === 'unknown_table') body.appendChild(el('span', 'ai-ev-note', 'AI에 제공하지 않은 표를 근거로 들었습니다. 직접 확인하세요.'));
    b.appendChild(body);
    b.title = ev.status === 'verified' ? '원자료에서 수치를 확인했습니다 · 클릭하면 표로 이동' : '클릭하면 표로 이동';
    if (ev.table_id) b.addEventListener('click', function () { focusTable(ev.table_id); });
    return b;
  }

  function bulletList(items, cls) {
    var ul = el('ul', 'ai-bullets ' + cls);
    items.forEach(function (x) { ul.appendChild(el('li', null, x)); });
    return ul;
  }

  function buildResultCard(r) {
    var rep = r.report || {};
    var card = el('article', 'ai-card' + (aiOpen[r.id] ? ' open' : ''));
    var head = el('div', 'ai-card-head');
    head.appendChild(el('span', 'ai-card-kind', aiChip(r.mode)));
    head.appendChild(el('span', 'ai-card-title', r.mode === 'table' ? tableTitle(r.table_id) : r.mode === 'question' ? (r.question || '질문') : (AI_KIND[r.mode] || r.label)));
    head.appendChild(el('span', 'ai-card-time', fmtClock(r.created_at)));
    head.appendChild(el('span', 'ai-card-caret'));
    var peek = el('div', 'ai-card-peek', rep.headline || rep.summary || '');
    function toggle() { aiOpen[r.id] = !aiOpen[r.id]; card.classList.toggle('open', !!aiOpen[r.id]); }
    head.addEventListener('click', toggle); peek.addEventListener('click', toggle);
    card.appendChild(head); card.appendChild(peek);

    var body = el('div', 'ai-card-body');
    if (r.question && r.mode === 'question') body.appendChild(el('div', 'ai-q', 'Q. ' + r.question));
    if (rep.headline) body.appendChild(el('div', 'ai-headline', rep.headline));
    if (rep.summary) body.appendChild(el('div', 'ai-summary', rep.summary));
    if ((rep.findings || []).length) {
      var sec = el('div', 'ai-sec');
      sec.appendChild(el('div', 'ai-sec-title', '발견 ' + rep.findings.length));
      rep.findings.forEach(function (f, i) {
        var box = el('div', 'ai-finding');
        box.appendChild(el('span', 'ai-finding-no', String(i + 1)));
        var fh = el('div', 'ai-finding-head');
        fh.appendChild(el('div', 'ai-finding-title', f.title));
        fh.appendChild(el('span', 'ai-strength s-' + (f.strength || '보통'), '근거 ' + (f.strength || '보통')));
        box.appendChild(fh);
        if (f.detail) box.appendChild(el('div', 'ai-finding-detail', f.detail));
        if ((f.evidence || []).length) {
          var evs = el('div', 'ai-evs');
          f.evidence.forEach(function (ev) { evs.appendChild(buildEvidence(ev)); });
          box.appendChild(evs);
        }
        sec.appendChild(box);
      });
      body.appendChild(sec);
    }
    if ((rep.cautions || []).length) {
      var c = el('div', 'ai-sec'); c.appendChild(el('div', 'ai-sec-title', '해석 주의점'));
      c.appendChild(bulletList(rep.cautions, 'caution')); body.appendChild(c);
    }
    if ((rep.next_steps || []).length) {
      var n = el('div', 'ai-sec'); n.appendChild(el('div', 'ai-sec-title', '다음 분석 제안'));
      n.appendChild(bulletList(rep.next_steps, 'next')); body.appendChild(n);
    }
    var llm = r.llm || {};
    if ((llm.notes || []).length) body.appendChild(el('div', 'ai-notes', llm.notes.join(' · ')));
    if (r.has_prompt) body.appendChild(promptDetails(projectApi('/ai-results/' + encodeURIComponent(r.id) + '/prompt')));

    var foot = el('div', 'ai-card-foot');
    var v = rep.verification || {};
    var total = (v.verified || 0) + (v.flagged || 0);
    if (total) {
      foot.appendChild(el('span', 'ai-verify ' + (v.flagged ? 'warn' : 'ok'),
        v.flagged ? '근거 ' + total + '개 중 ' + v.flagged + '개 확인 필요' : '근거 ' + total + '개 원자료 확인'));
    }
    var model = [llm.used, llm.model].filter(Boolean).join(' · ');
    if (llm.cost_usd) model += ' · $' + Number(llm.cost_usd).toFixed(4);
    if (model) foot.appendChild(el('span', null, model));
    if ((r.tables || []).length) foot.appendChild(el('span', null, '참고 표 ' + r.tables.length + '개'));
    foot.appendChild(el('span', 'grow'));
    var md = el('a', 'ai-link-btn', '.md 저장');
    md.href = projectApi('/ai-results/' + encodeURIComponent(r.id) + '.md');
    md.setAttribute('download', '');
    foot.appendChild(md);
    var del = el('button', 'ai-link-btn danger', '삭제'); del.type = 'button';
    var armed = null;
    del.addEventListener('click', function () {
      if (!armed) {
        del.textContent = '한 번 더 누르면 삭제';
        armed = setTimeout(function () { armed = null; del.textContent = '삭제'; }, 3000);
        return;
      }
      clearTimeout(armed);
      railApi(projectApi('/ai-results/' + encodeURIComponent(r.id)), { method: 'DELETE' })
        .then(function () { aiResults = aiResults.filter(function (x) { return x.id !== r.id; }); aiResultsVersion = null; renderAiResults(); })
        .catch(function (err) { toast(err.message || '삭제에 실패했습니다.'); });
    });
    foot.appendChild(del);
    body.appendChild(foot);
    card.appendChild(body);
    return card;
  }

  function renderAiResults() {
    var host = document.getElementById('aiResults');
    var scroll = document.getElementById('reportScroll'), top = scroll.scrollTop;
    // 펼친 프롬프트는 다시 그려도 열린 채로 둔다
    host.innerHTML = '';
    var jobs = aiJobs.filter(function (j) { return j.kind === 'report' && j.status !== 'done'; });
    jobs.forEach(function (j) { host.appendChild(buildJobCard(j)); });
    aiResults.forEach(function (r) { host.appendChild(buildResultCard(r)); });
    var n = aiResults.length, running = jobs.filter(function (j) { return j.status === 'running'; }).length;
    document.getElementById('aiResultCount').textContent = (running ? '진행 중 ' + running + ' · ' : '') + (n ? n + '개 저장됨' : '');
    if (!jobs.length && !n) {
      host.appendChild(el('div', 'ai-results-empty', '아직 분석 결과가 없습니다. 위에서 분석 방식을 고르거나 질문을 입력해 보세요.'));
    }
    scroll.scrollTop = top;
    var busy = {};
    jobs.forEach(function (j) { if (j.status === 'running') busy[j.mode === 'table' ? 't:' + j.table_id : j.mode] = true; });
    document.querySelectorAll('[data-ai-mode]').forEach(function (b) { b.classList.toggle('is-busy', !!busy[b.getAttribute('data-ai-mode')]); });
    document.querySelectorAll('.tc-ai-btn').forEach(function (b) { b.classList.toggle('is-busy', !!busy['t:' + b.getAttribute('data-table')]); });
  }

  // ---- 대화 ----
  // 아주 작은 마크다운 렌더러: 먼저 전부 이스케이프한 뒤 제목·목록·표·굵게·코드만 되살린다.
  function mdInline(s) {
    return s
      .replace(/`([^`]+)`/g, function (m, code) {
        var isTable = base && (base.tables || []).some(function (t) { return t.id === code; });
        return isTable ? '<code class="tref" data-table="' + code.replace(/"/g, '&quot;') + '" title="표로 이동">' + esc(tableTitle(code)) + '</code>' : '<code>' + code + '</code>';
      })
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  }

  function renderMarkdown(text) {
    var lines = esc(text).split('\n'), html = '', list = null, para = [], i = 0;
    function flushPara() { if (para.length) { html += '<p>' + mdInline(para.join('<br>')) + '</p>'; para = []; } }
    function flushList() { if (list) { html += '</' + list + '>'; list = null; } }
    for (; i < lines.length; i++) {
      var line = lines[i], m;
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        flushPara(); flushList();
        var cells = function (l) { return l.trim().replace(/^\||\|$/g, '').split('|').map(function (c) { return mdInline(c.trim()); }); };
        html += '<div class="md-table"><table><thead><tr>' + cells(line).map(function (c) { return '<th>' + c + '</th>'; }).join('') + '</tr></thead><tbody>';
        i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
          html += '<tr>' + cells(lines[i]).map(function (c) { return '<td>' + c + '</td>'; }).join('') + '</tr>'; i++;
        }
        i--; html += '</tbody></table></div>';
        continue;
      }
      if ((m = line.match(/^\s*#{1,4}\s+(.*)$/))) { flushPara(); flushList(); html += '<h4>' + mdInline(m[1]) + '</h4>'; continue; }
      if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) { flushPara(); if (list !== 'ul') { flushList(); html += '<ul>'; list = 'ul'; } html += '<li>' + mdInline(m[1]) + '</li>'; continue; }
      if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) { flushPara(); if (list !== 'ol') { flushList(); html += '<ol>'; list = 'ol'; } html += '<li>' + mdInline(m[1]) + '</li>'; continue; }
      if (/^\s*(---|\*\*\*)\s*$/.test(line)) { flushPara(); flushList(); continue; }
      if (!line.trim()) { flushPara(); flushList(); continue; }
      flushList(); para.push(line);
    }
    flushPara(); flushList();
    return html;
  }

  function chatBusy() { return chatLog.some(function (m) { return m.pending; }); }
  function chatJob(m) { return aiJobs.filter(function (j) { return j.id === m.job_id; })[0]; }

  function buildChatMessage(m) {
    var box = el('div', 'chat-msg ' + m.role + (m.error ? ' error' : ''));
    if (m.role === 'user') { box.textContent = m.content; return box; }
    if (m.pending) {
      var job = chatJob(m) || {};
      var st = el('div', 'chat-status'); st.appendChild(el('span', 'spin'));
      st.appendChild(el('span', 'chat-stage', job.stage || '통계표를 확인하는 중'));
      var t = el('span', 'chat-elapsed', elapsedText(m.created_at)); t.setAttribute('data-elapsed', m.created_at);
      st.appendChild(t);
      box.appendChild(st); return box;
    }
    if (m.error) { box.textContent = friendlyAiError(m.content); return box; }
    var md = el('div', 'md'); md.innerHTML = renderMarkdown(m.content || '');
    md.querySelectorAll('code.tref').forEach(function (c) {
      c.addEventListener('click', function () { focusTable(c.getAttribute('data-table')); });
    });
    box.appendChild(md);
    if ((m.tables || []).length) {
      var refs = el('div', 'chat-refs');
      m.tables.forEach(function (t) {
        var b = el('button', 'chat-ref', '▦ ' + t.title); b.type = 'button'; b.title = '표로 이동';
        b.addEventListener('click', function () { focusTable(t.id); });
        refs.appendChild(b);
      });
      box.appendChild(refs);
    }
    var meta = el('div', 'chat-meta');
    var llm = m.llm || {};
    var model = [llm.used, llm.model].filter(Boolean).join(' · ');
    if (llm.cost_usd) model += ' · $' + Number(llm.cost_usd).toFixed(4);
    if (model) meta.appendChild(el('span', null, model));
    if ((m.steps || []).length) {
      var d = el('details'); d.appendChild(el('summary', null, '조회 과정 ' + m.steps.length + '단계'));
      var ol = el('ol'); m.steps.forEach(function (s) { ol.appendChild(el('li', null, s)); }); d.appendChild(ol);
      meta.appendChild(d);
    }
    if ((llm.notes || []).length) meta.appendChild(el('span', null, llm.notes.join(' · ')));
    if (meta.childNodes.length) box.appendChild(meta);
    return box;
  }

  function renderChat() {
    var host = document.getElementById('aiChatMessages');
    var atBottom = host.scrollHeight - host.scrollTop - host.clientHeight < 60;
    host.innerHTML = '';
    if (!chatLog.length) {
      var w = el('div', 'chat-welcome');
      w.innerHTML = '<b>통계 결과에 대해 대화해 보세요.</b><br>AI가 이 프로젝트의 표를 직접 찾아 읽고, 필요하면 계산까지 해서 답합니다. 답에 나온 표 이름을 누르면 해당 표로 이동합니다. 대화는 계정에 저장되어 다른 기기에서도 이어집니다.';
      host.appendChild(w);
    }
    chatLog.forEach(function (m) { host.appendChild(buildChatMessage(m)); });
    if (atBottom || chatBusy()) host.scrollTop = host.scrollHeight;
    document.getElementById('chatSuggest').hidden = chatLog.length > 0;
    document.getElementById('aiChatSend').disabled = chatBusy();
  }

  function updateChatStage() {
    chatLog.forEach(function (m) {
      if (!m.pending) return;
      var job = chatJob(m), s = document.querySelector('#aiChatMessages .chat-stage');
      if (job && s) s.textContent = job.stage || s.textContent;
    });
  }

  function sendChat(question) {
    question = String(question || '').trim();
    if (!question || !currentMeta || chatBusy()) return;
    openAiSide('chat');
    var now = new Date().toISOString();
    chatLog = chatLog.concat([{ role: 'user', content: question, created_at: now }, { role: 'assistant', pending: true, created_at: now }]);
    renderChat();
    startAiJob({ mode: 'chat', question: question }).then(function (r) {
      chatLog[chatLog.length - 1].job_id = r.job_id;
    }).catch(function (err) {
      chatLog = chatLog.slice(0, -2);
      renderChat();
      toast(friendlyAiError(err.message));
      document.getElementById('aiChatInput').value = question;
    });
  }

  function autoGrow(ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'; }

  function bindAiSide() {
    var side = document.getElementById('side');
    if (!isMobileLayout() && lsGet(AI_SIDE_KEY) === '0') side.classList.add('collapsed');
    var w = parseInt(lsGet(AI_SIDE_W_KEY), 10);
    if (w >= 320 && w <= 680) side.style.setProperty('--side-w', w + 'px');
    syncSideToggle();
    mobileQuery.addEventListener('change', syncSideToggle);

    document.getElementById('aiSideBtn').addEventListener('click', function () {
      var open = document.getElementById('aiSideBtn').getAttribute('aria-expanded') === 'true';
      if (open) closeAiSide(); else openAiSide();
    });
    document.getElementById('sideCloseBtn').addEventListener('click', closeAiSide);
    document.getElementById('aiModelLine').addEventListener('click', openLlmSettings);
    document.querySelectorAll('.side-tab').forEach(function (b) {
      b.addEventListener('click', function () { setSideTab(b.getAttribute('data-side-tab')); });
    });
    document.querySelectorAll('[data-ai-mode]').forEach(function (b) {
      b.addEventListener('click', function () { runAiReport(b.getAttribute('data-ai-mode'), null, ''); });
    });

    var q = document.getElementById('aiQuestion');
    q.addEventListener('input', function () { autoGrow(q); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); document.getElementById('aiQuestionForm').requestSubmit(); }
    });
    document.getElementById('aiQuestionForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var text = q.value.trim();
      if (!text) { q.focus(); return; }
      q.value = ''; autoGrow(q);
      runAiReport('question', null, text);
    });

    var ci = document.getElementById('aiChatInput');
    ci.addEventListener('input', function () { autoGrow(ci); });
    ci.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); document.getElementById('aiChatForm').requestSubmit(); }
    });
    document.getElementById('aiChatForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var text = ci.value.trim();
      if (!text || chatBusy()) return;
      ci.value = ''; autoGrow(ci);
      sendChat(text);
    });
    document.querySelectorAll('[data-chat-prompt]').forEach(function (b) {
      b.addEventListener('click', function () { sendChat(b.getAttribute('data-chat-prompt')); });
    });
    var clearArmed = null, clearBtn = document.getElementById('aiChatClear');
    clearBtn.addEventListener('click', function () {
      if (!currentMeta || chatBusy() || !chatLog.length) return;
      if (!clearArmed) {
        clearBtn.textContent = '한 번 더 누르면 대화 삭제';
        clearArmed = setTimeout(function () { clearArmed = null; clearBtn.textContent = '새 대화'; }, 3000);
        return;
      }
      clearTimeout(clearArmed); clearArmed = null; clearBtn.textContent = '새 대화';
      railApi(projectApi('/ai-chat'), { method: 'DELETE' }).then(function () { chatLog = []; renderChat(); ci.focus(); })
        .catch(function (err) { toast(err.message); });
    });

    // 탭으로 돌아오면 바로 최신 상태를 읽는다(다른 기기에서 시작한 작업 포함)
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && currentMeta) { schedulePoll(0); pollAiActivity(); }
    });

    // 왼쪽 가장자리를 끌어 너비 조절
    var rz = document.getElementById('sideResizer');
    rz.addEventListener('mousedown', function (e) {
      e.preventDefault();
      rz.classList.add('active');
      var startX = e.clientX, startW = side.getBoundingClientRect().width;
      function move(ev) {
        var nw = Math.max(320, Math.min(680, startW + (startX - ev.clientX)));
        side.style.setProperty('--side-w', nw + 'px');
      }
      function up() {
        rz.classList.remove('active');
        document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
        lsSet(AI_SIDE_W_KEY, Math.round(side.getBoundingClientRect().width));
        resizeCharts();
      }
      document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
    });

    renderAiResults(); renderChat(); setSideTab(lsGet(AI_TAB_KEY));
    refreshModelLine();
    pollAiActivity();
  }

  function bindEvents() {
    document.getElementById('navManagerLink').addEventListener('click', openManagerApp);

    bindAiSide();

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
    document.getElementById('optCategory').addEventListener('change', updateWcVisibility);

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
    document.getElementById('crawlOptCategory').addEventListener('change', updateCrawlWcVisibility);

    // GPU 모니터 (사이드바 하단) — 3초 폴링, 데이터가 없으면 영역 자체를 숨긴다
    function fmtGpuGB(mib) { return (mib / 1024).toFixed(1); }
    function gpuRowHtml(g) {
      var memPct = g.mem_total ? Math.round(g.mem_used / g.mem_total * 100) : 0;
      var util = g.util != null ? g.util : 0;
      return '<div class="gpu-row">'
        + '<div class="gpu-row-head"><span>GPU' + g.index
        + ' <span class="gpu-name" title="' + esc(g.name) + '">' + esc(g.name) + '</span></span>'
        + '<span>' + util + '%</span></div>'
        + '<div class="gpu-bar" title="GPU 사용률 ' + util + '%"><div class="fill" style="width:' + util + '%"></div></div>'
        + '<div class="gpu-bar" title="VRAM ' + fmtGpuGB(g.mem_used || 0) + ' / ' + fmtGpuGB(g.mem_total || 0) + ' GB"><div class="fill" style="width:' + memPct + '%"></div></div>'
        + '<div class="gpu-sub"><span>VRAM ' + fmtGpuGB(g.mem_used || 0) + '/' + fmtGpuGB(g.mem_total || 0) + 'GB</span>'
        + '<span>' + (g.temp != null ? g.temp : '-') + '°C</span>'
        + '<span>' + (g.power != null ? Math.round(g.power) : '-') + 'W' + (g.power_limit ? '/' + Math.round(g.power_limit) + 'W' : '') + '</span>'
        + (g.fan != null ? '<span>팬 ' + g.fan + '%</span>' : '')
        + '</div></div>';
    }
    function pollGpuStats() {
      fetch('/api/gpu/stats').then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
        var w = document.getElementById('gpuWidget');
        var gpus = (data && data.gpus) || [];
        if (!gpus.length) { w.hidden = true; return; }
        w.hidden = false;
        document.getElementById('gpuBody').innerHTML = gpus.map(gpuRowHtml).join('');
      }).catch(function () { /* 다음 폴링에서 회복 */ });
    }
    pollGpuStats();
    setInterval(pollGpuStats, 3000);

    document.getElementById('progressModalClose').addEventListener('click', closeProgressModal);

    document.getElementById('railLogout').addEventListener('click', function () {
      // 로그인은 knpu.re.kr 중앙 로그인이 전담하므로, 로그아웃도 그쪽 세션(쿠키)을 지운다
      fetch(KNPU.logoutUrl(), { method: 'POST', credentials: 'include' })
        .then(function () { location.href = KNPU.loginUrl(); });
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
        currentMeta = null;
        aiSetProject(null);
      }
      highlightActiveRailItem();
    });

    // 화면 다크모드는 더 이상 이 앱만의 버튼이 아니라 상단 그라디언트 바의 테마
    // 설정(모든 KNPU 사이트 공용)에서 켜고 끈다. shared_ui/theme.js가 이 이벤트를
    // 쏘면 다크 팔레트를 쓰는 차트를 다시 그려준다.
    window.addEventListener('knpu-ui-theme-mode-change', function () {
      renderRail();
      if (base) renderDashboard();
    });
  }

  // ---------------------------------------------------------------
  // 초기화
  // ---------------------------------------------------------------
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
