(function () {
  'use strict';

  function parseProjectId() {
    var m = location.pathname.match(/^\/viewer\/([^\/]+)\/?$/);
    return m ? decodeURIComponent(m[1]) : null;
  }
  var projectId = parseProjectId();
  var LAST_PROJECT_KEY = 'kv_last_project'; // 마지막으로 열었던 프로젝트 — 사이트를 새로 열 때 자동 선택

  var currentMeta = null;
  var graph = null;             // /api/projects/{id}/graph 응답: metadata,dov,dod,final_signal,filtered_words,periods,trace
  var currentPlotTab = 'dov';   // 'dov' | 'dod'
  var interpretationsList = [];
  var hasSource = false;
  var searchQuery = '';

  // 웹에는 별도의 "조정" 단계가 없다 — 체크한 단어는 그래프에서 바로 꺼진다(숨김).
  // 기본값은 전체 표시(hiddenWords 비어있음). 해석(interpret)의 검색 키워드는 이것과
  // 완전히 별개인 interpretKeywords로 관리한다(끄기=제외, 해석=검색이라 의미가 반대).
  var hiddenWords = {};
  var groupVisible = { strong_signal: true, weak_signal: true, latent_signal: true, well_known_signal: true };
  var currentDetailWord = null;

  var interpretKeywords = {};
  var interpKwSearchQuery = '';
  var currentInterpretation = null;

  var SIGNAL_KEYS = ['strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal'];
  var SIGNAL_LABEL = { strong_signal: '강한 신호', weak_signal: '약한 신호', latent_signal: '잠재 신호', well_known_signal: '알려진 신호' };

  // ---------------------------------------------------------------
  // 공통 유틸
  // ---------------------------------------------------------------
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }
  function escAttr(s) { return esc(s).replace(/"/g, '&quot;'); }
  function cssVar(name) { return getComputedStyle(document.body).getPropertyValue(name).trim(); }

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

  function fmtAnalyzedAt(iso) {
    try {
      var d = new Date(iso);
      return d.getFullYear() + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + String(d.getDate()).padStart(2, '0')
        + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    } catch (e) { return iso; }
  }

  // ---------------------------------------------------------------
  // 프로젝트 로드
  // ---------------------------------------------------------------
  function resetViewState() {
    hiddenWords = {};
    groupVisible = { strong_signal: true, weak_signal: true, latent_signal: true, well_known_signal: true };
    searchQuery = '';
    document.getElementById('search').value = '';
    currentDetailWord = null;
    interpretKeywords = {};
    interpKwSearchQuery = '';
    document.getElementById('interpKwSearch').value = '';
    currentInterpretation = null;
    document.getElementById('interpretResult').innerHTML = '';
  }

  function loadProject(id) {
    document.getElementById('loading').classList.remove('hide');
    return Promise.all([
      api('/api/projects/' + id + '/meta'),
      api('/api/projects/' + id + '/graph'),
    ]).then(function (res) {
      var meta = res[0], g = res[1];
      currentMeta = meta;
      graph = g;
      hasSource = !!meta.has_source;

      document.getElementById('projectName').textContent = meta.name || 'KEMKIM Analyzer';
      document.title = (meta.name || 'KEMKIM Analyzer') + ' · KEMKIM Analyzer';
      document.getElementById('emptyProject').hidden = true;
      highlightActiveRailItem();
      localStorage.setItem(LAST_PROJECT_KEY, id);
      renderAnalysisOptions(meta.analysis_options);
      renderFilteredWords();
      updateSourceStatusUI();
      loadInterpretations();

      currentPlotTab = 'dov';
      document.getElementById('tabKem').classList.add('active');
      document.getElementById('tabKim').classList.remove('active');
      resetViewState();
      resetZoomState();
      buildPlotSkeleton();
      applyTransform();
      applyVisibility();
      renderGroupLegend();
      renderWordList();
      renderInterpretKeywordPicker();
      updateWordBadge();
      resetDetail();
      document.getElementById('loading').classList.add('hide');
    }).catch(function (err) {
      document.getElementById('loading').innerHTML =
        '<div style="color:#e08a52;font-weight:700">불러오기 실패</div><div>' + esc(err.message) + '</div>';
    });
  }

  function switchPlotTab(tab) {
    if (!graph) return;
    currentPlotTab = tab;
    document.getElementById('tabKem').classList.toggle('active', tab === 'dov');
    document.getElementById('tabKim').classList.toggle('active', tab === 'dod');
    resetZoomState();
    buildPlotSkeleton();
    applyTransform();
    applyVisibility();
    renderGroupLegend();
    renderWordList();
    renderInterpretKeywordPicker();
    updateWordBadge();
    if (currentDetailWord && graph[currentPlotTab].coordinates[currentDetailWord]) {
      showDetail(currentDetailWord);
    } else {
      resetDetail();
    }
  }

  function analysisOptionsStatsHtml(opt) {
    if (!opt) return '';
    var labels = {
      csv_name: '분석 데이터', analyzed_at: '분석 시각', start_date: '분석 시작일', end_date: '분석 종료일',
      period: '분석 기간 단위', topword: '상위 단어 개수', weight: '계산 가중치',
      filter_option: '비일관 단어 필터링', trace_standard: '추적 기준', ani_option: '애니메이션',
      split_option: '분할 기준', split_custom: '분할 상위%',
    };
    var html = '';
    Object.keys(labels).forEach(function (k) {
      var v = opt[k];
      if (v === null || v === undefined || v === '') return;
      html += '<div class="stat"><span>' + esc(labels[k]) + '</span><span>' + esc(v) + '</span></div>';
    });
    return html;
  }

  function renderAnalysisOptions(opt) {
    var section = document.getElementById('optionsSection');
    var body = document.getElementById('analysisOptions');
    var html = analysisOptionsStatsHtml(opt);
    if (!html) { section.hidden = true; body.innerHTML = ''; return; }
    section.hidden = false;
    body.innerHTML = html;
  }

  function renderFilteredWords() {
    var section = document.getElementById('filteredSection');
    var box = document.getElementById('filteredWords');
    var words = (graph && graph.filtered_words) || [];
    document.getElementById('filteredCount').textContent = words.length;
    if (!words.length) { section.hidden = true; box.innerHTML = ''; return; }
    section.hidden = false;
    box.innerHTML = words.map(function (w) {
      return '<span class="signal-chip" style="cursor:default">' + esc(w) + '</span>';
    }).join('');
  }

  function showProjectProperties(p) {
    document.getElementById('propsTitle').textContent = p.name + ' · 속성';
    var html = '';
    html += '<div class="stat"><span>이름</span><span>' + esc(p.name) + '</span></div>';
    html += '<div class="stat"><span>생성일</span><span>' + esc(fmtAnalyzedAt(p.created_at)) + '</span></div>';
    if (p.updated_at && p.updated_at !== p.created_at) {
      html += '<div class="stat"><span>수정일</span><span>' + esc(fmtAnalyzedAt(p.updated_at)) + '</span></div>';
    }
    var s = p.summary || {};
    if (s.dov_words != null) html += '<div class="stat"><span>KEM 단어 수</span><span>' + s.dov_words + '</span></div>';
    if (s.dod_words != null) html += '<div class="stat"><span>KIM 단어 수</span><span>' + s.dod_words + '</span></div>';
    if (s.strong_signal != null) html += '<div class="stat"><span>핵심 신호어</span><span>' + s.strong_signal + '</span></div>';
    html += '<div class="stat"><span>해석 결과 개수</span><span>' + ((p.interpretations || []).length) + '</span></div>';
    html += analysisOptionsStatsHtml(p.analysis_options) || '<div class="empty">저장된 분석 설정이 없습니다</div>';
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

  function loadMe() {
    railApi('/api/me').then(function (me) {
      document.getElementById('railUserName').textContent = me.name || '';
      document.getElementById('railUserName').title = me.name || '';
    }).catch(function () { });
  }

  function loadRailProjects() {
    return railApi('/api/projects').then(function (body) {
      railProjects = body.projects || [];
      renderRail();
    }).catch(function (err) {
      if (err.message !== 'unauthorized') toast('프로젝트 목록을 불러오지 못했습니다.');
    });
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
      var s = p.summary || {};
      var meta = s.strong_signal != null ? '핵심 신호어 ' + s.strong_signal + '개' : '';
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
      item.querySelector('[data-act="props"]').addEventListener('click', function (e) { e.stopPropagation(); showProjectProperties(p); });
      item.querySelector('[data-act="rename"]').addEventListener('click', function (e) { e.stopPropagation(); startRailRename(item, p); });
      item.querySelector('[data-act="delete"]').addEventListener('click', function (e) { e.stopPropagation(); deleteRailProject(p); });
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
          document.title = newName + ' · KEMKIM Analyzer';
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
          graph = null;
          history.pushState(null, '', '/viewer');
          document.getElementById('projectName').textContent = 'KEMKIM Analyzer';
          document.title = 'KEMKIM Analyzer';
          document.getElementById('emptyProject').hidden = false;
          document.getElementById('wordBadge').innerHTML = '<span class="pulse"></span>-';
          renderAnalysisOptions(null);
          document.getElementById('plot').innerHTML = '';
        }
      });
    }).catch(function () { toast('삭제에 실패했습니다.'); });
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
  // 업로드 모달 : zip 업로드 / 토큰 CSV 새 분석
  // ---------------------------------------------------------------
  function setModalStatus(msg, cls) {
    var el = document.getElementById('modalStatus');
    el.textContent = msg || '';
    el.className = 'modal-status' + (cls ? ' ' + cls : '');
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
    }).catch(function (err) { progEl.hidden = true; statusEl.textContent = err.message || String(err); });
  }

  function startAnalyze() {
    if (!analyzeStage) return;
    var statusEl = document.getElementById('analyzeStatus');
    var sd = document.getElementById('optStartDate').value;
    var ed = document.getElementById('optEndDate').value;
    if (!sd || !ed) { statusEl.textContent = '분석 시작일/종료일을 선택해주세요.'; return; }
    var splitOption = document.getElementById('optSplit').value;
    var option = {
      startdate: sd.replace(/-/g, ''),
      enddate: ed.replace(/-/g, ''),
      period: document.getElementById('optPeriod').value,
      weight: parseFloat(document.getElementById('optWeight').value) || 0.1,
      topword: parseInt(document.getElementById('optTopword').value, 10) || 500,
      graph_wordcnt: parseInt(document.getElementById('optGraphWordcnt').value, 10) || 10,
      split_option: splitOption,
      split_custom: splitOption.indexOf('직접') === 0 ? String(parseInt(document.getElementById('optSplitCustom').value, 10) || 10) : null,
      trace_standard: document.getElementById('optTraceStandard').value,
      filter_option: document.getElementById('optFilter').checked,
      ani_option: document.getElementById('optAni').checked,
    };
    var name = document.getElementById('analyzeProjectName').value.trim();
    var btn = document.getElementById('btnStartAnalyze');
    statusEl.textContent = ''; btn.disabled = true;
    postJson('/api/projects/analyze/start', { stage_id: analyzeStage, name: name, option: option }).then(function (res) {
      btn.disabled = false;
      analyzeStage = null;
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
  // 산점도 (KEM / KIM) — 확대/축소·이동 지원
  // ---------------------------------------------------------------
  var scale = 1, panX = 0, panY = 0;
  var isPanning = false, panMoved = false, dragStart = null, dragOrigPan = null;
  var plotLayout = null;      // {xmin,xmax,ymin,ymax,pad,w,h}
  var pointEls = {};          // word -> {circle, label, quadrant, rank}
  var labelRankOrder = [];    // word들을 rank(축에서 먼 순) 오름차순으로 정렬한 배열
  var rafPending = false;

  function quadrantOf(x, y, ax, ay) {
    if (x >= ax && y >= ay) return 'strong_signal';
    if (x <= ax && y >= ay) return 'weak_signal';
    if (x <= ax && y <= ay) return 'latent_signal';
    return 'well_known_signal';
  }

  function layoutXY(x, y) {
    if (!plotLayout) return { cx: 0, cy: 0 };
    var L = plotLayout;
    return {
      cx: L.pad + (x - L.xmin) / (L.xmax - L.xmin) * (L.w - 2 * L.pad),
      cy: L.h - L.pad - (y - L.ymin) / (L.ymax - L.ymin) * (L.h - 2 * L.pad),
    };
  }

  function resetZoomState() { scale = 1; panX = 0; panY = 0; }

  function applyTransform() {
    var vp = document.getElementById('viewport');
    if (vp) vp.setAttribute('transform', 'translate(' + panX + ',' + panY + ') scale(' + scale + ')');
    var zv = document.getElementById('zoomval');
    if (zv) zv.textContent = Math.round(scale * 100) + '%';
  }

  function scheduleVisibilityUpdate() {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(function () { rafPending = false; applyVisibility(); });
  }

  function zoomBy(factor, cx, cy) {
    var wrap = document.getElementById('plotWrap');
    if (cx == null) cx = wrap.clientWidth / 2;
    if (cy == null) cy = wrap.clientHeight / 2;
    var newScale = Math.max(0.4, Math.min(16, scale * factor));
    var wx = (cx - panX) / scale, wy = (cy - panY) / scale;
    panX = cx - wx * newScale;
    panY = cy - wy * newScale;
    scale = newScale;
    applyTransform();
    scheduleVisibilityUpdate();
  }

  function buildPlotSkeleton() {
    var svg = document.getElementById('plot');
    pointEls = {};
    labelRankOrder = [];
    plotLayout = null;

    if (!graph) { svg.innerHTML = ''; return; }
    var section = graph[currentPlotTab];
    var coords = (section && section.coordinates) || {};
    var axis = section && section.axis;
    var words = Object.keys(coords);

    var wrap = document.getElementById('plotWrap');
    var w = wrap.clientWidth || 800, h = wrap.clientHeight || 600;
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);

    if (!words.length || !axis) {
      svg.innerHTML = '<text x="' + (w / 2) + '" y="' + (h / 2) + '" text-anchor="middle" fill="' + cssVar('--sidebar-muted') + '" font-size="13">표시할 좌표가 없습니다</text>';
      return;
    }

    var xs = words.map(function (k) { return coords[k][0]; }).concat([axis[0]]);
    var ys = words.map(function (k) { return coords[k][1]; }).concat([axis[1]]);
    var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs);
    var ymin = Math.min.apply(null, ys), ymax = Math.max.apply(null, ys);
    if (xmin === xmax) { xmin -= 1; xmax += 1; }
    if (ymin === ymax) { ymin -= 1; ymax += 1; }
    var pad = 46;
    plotLayout = { xmin: xmin, xmax: xmax, ymin: ymin, ymax: ymax, pad: pad, w: w, h: h };

    var colors = {
      strong_signal: cssVar('--strong-signal'), weak_signal: cssVar('--weak-signal'),
      latent_signal: cssVar('--latent-signal'), well_known_signal: cssVar('--well-known-signal'),
    };
    var mutedColor = cssVar('--sidebar-muted');
    var textColor = cssVar('--sidebar-text');

    var axisXY = layoutXY(axis[0], axis[1]);
    var axisX = axisXY.cx, axisY = axisXY.cy;

    var parts = [];
    parts.push('<g id="viewport">');
    parts.push('<rect x="' + axisX + '" y="' + pad + '" width="' + Math.max(0, w - pad - axisX) + '" height="' + Math.max(0, axisY - pad) + '" fill="' + colors.strong_signal + '" fill-opacity="0.05"></rect>');
    parts.push('<rect x="' + pad + '" y="' + pad + '" width="' + Math.max(0, axisX - pad) + '" height="' + Math.max(0, axisY - pad) + '" fill="' + colors.weak_signal + '" fill-opacity="0.05"></rect>');
    parts.push('<rect x="' + pad + '" y="' + axisY + '" width="' + Math.max(0, axisX - pad) + '" height="' + Math.max(0, h - pad - axisY) + '" fill="' + colors.latent_signal + '" fill-opacity="0.05"></rect>');
    parts.push('<rect x="' + axisX + '" y="' + axisY + '" width="' + Math.max(0, w - pad - axisX) + '" height="' + Math.max(0, h - pad - axisY) + '" fill="' + colors.well_known_signal + '" fill-opacity="0.05"></rect>');
    parts.push('<line x1="' + axisX + '" y1="' + pad + '" x2="' + axisX + '" y2="' + (h - pad) + '" stroke="' + mutedColor + '" stroke-width="1" stroke-dasharray="4 4"></line>');
    parts.push('<line x1="' + pad + '" y1="' + axisY + '" x2="' + (w - pad) + '" y2="' + axisY + '" stroke="' + mutedColor + '" stroke-width="1" stroke-dasharray="4 4"></line>');

    var ranked = words.slice().sort(function (a, b) {
      var da = Math.pow(coords[a][0] - axis[0], 2) + Math.pow(coords[a][1] - axis[1], 2);
      var db = Math.pow(coords[b][0] - axis[0], 2) + Math.pow(coords[b][1] - axis[1], 2);
      return db - da;
    });
    labelRankOrder = ranked;
    var rankOf = {};
    ranked.forEach(function (wd, i) { rankOf[wd] = i + 1; });

    words.forEach(function (word) {
      var xy = coords[word];
      var pos = layoutXY(xy[0], xy[1]);
      var quadrant = quadrantOf(xy[0], xy[1], axis[0], axis[1]);
      parts.push('<circle class="pt" data-word="' + escAttr(word) + '" cx="' + pos.cx + '" cy="' + pos.cy
        + '" r="4" fill="' + colors[quadrant] + '"></circle>');
      parts.push('<text class="pt-label" data-word="' + escAttr(word) + '" x="' + (pos.cx + 6) + '" y="' + (pos.cy + 3)
        + '" font-size="10.5" fill="' + textColor + '">' + esc(word) + '</text>');
    });
    parts.push('<g id="traceOverlay"></g>');
    parts.push('</g>');
    svg.innerHTML = parts.join('');

    var circleEls = svg.querySelectorAll('.pt');
    var labelEls = svg.querySelectorAll('.pt-label');
    circleEls.forEach(function (el) {
      var word = el.getAttribute('data-word');
      pointEls[word] = { circle: el, label: null, quadrant: quadrantOf(coords[word][0], coords[word][1], axis[0], axis[1]), rank: rankOf[word] };
    });
    labelEls.forEach(function (el) {
      var word = el.getAttribute('data-word');
      if (pointEls[word]) pointEls[word].label = el;
    });
  }

  function applyVisibility() {
    if (!plotLayout) return;
    var budget = Math.max(15, Math.min(labelRankOrder.length, Math.round(40 * scale)));
    Object.keys(pointEls).forEach(function (word) {
      var pe = pointEls[word];
      var groupOn = groupVisible[pe.quadrant];
      var visible = groupOn && !hiddenWords[word];
      var matched = !searchQuery || word.toLowerCase().indexOf(searchQuery) >= 0;

      pe.circle.style.display = visible ? '' : 'none';
      pe.circle.style.opacity = (visible && searchQuery && !matched) ? '0.15' : '1';
      pe.circle.setAttribute('r', (matched && searchQuery) ? '6' : '4');
      pe.circle.removeAttribute('stroke');
      pe.circle.removeAttribute('stroke-width');

      if (pe.label) {
        var forced = searchQuery && matched;
        var withinBudget = pe.rank <= budget;
        var showLabel = visible && (forced || withinBudget);
        pe.label.style.display = showLabel ? '' : 'none';
        pe.label.style.opacity = (showLabel && searchQuery && !matched) ? '0.15' : '1';
      }
    });
    document.getElementById('selCount').textContent = Object.keys(hiddenWords).length;
  }

  function bindPlotEvents() {
    var svg = document.getElementById('plot');
    var tooltip = document.getElementById('plotTooltip');

    svg.addEventListener('wheel', function (e) {
      if (!plotLayout) return;
      e.preventDefault();
      var rect = svg.getBoundingClientRect();
      var factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      zoomBy(factor, e.clientX - rect.left, e.clientY - rect.top);
    }, { passive: false });

    svg.addEventListener('mousedown', function (e) {
      if (!plotLayout) return;
      isPanning = true; panMoved = false;
      dragStart = { x: e.clientX, y: e.clientY };
      dragOrigPan = { x: panX, y: panY };
    });
    window.addEventListener('mousemove', function (e) {
      if (isPanning) {
        var dx = e.clientX - dragStart.x, dy = e.clientY - dragStart.y;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) panMoved = true;
        panX = dragOrigPan.x + dx; panY = dragOrigPan.y + dy;
        applyTransform();
        scheduleVisibilityUpdate();
        tooltip.style.display = 'none';
        return;
      }
      var t = e.target;
      if (t && t.classList && (t.classList.contains('pt') || t.classList.contains('pt-label'))) {
        var word = t.getAttribute('data-word');
        var section = graph[currentPlotTab];
        var xy = section.coordinates[word];
        tooltip.innerHTML = '<b>' + esc(word) + '</b>x ' + xy[0].toFixed(3) + ' · y ' + xy[1].toFixed(3);
        tooltip.style.display = 'block';
        var rect = svg.getBoundingClientRect();
        tooltip.style.left = (e.clientX - rect.left + 14) + 'px';
        tooltip.style.top = (e.clientY - rect.top + 10) + 'px';
      } else {
        tooltip.style.display = 'none';
      }
    });
    window.addEventListener('mouseup', function () { isPanning = false; });
    svg.addEventListener('mouseleave', function () { tooltip.style.display = 'none'; });

    svg.addEventListener('click', function (e) {
      if (panMoved) { panMoved = false; return; }
      var t = e.target;
      if (t && t.classList && (t.classList.contains('pt') || t.classList.contains('pt-label'))) {
        showDetail(t.getAttribute('data-word'));
        if (window.matchMedia('(max-width:1100px)').matches) openMobileDrawer('side');
      }
    });
  }

  function updateWordBadge() {
    if (!graph) { document.getElementById('wordBadge').innerHTML = '<span class="pulse"></span>-'; return; }
    var section = graph[currentPlotTab];
    var n = Object.keys(section.coordinates || {}).length;
    var strong = (section.signal && section.signal.strong_signal || []).length;
    document.getElementById('wordBadge').innerHTML = '<span class="pulse"></span>단어 ' + n.toLocaleString() + '개 · 강한 신호 ' + strong + '개';
  }

  // ---------------------------------------------------------------
  // 사분면 표시(그룹) 레전드
  // ---------------------------------------------------------------
  function renderGroupLegend() {
    var box = document.getElementById('groupLegend');
    if (!graph) { box.innerHTML = ''; return; }
    var signal = graph[currentPlotTab].signal || {};
    var html = '';
    SIGNAL_KEYS.forEach(function (sk) {
      var count = (signal[sk] || []).length;
      html += '<div class="group-row"><input type="checkbox" data-group="' + sk + '"' + (groupVisible[sk] ? ' checked' : '') + '>'
        + '<span class="signal-dot ' + sk + '"></span>'
        + '<span class="group-name">' + esc(SIGNAL_LABEL[sk]) + '</span>'
        + '<span class="group-cnt">' + count + '</span></div>';
    });
    box.innerHTML = html;
  }

  // ---------------------------------------------------------------
  // 단어 선택 · 표시 (해석 키워드로도 재사용됨)
  // ---------------------------------------------------------------
  function currentListedWords() {
    if (!graph) return [];
    var signal = graph[currentPlotTab].signal || {};
    var all = [];
    SIGNAL_KEYS.forEach(function (sk) {
      (signal[sk] || []).forEach(function (w) {
        if (!searchQuery || w.toLowerCase().indexOf(searchQuery) >= 0) all.push(w);
      });
    });
    return all;
  }

  function renderWordList() {
    var box = document.getElementById('wlBox');
    if (!graph) { box.innerHTML = ''; return; }
    var signal = graph[currentPlotTab].signal || {};
    var html = '';
    SIGNAL_KEYS.forEach(function (sk) {
      var list = (signal[sk] || []).filter(function (w) { return !searchQuery || w.toLowerCase().indexOf(searchQuery) >= 0; });
      if (!list.length) return;
      html += '<div class="wl-group-head"><span class="signal-dot ' + sk + '"></span>' + esc(SIGNAL_LABEL[sk]) + ' (' + list.length + ')</div>';
      list.forEach(function (w) {
        html += '<label class="wl-item"><input type="checkbox" data-word="' + escAttr(w) + '"' + (hiddenWords[w] ? ' checked' : '') + '><span class="wl-name">' + esc(w) + '</span></label>';
      });
    });
    box.innerHTML = html || '<div class="empty" style="padding:18px">일치하는 단어가 없습니다</div>';
    document.getElementById('selCount').textContent = Object.keys(hiddenWords).length;
  }

  function syncWlCheckbox(word) {
    try {
      var el = document.querySelector('#wlBox input[data-word="' + CSS.escape(word) + '"]');
      if (el) el.checked = !!hiddenWords[word];
    } catch (e) { /* CSS.escape 미지원 브라우저는 다음 목록 재구성 때 자연히 반영됨 */ }
  }

  function setWordHidden(word, hidden) {
    if (hidden) hiddenWords[word] = true; else delete hiddenWords[word];
    syncWlCheckbox(word);
    document.getElementById('selCount').textContent = Object.keys(hiddenWords).length;
    applyVisibility();
  }

  // ---------------------------------------------------------------
  // 해석용 키워드 피커 (단어 끄기와 완전히 별개의 선택 상태)
  // ---------------------------------------------------------------
  function currentInterpretableWords() {
    if (!graph) return [];
    var signal = graph[currentPlotTab].signal || {};
    var all = [];
    SIGNAL_KEYS.forEach(function (sk) {
      (signal[sk] || []).forEach(function (w) {
        if (!interpKwSearchQuery || w.toLowerCase().indexOf(interpKwSearchQuery) >= 0) all.push(w);
      });
    });
    return all;
  }

  function renderInterpretKeywordPicker() {
    var box = document.getElementById('interpKwChips');
    if (!graph) { box.innerHTML = ''; return; }
    var words = currentInterpretableWords();
    box.innerHTML = words.length ? words.map(function (w) {
      return '<label class="signal-chip' + (interpretKeywords[w] ? ' checked' : '') + '"><input type="checkbox" data-kw="' + escAttr(w) + '"'
        + (interpretKeywords[w] ? ' checked' : '') + '>' + esc(w) + '</label>';
    }).join('') : '<div class="hint">일치하는 단어가 없습니다</div>';
    document.getElementById('interpKwCount').textContent = Object.keys(interpretKeywords).length;
  }

  function setInterpretKeyword(word, checked) {
    if (checked) interpretKeywords[word] = true; else delete interpretKeywords[word];
    document.getElementById('interpKwCount').textContent = Object.keys(interpretKeywords).length;
    try {
      var chip = document.querySelector('#interpKwChips input[data-kw="' + CSS.escape(word) + '"]');
      if (chip) chip.closest('.signal-chip').classList.toggle('checked', checked);
    } catch (e) { /* 다음 렌더에서 자연히 반영됨 */ }
  }

  // ---------------------------------------------------------------
  // 단어 상세 (기간별 추이 스파크라인 + 이동 경로 추적)
  // ---------------------------------------------------------------
  function resetDetail() {
    currentDetailWord = null;
    clearTraceOverlay();
    document.getElementById('detail').innerHTML = '<div class="empty">산점도에서 점을 클릭하면<br>상세 지표와 기간별 추이가 표시됩니다</div>';
  }

  function membershipChips(word) {
    var chips = [];
    ['dov', 'dod'].forEach(function (tabKey) {
      var sig = graph[tabKey] && graph[tabKey].signal;
      if (!sig) return;
      SIGNAL_KEYS.forEach(function (sk) {
        if ((sig[sk] || []).indexOf(word) >= 0) {
          chips.push('<span class="signal-chip" style="cursor:default"><span class="signal-dot ' + sk + '"></span>' + (tabKey === 'dov' ? 'KEM' : 'KIM') + ' · ' + esc(SIGNAL_LABEL[sk]) + '</span>');
        }
      });
    });
    return chips.join(' ');
  }

  function sparklineSvg(values) {
    var w = 140, h = 26, pad = 2;
    var present = values.filter(function (v) { return v != null; });
    if (!present.length) return '';
    var mn = Math.min.apply(null, present), mx = Math.max.apply(null, present);
    if (mn === mx) { mn -= 1; mx += 1; }
    var step = values.length > 1 ? (w - 2 * pad) / (values.length - 1) : 0;
    var pts = [];
    values.forEach(function (v, i) {
      if (v == null) return;
      var x = pad + i * step;
      var y = h - pad - (v - mn) / (mx - mn) * (h - 2 * pad);
      pts.push(x + ',' + y);
    });
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none"><polyline points="' + pts.join(' ')
      + '" fill="none" stroke="' + cssVar('--accent') + '" stroke-width="1.6"></polyline></svg>';
  }

  function clearTraceOverlay() {
    var g = document.getElementById('traceOverlay');
    if (g) g.innerHTML = '';
  }

  function drawTraceOverlay(word) {
    clearTraceOverlay();
    var g = document.getElementById('traceOverlay');
    if (!g || !graph.trace) return;
    var pts = (graph.trace[currentPlotTab] || {})[word];
    if (!pts || pts.length < 2) return;
    var dotColor = cssVar('--text-strong');
    var html = '';
    var coordsStr = pts.map(function (p) { var xy = layoutXY(p.x, p.y); return xy.cx + ',' + xy.cy; }).join(' ');
    html += '<polyline class="trace-path" points="' + coordsStr + '"></polyline>';
    pts.forEach(function (p) {
      var xy = layoutXY(p.x, p.y);
      html += '<circle class="trace-dot" cx="' + xy.cx + '" cy="' + xy.cy + '" r="3" fill="' + dotColor + '"></circle>';
      html += '<text class="trace-label" x="' + (xy.cx + 5) + '" y="' + (xy.cy - 5) + '">' + esc(p.period) + '</text>';
    });
    g.innerHTML = html;
  }

  function showDetail(word) {
    var section = graph[currentPlotTab];
    var xy = section.coordinates[word];
    if (!xy) return;
    currentDetailWord = word;

    var html = '';
    html += '<div style="font-size:19px;font-weight:800;margin-bottom:8px;color:var(--text-strong)">' + esc(word) + '</div>';
    html += '<div style="margin-bottom:10px">' + membershipChips(word) + '</div>';
    html += '<div class="metric"><span>' + (currentPlotTab === 'dov' ? '평균 단어 빈도(TF)' : '평균 문서 빈도(DF)') + '</span><span>' + xy[0].toFixed(4) + '</span></div>';
    html += '<div class="metric"><span>시간가중 증가율</span><span>' + xy[1].toFixed(4) + '</span></div>';

    var periodKeys = Object.keys(graph.periods || {}).sort();
    if (periodKeys.length) {
      var sparkHtml = '';
      ['TF', 'DF', 'DoV', 'DoD'].forEach(function (metric) {
        var values = periodKeys.map(function (pk) {
          var pd = graph.periods[pk];
          return (pd && pd[metric] && (word in pd[metric])) ? pd[metric][word] : null;
        });
        var spark = sparklineSvg(values);
        if (!spark) return;
        var last = null;
        for (var i = values.length - 1; i >= 0; i--) { if (values[i] != null) { last = values[i]; break; } }
        sparkHtml += '<div class="spark-row"><span class="spark-label">' + metric + '</span>' + spark
          + '<span class="spark-last">' + (last != null ? last.toFixed(2) : '-') + '</span></div>';
      });
      if (sparkHtml) {
        html += '<div class="row" style="margin-top:14px"><label>기간별 추이</label></div>' + sparkHtml;
      }
    }

    var tracePts = (graph.trace && graph.trace[currentPlotTab] && graph.trace[currentPlotTab][word]) || [];
    if (tracePts.length > 1) {
      html += '<div class="row" style="margin-top:14px"><label>이동 경로 (그래프에 점선 표시)</label></div>';
      tracePts.forEach(function (p) {
        html += '<div class="metric"><span>' + esc(p.period) + '</span><span>x ' + p.x.toFixed(3) + ' · y ' + p.y.toFixed(3) + '</span></div>';
      });
    }

    html += '<div class="chk-row" style="margin-top:14px">'
      + '<input type="checkbox" id="detailSelectChk" ' + (hiddenWords[word] ? 'checked' : '') + '>'
      + '<label for="detailSelectChk">이 단어 끄기 (그래프에서 숨기기)</label></div>';

    document.getElementById('detail').innerHTML = html;
    document.getElementById('detailSelectChk').addEventListener('change', function (e) {
      setWordHidden(word, e.target.checked);
    });

    drawTraceOverlay(word);
  }

  // ---------------------------------------------------------------
  // 해석
  // ---------------------------------------------------------------
  function updateSourceStatusUI() {
    document.getElementById('sourceFileLabel').textContent = hasSource
      ? '원본 CSV 첨부됨 (다시 올리면 교체)'
      : '원본(토큰화 전) CSV 업로드';
  }

  function uploadSource(file) {
    var statusEl = document.getElementById('sourceStatus');
    statusEl.textContent = ''; statusEl.className = 'modal-status';
    if (!file) return;
    if (!/\.csv$/i.test(file.name)) { statusEl.textContent = 'CSV 파일만 업로드할 수 있습니다.'; statusEl.className = 'modal-status err'; return; }

    var progEl = document.getElementById('sourceProgress');
    var fillEl = document.getElementById('sourceProgressFill');
    var labelEl = document.getElementById('sourceProgressLabel');
    progEl.hidden = false; fillEl.style.width = '0%'; labelEl.textContent = '업로드 중... 0%';

    var fd = new FormData();
    fd.append('file', file);
    uploadWithProgress('/api/projects/' + projectId + '/source', fd, function (pct) {
      fillEl.style.width = pct + '%'; labelEl.textContent = '업로드 중... ' + pct + '%';
    }).then(function () {
      progEl.hidden = true;
      hasSource = true;
      updateSourceStatusUI();
      statusEl.textContent = '원본 CSV가 저장되었습니다.'; statusEl.className = 'modal-status ok';
    }).catch(function (err) {
      progEl.hidden = true;
      statusEl.textContent = err.message || String(err); statusEl.className = 'modal-status err';
    });
  }

  function markContext(context, keyword) {
    var marker = '_____' + keyword + '_____';
    return esc(context).split(esc(marker)).join('<mark>' + esc(keyword) + '</mark>');
  }

  function renderInterpretResult(interp) {
    currentInterpretation = interp;
    var box = document.getElementById('interpretResult');
    var html = '';
    html += '<div class="interp-summary">매칭 문서 ' + (interp.matched_documents || 0).toLocaleString() + '건 · '
      + esc((interp.match_mode || 'or').toUpperCase()) + ' 검색 · ' + esc((interp.keywords || []).join(', ')) + '</div>';

    if (interp.ai_analysis) {
      html += '<div class="ai-box">' + esc(interp.ai_analysis) + '</div>';
    } else if (interp.ai_error) {
      html += '<div class="hint" style="color:var(--danger)">' + esc(interp.ai_error) + '</div>';
    }

    // 뉴스기사를 사이드바에 전부 풀어놓지 않고, 단어(키워드)당 한 줄만 보여준 뒤 클릭하면
    // 모달에서 기사 목록을 확인하도록 한다 — 목록 자체는 스크롤 가능한 고정 높이 박스.
    html += '<div class="wl-box" style="max-height:220px">';
    (interp.results || []).forEach(function (r) {
      html += '<div class="rev-item" data-kw-tab="' + escAttr(r.keyword) + '">'
        + '<span class="rev-label">' + esc(r.keyword) + '</span>'
        + '<span class="rev-date">' + r.count + '건</span></div>';
    });
    html += '</div>';

    if (interp.id) {
      html += '<a class="btn" style="display:block;text-align:center;text-decoration:none;margin-top:10px" href="/api/projects/' + projectId + '/interpretations/' + interp.id + '/export">CSV로 내보내기</a>';
    }
    box.innerHTML = html;
    box.querySelectorAll('[data-kw-tab]').forEach(function (el) {
      el.addEventListener('click', function () { openArticleModal(el.getAttribute('data-kw-tab')); });
    });
  }

  function openArticleModal(keyword) {
    if (!currentInterpretation) return;
    var entry = (currentInterpretation.results || []).find(function (r) { return r.keyword === keyword; });
    document.getElementById('articleModalTitle').textContent = keyword + ' · ' + (entry ? entry.count : 0) + '건';
    var body = document.getElementById('articleModalBody');
    var matches = (entry && entry.matches) || [];
    if (!matches.length) {
      body.innerHTML = '<div class="empty">매칭된 기사가 없습니다</div>';
    } else {
      body.innerHTML = matches.map(function (m, i) {
        return '<div class="interp-match">'
          + '<div class="im-meta">' + esc(m.title || '') + (m.date ? ' · ' + esc(m.date) : '') + '</div>'
          + '<div>' + markContext(m.context, keyword) + '</div>'
          + (m.full_text ? '<button class="btn btn-sm im-expand" data-idx="' + i + '">원문 보기</button>' +
            '<div class="im-full" data-idx="' + i + '" hidden></div>' : '')
          + '</div>';
      }).join('');
      body.querySelectorAll('.im-expand').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var idx = parseInt(btn.getAttribute('data-idx'), 10);
          var full = body.querySelector('.im-full[data-idx="' + idx + '"]');
          var isHidden = full.hidden;
          full.hidden = !isHidden;
          btn.textContent = isHidden ? '원문 접기' : '원문 보기';
          if (isHidden && !full.textContent) full.textContent = matches[idx].full_text;
        });
      });
    }
    closeMobileDrawers();
    document.getElementById('articleModal').hidden = false;
  }

  function doInterpret() {
    var keywords = Object.keys(interpretKeywords);
    var statusEl = document.getElementById('interpretStatus');
    if (!keywords.length) { statusEl.textContent = '해석할 키워드를 위 목록에서 선택해주세요.'; statusEl.className = 'modal-status err'; return; }
    if (!hasSource) { statusEl.textContent = '먼저 원본(토큰화 전) CSV를 업로드해주세요.'; statusEl.className = 'modal-status err'; return; }
    var matchMode = document.querySelector('input[name=matchMode]:checked').value;
    var useAi = document.getElementById('useAi').checked;
    var btn = document.getElementById('btnInterpret');
    btn.disabled = true;
    statusEl.textContent = '해석 실행 중...'; statusEl.className = 'modal-status';
    postJson('/api/projects/' + projectId + '/interpret', {
      keywords: keywords, match_mode: matchMode, use_ai: useAi
    }).then(function (interp) {
      btn.disabled = false;
      statusEl.textContent = '완료되었습니다.'; statusEl.className = 'modal-status ok';
      renderInterpretResult(interp);
      loadInterpretations();
    }).catch(function (err) {
      btn.disabled = false;
      statusEl.textContent = err.message || String(err); statusEl.className = 'modal-status err';
    });
  }

  function loadInterpretations() {
    api('/api/projects/' + projectId + '/interpretations').then(function (res) {
      interpretationsList = res.interpretations || [];
      renderInterpretationList();
    }).catch(function () { });
  }

  function renderInterpretationList() {
    var box = document.getElementById('interpretationList');
    if (!interpretationsList.length) { box.innerHTML = '<div class="empty" style="padding:14px 0">아직 해석 결과가 없습니다</div>'; return; }
    var html = '';
    interpretationsList.slice().reverse().forEach(function (it) {
      html += '<div class="rev-item" data-interp="' + escAttr(it.id) + '">'
        + '<span class="rev-label">' + esc((it.keywords || []).join(', ')) + (it.has_ai ? ' 🤖' : '') + '</span>'
        + '<span class="rev-date">' + esc(fmtAnalyzedAt(it.created_at)) + '</span></div>';
    });
    box.innerHTML = html;
    box.querySelectorAll('[data-interp]').forEach(function (el) {
      el.addEventListener('click', function () {
        var id = el.getAttribute('data-interp');
        api('/api/projects/' + projectId + '/interpretations/' + id).then(renderInterpretResult);
      });
    });
  }

  // ---------------------------------------------------------------
  // PNG 내보내기
  // ---------------------------------------------------------------
  function exportPlotPng() {
    try {
      var svg = document.getElementById('plot');
      var wrap = document.getElementById('plotWrap');
      var w = wrap.clientWidth, h = wrap.clientHeight;
      var clone = svg.cloneNode(true);
      clone.setAttribute('width', w);
      clone.setAttribute('height', h);
      var svgStr = new XMLSerializer().serializeToString(clone);
      var svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      var url = URL.createObjectURL(svgBlob);
      var img = new Image();
      img.onload = function () {
        var canvas = document.createElement('canvas');
        var ratio = 2;
        canvas.width = w * ratio; canvas.height = h * ratio;
        var ctx = canvas.getContext('2d');
        ctx.scale(ratio, ratio);
        ctx.fillStyle = document.body.classList.contains('dark-theme') ? '#212121' : '#ecf0f1';
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        URL.revokeObjectURL(url);
        canvas.toBlob(function (blob) {
          var link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = 'kemkim_' + currentPlotTab + '_' + (projectId || 'export') + '.png';
          document.body.appendChild(link); link.click(); document.body.removeChild(link);
          setTimeout(function () { URL.revokeObjectURL(link.href); }, 4000);
        });
        toast('PNG로 저장했습니다');
      };
      img.onerror = function () { URL.revokeObjectURL(url); toast('PNG 저장 실패'); };
      img.src = url;
    } catch (err) { toast('PNG 저장 실패'); }
  }

  // ---------------------------------------------------------------
  // 모바일 드로어 / 우클릭 메뉴 / 레일 리사이즈
  // ---------------------------------------------------------------
  var RAIL_MIN_WIDTH = 180, RAIL_MAX_WIDTH = 440, RAIL_DEFAULT_WIDTH = 236;
  var mobileQuery = window.matchMedia('(max-width:1100px)');

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

  function onPlotResize() {
    if (!graph) return;
    buildPlotSkeleton();
    applyTransform();
    applyVisibility();
    if (currentDetailWord) drawTraceOverlay(currentDetailWord);
  }

  function bindEvents() {
    var rail = document.getElementById('rail');
    var toggle = document.getElementById('railToggle');

    var collapsed = localStorage.getItem('kv_rail_collapsed') === '1';
    var savedWidth = parseInt(localStorage.getItem('kv_rail_width'), 10);
    if (!savedWidth || isNaN(savedWidth)) savedWidth = RAIL_DEFAULT_WIDTH;
    savedWidth = Math.max(RAIL_MIN_WIDTH, Math.min(RAIL_MAX_WIDTH, savedWidth));
    if (!mobileQuery.matches) {
      if (!collapsed) rail.style.width = savedWidth + 'px';
      rail.classList.toggle('collapsed', collapsed);
    }

    toggle.addEventListener('click', function () {
      if (mobileQuery.matches) { closeMobileDrawers(); return; }
      var isCollapsed = rail.classList.toggle('collapsed');
      localStorage.setItem('kv_rail_collapsed', isCollapsed ? '1' : '0');
      if (!isCollapsed) rail.style.width = savedWidth + 'px';
      setTimeout(onPlotResize, 200);
    });

    document.getElementById('mobileRailBtn').addEventListener('click', function () { openMobileDrawer('rail'); });
    document.getElementById('mobileSideBtn').addEventListener('click', function () { openMobileDrawer('side'); });
    document.getElementById('sideCloseBtn').addEventListener('click', closeMobileDrawers);
    document.getElementById('mobileBackdrop').addEventListener('click', closeMobileDrawers);

    var mqHandler = function () {
      rail.classList.remove('collapsed');
      rail.style.width = mobileQuery.matches ? '' : savedWidth + 'px';
      closeMobileDrawers();
      setTimeout(onPlotResize, 250);
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
      localStorage.setItem('kv_rail_width', String(savedWidth));
      onPlotResize();
    });

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
    document.addEventListener('click', function (e) { if (!ctxMenu.hidden && !ctxMenu.contains(e.target)) closeRailCtxMenu(); });
    document.addEventListener('contextmenu', function (e) { if (!ctxMenu.hidden && !ctxMenu.contains(e.target) && !e.target.closest('.rail-item')) closeRailCtxMenu(); });
    window.addEventListener('resize', function () { closeRailCtxMenu(); onPlotResize(); });
    window.addEventListener('scroll', closeRailCtxMenu, true);
    window.addEventListener('blur', closeRailCtxMenu);

    document.getElementById('propsModalClose').addEventListener('click', function () { document.getElementById('propsModal').hidden = true; });
    document.getElementById('propsModal').addEventListener('click', function (e) { if (e.target.id === 'propsModal') document.getElementById('propsModal').hidden = true; });

    document.getElementById('railUploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('emptyUploadBtn').addEventListener('click', openUploadModal);
    document.getElementById('uploadModalClose').addEventListener('click', closeUploadModal);
    document.getElementById('uploadModal').addEventListener('click', function (e) { if (e.target.id === 'uploadModal') closeUploadModal(); });
    window.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (!ctxMenu.hidden) closeRailCtxMenu();
      else if (!document.getElementById('articleModal').hidden) document.getElementById('articleModal').hidden = true;
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

    var analyzeInput = document.getElementById('analyzeFileInput');
    var analyzeDropzone = document.getElementById('analyzeDropzone');
    analyzeInput.addEventListener('change', function () { onAnalyzeFileSelected(analyzeInput.files[0]); analyzeInput.value = ''; });
    ['dragenter', 'dragover'].forEach(function (evt) { analyzeDropzone.addEventListener(evt, function (e) { e.preventDefault(); analyzeDropzone.classList.add('drag'); }); });
    ['dragleave', 'drop'].forEach(function (evt) { analyzeDropzone.addEventListener(evt, function (e) { e.preventDefault(); analyzeDropzone.classList.remove('drag'); }); });
    analyzeDropzone.addEventListener('drop', function (e) { onAnalyzeFileSelected(e.dataTransfer.files && e.dataTransfer.files[0]); });
    document.getElementById('btnStartAnalyze').addEventListener('click', startAnalyze);
    document.getElementById('optSplit').addEventListener('change', function () {
      document.getElementById('splitCustomField').hidden = this.value.indexOf('직접') !== 0;
    });

    document.getElementById('progressModalClose').addEventListener('click', closeProgressModal);

    document.getElementById('railLogout').addEventListener('click', function () {
      // 로그인은 knpu.re.kr 중앙 로그인이 전담하므로, 로그아웃도 그쪽 세션(쿠키)을 지운다
      fetch('https://knpu.re.kr/api/auth/logout', { method: 'POST', credentials: 'include' })
        .then(function () { location.href = 'https://knpu.re.kr/login'; });
    });

    document.getElementById('btnTheme').addEventListener('click', function () {
      var dark = document.body.classList.toggle('dark-theme');
      localStorage.setItem('kv_theme', dark ? 'dark' : 'light');
      renderRail();
      onPlotResize();
      renderGroupLegend();
    });

    // ---- 산점도 탭 / 확대·축소 ----
    document.getElementById('tabKem').addEventListener('click', function () { switchPlotTab('dov'); });
    document.getElementById('tabKim').addEventListener('click', function () { switchPlotTab('dod'); });
    document.getElementById('btnZoomIn').addEventListener('click', function () { zoomBy(1.3); });
    document.getElementById('btnZoomOut').addEventListener('click', function () { zoomBy(1 / 1.3); });
    document.getElementById('btnZoomReset').addEventListener('click', function () { resetZoomState(); applyTransform(); applyVisibility(); });
    bindPlotEvents();

    // ---- 검색 ----
    document.getElementById('search').addEventListener('input', function (e) {
      searchQuery = e.target.value.trim().toLowerCase();
      renderWordList();
      applyVisibility();
    });

    // ---- 사분면(그룹) 표시 토글 ----
    document.getElementById('groupLegend').addEventListener('change', function (e) {
      var g = e.target.getAttribute && e.target.getAttribute('data-group');
      if (!g) return;
      groupVisible[g] = e.target.checked;
      applyVisibility();
    });
    document.getElementById('groupAll').addEventListener('click', function () {
      SIGNAL_KEYS.forEach(function (k) { groupVisible[k] = true; });
      renderGroupLegend(); applyVisibility();
    });
    document.getElementById('groupNone').addEventListener('click', function () {
      SIGNAL_KEYS.forEach(function (k) { groupVisible[k] = false; });
      renderGroupLegend(); applyVisibility();
    });

    // ---- 단어 끄기 ----
    document.getElementById('wlSearch').addEventListener('input', function (e) {
      searchQuery = e.target.value.trim().toLowerCase();
      document.getElementById('search').value = e.target.value;
      renderWordList();
      applyVisibility();
    });
    document.getElementById('wlBox').addEventListener('change', function (e) {
      var t = e.target;
      if (t && t.matches('input[data-word]')) setWordHidden(t.getAttribute('data-word'), t.checked);
    });
    document.getElementById('wlAll').addEventListener('click', function () {
      currentListedWords().forEach(function (w) { hiddenWords[w] = true; });
      renderWordList(); applyVisibility();
    });
    document.getElementById('wlNone').addEventListener('click', function () {
      currentListedWords().forEach(function (w) { delete hiddenWords[w]; });
      renderWordList(); applyVisibility();
    });
    document.getElementById('wlInvert').addEventListener('click', function () {
      currentListedWords().forEach(function (w) { if (hiddenWords[w]) delete hiddenWords[w]; else hiddenWords[w] = true; });
      renderWordList(); applyVisibility();
    });

    // ---- 해석 ----
    document.getElementById('interpKwSearch').addEventListener('input', function (e) {
      interpKwSearchQuery = e.target.value.trim().toLowerCase();
      renderInterpretKeywordPicker();
    });
    document.getElementById('interpKwChips').addEventListener('change', function (e) {
      var t = e.target;
      if (t && t.matches('input[data-kw]')) setInterpretKeyword(t.getAttribute('data-kw'), t.checked);
    });
    document.getElementById('btnInterpret').addEventListener('click', doInterpret);
    document.getElementById('articleModalClose').addEventListener('click', function () { document.getElementById('articleModal').hidden = true; });
    document.getElementById('articleModal').addEventListener('click', function (e) { if (e.target.id === 'articleModal') document.getElementById('articleModal').hidden = true; });
    var sourceInput = document.getElementById('sourceFileInput');
    var sourceDropzone = document.getElementById('sourceDropzone');
    sourceInput.addEventListener('change', function () { uploadSource(sourceInput.files[0]); sourceInput.value = ''; });
    ['dragenter', 'dragover'].forEach(function (evt) { sourceDropzone.addEventListener(evt, function (e) { e.preventDefault(); sourceDropzone.classList.add('drag'); }); });
    ['dragleave', 'drop'].forEach(function (evt) { sourceDropzone.addEventListener(evt, function (e) { e.preventDefault(); sourceDropzone.classList.remove('drag'); }); });
    sourceDropzone.addEventListener('drop', function (e) { uploadSource(e.dataTransfer.files && e.dataTransfer.files[0]); });

    // ---- 내보내기 ----
    document.getElementById('btnExportPng').addEventListener('click', exportPlotPng);
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
        graph = null;
        document.getElementById('emptyProject').hidden = false;
        document.getElementById('projectName').textContent = 'KEMKIM Analyzer';
        document.getElementById('plot').innerHTML = '';
        renderAnalysisOptions(null);
      }
      highlightActiveRailItem();
    });
  }

  // ---------------------------------------------------------------
  // 초기화
  // ---------------------------------------------------------------
  if (localStorage.getItem('kv_theme') === 'dark') document.body.classList.add('dark-theme');

  bindEvents();
  loadMe();
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
})();
