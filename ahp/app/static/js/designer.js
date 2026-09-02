(function () {
  'use strict';

  const projectId = location.pathname.split('/')[2];
  let tree = { version: 0, nodes: [] };
  let alternatives = [];
  let dirty = false;
  let selectedParentId = null;
  const expanded = new Set();
  const BRAIN_KEY = 'ahp_brainstorm_' + projectId;

  function setDirty(v) {
    dirty = v;
    document.getElementById('dirtyBadge').hidden = !v;
  }
  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  function byId(id) { return tree.nodes.find(function (n) { return n.uuid === id; }); }
  function childrenOf(id) {
    return tree.nodes
      .filter(function (n) { return n.parent_id === id; })
      .sort(function (a, b) { return a.order - b.order; });
  }
  function root() { return tree.nodes.find(function (n) { return n.parent_id === null; }); }

  function descendantCount(id) {
    let count = 0;
    const stack = childrenOf(id).map(function (n) { return n.uuid; });
    while (stack.length) {
      const cur = stack.pop();
      count += 1;
      childrenOf(cur).forEach(function (c) { stack.push(c.uuid); });
    }
    return count;
  }

  // ── 트리 렌더링 ──────────────────────────────────────────────────────────
  function renderTree() {
    const rootNode = root();
    const container = document.getElementById('treeRoot');
    if (!rootNode) { container.innerHTML = ''; } else {
      container.innerHTML = '';
      container.appendChild(renderNode(rootNode));
    }
    // 계층도는 별도 버튼 없이 트리를 편집할 때마다(추가/삭제/이동/이름변경)
    // 항상 최신 상태로 갱신된다 — 팝업을 열어야만 보이던 이전 UX를 인라인으로 바꿈.
    window.AHPHierarchyDiagram.render(document.getElementById('diagramContainer'), tree.nodes);
  }

  function renderNode(node) {
    const kids = childrenOf(node.uuid);
    const wrap = document.createElement('div');
    wrap.className = 'tree-node';

    const row = document.createElement('div');
    row.className = 'tree-node-row' + (selectedParentId === node.uuid ? ' selected' : '');
    row.dataset.id = node.uuid;

    const toggle = document.createElement('span');
    toggle.className = 'tn-toggle' + (kids.length ? '' : ' leaf');
    toggle.textContent = kids.length ? (expanded.has(node.uuid) ? '▾' : '▸') : '';
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      if (!kids.length) return;
      if (expanded.has(node.uuid)) expanded.delete(node.uuid); else expanded.add(node.uuid);
      renderTree();
    });

    const main = document.createElement('div');
    main.className = 'tn-main';
    main.innerHTML = '<div class="tn-name">' + ahpEsc(node.name) + '</div>' +
      (node.description ? '<div class="tn-desc">' + ahpEsc(node.description) + '</div>' : '');
    main.addEventListener('click', function () {
      selectedParentId = node.uuid;
      renderTree();
    });

    const count = document.createElement('span');
    count.className = 'tn-count';
    count.hidden = !kids.length;
    count.textContent = kids.length + '개';

    const actions = document.createElement('div');
    actions.className = 'tn-actions';
    actions.innerHTML =
      '<button data-act="add" title="하위 항목 추가">＋</button>' +
      '<button data-act="edit" title="편집">✎</button>' +
      (node.parent_id !== null ? '<button data-act="up" title="위로">↑</button>' +
        '<button data-act="down" title="아래로">↓</button>' +
        '<button data-act="move" title="다른 항목의 하위로 이동">⇥</button>' +
        '<button data-act="del" class="danger" title="삭제">🗑</button>' : '');
    actions.addEventListener('click', function (e) {
      const btn = e.target.closest('button');
      if (!btn) return;
      e.stopPropagation();
      const act = btn.dataset.act;
      if (act === 'add') openAddChild(node.uuid);
      else if (act === 'edit') openEditNode(node.uuid);
      else if (act === 'up') moveSibling(node.uuid, -1);
      else if (act === 'down') moveSibling(node.uuid, 1);
      else if (act === 'move') openMoveTarget(node.uuid);
      else if (act === 'del') deleteNode(node.uuid);
    });

    row.appendChild(toggle);
    row.appendChild(main);
    row.appendChild(count);
    row.appendChild(actions);
    wrap.appendChild(row);

    if (kids.length && expanded.has(node.uuid)) {
      const childBox = document.createElement('div');
      childBox.className = 'tree-children';
      kids.forEach(function (k) { childBox.appendChild(renderNode(k)); });
      wrap.appendChild(childBox);
    } else if (!kids.length) {
      // 리프도 처음엔 접힘 상태로 취급하지 않도록(토글이 안 보이니 무해)
    }
    return wrap;
  }

  // 최초 로드시 전부 펼쳐서 보여준다(구조가 작을 때 파악이 쉽도록)
  function expandAll() {
    tree.nodes.forEach(function (n) { if (childrenOf(n.uuid).length) expanded.add(n.uuid); });
  }

  // ── 노드 편집 ────────────────────────────────────────────────────────────
  let editingNodeId = null;
  function openEditNode(id) {
    const node = byId(id);
    editingNodeId = id;
    document.getElementById('nodeEditTitle').textContent = node.parent_id === null ? '최상위 목표 편집' : '항목 편집';
    document.getElementById('nodeEditName').value = node.name;
    document.getElementById('nodeEditDesc').value = node.description || '';
    document.getElementById('nodeEditModal').hidden = false;
    document.getElementById('nodeEditName').focus();
  }

  function openAddChild(parentId) {
    const kids = childrenOf(parentId);
    const newNode = {
      uuid: crypto.randomUUID(),
      parent_id: parentId,
      name: '', description: '',
      order: kids.length ? Math.max.apply(null, kids.map(function (k) { return k.order; })) + 1 : 0,
    };
    tree.nodes.push(newNode);
    expanded.add(parentId);
    openEditNode(newNode.uuid);
  }

  function deleteNode(id) {
    const node = byId(id);
    if (node.parent_id === null) { ahpToast('최상위 목표는 삭제할 수 없습니다', true); return; }
    const n = descendantCount(id);
    const msg = n > 0
      ? ('"' + node.name + '"과(와) 하위 ' + n + '개 항목이 함께 삭제됩니다. 계속할까요?')
      : ('"' + node.name + '"을(를) 삭제할까요?');
    if (!confirm(msg)) return;
    const toRemove = new Set([id]);
    let changed = true;
    while (changed) {
      changed = false;
      tree.nodes.forEach(function (nd) {
        if (nd.parent_id && toRemove.has(nd.parent_id) && !toRemove.has(nd.uuid)) {
          toRemove.add(nd.uuid); changed = true;
        }
      });
    }
    tree.nodes = tree.nodes.filter(function (nd) { return !toRemove.has(nd.uuid); });
    setDirty(true);
    renderTree();
  }

  function moveSibling(id, dir) {
    const node = byId(id);
    const sibs = childrenOf(node.parent_id);
    const idx = sibs.findIndex(function (s) { return s.uuid === id; });
    const swapIdx = idx + dir;
    if (swapIdx < 0 || swapIdx >= sibs.length) return;
    const a = sibs[idx], b = sibs[swapIdx];
    const tmp = a.order; a.order = b.order; b.order = tmp;
    setDirty(true);
    renderTree();
  }

  // ── 재부모화(다른 항목의 하위로 이동) ───────────────────────────────────────
  function descendantIds(id) {
    const out = new Set();
    const stack = childrenOf(id).map(function (n) { return n.uuid; });
    while (stack.length) {
      const cur = stack.pop();
      out.add(cur);
      childrenOf(cur).forEach(function (c) { stack.push(c.uuid); });
    }
    return out;
  }

  let movingNodeId = null;
  function openMoveTarget(id) {
    movingNodeId = id;
    const excluded = descendantIds(id);
    excluded.add(id);
    const sel = document.getElementById('moveTargetSelect');
    sel.innerHTML = tree.nodes
      .filter(function (n) { return !excluded.has(n.uuid); })
      .slice()
      .sort(function (a, b) { return a.level - b.level; })
      .map(function (n) { return '<option value="' + n.uuid + '">' + '　'.repeat(n.level) + ahpEsc(n.name) + '</option>'; })
      .join('');
    document.getElementById('moveModal').hidden = false;
  }

  function moveNode() {
    const newParentId = document.getElementById('moveTargetSelect').value;
    if (!newParentId) { ahpToast('이동할 위치를 선택해 주세요', true); return; }
    const node = byId(movingNodeId);
    node.parent_id = newParentId;
    const sibs = childrenOf(newParentId).filter(function (s) { return s.uuid !== node.uuid; });
    node.order = sibs.length ? Math.max.apply(null, sibs.map(function (s) { return s.order; })) + 1 : 0;
    expanded.add(newParentId);
    setDirty(true);
    document.getElementById('moveModal').hidden = true;
    renderTree();
    ahpToast('이동했습니다. 저장을 눌러야 반영됩니다.');
  }

  // ── 대안 관리 ────────────────────────────────────────────────────────────
  function renderAltList() {
    const list = document.getElementById('altList');
    if (!alternatives.length) {
      list.innerHTML = '<p style="font-size:12px;color:var(--sidebar-muted)">비교할 대안을 추가해 주세요.</p>';
      return;
    }
    list.innerHTML = alternatives.slice().sort(function (a, b) { return a.order - b.order; }).map(function (a) {
      return '<div class="brain-card"><span class="bc-text">' + ahpEsc(a.name) + '</span>' +
        '<span class="bc-actions"><button data-act="remove-alt" data-id="' + a.uuid + '" title="삭제">×</button></span></div>';
    }).join('');
  }

  function addAlternative(name) {
    alternatives.push({ uuid: crypto.randomUUID(), name: name, description: '', order: alternatives.length });
    setDirty(true);
    renderAltList();
  }

  function removeAlternative(id) {
    alternatives = alternatives.filter(function (a) { return a.uuid !== id; });
    setDirty(true);
    renderAltList();
  }

  // ── 저장 ────────────────────────────────────────────────────────────────
  async function saveHierarchy() {
    const btn = document.getElementById('saveHierarchyBtn');
    btn.disabled = true;
    try {
      const payload = tree.nodes.map(function (n) {
        return { uuid: n.uuid, parent_id: n.parent_id, name: n.name, description: n.description, order: n.order };
      });
      const altPayload = alternatives.map(function (a) {
        return { uuid: a.uuid, name: a.name, description: a.description, order: a.order };
      });
      const res = await ahpApi('/api/projects/' + projectId + '/hierarchy', {
        method: 'PUT', body: { nodes: payload, alternatives: altPayload },
      });
      tree.version = res.version;
      tree.nodes = res.nodes;
      alternatives = res.alternatives || [];
      setDirty(false);
      renderWarnings(res.warnings || []);
      ahpToast('저장했습니다 (v' + res.version + ')');
      renderTree();
      renderAltList();
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    } finally {
      btn.disabled = false;
    }
  }

  function renderWarnings(warnings) {
    const box = document.getElementById('warningsBox');
    box.innerHTML = warnings.map(function (w) {
      return '<div class="warn-item">⚠ ' + ahpEsc(w.message) + '</div>';
    }).join('');
  }

  // ── 브레인스토밍 패드 ────────────────────────────────────────────────────
  function loadBrainCards() {
    try { return JSON.parse(localStorage.getItem(BRAIN_KEY) || '[]'); } catch (e) { return []; }
  }
  function saveBrainCards(cards) {
    localStorage.setItem(BRAIN_KEY, JSON.stringify(cards));
  }
  let brainCards = loadBrainCards();

  function renderBrainList() {
    const list = document.getElementById('brainList');
    if (!brainCards.length) {
      list.innerHTML = '<p style="font-size:12px;color:var(--sidebar-muted)">떠오르는 기준·항목을 자유롭게 적어보세요.</p>';
      return;
    }
    list.innerHTML = brainCards.map(function (c, i) {
      return '<div class="brain-card' + (c.promoted ? ' promoted' : '') + '">' +
        '<span class="bc-text">' + ahpEsc(c.text) + (c.promoted ? ' <small>(승격됨)</small>' : '') + '</span>' +
        '<span class="bc-actions">' +
        (c.promoted ? '' : '<button data-act="promote" data-i="' + i + '" title="트리로 승격">↗</button>') +
        '<button data-act="remove" data-i="' + i + '" title="삭제">×</button>' +
        '</span></div>';
    }).join('');
  }

  let promotingIndex = null;
  function openPromote(i) {
    promotingIndex = i;
    const sel = document.getElementById('promoteParentSelect');
    sel.innerHTML = tree.nodes
      .slice()
      .sort(function (a, b) { return a.level - b.level; })
      .map(function (n) { return '<option value="' + n.uuid + '">' + '　'.repeat(n.level) + ahpEsc(n.name) + '</option>'; })
      .join('');
    document.getElementById('promoteModal').hidden = false;
  }

  // ── 방법론 설정 모달 ──────────────────────────────────────────────────────
  async function openSettings() {
    const data = await ahpApi('/api/projects/' + projectId + '/settings');
    document.getElementById('setAggregation').value = data.settings.aggregation;
    document.getElementById('setWeightMethod').value = data.settings.weight_method;
    document.getElementById('setAltLayer').value = data.settings.alt_layer;
    document.getElementById('setIncomplete').value = data.settings.incomplete_policy;
    document.getElementById('setScale').value = String(data.settings.scale);
    document.getElementById('setCrThreshold').value = data.settings.cr_threshold;
    document.getElementById('setCrAction').value = data.settings.cr_action;
    document.getElementById('setCollectDemographics').value = data.settings.collect_demographics || 'off';

    document.getElementById('settingsLockNotice').hidden = !data.locked;
    ['setAggregation', 'setWeightMethod', 'setAltLayer', 'setScale'].forEach(function (id) {
      document.getElementById(id).disabled = !!data.locked;
    });
    document.getElementById('settingsModal').hidden = false;
  }

  async function saveSettings() {
    const body = {
      aggregation: document.getElementById('setAggregation').value,
      weight_method: document.getElementById('setWeightMethod').value,
      alt_layer: document.getElementById('setAltLayer').value,
      incomplete_policy: document.getElementById('setIncomplete').value,
      scale: Number(document.getElementById('setScale').value),
      cr_threshold: Number(document.getElementById('setCrThreshold').value),
      cr_action: document.getElementById('setCrAction').value,
      collect_demographics: document.getElementById('setCollectDemographics').value,
    };
    try {
      await ahpApi('/api/projects/' + projectId + '/settings', { method: 'PUT', body: body });
      document.getElementById('settingsModal').hidden = true;
      document.getElementById('altPanel').hidden = body.alt_layer !== 'on';
      ahpToast('설정을 저장했습니다');
    } catch (e) {
      ahpToast(e.message || '설정 저장에 실패했습니다', true);
    }
  }

  // ── 초기화 ──────────────────────────────────────────────────────────────
  async function init() {
    try {
      const project = await ahpApi('/api/projects/' + projectId);
      document.getElementById('projTitle').textContent = project.title;
      document.getElementById('altPanel').hidden = project.settings.alt_layer !== 'on';
      if (window.AHPShell) window.AHPShell.setActiveProject(projectId);
    } catch (e) {
      ahpToast('프로젝트를 불러오지 못했습니다', true);
      return;
    }

    const h = await ahpApi('/api/projects/' + projectId + '/hierarchy');
    tree = { version: h.version, nodes: h.nodes };
    alternatives = h.alternatives || [];
    selectedParentId = root() ? root().uuid : null;
    expandAll();
    renderTree();
    renderWarnings(h.warnings || []);
    renderBrainList();
    renderAltList();

    // 스테이지 탭 링크 연결
    document.querySelectorAll('#stageTabs .stage-tab').forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        e.preventDefault();
        const stage = tab.dataset.stage;
        if (stage === 'design') return;
        if (stage === 'survey') location.href = '/survey/' + projectId + '?from=project';
        if (stage === 'collect') location.href = '/collect/' + projectId + '?from=project';
        if (stage === 'result') location.href = '/result/' + projectId + '?from=project';
      });
    });

    document.getElementById('addRootChildBtn').addEventListener('click', function () {
      openAddChild(selectedParentId || (root() ? root().uuid : null));
    });
    document.getElementById('saveHierarchyBtn').addEventListener('click', saveHierarchy);
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); saveHierarchy(); }
    });

    function downloadDiagram(format) {
      if (!tree.nodes.length) { ahpToast('먼저 계층을 만들어 주세요', true); return; }
      const title = (document.getElementById('projTitle').textContent || '계층도').trim();
      window.AHPHierarchyDiagram.download(tree.nodes, { format: format, filename: title + '_계층도' });
    }
    document.getElementById('dlDiagramSvg').addEventListener('click', function () { downloadDiagram('svg'); });
    document.getElementById('dlDiagramPng').addEventListener('click', function () { downloadDiagram('png'); });

    document.getElementById('nodeEditClose').addEventListener('click', function () {
      document.getElementById('nodeEditModal').hidden = true;
    });
    document.getElementById('nodeEditSave').addEventListener('click', function () {
      const node = byId(editingNodeId);
      const name = document.getElementById('nodeEditName').value.trim();
      if (!name) { ahpToast('이름을 입력해 주세요', true); return; }
      node.name = name;
      node.description = document.getElementById('nodeEditDesc').value.trim();
      document.getElementById('nodeEditModal').hidden = true;
      setDirty(true);
      renderTree();
    });

    document.getElementById('altInput').addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      const text = e.target.value.trim();
      if (!text) return;
      addAlternative(text);
      e.target.value = '';
    });
    document.getElementById('altList').addEventListener('click', function (e) {
      const btn = e.target.closest('button');
      if (!btn || btn.dataset.act !== 'remove-alt') return;
      removeAlternative(btn.dataset.id);
    });

    document.getElementById('brainInput').addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      const text = e.target.value.trim();
      if (!text) return;
      brainCards.push({ text: text, promoted: false });
      saveBrainCards(brainCards);
      e.target.value = '';
      renderBrainList();
    });
    document.getElementById('brainList').addEventListener('click', function (e) {
      const btn = e.target.closest('button');
      if (!btn) return;
      const i = Number(btn.dataset.i);
      if (btn.dataset.act === 'remove') {
        brainCards.splice(i, 1);
        saveBrainCards(brainCards);
        renderBrainList();
      } else if (btn.dataset.act === 'promote') {
        openPromote(i);
      }
    });
    document.getElementById('moveClose').addEventListener('click', function () {
      document.getElementById('moveModal').hidden = true;
    });
    document.getElementById('moveSave').addEventListener('click', moveNode);

    document.getElementById('promoteClose').addEventListener('click', function () {
      document.getElementById('promoteModal').hidden = true;
    });
    document.getElementById('promoteSave').addEventListener('click', function () {
      const parentId = document.getElementById('promoteParentSelect').value;
      const card = brainCards[promotingIndex];
      const kids = childrenOf(parentId);
      tree.nodes.push({
        uuid: crypto.randomUUID(), parent_id: parentId,
        name: card.text, description: '',
        order: kids.length ? Math.max.apply(null, kids.map(function (k) { return k.order; })) + 1 : 0,
      });
      card.promoted = true;
      saveBrainCards(brainCards);
      expanded.add(parentId);
      setDirty(true);
      document.getElementById('promoteModal').hidden = true;
      renderBrainList();
      renderTree();
      ahpToast('트리에 추가했습니다. 저장을 눌러야 반영됩니다.');
    });

    document.getElementById('settingsBtn').addEventListener('click', openSettings);
    document.getElementById('settingsClose').addEventListener('click', function () {
      document.getElementById('settingsModal').hidden = true;
    });
    document.getElementById('settingsSave').addEventListener('click', saveSettings);

    document.getElementById('renameProjectBtn').addEventListener('click', async function () {
      const current = document.getElementById('projTitle').textContent;
      const next = prompt('새 프로젝트 이름', current);
      if (next === null) return;
      const trimmed = next.trim();
      if (!trimmed || trimmed === current) return;
      try {
        await ahpApi('/api/projects/' + projectId, { method: 'PUT', body: { title: trimmed } });
        document.getElementById('projTitle').textContent = trimmed;
        if (window.AHPShell) window.AHPShell.refreshProjects();
        ahpToast('이름을 변경했습니다');
      } catch (e) {
        ahpToast(e.message || '이름 변경에 실패했습니다', true);
      }
    });

    document.getElementById('deleteProjectBtn').addEventListener('click', async function () {
      const title = document.getElementById('projTitle').textContent;
      if (!confirm('"' + title + '"을(를) 삭제할까요?\n계층·설문지·수집된 모든 응답이 함께 삭제되며 되돌릴 수 없습니다.')) return;
      try {
        await ahpApi('/api/projects/' + projectId, { method: 'DELETE' });
        ahpToast('삭제했습니다');
        location.href = '/';
      } catch (e) {
        ahpToast(e.message || '삭제에 실패했습니다', true);
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
