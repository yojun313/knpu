/* 계층도 시각화 — React Flow 등 새 의존성 없이 순수 SVG로 그린다(PLAN.md의
   "의존성 최소화" 원칙, ahp/PLAN.md 참고). 노드 수가 많지 않은 AHP 특성상
   재귀적 리프-기준 배치만으로 충분하다: 리프는 왼쪽부터 순서대로 한 칸씩 차지하고,
   내부 노드는 자식들의 x 평균에 놓인다.

   render()  : 화면용. <foreignObject>+HTML로 그려 테마 CSS(admin.css)를 그대로 탄다.
   toSVGString()/download() : 논문·인쇄용. foreignObject 없이 <rect>+<text>로만 그리고
     색을 리터럴로 박은 "자립형" SVG를 만든다 — Inkscape/PowerPoint/Illustrator/PNG
     변환기 모두에서 그대로 열린다(foreignObject는 이들 대부분에서 안 보인다). */
(function () {
  'use strict';

  // render()와 toSVGString()이 공유하는 배치 기하 — 한 곳에서만 정의한다.
  var GEO = { BOX_W: 150, BOX_H: 54, GAP_X: 22, GAP_Y: 60, PAD: 24 };

  // 내보낸 SVG에 박아 넣는 색(기본 테마 팔레트의 리터럴 값 — admin.css 토큰과 대응).
  var PALETTE = {
    edge: '#bdc3c7',        // --sidebar-border
    boxFill: '#ffffff',     // --sidebar-bg
    boxStroke: '#bdc3c7',   // --sidebar-border
    boxText: '#16212c',     // --text-strong
    rootFill: '#2c3e50',    // --accent
    rootStroke: '#2c3e50',
    rootText: '#ffffff',
    font: "'Malgun Gothic','Pretendard',-apple-system,'Segoe UI',Roboto,sans-serif",
  };

  function buildLayout(nodes) {
    const byId = {};
    nodes.forEach(function (n) { byId[n.uuid] = n; });
    const childrenOf = {};
    nodes.forEach(function (n) {
      if (n.parent_id != null) {
        (childrenOf[n.parent_id] = childrenOf[n.parent_id] || []).push(n);
      }
    });
    Object.keys(childrenOf).forEach(function (pid) {
      childrenOf[pid].sort(function (a, b) { return a.order - b.order; });
    });
    const root = nodes.find(function (n) { return n.parent_id == null; });
    if (!root) return { positions: {}, edges: [], leafCount: 0, maxLevel: 0, byId: byId };

    let leafCounter = 0;
    const positions = {};
    function layout(node) {
      const kids = childrenOf[node.uuid] || [];
      if (!kids.length) {
        positions[node.uuid] = { x: leafCounter, level: node.level };
        leafCounter += 1;
        return positions[node.uuid].x;
      }
      const xs = kids.map(layout);
      const x = xs.reduce(function (a, b) { return a + b; }, 0) / xs.length;
      positions[node.uuid] = { x: x, level: node.level };
      return x;
    }
    layout(root);

    const edges = [];
    nodes.forEach(function (n) {
      if (n.parent_id != null && byId[n.parent_id]) edges.push([n.parent_id, n.uuid]);
    });
    const maxLevel = Math.max.apply(null, nodes.map(function (n) { return n.level; }).concat([0]));
    return {
      positions: positions, edges: edges,
      leafCount: Math.max(leafCounter, 1), maxLevel: maxLevel, byId: byId,
    };
  }

  // 화면·내보내기 공통: 캔버스 크기와 각 노드의 좌상단/중심 좌표.
  function metrics(layout) {
    const width = layout.leafCount * (GEO.BOX_W + GEO.GAP_X) - GEO.GAP_X + GEO.PAD * 2;
    const height = (layout.maxLevel + 1) * (GEO.BOX_H + GEO.GAP_Y) - GEO.GAP_Y + GEO.PAD * 2;
    function boxOf(uuid) {
      const p = layout.positions[uuid];
      return { x: GEO.PAD + p.x * (GEO.BOX_W + GEO.GAP_X), y: GEO.PAD + p.level * (GEO.BOX_H + GEO.GAP_Y) };
    }
    function centerOf(uuid) {
      const b = boxOf(uuid);
      return { x: b.x + GEO.BOX_W / 2, y: b.y + GEO.BOX_H / 2 };
    }
    function edgePath(parentUuid, childUuid) {
      const a = centerOf(parentUuid);
      const b = centerOf(childUuid);
      const midY = (a.y + b.y) / 2;
      return 'M' + a.x + ',' + (a.y + GEO.BOX_H / 2) +
        ' C ' + a.x + ',' + midY + ' ' + b.x + ',' + midY + ' ' + b.x + ',' + (b.y - GEO.BOX_H / 2);
    }
    return { width: width, height: height, boxOf: boxOf, centerOf: centerOf, edgePath: edgePath };
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // 박스 폭(150px, 12px bold)에 맞춰 이름을 최대 2줄로 자른다. 한국어는 공백이 없어
  // 글자 수 기준으로 끊고, 공백이 있으면 그 자리를 우선한다. 넘치면 말줄임.
  function wrapLabel(name, maxCharsPerLine, maxLines) {
    var text = String(name == null ? '' : name).trim();
    if (!text) return [''];
    var lines = [];
    var rest = text;
    while (rest.length && lines.length < maxLines) {
      if (rest.length <= maxCharsPerLine) { lines.push(rest); rest = ''; break; }
      var slice = rest.slice(0, maxCharsPerLine);
      var sp = slice.lastIndexOf(' ');
      var cut = sp > maxCharsPerLine * 0.5 ? sp : maxCharsPerLine;
      lines.push(rest.slice(0, cut).trim());
      rest = rest.slice(cut).trim();
    }
    if (rest.length && lines.length) {
      var last = lines[lines.length - 1];
      lines[lines.length - 1] = last.slice(0, Math.max(0, maxCharsPerLine - 1)).trim() + '…';
    }
    return lines;
  }

  function render(container, nodes) {
    container.innerHTML = '';
    if (!nodes || !nodes.length) {
      container.innerHTML = '<p style="padding:20px;color:var(--sidebar-muted);font-size:12.5px">표시할 계층이 없습니다.</p>';
      return;
    }
    const layout = buildLayout(nodes);
    const m = metrics(layout);

    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('width', m.width);
    svg.setAttribute('height', m.height);
    svg.setAttribute('viewBox', '0 0 ' + m.width + ' ' + m.height);

    layout.edges.forEach(function (edge) {
      const path = document.createElementNS(svgNS, 'path');
      path.setAttribute('d', m.edgePath(edge[0], edge[1]));
      path.setAttribute('class', 'hd-edge');
      svg.appendChild(path);
    });

    Object.keys(layout.positions).forEach(function (uuid) {
      const node = layout.byId[uuid];
      const b = m.boxOf(uuid);
      const fo = document.createElementNS(svgNS, 'foreignObject');
      fo.setAttribute('x', b.x);
      fo.setAttribute('y', b.y);
      fo.setAttribute('width', GEO.BOX_W);
      fo.setAttribute('height', GEO.BOX_H);
      fo.innerHTML = '<div xmlns="http://www.w3.org/1999/xhtml" class="hd-box' +
        (node.parent_id == null ? ' hd-root' : '') + '">' + esc(node.name) + '</div>';
      svg.appendChild(fo);
    });

    container.appendChild(svg);
  }

  // ── 논문·인쇄용 자립형 SVG ────────────────────────────────────────────────
  function buildSVG(nodes, opts) {
    opts = opts || {};
    var pal = Object.assign({}, PALETTE, opts.palette || {});
    var layout = buildLayout(nodes || []);
    var m = metrics(layout);
    var LH = 15; // 줄 높이(12px 글꼴 기준)

    var parts = [];
    parts.push(
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + m.width + '" height="' + m.height +
      '" viewBox="0 0 ' + m.width + ' ' + m.height + '" font-family="' + pal.font + '">'
    );
    parts.push(
      '<style>' +
      '.hd-e{fill:none;stroke:' + pal.edge + ';stroke-width:1.6}' +
      '.hd-b{fill:' + pal.boxFill + ';stroke:' + pal.boxStroke + ';stroke-width:1.5}' +
      '.hd-t{fill:' + pal.boxText + ';font-size:12px;font-weight:700}' +
      '.hd-r .hd-b{fill:' + pal.rootFill + ';stroke:' + pal.rootStroke + '}' +
      '.hd-r .hd-t{fill:' + pal.rootText + '}' +
      '</style>'
    );

    layout.edges.forEach(function (edge) {
      parts.push('<path class="hd-e" d="' + m.edgePath(edge[0], edge[1]) + '"/>');
    });

    Object.keys(layout.positions).forEach(function (uuid) {
      var node = layout.byId[uuid];
      var b = m.boxOf(uuid);
      var isRoot = node.parent_id == null;
      var cx = b.x + GEO.BOX_W / 2;
      var cy = b.y + GEO.BOX_H / 2;
      var lines = wrapLabel(node.name, 13, 2);
      var startDy = -((lines.length - 1) / 2) * LH;
      var tspans = lines.map(function (ln, i) {
        return '<tspan x="' + cx + '" dy="' + (i === 0 ? startDy : LH) + '">' + esc(ln) + '</tspan>';
      }).join('');
      parts.push(
        '<g class="' + (isRoot ? 'hd-r' : '') + '">' +
        '<rect class="hd-b" x="' + b.x + '" y="' + b.y + '" width="' + GEO.BOX_W +
        '" height="' + GEO.BOX_H + '" rx="10"/>' +
        '<text class="hd-t" x="' + cx + '" y="' + cy +
        '" text-anchor="middle" dominant-baseline="central">' + tspans + '</text>' +
        '</g>'
      );
    });

    parts.push('</svg>');
    return { svg: parts.join(''), width: m.width, height: m.height, empty: !layout.leafCount || !nodes || !nodes.length };
  }

  function toSVGString(nodes, opts) {
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + buildSVG(nodes, opts).svg;
  }

  function triggerDownload(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  // format: 'svg' | 'png'. png는 새 의존성 없이 <canvas>로 래스터화한다
  // (foreignObject를 안 써서 캔버스 오염 없이 변환된다).
  function download(nodes, opts) {
    opts = opts || {};
    var format = opts.format === 'png' ? 'png' : 'svg';
    var base = (opts.filename || '계층도').replace(/[\\/:*?"<>|]/g, '_');
    var built = buildSVG(nodes, opts);
    var xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + built.svg;

    if (format === 'svg') {
      triggerDownload(new Blob([xml], { type: 'image/svg+xml;charset=utf-8' }), base + '.svg');
      return;
    }

    var scale = opts.scale || 2;
    var img = new Image();
    img.onload = function () {
      var canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(built.width * scale));
      canvas.height = Math.max(1, Math.round(built.height * scale));
      var ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.drawImage(img, 0, 0, built.width, built.height);
      canvas.toBlob(function (blob) {
        if (blob) triggerDownload(blob, base + '.png');
      }, 'image/png');
    };
    img.onerror = function () { alert('PNG 변환에 실패했습니다. SVG로 내려받아 주세요.'); };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
  }

  window.AHPHierarchyDiagram = { render: render, toSVGString: toSVGString, download: download };
})();
