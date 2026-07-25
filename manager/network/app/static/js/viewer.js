(function () {
  'use strict';

  function parseProjectId() {
    var m = location.pathname.match(/^\/viewer\/([^\/]+)\/?$/);
    return m ? decodeURIComponent(m[1]) : null;
  }
  var projectId = parseProjectId();
  var LAST_PROJECT_KEY = 'nv_last_project'; // 마지막으로 열었던 프로젝트 — 사이트를 새로 열 때 자동 선택
  var qs = new URLSearchParams(location.search);
  var currentTag = qs.get('tag') || '';

  var rawNodes = [], rawEdges = [];
  var summary = null;
  var net = null;
  var nodes = new vis.DataSet([]);
  var edges = new vis.DataSet([]);
  var container = document.getElementById('net');
  var bgContainer = document.getElementById('netWrap');

  // ---------------------------------------------------------------
  // 데이터 로드
  // ---------------------------------------------------------------
  function api(path) {
    return fetch(path).then(function (res) {
      if (!res.ok) return res.json().then(function (b) { throw new Error(b.detail || res.statusText); });
      return res.json();
    });
  }

  function loadNetwork(tag) {
    document.getElementById('loading').classList.remove('hide');
    return Promise.all([
      api('/api/projects/' + projectId + '/data?tag=' + encodeURIComponent(tag)),
      api('/api/projects/' + projectId + '/summary?tag=' + encodeURIComponent(tag)),
      api('/api/projects/' + projectId + '/meta'),
    ]).then(function (res) {
      var data = res[0], summ = res[1], meta = res[2];
      rawNodes = data.nodes;
      rawEdges = data.edges;
      summary = summ;
      currentTag = tag;
      document.getElementById('projectName').textContent = meta.name || 'Network Analyzer';
      document.title = (meta.name || 'Network Analyzer') + ' · Network Analyzer';
      document.getElementById('emptyProject').hidden = true;
      highlightActiveRailItem();
      localStorage.setItem(LAST_PROJECT_KEY, projectId);
      initNetworkSelect(meta);
      renderAnalysisOptions(meta.analysis_options);
      var warn = data.truncated
        ? '⚠ 전체 엣지 ' + data.total_edges.toLocaleString() + '개 중 상위 ' + data.edges.length.toLocaleString() + '개 표시'
        : '엣지 ' + data.edges.length.toLocaleString() + '개 · 노드 ' + rawNodes.length.toLocaleString() + '개';
      document.getElementById('totalBadge').innerHTML = '<span class="pulse"></span>' + warn;
      boot();
      document.getElementById('loading').classList.add('hide');
    }).catch(function (err) {
      document.getElementById('loading').innerHTML =
        '<div style="color:#e08a52;font-weight:700">불러오기 실패</div><div>' + esc(err.message) + '</div>';
    });
  }

  function initNetworkSelect(meta) {
    var sel = document.getElementById('networkSelect');
    if (!meta.networks || meta.networks.length < 2) { sel.hidden = true; return; }
    sel.hidden = false;
    sel.innerHTML = '';
    meta.networks.forEach(function (nw) {
      var o = document.createElement('option');
      o.value = nw.tag; o.text = nw.label;
      if (nw.tag === currentTag) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = function () {
      history.replaceState(null, '', '?tag=' + encodeURIComponent(sel.value));
      loadNetwork(sel.value);
    };
  }

  function fmtAnalyzedAt(iso) {
    try {
      var d = new Date(iso);
      return d.getFullYear() + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + String(d.getDate()).padStart(2, '0')
        + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    } catch (e) { return iso; }
  }

  function analysisOptionsStatsHtml(analysisOptions) {
    if (!analysisOptions || !analysisOptions.options_label) return '';
    var html = '';
    if (analysisOptions.analyzed_at) {
      html += '<div class="stat"><span>분석 시각</span><span>' + esc(fmtAnalyzedAt(analysisOptions.analyzed_at)) + '</span></div>';
    }
    if (analysisOptions.source_filename) {
      html += '<div class="stat"><span>원본 파일</span><span title="' + escAttr(analysisOptions.source_filename) + '">' + esc(analysisOptions.source_filename) + '</span></div>';
    }
    var labels = analysisOptions.options_label;
    Object.keys(labels).forEach(function (k) {
      var v = labels[k];
      if (v === null || v === undefined || v === '') return;
      html += '<div class="stat"><span>' + esc(k) + '</span><span>' + esc(v) + '</span></div>';
    });
    return html;
  }

  function renderAnalysisOptions(analysisOptions) {
    var section = document.getElementById('optionsSection');
    var body = document.getElementById('analysisOptions');
    if (!analysisOptions || !analysisOptions.options_label) {
      section.hidden = true;
      body.innerHTML = '';
      return;
    }
    section.hidden = false;
    body.innerHTML = analysisOptionsStatsHtml(analysisOptions) || '<div class="empty">저장된 분석 설정이 없습니다</div>';
  }

  function showProjectProperties(p) {
    document.getElementById('propsTitle').textContent = p.name + ' · 속성';
    var html = '';
    html += '<div class="stat"><span>이름</span><span>' + esc(p.name) + '</span></div>';
    html += '<div class="stat"><span>생성일</span><span>' + esc(fmtAnalyzedAt(p.created_at)) + '</span></div>';
    if (p.updated_at && p.updated_at !== p.created_at) {
      html += '<div class="stat"><span>수정일</span><span>' + esc(fmtAnalyzedAt(p.updated_at)) + '</span></div>';
    }
    var networks = p.networks || [];
    html += '<div class="stat"><span>네트워크(기간) 개수</span><span>' + networks.length + '</span></div>';
    networks.forEach(function (nw) {
      html += '<div class="stat"><span>' + esc(nw.label || nw.tag || '-') + '</span><span>노드 '
        + (nw.nodes || 0).toLocaleString() + ' · 엣지 ' + (nw.edges || 0).toLocaleString() + '</span></div>';
    });
    html += analysisOptionsStatsHtml(p.analysis_options) || '<div class="empty">저장된 분석 설정이 없습니다</div>';
    document.getElementById('propsBody').innerHTML = html;
    closeMobileDrawers();
    document.getElementById('propsModal').hidden = false;
  }

  // ---------------------------------------------------------------
  // 왼쪽 프로젝트 레일 (VSCode 사이드바처럼 접고 펼치기 + 프로젝트 전환/업로드/관리)
  // ---------------------------------------------------------------
  var railProjects = [];

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

  // fetch()는 업로드 진행률(progress)을 알려주지 않으므로, 진행률 표시가 필요한
  // 업로드(zip / 토큰 CSV)는 XMLHttpRequest로 보낸다.
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

  function setModalStatus(msg, cls) {
    var el = document.getElementById('modalStatus');
    el.textContent = msg || '';
    el.className = 'modal-status' + (cls ? ' ' + cls : '');
  }

  function railDotColor(i) {
    var pal = document.body.classList.contains('dark-theme') ? PALETTE_DARK : PALETTE_LIGHT;
    return pal[((i % pal.length) + pal.length) % pal.length];
  }

  function loadMe() {
    railApi('/api/me').then(function (me) {
      document.getElementById('railUserName').textContent = me.name || '';
      document.getElementById('railUserName').title = me.name || '';
    }).catch(function () {});
  }

  function loadRailProjects() {
    return railApi('/api/projects').then(function (body) {
      railProjects = body.projects || [];
      renderRail();
    }).catch(function (err) {
      if (err.message !== 'unauthorized') toast('프로젝트 목록을 불러오지 못했습니다.');
    });
  }

  function railInitial(name) {
    return (name || '?').trim().charAt(0).toUpperCase();
  }

  function renderRail() {
    var listEl = document.getElementById('railList');
    var emptyEl = document.getElementById('railEmpty');
    listEl.innerHTML = '';
    emptyEl.hidden = railProjects.length > 0;

    railProjects.forEach(function (p, idx) {
      var item = document.createElement('div');
      item.className = 'rail-item' + (p.project_id === projectId ? ' active' : '');
      item.setAttribute('data-id', p.project_id);
      item.title = p.name;
      var meta = p.networks && p.networks.length === 1
        ? '노드 ' + p.networks[0].nodes.toLocaleString() + ' · 엣지 ' + p.networks[0].edges.toLocaleString()
        : (p.networks ? p.networks.length + '개 네트워크' : '');
      item.innerHTML =
        '<span class="ri-dot" style="background:' + railDotColor(idx) + '">' + esc(railInitial(p.name)) + '</span>'
        + '<span class="ri-main"><span class="ri-name">' + esc(p.name) + '</span>'
        + '<span class="ri-meta">' + esc(meta) + '</span></span>'
        + '<span class="ri-actions">'
        + '<button class="ri-btn" data-act="props" title="속성">ℹ</button>'
        + '<button class="ri-btn" data-act="rename" title="이름 변경">✎</button>'
        + '<button class="ri-btn danger" data-act="delete" title="삭제">🗑</button>'
        + '</span>';
      item.addEventListener('click', function (e) {
        if (e.target.closest('[data-act]')) return;
        switchProject(p.project_id);
        closeMobileDrawers();
      });
      item.addEventListener('contextmenu', function (e) {
        e.preventDefault(); e.stopPropagation();
        openRailCtxMenu(e.clientX, e.clientY, p, item);
      });
      item.querySelector('[data-act="props"]').addEventListener('click', function (e) {
        e.stopPropagation(); showProjectProperties(p);
      });
      item.querySelector('[data-act="rename"]').addEventListener('click', function (e) {
        e.stopPropagation(); startRailRename(item, p);
      });
      item.querySelector('[data-act="delete"]').addEventListener('click', function (e) {
        e.stopPropagation(); deleteRailProject(p);
      });
      listEl.appendChild(item);
    });
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
          document.title = newName + ' · Network Analyzer';
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
      clearSavedSettings(p.project_id);
      if (wasCurrent) localStorage.removeItem(LAST_PROJECT_KEY);
      loadRailProjects().then(function () {
        if (wasCurrent) {
          projectId = null;
          history.pushState(null, '', '/viewer');
          document.getElementById('projectName').textContent = 'Network Analyzer';
          document.title = 'Network Analyzer';
          document.getElementById('emptyProject').hidden = false;
          document.getElementById('totalBadge').innerHTML = '<span class="pulse"></span>-';
          document.getElementById('liveBadge').innerHTML = '<span class="pulse"></span>표시 중 -';
          renderAnalysisOptions(null);
        }
      });
    }).catch(function () { toast('삭제에 실패했습니다.'); });
  }

  function switchProject(id, replace) {
    if (!id || id === projectId) return;
    projectId = id;
    currentTag = '';
    if (replace) history.replaceState(null, '', '/viewer/' + encodeURIComponent(id));
    else history.pushState(null, '', '/viewer/' + encodeURIComponent(id));
    highlightActiveRailItem();
    loadNetwork('');
  }

  function switchModalTab(tab) {
    document.getElementById('tabBtnZip').classList.toggle('active', tab === 'zip');
    document.getElementById('tabBtnAnalyze').classList.toggle('active', tab === 'analyze');
    document.getElementById('tabZip').classList.toggle('active', tab === 'zip');
    document.getElementById('tabAnalyze').classList.toggle('active', tab === 'analyze');
  }

  var zipStage = null;
  var analyzeStage = null;

  function resetUploadModalState() {
    zipStage = null;
    analyzeStage = null;
    setModalStatus('');
    document.getElementById('zipProgress').hidden = true;
    document.getElementById('zipConfirm').hidden = true;
    document.getElementById('analyzeStatus').textContent = '';
    document.getElementById('analyzeProgress').hidden = true;
    document.getElementById('analyzeForm').hidden = true;
    document.getElementById('analyzeFileLabel').textContent = '토큰화된 CSV 파일을 선택하세요';
  }

  function openUploadModal() {
    closeMobileDrawers();
    document.getElementById('uploadModal').hidden = false;
    resetUploadModalState();
    switchModalTab('zip');
  }
  function closeUploadModal() {
    document.getElementById('uploadModal').hidden = true;
  }

  // ---------------------------------------------------------------
  // 결과 zip 업로드: 진행률 표시(1단계) → 이름 확정(2단계)
  // ---------------------------------------------------------------
  function uploadToRail(file) {
    if (!file) return;
    if (!/\.zip$/i.test(file.name)) { setModalStatus('zip 파일만 업로드할 수 있습니다.', 'err'); return; }
    setModalStatus('');
    document.getElementById('zipConfirm').hidden = true;
    var progEl = document.getElementById('zipProgress');
    var fillEl = document.getElementById('zipProgressFill');
    var labelEl = document.getElementById('zipProgressLabel');
    progEl.hidden = false;
    fillEl.style.width = '0%';
    labelEl.textContent = '업로드 중... 0%';

    var fd = new FormData();
    fd.append('file', file);
    uploadWithProgress('/api/projects/upload-zip', fd, function (pct) {
      fillEl.style.width = pct + '%';
      labelEl.textContent = '업로드 중... ' + pct + '%';
    }).then(function (res) {
      progEl.hidden = true;
      zipStage = res.stage_id;
      document.getElementById('zipProjectName').value = res.suggested_name || '';
      document.getElementById('zipConfirm').hidden = false;
    }).catch(function (err) {
      progEl.hidden = true;
      setModalStatus(err.message || String(err), 'err');
    });
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

  // ---------------------------------------------------------------
  // 토큰 CSV 업로드: 진행률 표시(1단계, 업로드 완료 전까지 설정 폼은 숨김) →
  // 이름·옵션 확정(2단계) → MANAGER 서버(기존 분석 파이프라인) 그대로 호출
  // ---------------------------------------------------------------
  function parseCsvHeader(file, cb) {
    var reader = new FileReader();
    reader.onload = function (e) {
      var firstLine = String(e.target.result).split(/\r?\n/)[0] || '';
      var cols = firstLine.split(',')
        .map(function (c) { return c.trim().replace(/^"|"$/g, ''); })
        .filter(Boolean);
      cb(cols);
    };
    reader.readAsText(file.slice(0, 16384));
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
    progEl.hidden = false;
    fillEl.style.width = '0%';
    labelEl.textContent = '업로드 중... 0%';

    var fd = new FormData();
    fd.append('file', file);
    uploadWithProgress('/api/projects/analyze/upload', fd, function (pct) {
      fillEl.style.width = pct + '%';
      labelEl.textContent = '업로드 중... ' + pct + '%';
    }).then(function (res) {
      progEl.hidden = true;
      analyzeStage = res.stage_id;
      document.getElementById('analyzeProjectName').value = res.suggested_name || '';
      parseCsvHeader(file, function (cols) {
        if (!cols.length) { statusEl.textContent = '열 이름을 읽지 못했습니다. CSV 형식을 확인해주세요.'; return; }
        var sel = document.getElementById('optTextCol');
        sel.innerHTML = '';
        cols.forEach(function (c) {
          var o = document.createElement('option'); o.value = c; o.text = c; sel.appendChild(o);
        });
        var textLike = cols.filter(function (c) { return /text/i.test(c); })[0];
        if (textLike) sel.value = textLike;
        document.getElementById('analyzeForm').hidden = false;
      });
    }).catch(function (err) {
      progEl.hidden = true;
      statusEl.textContent = err.message || String(err);
    });
  }

  function startAnalyze() {
    if (!analyzeStage) return;
    var overrides = {
      text_col: document.getElementById('optTextCol').value,
      measure: document.getElementById('optMeasure').value,
      period: document.getElementById('optPeriod').value,
      min_freq: parseInt(document.getElementById('optMinFreq').value, 10) || 5,
      min_edge_weight: parseInt(document.getElementById('optMinEdge').value, 10) || 2,
      top_n: parseInt(document.getElementById('optTopN').value, 10) || 0,
      community: document.getElementById('optCommunity').value,
      layout: document.getElementById('optLayout').value,
    };
    var name = document.getElementById('analyzeProjectName').value.trim();
    var statusEl = document.getElementById('analyzeStatus');
    var btn = document.getElementById('btnStartAnalyze');
    statusEl.textContent = '';
    btn.disabled = true;
    postJson('/api/projects/analyze/start', { stage_id: analyzeStage, name: name, option: overrides }).then(function (res) {
      btn.disabled = false;
      analyzeStage = null;
      closeUploadModal();
      openProgressModal(res.pid);
    }).catch(function (err) {
      btn.disabled = false;
      statusEl.textContent = err.message || String(err);
    });
  }

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

  function closeProgressWs() {
    if (progressWs) { try { progressWs.close(); } catch (e) { /* noop */ } progressWs = null; }
  }

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
          } catch (e) { /* noop */ }
        };
      } catch (e) { /* WebSocket 연결 실패해도 상태 폴링으로 계속 진행 */ }
    }).catch(function () { /* noop */ });

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
      }).catch(function () { /* 다음 폴링에서 재시도 */ });
    }, 2000);
  }

  var RAIL_MIN_WIDTH = 180;
  var RAIL_MAX_WIDTH = 440;
  var RAIL_DEFAULT_WIDTH = 236;
  var mobileQuery = window.matchMedia('(max-width:1100px)');

  // ---- 모바일: 좌/우 패널을 오프캔버스 드로어로 열고 닫기 ----
  function closeMobileDrawers() {
    document.getElementById('rail').classList.remove('mobile-open');
    document.getElementById('side').classList.remove('mobile-open');
    document.getElementById('mobileBackdrop').classList.remove('show');
  }
  function openMobileDrawer(id) {
    closeMobileDrawers();
    document.getElementById(id).classList.add('mobile-open');
    document.getElementById('mobileBackdrop').classList.add('show');
  }

  // ---- 프로젝트 우클릭 컨텍스트 메뉴 (항상 화면 안쪽에 표시되도록 위치 보정) ----
  var ctxMenuProject = null;
  var ctxMenuItem = null;
  function closeRailCtxMenu() {
    document.getElementById('railCtxMenu').hidden = true;
    ctxMenuProject = null;
    ctxMenuItem = null;
  }
  function openRailCtxMenu(x, y, p, item) {
    var menu = document.getElementById('railCtxMenu');
    ctxMenuProject = p;
    ctxMenuItem = item;
    menu.hidden = false;
    menu.style.left = '-9999px';
    menu.style.top = '-9999px';
    var pad = 8;
    var mw = menu.offsetWidth, mh = menu.offsetHeight;
    var left = Math.max(pad, Math.min(x, window.innerWidth - mw - pad));
    var top = Math.max(pad, Math.min(y, window.innerHeight - mh - pad));
    menu.style.left = left + 'px';
    menu.style.top = top + 'px';
  }

  function bindRailEvents() {
    var rail = document.getElementById('rail');
    var toggle = document.getElementById('railToggle');

    // ---- 접기/펼치기 (데스크톱 전용, 모바일은 드로어로 대체) ----
    var collapsed = localStorage.getItem('nv_rail_collapsed') === '1';
    var savedWidth = parseInt(localStorage.getItem('nv_rail_width'), 10);
    if (!savedWidth || isNaN(savedWidth)) savedWidth = RAIL_DEFAULT_WIDTH;
    savedWidth = Math.max(RAIL_MIN_WIDTH, Math.min(RAIL_MAX_WIDTH, savedWidth));
    if (!mobileQuery.matches) {
      if (!collapsed) rail.style.width = savedWidth + 'px';
      rail.classList.toggle('collapsed', collapsed);
    }

    toggle.addEventListener('click', function () {
      if (mobileQuery.matches) { closeMobileDrawers(); return; }
      var isCollapsed = rail.classList.toggle('collapsed');
      localStorage.setItem('nv_rail_collapsed', isCollapsed ? '1' : '0');
      if (!isCollapsed) rail.style.width = savedWidth + 'px';
      if (net) setTimeout(function () { net.redraw(); }, 200);
    });

    document.getElementById('mobileRailBtn').addEventListener('click', function () { openMobileDrawer('rail'); });
    document.getElementById('mobileSideBtn').addEventListener('click', function () { openMobileDrawer('side'); });
    document.getElementById('sideCloseBtn').addEventListener('click', closeMobileDrawers);
    document.getElementById('mobileBackdrop').addEventListener('click', closeMobileDrawers);

    var mqChangeHandler = function () {
      rail.classList.remove('collapsed');
      rail.style.width = mobileQuery.matches ? '' : savedWidth + 'px';
      closeMobileDrawers();
      if (net) setTimeout(function () { net.redraw(); }, 250);
    };
    if (mobileQuery.addEventListener) mobileQuery.addEventListener('change', mqChangeHandler);
    else mobileQuery.addListener(mqChangeHandler);

    // ---- 마우스로 너비 조절 ----
    var resizer = document.getElementById('railResizer');
    var dragging = false;
    resizer.addEventListener('mousedown', function (e) {
      if (rail.classList.contains('collapsed') || mobileQuery.matches) return;
      dragging = true;
      rail.classList.add('resizing');
      resizer.classList.add('active');
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });
    window.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      var w = Math.max(RAIL_MIN_WIDTH, Math.min(RAIL_MAX_WIDTH, e.clientX));
      rail.style.width = w + 'px';
      savedWidth = w;
    });
    window.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      rail.classList.remove('resizing');
      resizer.classList.remove('active');
      document.body.style.userSelect = '';
      localStorage.setItem('nv_rail_width', String(savedWidth));
      if (net) net.redraw();
    });

    // ---- 프로젝트 우클릭 컨텍스트 메뉴 ----
    var ctxMenu = document.getElementById('railCtxMenu');
    ctxMenu.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-act]');
      if (!btn || !ctxMenuProject) return;
      var p = ctxMenuProject, item = ctxMenuItem, act = btn.getAttribute('data-act');
      closeRailCtxMenu();
      if (act === 'props') showProjectProperties(p);
      else if (act === 'rename') startRailRename(item, p);
      else if (act === 'delete') deleteRailProject(p);
    });
    document.addEventListener('click', function (e) {
      if (!ctxMenu.hidden && !ctxMenu.contains(e.target)) closeRailCtxMenu();
    });
    document.addEventListener('contextmenu', function (e) {
      if (!ctxMenu.hidden && !ctxMenu.contains(e.target) && !e.target.closest('.rail-item')) closeRailCtxMenu();
    });
    window.addEventListener('resize', closeRailCtxMenu);
    window.addEventListener('scroll', closeRailCtxMenu, true);
    window.addEventListener('blur', closeRailCtxMenu);

    // ---- 속성 모달 ----
    document.getElementById('propsModalClose').addEventListener('click', function () {
      document.getElementById('propsModal').hidden = true;
    });
    document.getElementById('propsModal').addEventListener('click', function (e) {
      if (e.target.id === 'propsModal') document.getElementById('propsModal').hidden = true;
    });

    // ---- 업로드 모달 ----
    document.getElementById('railUploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('emptyUploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('uploadModalClose').addEventListener('click', closeUploadModal);
    document.getElementById('uploadModal').addEventListener('click', function (e) {
      if (e.target.id === 'uploadModal') closeUploadModal();
    });
    window.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (!ctxMenu.hidden) closeRailCtxMenu();
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

    // ---- 탭 전환 ----
    document.getElementById('tabBtnZip').addEventListener('click', function () { switchModalTab('zip'); });
    document.getElementById('tabBtnAnalyze').addEventListener('click', function () { switchModalTab('analyze'); });

    // ---- 토큰 CSV로 분석 ----
    var analyzeInput = document.getElementById('analyzeFileInput');
    var analyzeDropzone = document.getElementById('analyzeDropzone');
    analyzeInput.addEventListener('change', function () { onAnalyzeFileSelected(analyzeInput.files[0]); analyzeInput.value = ''; });
    ['dragenter', 'dragover'].forEach(function (evt) { analyzeDropzone.addEventListener(evt, function (e) { e.preventDefault(); analyzeDropzone.classList.add('drag'); }); });
    ['dragleave', 'drop'].forEach(function (evt) { analyzeDropzone.addEventListener(evt, function (e) { e.preventDefault(); analyzeDropzone.classList.remove('drag'); }); });
    analyzeDropzone.addEventListener('drop', function (e) { onAnalyzeFileSelected(e.dataTransfer.files && e.dataTransfer.files[0]); });
    document.getElementById('btnStartAnalyze').addEventListener('click', startAnalyze);

    // ---- 진행 상황 모달 ----
    document.getElementById('progressModalClose').addEventListener('click', closeProgressModal);

    document.getElementById('railLogout').addEventListener('click', function () {
      // 로그인은 knpu.re.kr 중앙 로그인이 전담하므로, 로그아웃도 그쪽 세션(쿠키)을 지운다
      fetch('https://knpu.re.kr/api/auth/logout', { method: 'POST', credentials: 'include' })
        .then(function () { location.href = 'https://knpu.re.kr/login'; });
    });

    window.addEventListener('popstate', function () {
      var id = parseProjectId();
      if (id === projectId) return;
      projectId = id;
      currentTag = '';
      highlightActiveRailItem();
      if (id) {
        document.getElementById('emptyProject').hidden = true;
        loadNetwork('');
      } else {
        document.getElementById('emptyProject').hidden = false;
        document.getElementById('projectName').textContent = 'Network Analyzer';
        renderAnalysisOptions(null);
      }
    });
  }

  // ---------------------------------------------------------------
  // 아래부터는 매 네트워크 로드마다 다시 구성
  // ---------------------------------------------------------------
  var mnames = {
    freq: '빈도(freq)', degree: '연결 정도', strength: '강도', betweenness: '매개 중심성',
    closeness: '근접 중심성', eigenvector: '고유벡터', pagerank: 'PageRank',
    coreness: 'k-core', constraint: '구조적 공백'
  };
  var metricKeys = [];
  function getMetricValue(n, key) {
    if (key === 'freq') return n.freq;
    var v = n.info ? n.info[key] : null;
    return (typeof v === 'number') ? v : 0;
  }
  function metricRangeOf(key) {
    var mn = Infinity, mx = -Infinity;
    rawNodes.forEach(function (n) { var v = getMetricValue(n, key); if (v < mn) mn = v; if (v > mx) mx = v; });
    if (!isFinite(mn)) { mn = 0; mx = 1; }
    return { min: mn, max: mx };
  }

  // 검증된 8색 범주형 팔레트(고정 순서: blue, orange, aqua, yellow, magenta, green, violet, red) +
  // 커뮤니티가 8개를 넘는 경우를 위한 확장 톤. 라이트/다크 캔버스 각각에 맞춰 스텝을 달리한다.
  var PALETTE_LIGHT = [
    '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948',
    '#8fb8ea', '#f0a578', '#7fd1b3', '#f0c775', '#f0aec8', '#5fa85f', '#9d8ed0', '#e88f8e'
  ];
  var PALETTE_DARK = [
    '#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767',
    '#6fa3e0', '#d98b5e', '#5fbf9a', '#d9ae5e', '#d98fac', '#4f9f4f', '#b3a8e8', '#d98080'
  ];
  function currentPalette() { return cfg.theme === 'dark' ? PALETTE_DARK : PALETTE_LIGHT; }

  function hexToRgb(h) { h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(function (c) { return c + c; }).join(''); var num = parseInt(h, 16); return [num >> 16 & 255, num >> 8 & 255, num & 255]; }
  function clamp255(x) { return Math.max(0, Math.min(255, Math.round(x))); }
  function rgbToHex(r, g, b) { return '#' + [r, g, b].map(function (x) { var s = clamp255(x).toString(16); return s.length < 2 ? '0' + s : s; }).join(''); }
  function lerpColor(a, b, t) { var A = hexToRgb(a), B = hexToRgb(b); return rgbToHex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t); }
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }
  function escAttr(s) { return esc(s).replace(/"/g, '&quot;'); }

  var defaultCfg = {
    shape: 'dot', sizeBy: 'freq', sizeMin: 6, sizeMax: 55,
    colorBy: 'community', colorUniform: '#2c3e50',
    colorGradMetric: 'freq', colorGradLow: '#dbe9f6', colorGradHigh: '#2c3e50',
    borderWidth: 1.5, borderColor: '#ffffff',
    labelShow: true, labelTopOnly: false, labelTopN: 30, fontSize: 14, fontColor: '#2c3e50',
    edgeColor: '#bdc3c7', edgeOpacity: 0.55, edgeWidthMin: 0.5, edgeWidthMax: 6,
    edgeSmooth: false, arrows: false,
    zoomWheel: true, dragNodes: true,
    bgCenter: '#ffffff', bgEdge: '#ecf0f1', theme: 'light',
    minWeight: 0, minFreq: 0, hideIsolated: false
  };
  var cfg;

  var nodeMap, currentVisibleIds, communityCounts, communityIds;
  var commNames, commColors, commVisible, selectedWords, wordSelectMode;
  var adj, wlOrder;

  function initCommState() {
    commNames = {}; commColors = {}; commVisible = {};
    communityIds.forEach(function (c) { commNames[c] = '커뮤니티 ' + c; commVisible[c] = true; });
  }
  function initWordSel() {
    selectedWords = {};
    rawNodes.forEach(function (n) { selectedWords[n.id] = true; });
    wordSelectMode = false;
  }

  // ---------------------------------------------------------------
  // 프로젝트별 화면 설정 저장 (localStorage) — 설정 초기화를 누르기 전까지 유지
  // ---------------------------------------------------------------
  var SETTINGS_KEY_PREFIX = 'nv_settings_';
  var saveSettingsTimer = null;

  function loadSavedSettings(pid) {
    if (!pid) return null;
    try {
      var raw = localStorage.getItem(SETTINGS_KEY_PREFIX + pid);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function saveSettingsNow() {
    if (!projectId) return;
    try {
      localStorage.setItem(SETTINGS_KEY_PREFIX + projectId, JSON.stringify({
        cfg: cfg, commNames: commNames, commColors: commColors, commVisible: commVisible,
        wordSelectMode: wordSelectMode, selectedWords: selectedWords
      }));
    } catch (e) { /* 저장 공간 부족 등은 조용히 무시 */ }
  }

  function scheduleSaveSettings(e) {
    if (e && e.target && e.target.closest && e.target.closest('#btnReset')) return;
    clearTimeout(saveSettingsTimer);
    saveSettingsTimer = setTimeout(saveSettingsNow, 250);
  }

  function clearSavedSettings(pid) {
    if (!pid) return;
    try { localStorage.removeItem(SETTINGS_KEY_PREFIX + pid); } catch (e) { /* noop */ }
  }

  function applySavedSettings() {
    var saved = loadSavedSettings(projectId);
    if (!saved) return;
    if (saved.cfg) cfg = Object.assign({}, defaultCfg, saved.cfg);
    if (metricKeys.indexOf(cfg.sizeBy) === -1) cfg.sizeBy = 'freq';
    if (metricKeys.indexOf(cfg.colorGradMetric) === -1) cfg.colorGradMetric = 'freq';
    if (saved.commNames) Object.keys(saved.commNames).forEach(function (g) { if (g in commNames) commNames[g] = saved.commNames[g]; });
    if (saved.commColors) Object.keys(saved.commColors).forEach(function (g) { if (g in commVisible) commColors[g] = saved.commColors[g]; });
    if (saved.commVisible) Object.keys(saved.commVisible).forEach(function (g) { if (g in commVisible) commVisible[g] = saved.commVisible[g]; });
    if (saved.selectedWords) {
      var restored = {};
      Object.keys(saved.selectedWords).forEach(function (id) { if (nodeMap[id] && saved.selectedWords[id]) restored[id] = true; });
      if (Object.keys(restored).length) selectedWords = restored;
    }
    if (typeof saved.wordSelectMode === 'boolean') wordSelectMode = saved.wordSelectMode;
  }

  function egoSet(start, hops) {
    var seen = {}; seen[start] = true; var frontier = [start];
    for (var h = 0; h < hops; h++) {
      var next = [];
      frontier.forEach(function (x) {
        (adj[x] || []).forEach(function (y) { if (!seen[y]) { seen[y] = true; next.push(y); } });
      });
      frontier = next;
    }
    return Object.keys(seen).map(Number);
  }

  function topLabelIds() {
    var set = {};
    var arr = rawNodes.slice().sort(function (a, b) { return getMetricValue(b, cfg.sizeBy) - getMetricValue(a, cfg.sizeBy); });
    arr.slice(0, cfg.labelTopN).forEach(function (n) { set[n.id] = true; });
    return set;
  }

  var emptyDetailHtml = '<div class="empty"><svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#8b98a8" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="1.4" fill="#8b98a8"/></svg><br>노드를 클릭하면<br>상세 지표가 표시됩니다</div>';

  function syncControlsFromCfg() {
    document.getElementById('selShape').value = cfg.shape;
    document.getElementById('selSizeBy').value = cfg.sizeBy;
    document.getElementById('numSizeMin').value = cfg.sizeMin;
    document.getElementById('numSizeMax').value = cfg.sizeMax;
    document.getElementById('rangeBorderWidth').value = cfg.borderWidth;
    document.getElementById('borderWidthVal').innerText = cfg.borderWidth;
    document.getElementById('colorBorder').value = cfg.borderColor;
    document.getElementById('selColorBy').value = cfg.colorBy;
    document.getElementById('colorUniform').value = cfg.colorUniform;
    document.getElementById('selGradMetric').value = cfg.colorGradMetric;
    document.getElementById('colorGradLow').value = cfg.colorGradLow;
    document.getElementById('colorGradHigh').value = cfg.colorGradHigh;
    document.getElementById('gridUniform').classList.toggle('show', cfg.colorBy === 'uniform');
    document.getElementById('gridGradient').classList.toggle('show', cfg.colorBy === 'gradient');
    document.getElementById('chkLabelShow').checked = cfg.labelShow;
    document.getElementById('chkLabelTop').checked = cfg.labelTopOnly;
    document.getElementById('rangeLabelTopN').value = cfg.labelTopN;
    document.getElementById('labelTopNVal').innerText = cfg.labelTopN;
    document.getElementById('rangeFontSize').value = cfg.fontSize;
    document.getElementById('fontSizeVal').innerText = cfg.fontSize;
    document.getElementById('colorFont').value = cfg.fontColor;
    document.getElementById('colorEdge').value = cfg.edgeColor;
    document.getElementById('rangeEdgeOpacity').value = cfg.edgeOpacity;
    document.getElementById('edgeOpVal').innerText = cfg.edgeOpacity.toFixed(2);
    document.getElementById('numEdgeMin').value = cfg.edgeWidthMin;
    document.getElementById('numEdgeMax').value = cfg.edgeWidthMax;
    document.getElementById('chkEdgeSmooth').checked = cfg.edgeSmooth;
    document.getElementById('chkArrows').checked = cfg.arrows;
    document.getElementById('chkZoomWheel').checked = cfg.zoomWheel;
    document.getElementById('chkDragNodes').checked = cfg.dragNodes;
    document.getElementById('colorBgCenter').value = cfg.bgCenter;
    document.getElementById('colorBgEdge').value = cfg.bgEdge;
    document.getElementById('wslider').value = cfg.minWeight;
    document.getElementById('wnum').value = round4(cfg.minWeight);
    document.getElementById('fslider').value = cfg.minFreq;
    document.getElementById('fnum').value = cfg.minFreq;
    document.getElementById('chkHideIsolated').checked = cfg.hideIsolated;
    document.getElementById('chkWordMode').checked = wordSelectMode;
  }

  function round4(v) { return Math.round(v * 10000) / 10000; }

  function applyBackground() {
    bgContainer.style.background = 'radial-gradient(ellipse at 50% 38%,' + cfg.bgCenter + ' 0%,' + cfg.bgEdge + ' 100%)';
  }

  function computeNodeColor(n) {
    if (cfg.colorBy === 'community') { var pal = currentPalette(); return commColors[n.group] || pal[((n.group % pal.length) + pal.length) % pal.length]; }
    if (cfg.colorBy === 'uniform') return cfg.colorUniform;
    var r = metricRangeOf(cfg.colorGradMetric);
    var val = getMetricValue(n, cfg.colorGradMetric);
    var t = (val - r.min) / ((r.max - r.min) || 1);
    return lerpColor(cfg.colorGradLow, cfg.colorGradHigh, Math.max(0, Math.min(1, t)));
  }

  // vis-network의 value 기반 크기 스케일링은 "현재 데이터셋에 실제로 들어있는 노드들"의
  // 최소·최대값을 기준으로 다시 정규화한다. 그래서 필터/이웃보기 등으로 보이는 노드
  // 집합이 바뀔 때마다 같은 노드인데도 반지름이 달라지는 문제가 있었다. 색상 그라디언트와
  // 마찬가지로 전체 노드(rawNodes) 기준 고정 범위로 우리가 직접 px 크기를 계산해 넣는다.
  function computeNodeSize(n) {
    var r = metricRangeOf(cfg.sizeBy);
    var val = getMetricValue(n, cfg.sizeBy);
    var t = (val - r.min) / ((r.max - r.min) || 1);
    return cfg.sizeMin + Math.max(0, Math.min(1, t)) * (cfg.sizeMax - cfg.sizeMin);
  }

  function renderGraph() {
    var filteredNodes = rawNodes.filter(function (n) {
      if (n.freq < cfg.minFreq) return false;
      if (commVisible[n.group] === false) return false;
      if (wordSelectMode && !selectedWords[n.id]) return false;
      return true;
    });
    var idSet = {}; filteredNodes.forEach(function (n) { idSet[n.id] = true; });
    var filteredEdges = rawEdges.filter(function (e) { return e.weight >= cfg.minWeight && idSet[e.source] && idSet[e.target]; });

    if (cfg.hideIsolated) {
      var connected = {};
      filteredEdges.forEach(function (e) { connected[e.source] = true; connected[e.target] = true; });
      filteredNodes = filteredNodes.filter(function (n) { return connected[n.id]; });
      idSet = {}; filteredNodes.forEach(function (n) { idSet[n.id] = true; });
      filteredEdges = filteredEdges.filter(function (e) { return idSet[e.source] && idSet[e.target]; });
    }

    currentVisibleIds = {}; filteredNodes.forEach(function (n) { currentVisibleIds[n.id] = true; });

    var strokeColor = cfg.theme === 'dark' ? '#212121' : '#ffffff';
    // dot/star/diamond 등은 라벨이 노드 아래쪽에 고정 오프셋으로 그려져서, 노드 크기가
    // 제각각이고 촘촘히 겹친 구간에서는 어느 라벨이 어느 원의 것인지 헷갈리기 쉽다.
    // 라벨 뒤에 반투명 배경 칩을 깔아 텍스트를 독립된 태그처럼 보이게 해서 완화한다.
    var labelBg = cfg.theme === 'dark' ? 'rgba(33,33,33,0.72)' : 'rgba(255,255,255,0.72)';
    var labelSet = (cfg.labelShow && cfg.labelTopOnly) ? topLabelIds() : null;

    var displayNodes = filteredNodes.map(function (n) {
      var showLabel = cfg.labelShow && (!labelSet || labelSet[n.id]);
      var hasXY = (n.x !== null && n.x !== undefined && n.y !== null && n.y !== undefined);
      var d = {
        id: n.id,
        label: showLabel ? n.label : undefined,
        size: computeNodeSize(n),
        shape: cfg.shape,
        color: {
          background: computeNodeColor(n), border: cfg.borderColor,
          highlight: { background: computeNodeColor(n), border: '#4C78A8' }
        },
        borderWidth: cfg.borderWidth,
        font: { color: cfg.fontColor, size: cfg.fontSize, face: 'Malgun Gothic', strokeWidth: 3, strokeColor: strokeColor, background: labelBg }
      };
      if (hasXY) { d.x = n.x; d.y = n.y; }
      return d;
    });

    var edgeIdSeen = {};
    var displayEdges = filteredEdges.map(function (e) {
      var base = e.source + '_' + e.target;
      var n = (edgeIdSeen[base] = (edgeIdSeen[base] || 0) + 1);
      var id = n > 1 ? base + '_' + n : base;
      return { id: id, from: e.source, to: e.target, value: e.weight };
    });

    var newNodeIds = displayNodes.map(function (n) { return n.id; });
    var oldNodeIds = nodes.getIds();
    var nodesToRemove = oldNodeIds.filter(function (id) { return newNodeIds.indexOf(id) === -1; });
    nodes.update(displayNodes);
    if (nodesToRemove.length > 0) nodes.remove(nodesToRemove);

    var newEdgeIds = displayEdges.map(function (e) { return e.id; });
    var oldEdgeIds = edges.getIds();
    var edgesToRemove = oldEdgeIds.filter(function (id) { return newEdgeIds.indexOf(id) === -1; });
    edges.update(displayEdges);
    if (edgesToRemove.length > 0) edges.remove(edgesToRemove);

    document.getElementById('liveBadge').innerHTML = '<span class="pulse"></span>표시 중 ' + filteredNodes.length.toLocaleString() + '개 노드 · ' + filteredEdges.length.toLocaleString() + '개 엣지';
    updateStats(filteredNodes, filteredEdges);
  }

  function updateStats(fnodes, fedges) {
    var N = fnodes.length, E = fedges.length;
    var deg = {}; fnodes.forEach(function (n) { deg[n.id] = 0; });
    var wsum = 0;
    fedges.forEach(function (e) { if (deg[e.from] != null) deg[e.from]++; if (deg[e.to] != null) deg[e.to]++; wsum += e.value; });
    var isolated = 0; fnodes.forEach(function (n) { if (deg[n.id] === 0) isolated++; });
    var density = N > 1 ? (2 * E) / (N * (N - 1)) : 0;
    var avgDeg = N > 0 ? (2 * E) / N : 0;
    var parent = {}; fnodes.forEach(function (n) { parent[n.id] = n.id; });
    function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
    fedges.forEach(function (e) {
      if (parent[e.from] != null && parent[e.to] != null) { var a = find(e.from), b = find(e.to); if (a !== b) parent[a] = b; }
    });
    var roots = {}; fnodes.forEach(function (n) { roots[find(n.id)] = true; });
    var comps = Object.keys(roots).length;
    var avgW = E > 0 ? wsum / E : 0;
    var visComm = {}; fnodes.forEach(function (n) { visComm[n.group] = true; });
    function row(a, b) { return '<div class="stat"><span>' + a + '</span><span>' + b + '</span></div>'; }
    var html = '';
    html += row('노드 수', N.toLocaleString());
    html += row('엣지 수', E.toLocaleString());
    html += row('밀도(density)', density.toFixed(4));
    html += row('평균 연결정도', avgDeg.toFixed(2));
    html += row('연결요소 수', comps.toLocaleString());
    html += row('고립 노드', isolated.toLocaleString());
    html += row('표시 커뮤니티', Object.keys(visComm).length.toLocaleString());
    html += row('평균 엣지 가중치', avgW.toFixed(2));
    document.getElementById('stats').innerHTML = html;
  }

  function getNetworkOptions() {
    return {
      layout: { improvedLayout: false },
      nodes: {
        // 노드를 클릭/선택해도 크기가 커지지 않도록 고정 (선택 시 크기가 바뀌어 되돌리기 어렵다는 피드백 반영).
        // 크기 자체는 renderGraph()에서 size로 직접 계산해 넣으므로 value 기반 scaling은 쓰지 않는다.
        chosen: {
          node: function (values) { /* no-op: keep original size, don't enlarge on select/hover */ },
          label: false
        }
      },
      edges: {
        color: { color: cfg.edgeColor, highlight: cfg.theme === 'dark' ? '#8fb3dd' : '#2c3e50', opacity: cfg.edgeOpacity },
        smooth: cfg.edgeSmooth ? { type: 'continuous' } : false,
        arrows: { to: { enabled: cfg.arrows } },
        scaling: { min: cfg.edgeWidthMin, max: cfg.edgeWidthMax },
        selectionWidth: 2
      },
      // 물리 엔진은 배치가 흔들리고 결과가 일관되지 않는다는 피드백에 따라 사용하지 않음.
      // 분석 시 서버에서 계산해 둔 좌표(x, y)를 고정 배치로 그대로 사용한다.
      physics: { enabled: false },
      interaction: { zoomView: cfg.zoomWheel, dragNodes: cfg.dragNodes, hover: true, tooltipDelay: 120, navigationButtons: false, keyboard: false }
    };
  }

  function applyOptions() {
    if (!net) return;
    net.setOptions(getNetworkOptions());
    net.redraw();
  }

  // ---- 토스트 ----
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

  function updateSelCount() {
    var c = 0; rawNodes.forEach(function (n) { if (selectedWords[n.id]) c++; });
    document.getElementById('selCount').innerText = c + ' / ' + rawNodes.length;
  }
  function buildWordList() {
    var box = document.getElementById('wlBox');
    var q = (document.getElementById('wlSearch').value || '').trim();
    var html = '';
    wlOrder.forEach(function (n) {
      if (q && n.label.indexOf(q) < 0) return;
      html += '<label class="wl-item"><input type="checkbox" data-id="' + n.id + '"' + (selectedWords[n.id] ? ' checked' : '') + '>'
        + '<span class="wl-name">' + esc(n.label) + '</span><span class="wl-freq">' + n.freq + '</span></label>';
    });
    box.innerHTML = html || '<div class="empty" style="padding:18px">일치하는 단어가 없습니다</div>';
    updateSelCount();
  }
  function syncWordChecks() {
    var boxes = document.querySelectorAll('#wlBox input[data-id]');
    boxes.forEach(function (b) { b.checked = !!selectedWords[b.getAttribute('data-id')]; });
    updateSelCount();
  }
  function visibleWlIds() {
    var q = (document.getElementById('wlSearch').value || '').trim();
    return wlOrder.filter(function (n) { return !q || n.label.indexOf(q) >= 0; }).map(function (n) { return n.id; });
  }

  function communityKeywordsHtml(g) {
    if (!summary || !summary.community_keywords) return '';
    var ck = summary.community_keywords.filter(function (c) { return c.group === g; })[0];
    if (!ck) return '';
    var freqWords = ck.top_freq.map(function (w) { return esc(w.label); }).join(', ');
    var hubWords = ck.top_internal_degree.map(function (w) { return esc(w.label); }).join(', ');
    return '<div class="comm-keywords">'
      + '<div class="kw-line"><b>핵심어(빈도)</b> ' + (freqWords || '-') + '</div>'
      + '<div class="kw-line"><b>응집 허브어(내부연결)</b> ' + (hubWords || '-') + '</div>'
      + '</div>';
  }

  function buildLegend() {
    var legend = document.getElementById('legend');
    document.getElementById('commCount').innerText = communityIds.length;
    if (!communityIds.length) { legend.innerHTML = '<div class="empty">표시할 커뮤니티가 없습니다</div>'; return; }
    var html = '';
    var pal = currentPalette();
    communityIds.forEach(function (c) {
      var col = commColors[c] || pal[((c % pal.length) + pal.length) % pal.length];
      html += '<div class="comm-row">'
        + '<input type="checkbox" class="comm-vis" data-g="' + c + '"' + (commVisible[c] !== false ? ' checked' : '') + '>'
        + '<input type="color" class="comm-color" data-g="' + c + '" value="' + col + '">'
        + '<input type="text" class="comm-name" data-g="' + c + '" value="' + escAttr(commNames[c] || ('커뮤니티 ' + c)) + '">'
        + '<span class="comm-cnt">' + (communityCounts[c] || 0) + '</span>'
        + '<button class="comm-focus" data-g="' + c + '" title="이 커뮤니티로 이동">⤢</button>'
        + '</div>'
        + communityKeywordsHtml(c);
    });
    legend.innerHTML = html;
  }

  function showDetail(n) {
    if (!currentVisibleIds[n.id]) {
      document.getElementById('detail').innerHTML = '<div class="empty">현재 필터에 의해<br>숨겨진 노드입니다</div>';
      return;
    }
    var cname = commNames[n.group] || ('커뮤니티 ' + n.group);
    var h = '<div class="node-title">' + esc(n.label) + '</div>' +
      '<div class="node-sub"><span class="chip">' + esc(cname) + '</span><span>빈도 ' + n.freq + '</span></div>';
    var info = n.info || {};
    Object.keys(info).forEach(function (k) {
      if (info[k] == null) return;
      h += '<div class="metric"><span>' + (mnames[k] || k) + '</span><span>' + info[k] + '</span></div>';
    });
    h += '<div class="btn-row" style="margin-top:14px">'
      + '<button class="btn btn-sm" data-ego="1" data-node="' + n.id + '" style="flex:1">이웃만 보기</button>'
      + '<button class="btn btn-sm" data-ego="2" data-node="' + n.id + '" style="flex:1">2단계 이웃</button>'
      + '</div>'
      + '<button class="btn btn-sm" data-focusnode="' + n.id + '" style="width:100%">이 노드로 이동</button>';
    document.getElementById('detail').innerHTML = h;
    net.selectNodes([n.id]);
    // scale을 강제로 지정하면 클릭할 때마다 현재 확대/축소 배율이 바뀌어 노드가
    // 커졌다 작아졌다 하는 것처럼 보인다. scale을 생략하면 현재 배율을 유지한 채
    // 화면만 이동한다.
    net.focus(n.id, { animation: { duration: 400 } });
  }

  function fallbackCopy(text, cb) {
    var ta = document.createElement('textarea'); ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px'; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); if (cb) cb(); } catch (err) { alert('복사에 실패했습니다.'); }
    document.body.removeChild(ta);
  }

  function updateZoomDisplay() {
    if (net) document.getElementById('zoomval').innerText = Math.round(net.getScale() * 100) + '%';
  }
  function clampScale(s) { return Math.max(0.02, Math.min(20, s)); }

  function setWeightHint() {
    var p = summary && summary.weight_percentiles;
    var el = document.getElementById('wHint');
    if (!p) { el.textContent = ''; return; }
    el.textContent = '참고: 중앙값 ' + p.p50 + ' · 상위 25% ' + p.p75 + ' · 상위 10% ' + p.p90 + ' — 관계가 너무 많으면 p75~p90 부근부터 올려보세요.';
  }
  function setFreqHint() {
    var p = summary && summary.freq_percentiles;
    var el = document.getElementById('fHint');
    if (!p) { el.textContent = ''; return; }
    el.textContent = '참고: 중앙값 ' + p.p50 + ' · 상위 25% ' + p.p75 + ' · 상위 10% ' + p.p90;
  }

  var eventsBound = false;
  function bindEventsOnce() {
    if (eventsBound) return;
    eventsBound = true;

    // ---- 오른쪽 패널에서 바뀌는 설정은 모두 프로젝트별로 자동 저장 ----
    var sideEl = document.getElementById('side');
    sideEl.addEventListener('input', scheduleSaveSettings);
    sideEl.addEventListener('change', scheduleSaveSettings);
    sideEl.addEventListener('click', scheduleSaveSettings);

    document.getElementById('search').addEventListener('input', function (e) {
      var q = e.target.value.trim();
      if (!q) { net.unselectAll(); return; }
      var hit = rawNodes.filter(function (n) { return n.label.indexOf(q) >= 0; });
      if (hit.length) {
        showDetail(hit[0]);
      } else {
        net.unselectAll();
        document.getElementById('detail').innerHTML = '<div class="empty">"' + esc(q) + '"과(와)<br>일치하는 단어가 없습니다</div>';
      }
    });

    function setMinWeight(v) {
      cfg.minWeight = v;
      document.getElementById('wslider').value = v;
      document.getElementById('wnum').value = round4(v);
      renderGraph();
    }
    function setMinFreq(v) {
      cfg.minFreq = v;
      document.getElementById('fslider').value = v;
      document.getElementById('fnum').value = v;
      renderGraph();
    }
    document.getElementById('wslider').addEventListener('input', function (e) { setMinWeight(parseFloat(e.target.value)); });
    document.getElementById('wnum').addEventListener('change', function (e) {
      var v = Math.max(0, parseFloat(e.target.value) || 0);
      var max = parseFloat(document.getElementById('wslider').max);
      if (v > max) { document.getElementById('wslider').max = v; }
      setMinWeight(v);
    });
    document.getElementById('fslider').addEventListener('input', function (e) { setMinFreq(parseInt(e.target.value, 10)); });
    document.getElementById('fnum').addEventListener('change', function (e) {
      var v = Math.max(0, parseInt(e.target.value, 10) || 0);
      var max = parseInt(document.getElementById('fslider').max, 10);
      if (v > max) { document.getElementById('fslider').max = v; }
      setMinFreq(v);
    });
    document.getElementById('chkHideIsolated').addEventListener('change', function (e) { cfg.hideIsolated = e.target.checked; renderGraph(); });

    document.getElementById('chkWordMode').addEventListener('change', function (e) { wordSelectMode = e.target.checked; renderGraph(); });
    document.getElementById('wlSearch').addEventListener('input', buildWordList);
    document.getElementById('wlBox').addEventListener('change', function (e) {
      var t = e.target;
      if (t && t.matches && t.matches('input[data-id]')) {
        var id = t.getAttribute('data-id');
        if (t.checked) selectedWords[id] = true; else delete selectedWords[id];
        updateSelCount();
        if (wordSelectMode) renderGraph();
      }
    });
    document.getElementById('wlAll').addEventListener('click', function () { visibleWlIds().forEach(function (id) { selectedWords[id] = true; }); syncWordChecks(); if (wordSelectMode) renderGraph(); });
    document.getElementById('wlNone').addEventListener('click', function () { visibleWlIds().forEach(function (id) { delete selectedWords[id]; }); syncWordChecks(); if (wordSelectMode) renderGraph(); });
    document.getElementById('wlInvert').addEventListener('click', function () { visibleWlIds().forEach(function (id) { if (selectedWords[id]) delete selectedWords[id]; else selectedWords[id] = true; }); syncWordChecks(); if (wordSelectMode) renderGraph(); });
    document.getElementById('btnTopN').addEventListener('click', function () {
      var metric = document.getElementById('topMetric').value;
      var N = parseInt(document.getElementById('topN').value, 10) || 20;
      var sorted = rawNodes.slice().sort(function (a, b) { return getMetricValue(b, metric) - getMetricValue(a, metric); });
      selectedWords = {};
      sorted.slice(0, N).forEach(function (n) { selectedWords[n.id] = true; });
      wordSelectMode = true;
      document.getElementById('chkWordMode').checked = true;
      buildWordList();
      renderGraph();
      var ids = sorted.slice(0, N).map(function (n) { return n.id; });
      if (ids.length) net.fit({ nodes: ids, animation: true });
      toast('상위 ' + Math.min(N, sorted.length) + '개 단어 표시 (' + (mnames[metric] || metric) + ')');
    });
    document.getElementById('btnCopyWords').addEventListener('click', function () {
      var labels = []; wlOrder.forEach(function (n) { if (selectedWords[n.id]) labels.push(n.label); });
      var text = labels.join('\n');
      function done() { toast('복사됨: ' + labels.length + '개 단어'); }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text, done); });
      } else fallbackCopy(text, done);
    });

    document.getElementById('detail').addEventListener('click', function (e) {
      var t = e.target;
      var ego = t.getAttribute && t.getAttribute('data-ego');
      var fn = t.getAttribute && t.getAttribute('data-focusnode');
      if (ego != null) {
        var start = parseInt(t.getAttribute('data-node'), 10);
        var set = egoSet(start, parseInt(ego, 10));
        selectedWords = {}; set.forEach(function (id) { selectedWords[id] = true; });
        wordSelectMode = true;
        document.getElementById('chkWordMode').checked = true;
        buildWordList();
        renderGraph();
        if (set.length) net.fit({ nodes: set, animation: true });
        toast('이웃 ' + set.length + '개 단어만 표시');
      } else if (fn != null) {
        var id = parseInt(fn, 10);
        net.selectNodes([id]);
        net.focus(id, { animation: true });
      }
    });

    document.getElementById('selShape').addEventListener('change', function (e) { cfg.shape = e.target.value; renderGraph(); });
    document.getElementById('selSizeBy').addEventListener('change', function (e) { cfg.sizeBy = e.target.value; renderGraph(); });
    document.getElementById('numSizeMin').addEventListener('change', function (e) { var v = parseFloat(e.target.value) || 1; cfg.sizeMin = Math.min(v, cfg.sizeMax); e.target.value = cfg.sizeMin; applyOptions(); });
    document.getElementById('numSizeMax').addEventListener('change', function (e) { var v = parseFloat(e.target.value) || 50; cfg.sizeMax = Math.max(v, cfg.sizeMin); e.target.value = cfg.sizeMax; applyOptions(); });
    document.getElementById('rangeBorderWidth').addEventListener('input', function (e) { cfg.borderWidth = parseFloat(e.target.value); document.getElementById('borderWidthVal').innerText = cfg.borderWidth; renderGraph(); });
    document.getElementById('colorBorder').addEventListener('input', function (e) { cfg.borderColor = e.target.value; renderGraph(); });

    document.getElementById('selColorBy').addEventListener('change', function (e) {
      cfg.colorBy = e.target.value;
      document.getElementById('gridUniform').classList.toggle('show', cfg.colorBy === 'uniform');
      document.getElementById('gridGradient').classList.toggle('show', cfg.colorBy === 'gradient');
      renderGraph();
    });
    document.getElementById('colorUniform').addEventListener('input', function (e) { cfg.colorUniform = e.target.value; renderGraph(); });
    document.getElementById('selGradMetric').addEventListener('change', function (e) { cfg.colorGradMetric = e.target.value; renderGraph(); });
    document.getElementById('colorGradLow').addEventListener('input', function (e) { cfg.colorGradLow = e.target.value; renderGraph(); });
    document.getElementById('colorGradHigh').addEventListener('input', function (e) { cfg.colorGradHigh = e.target.value; renderGraph(); });

    document.getElementById('chkLabelShow').addEventListener('change', function (e) { cfg.labelShow = e.target.checked; renderGraph(); });
    document.getElementById('chkLabelTop').addEventListener('change', function (e) { cfg.labelTopOnly = e.target.checked; renderGraph(); });
    document.getElementById('rangeLabelTopN').addEventListener('input', function (e) { cfg.labelTopN = parseInt(e.target.value, 10); document.getElementById('labelTopNVal').innerText = cfg.labelTopN; if (cfg.labelShow && cfg.labelTopOnly) renderGraph(); });
    document.getElementById('rangeFontSize').addEventListener('input', function (e) { cfg.fontSize = parseFloat(e.target.value); document.getElementById('fontSizeVal').innerText = cfg.fontSize; renderGraph(); });
    document.getElementById('colorFont').addEventListener('input', function (e) { cfg.fontColor = e.target.value; renderGraph(); });

    document.getElementById('colorEdge').addEventListener('input', function (e) { cfg.edgeColor = e.target.value; applyOptions(); });
    document.getElementById('rangeEdgeOpacity').addEventListener('input', function (e) { cfg.edgeOpacity = parseFloat(e.target.value); document.getElementById('edgeOpVal').innerText = cfg.edgeOpacity.toFixed(2); applyOptions(); });
    document.getElementById('numEdgeMin').addEventListener('change', function (e) { var v = parseFloat(e.target.value) || 0.1; cfg.edgeWidthMin = Math.min(v, cfg.edgeWidthMax); e.target.value = cfg.edgeWidthMin; applyOptions(); });
    document.getElementById('numEdgeMax').addEventListener('change', function (e) { var v = parseFloat(e.target.value) || 1; cfg.edgeWidthMax = Math.max(v, cfg.edgeWidthMin); e.target.value = cfg.edgeWidthMax; applyOptions(); });
    document.getElementById('chkEdgeSmooth').addEventListener('change', function (e) { cfg.edgeSmooth = e.target.checked; applyOptions(); });
    document.getElementById('chkArrows').addEventListener('change', function (e) { cfg.arrows = e.target.checked; applyOptions(); });

    document.getElementById('chkZoomWheel').addEventListener('change', function (e) { cfg.zoomWheel = e.target.checked; applyOptions(); });
    document.getElementById('chkDragNodes').addEventListener('change', function (e) { cfg.dragNodes = e.target.checked; applyOptions(); });
    document.getElementById('btnFit').addEventListener('click', function () { net.fit({ animation: true }); });
    document.getElementById('colorBgCenter').addEventListener('input', function (e) { cfg.bgCenter = e.target.value; applyBackground(); });
    document.getElementById('colorBgEdge').addEventListener('input', function (e) { cfg.bgEdge = e.target.value; applyBackground(); });

    document.getElementById('btnZoomIn').addEventListener('click', function () { net.moveTo({ scale: clampScale(net.getScale() * 1.2) }); });
    document.getElementById('btnZoomOut').addEventListener('click', function () { net.moveTo({ scale: clampScale(net.getScale() / 1.2) }); });
    document.getElementById('btnZoomReset').addEventListener('click', function () { net.fit({ animation: true }); });

    document.getElementById('btnTheme').addEventListener('click', function () {
      try {
        cfg.theme = cfg.theme === 'light' ? 'dark' : 'light';
        document.body.classList.toggle('dark-theme', cfg.theme === 'dark');
        if (cfg.theme === 'dark') {
          cfg.bgCenter = '#2b2b2b'; cfg.bgEdge = '#212121';
          cfg.fontColor = '#eaeaea'; cfg.borderColor = '#2b2b2b'; cfg.edgeColor = '#5a5a5a';
          if (cfg.colorUniform === '#2c3e50') cfg.colorUniform = '#34495e';
        } else {
          cfg.bgCenter = '#ffffff'; cfg.bgEdge = '#ecf0f1';
          cfg.fontColor = '#2c3e50'; cfg.borderColor = '#ffffff'; cfg.edgeColor = '#bdc3c7';
          if (cfg.colorUniform === '#34495e') cfg.colorUniform = '#2c3e50';
        }
        syncControlsFromCfg();
        applyBackground();
        applyOptions();
        buildLegend();
        renderRail();
        renderGraph();
        if (net) requestAnimationFrame(function () { net.redraw(); });
      } catch (err) { console.error('테마 전환 실패:', err); }
    });

    var legendEl = document.getElementById('legend');
    legendEl.addEventListener('change', function (e) {
      var t = e.target, g = t.getAttribute && t.getAttribute('data-g'); if (g == null) return; g = parseInt(g, 10);
      if (t.classList.contains('comm-vis')) { commVisible[g] = t.checked; renderGraph(); }
      else if (t.classList.contains('comm-name')) { commNames[g] = t.value; }
    });
    legendEl.addEventListener('input', function (e) {
      var t = e.target, g = t.getAttribute && t.getAttribute('data-g'); if (g == null) return; g = parseInt(g, 10);
      if (t.classList.contains('comm-color')) { commColors[g] = t.value; if (cfg.colorBy === 'community') renderGraph(); }
    });
    legendEl.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('.comm-focus') : null;
      if (b) {
        var g = parseInt(b.getAttribute('data-g'), 10);
        var ids = rawNodes.filter(function (n) { return n.group === g && currentVisibleIds[n.id]; }).map(function (n) { return n.id; });
        if (ids.length) { net.selectNodes(ids); net.fit({ nodes: ids, animation: true }); }
        else toast('현재 표시된 노드가 없습니다');
      }
    });
    document.getElementById('commAll').addEventListener('click', function () { communityIds.forEach(function (c) { commVisible[c] = true; }); buildLegend(); renderGraph(); });
    document.getElementById('commNone').addEventListener('click', function () { communityIds.forEach(function (c) { commVisible[c] = false; }); buildLegend(); renderGraph(); });

    document.getElementById('btnExportPng').addEventListener('click', function () {
      try {
        var canvas = container.querySelector('canvas');
        canvas.toBlob(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url; a.download = 'network' + (currentTag ? currentTag : '') + '.png';
          document.body.appendChild(a); a.click(); document.body.removeChild(a);
          setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
          toast('PNG로 저장했습니다');
        });
      } catch (err) { toast('PNG 저장 실패'); }
    });
    document.getElementById('btnReset').addEventListener('click', function () {
      clearTimeout(saveSettingsTimer);
      clearSavedSettings(projectId);
      cfg = Object.assign({}, defaultCfg);
      initCommState();
      wordSelectMode = false;
      selectedWords = {}; rawNodes.forEach(function (n) { selectedWords[n.id] = true; });
      document.getElementById('chkWordMode').checked = false;
      document.getElementById('wlSearch').value = '';
      document.body.classList.remove('dark-theme');
      syncControlsFromCfg();
      buildWordList();
      buildLegend();
      applyBackground();
      applyOptions();
      renderGraph();
      renderRail();
      net.fit({ animation: true });
      toast('설정을 초기화했습니다');
    });

    net.on('click', function (p) {
      if (p.nodes.length) {
        showDetail(nodeMap[p.nodes[0]]);
        if (mobileQuery.matches) openMobileDrawer('side');
      } else {
        document.getElementById('detail').innerHTML = emptyDetailHtml;
      }
    });
    net.on('zoom', updateZoomDisplay);
  }

  // ---------------------------------------------------------------
  // 네트워크(재)구성
  // ---------------------------------------------------------------
  function boot() {
    cfg = Object.assign({}, defaultCfg);

    nodeMap = {}; rawNodes.forEach(function (n) { nodeMap[n.id] = n; });
    communityCounts = {};
    rawNodes.forEach(function (n) { communityCounts[n.group] = (communityCounts[n.group] || 0) + 1; });
    communityIds = Object.keys(communityCounts).map(Number).sort(function (a, b) { return a - b; });
    initCommState();
    initWordSel();

    adj = {}; rawNodes.forEach(function (n) { adj[n.id] = []; });
    rawEdges.forEach(function (e) { if (adj[e.source]) adj[e.source].push(e.target); if (adj[e.target]) adj[e.target].push(e.source); });

    wlOrder = rawNodes.slice().sort(function (a, b) { return b.freq - a.freq; });

    metricKeys = ['freq'];
    var seen = { freq: true };
    rawNodes.forEach(function (n) {
      if (!n.info) return;
      Object.keys(n.info).forEach(function (k) { if (!seen[k]) { seen[k] = true; metricKeys.push(k); } });
    });
    ['selSizeBy', 'selGradMetric', 'topMetric'].forEach(function (id) {
      var sel = document.getElementById(id);
      sel.innerHTML = '';
      metricKeys.forEach(function (k) {
        var o = document.createElement('option'); o.value = k; o.text = mnames[k] || k; sel.appendChild(o);
      });
    });

    applySavedSettings();
    document.body.classList.toggle('dark-theme', cfg.theme === 'dark');

    var maxFreq = metricRangeOf('freq').max;
    document.getElementById('fslider').max = Math.max(1, Math.ceil(maxFreq));
    document.getElementById('rangeLabelTopN').max = Math.max(1, rawNodes.length);
    var maxW = rawEdges.length ? Math.max.apply(null, rawEdges.map(function (e) { return e.weight; })) : 1;
    document.getElementById('wslider').max = maxW || 1;
    document.getElementById('wslider').step = Math.max(maxW / 200, 0.0001);
    setWeightHint();
    setFreqHint();

    syncControlsFromCfg();
    applyBackground();
    buildWordList();
    buildLegend();

    nodes.clear(); edges.clear();
    renderGraph();

    if (!net) {
      net = new vis.Network(container, { nodes: nodes, edges: edges }, getNetworkOptions());
      bindEventsOnce();
    } else {
      net.setOptions(getNetworkOptions());
    }
    net.fit({ animation: false });
    updateZoomDisplay();
  }

  bindRailEvents();
  loadMe();
  if (projectId) {
    loadRailProjects();
    loadNetwork(currentTag);
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
})();
