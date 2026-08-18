/* 계층도 시각화 — React Flow 등 새 의존성 없이 순수 SVG로 그린다(PLAN.md의
   "의존성 최소화" 원칙, ahp/PLAN.md 참고). 노드 수가 많지 않은 AHP 특성상
   재귀적 리프-기준 배치만으로 충분하다: 리프는 왼쪽부터 순서대로 한 칸씩 차지하고,
   내부 노드는 자식들의 x 평균에 놓인다. */
(function () {
  'use strict';

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

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function render(container, nodes) {
    container.innerHTML = '';
    if (!nodes || !nodes.length) {
      container.innerHTML = '<p style="padding:20px;color:var(--sidebar-muted);font-size:12.5px">표시할 계층이 없습니다.</p>';
      return;
    }
    const layout = buildLayout(nodes);
    const BOX_W = 150, BOX_H = 54, GAP_X = 22, GAP_Y = 60, PAD = 24;
    const width = layout.leafCount * (BOX_W + GAP_X) - GAP_X + PAD * 2;
    const height = (layout.maxLevel + 1) * (BOX_H + GAP_Y) - GAP_Y + PAD * 2;

    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);

    function centerOf(uuid) {
      const p = layout.positions[uuid];
      return {
        x: PAD + p.x * (BOX_W + GAP_X) + BOX_W / 2,
        y: PAD + p.level * (BOX_H + GAP_Y) + BOX_H / 2,
      };
    }

    layout.edges.forEach(function (edge) {
      const a = centerOf(edge[0]);
      const b = centerOf(edge[1]);
      const midY = (a.y + b.y) / 2;
      const path = document.createElementNS(svgNS, 'path');
      path.setAttribute(
        'd',
        'M' + a.x + ',' + (a.y + BOX_H / 2) +
        ' C ' + a.x + ',' + midY + ' ' + b.x + ',' + midY + ' ' + b.x + ',' + (b.y - BOX_H / 2)
      );
      path.setAttribute('class', 'hd-edge');
      svg.appendChild(path);
    });

    Object.keys(layout.positions).forEach(function (uuid) {
      const node = layout.byId[uuid];
      const p = layout.positions[uuid];
      const x = PAD + p.x * (BOX_W + GAP_X);
      const y = PAD + p.level * (BOX_H + GAP_Y);

      const fo = document.createElementNS(svgNS, 'foreignObject');
      fo.setAttribute('x', x);
      fo.setAttribute('y', y);
      fo.setAttribute('width', BOX_W);
      fo.setAttribute('height', BOX_H);
      fo.innerHTML = '<div xmlns="http://www.w3.org/1999/xhtml" class="hd-box' +
        (node.parent_id == null ? ' hd-root' : '') + '">' + esc(node.name) + '</div>';
      svg.appendChild(fo);
    });

    container.appendChild(svg);
  }

  window.AHPHierarchyDiagram = { render: render };
})();
