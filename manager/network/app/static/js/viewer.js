(function () {
  'use strict';

  var sessionId = location.pathname.replace(/\/$/, '').split('/').pop();
  var qs = new URLSearchParams(location.search);
  var currentTag = qs.get('tag') || '';

  var rawNodes = [], rawEdges = [];
  var summary = null;
  var net = null;
  var nodes = new vis.DataSet([]);
  var edges = new vis.DataSet([]);
  var container = document.getElementById('net');

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
      api('/api/graph/' + sessionId + '/data?tag=' + encodeURIComponent(tag)),
      api('/api/graph/' + sessionId + '/summary?tag=' + encodeURIComponent(tag)),
      api('/api/graph/' + sessionId + '/meta'),
    ]).then(function (res) {
      var data = res[0], summ = res[1], meta = res[2];
      rawNodes = data.nodes;
      rawEdges = data.edges;
      summary = summ;
      currentTag = tag;
      initNetworkSelect(meta);
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

  var palette = ['#4C78A8', '#F58518', '#54A24B', '#E45756', '#72B7B2', '#FF9DA6', '#9D755D',
    '#BAB0AC', '#B279A2', '#EECA3B', '#59A14F', '#9C755F', '#79706E', '#D37295', '#8CD17D'];

  function hexToRgb(h) { h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(function (c) { return c + c; }).join(''); var num = parseInt(h, 16); return [num >> 16 & 255, num >> 8 & 255, num & 255]; }
  function clamp255(x) { return Math.max(0, Math.min(255, Math.round(x))); }
  function rgbToHex(r, g, b) { return '#' + [r, g, b].map(function (x) { var s = clamp255(x).toString(16); return s.length < 2 ? '0' + s : s; }).join(''); }
  function lerpColor(a, b, t) { var A = hexToRgb(a), B = hexToRgb(b); return rgbToHex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t); }
  function esc(s) { return String(s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }
  function escAttr(s) { return esc(s).replace(/"/g, '&quot;'); }

  var defaultCfg = {
    shape: 'circle', sizeBy: 'freq', sizeMin: 6, sizeMax: 55,
    colorBy: 'community', colorUniform: '#4C78A8',
    colorGradMetric: 'freq', colorGradLow: '#dbe9f6', colorGradHigh: '#1428A0',
    borderWidth: 1.5, borderColor: '#ffffff',
    labelShow: true, labelTopOnly: false, labelTopN: 30, fontSize: 14, fontColor: '#2c3e50',
    edgeColor: '#9fb0c4', edgeOpacity: 0.55, edgeWidthMin: 0.5, edgeWidthMax: 6,
    edgeSmooth: false, arrows: false,
    physics: false, solver: 'barnesHut', gravity: -12000, springLength: 120, springConstant: 0.04, damping: 0.09,
    zoomWheel: true, dragNodes: true,
    bgCenter: '#ffffff', bgEdge: '#eef1f4', theme: 'light',
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
    document.getElementById('chkPhysics').checked = cfg.physics;
    document.getElementById('selSolver').value = cfg.solver;
    document.getElementById('rangeGravity').value = cfg.gravity;
    document.getElementById('gravityVal').innerText = cfg.gravity;
    document.getElementById('rangeSpringLen').value = cfg.springLength;
    document.getElementById('springLenVal').innerText = cfg.springLength;
    document.getElementById('rangeSpringConst').value = cfg.springConstant;
    document.getElementById('springConstVal').innerText = cfg.springConstant.toFixed(2);
    document.getElementById('rangeDamping').value = cfg.damping;
    document.getElementById('dampingVal').innerText = cfg.damping.toFixed(2);
    document.getElementById('chkZoomWheel').checked = cfg.zoomWheel;
    document.getElementById('chkDragNodes').checked = cfg.dragNodes;
    document.getElementById('colorBgCenter').value = cfg.bgCenter;
    document.getElementById('colorBgEdge').value = cfg.bgEdge;
    document.getElementById('wslider').value = cfg.minWeight;
    document.getElementById('wnum').value = round4(cfg.minWeight);
    document.getElementById('fslider').value = cfg.minFreq;
    document.getElementById('fnum').value = cfg.minFreq;
    document.getElementById('chkHideIsolated').checked = cfg.hideIsolated;
  }

  function round4(v) { return Math.round(v * 10000) / 10000; }

  function applyBackground() {
    container.style.background = 'radial-gradient(ellipse at 50% 38%,' + cfg.bgCenter + ' 0%,' + cfg.bgEdge + ' 100%)';
  }

  function computeNodeColor(n) {
    if (cfg.colorBy === 'community') return commColors[n.group] || palette[((n.group % palette.length) + palette.length) % palette.length];
    if (cfg.colorBy === 'uniform') return cfg.colorUniform;
    var r = metricRangeOf(cfg.colorGradMetric);
    var val = getMetricValue(n, cfg.colorGradMetric);
    var t = (val - r.min) / ((r.max - r.min) || 1);
    return lerpColor(cfg.colorGradLow, cfg.colorGradHigh, Math.max(0, Math.min(1, t)));
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

    var strokeColor = cfg.theme === 'dark' ? '#0c1017' : '#ffffff';
    var labelSet = (cfg.labelShow && cfg.labelTopOnly) ? topLabelIds() : null;

    var displayNodes = filteredNodes.map(function (n) {
      var showLabel = cfg.labelShow && (!labelSet || labelSet[n.id]);
      var hasXY = (n.x !== null && n.x !== undefined && n.y !== null && n.y !== undefined);
      var d = {
        id: n.id,
        label: showLabel ? n.label : undefined,
        value: getMetricValue(n, cfg.sizeBy),
        shape: cfg.shape,
        color: {
          background: computeNodeColor(n), border: cfg.borderColor,
          highlight: { background: computeNodeColor(n), border: '#4C78A8' }
        },
        borderWidth: cfg.borderWidth,
        font: { color: cfg.fontColor, size: cfg.fontSize, face: 'Malgun Gothic', strokeWidth: 3, strokeColor: strokeColor }
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

  var stabilizeTimeout = null;
  function getNetworkOptions() {
    return {
      layout: { improvedLayout: false },
      nodes: {
        scaling: { min: cfg.sizeMin, max: cfg.sizeMax },
        // 노드를 클릭/선택해도 크기가 커지지 않도록 고정 (선택 시 크기가 바뀌어 되돌리기 어렵다는 피드백 반영)
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
      physics: {
        enabled: cfg.physics,
        solver: cfg.solver,
        barnesHut: { gravitationalConstant: cfg.gravity, springLength: cfg.springLength, springConstant: cfg.springConstant, damping: cfg.damping },
        forceAtlas2Based: { gravitationalConstant: cfg.gravity, springLength: cfg.springLength, springConstant: cfg.springConstant, damping: cfg.damping },
        repulsion: { springLength: cfg.springLength, springConstant: cfg.springConstant, damping: cfg.damping },
        // 켜지면 스스로 안정화될 때까지만 계산하고 자동으로 멈춘다 (계속 흔들리는 문제 방지)
        stabilization: { enabled: cfg.physics, iterations: 300, updateInterval: 25, fit: false }
      },
      interaction: { zoomView: cfg.zoomWheel, dragNodes: cfg.dragNodes, hover: true, tooltipDelay: 120, navigationButtons: false, keyboard: false }
    };
  }

  function applyOptions() {
    if (!net) return;
    net.setOptions(getNetworkOptions());
    net.redraw();
    if (cfg.physics) {
      net.once('stabilizationIterationsDone', function () {
        cfg.physics = false;
        net.setOptions({ physics: { enabled: false } });
        document.getElementById('chkPhysics').checked = false;
      });
    }
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
    communityIds.forEach(function (c) {
      var col = commColors[c] || palette[((c % palette.length) + palette.length) % palette.length];
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
    net.focus(n.id, { scale: 1.1, animation: { duration: 400 } });
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
        net.focus(id, { scale: 1.3, animation: true });
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

    document.getElementById('chkPhysics').addEventListener('change', function (e) {
      if (stabilizeTimeout) { clearTimeout(stabilizeTimeout); stabilizeTimeout = null; }
      cfg.physics = e.target.checked; applyOptions();
    });
    document.getElementById('selSolver').addEventListener('change', function (e) { cfg.solver = e.target.value; applyOptions(); });
    document.getElementById('rangeGravity').addEventListener('input', function (e) { cfg.gravity = parseFloat(e.target.value); document.getElementById('gravityVal').innerText = cfg.gravity; applyOptions(); });
    document.getElementById('rangeSpringLen').addEventListener('input', function (e) { cfg.springLength = parseFloat(e.target.value); document.getElementById('springLenVal').innerText = cfg.springLength; applyOptions(); });
    document.getElementById('rangeSpringConst').addEventListener('input', function (e) { cfg.springConstant = parseFloat(e.target.value); document.getElementById('springConstVal').innerText = cfg.springConstant.toFixed(2); applyOptions(); });
    document.getElementById('rangeDamping').addEventListener('input', function (e) { cfg.damping = parseFloat(e.target.value); document.getElementById('dampingVal').innerText = cfg.damping.toFixed(2); applyOptions(); });
    document.getElementById('btnRestabilize').addEventListener('click', function () {
      if (stabilizeTimeout) { clearTimeout(stabilizeTimeout); stabilizeTimeout = null; }
      var wasPhysics = cfg.physics;
      cfg.physics = true; applyOptions();
      net.stabilize(300);
      if (!wasPhysics) {
        net.once('stabilizationIterationsDone', function () {
          cfg.physics = false; net.setOptions({ physics: { enabled: false } });
          document.getElementById('chkPhysics').checked = false;
        });
      }
    });

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
          cfg.bgCenter = '#141a24'; cfg.bgEdge = '#0c1017';
          cfg.fontColor = '#e6e8ee'; cfg.borderColor = '#0c1017'; cfg.edgeColor = '#3a4a5f';
        } else {
          cfg.bgCenter = '#ffffff'; cfg.bgEdge = '#eef1f4';
          cfg.fontColor = '#2c3e50'; cfg.borderColor = '#ffffff'; cfg.edgeColor = '#9fb0c4';
        }
        syncControlsFromCfg();
        applyBackground();
        applyOptions();
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
      cfg = Object.assign({}, defaultCfg);
      initCommState();
      wordSelectMode = false;
      selectedWords = {}; rawNodes.forEach(function (n) { selectedWords[n.id] = true; });
      document.getElementById('chkWordMode').checked = false;
      document.getElementById('wlSearch').value = '';
      syncControlsFromCfg();
      buildWordList();
      buildLegend();
      applyBackground();
      applyOptions();
      renderGraph();
      net.fit({ animation: true });
      toast('설정을 초기화했습니다');
    });

    net.on('click', function (p) {
      if (p.nodes.length) { showDetail(nodeMap[p.nodes[0]]); }
      else { document.getElementById('detail').innerHTML = emptyDetailHtml; }
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

  loadNetwork(currentTag);
})();
