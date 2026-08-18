(function () {
  'use strict';

  const collectionId = location.pathname.split('/')[2];
  let grid = { matrices: [], respondents: [] };
  let selectedRespondentId = null;
  let scaleMax = 9;

  function scaleOptionsHtml(nameA, nameB, currentAOverB) {
    const opts = [];
    for (let n = scaleMax; n >= 2; n--) {
      opts.push({ v: n, label: ahpEsc(nameA) + '가(이) ' + n + '배 더 중요' });
    }
    opts.push({ v: 1, label: '동일하게 중요' });
    for (let n = 2; n <= scaleMax; n++) {
      opts.push({ v: 1 / n, label: ahpEsc(nameB) + '가(이) ' + n + '배 더 중요' });
    }
    return opts.map(function (o) {
      const sel = Math.abs(o.v - currentAOverB) < 1e-6 ? ' selected' : '';
      return '<option value="' + o.v + '"' + sel + '>' + o.label + '</option>';
    }).join('');
  }

  function renderRespondents() {
    const box = document.getElementById('respondentList');
    if (!grid.respondents.length) {
      box.innerHTML = '<p style="padding:10px;font-size:12px;color:var(--sidebar-muted)">응답자를 추가해 주세요.</p>';
      return;
    }
    box.innerHTML = grid.respondents.map(function (r) {
      const sel = r.id === selectedRespondentId ? ' selected' : '';
      const statusDot = r.status === 'submitted' ? '✓ ' : '';
      return '<div class="entry-resp-item' + sel + '" data-id="' + r.id + '">' +
        '<span class="er-name">' + statusDot + ahpEsc(r.label) + '</span>' +
        '<button class="er-del" data-id="' + r.id + '" title="삭제">×</button></div>';
    }).join('');
  }

  function currentRespondent() {
    return grid.respondents.find(function (r) { return r.id === selectedRespondentId; });
  }

  function renderMatrices() {
    const box = document.getElementById('matricesForm');
    const resp = currentRespondent();
    if (!resp) {
      box.innerHTML = '<p style="color:var(--sidebar-muted);font-size:12.5px">왼쪽에서 응답자를 선택하세요.</p>';
      return;
    }
    if (!grid.matrices.length) {
      box.innerHTML = '<p style="color:var(--sidebar-muted);font-size:12.5px">비교할 항목이 없습니다.</p>';
      return;
    }
    box.innerHTML = grid.matrices.map(function (m) {
      const answers = resp.answers[m.matrix_id] || {};
      const rows = m.pairs.map(function (p) {
        const pid = [p.uuid_a, p.uuid_b].sort().join(':');
        const nameA = (m.children.find(function (c) { return c.uuid === p.uuid_a; }) || {}).name || p.uuid_a;
        const nameB = (m.children.find(function (c) { return c.uuid === p.uuid_b; }) || {}).name || p.uuid_b;
        const current = pid in answers ? answers[pid] : 1;
        return '<div class="entry-pair-row" data-matrix="' + m.matrix_id + '" data-a="' + p.uuid_a + '" data-b="' + p.uuid_b + '">' +
          '<span class="ep-label">' + ahpEsc(nameA) + ' vs ' + ahpEsc(nameB) + '</span>' +
          '<select>' + scaleOptionsHtml(nameA, nameB, current) + '</select></div>';
      }).join('');
      return '<div class="entry-matrix" data-matrix-block="' + m.matrix_id + '">' +
        '<div class="entry-matrix-head"><h4>' + ahpEsc(m.parent_name) + '</h4>' +
        '<span class="badge muted" data-cr-badge="' + m.matrix_id + '">-</span></div>' +
        rows + '</div>';
    }).join('');

    grid.matrices.forEach(function (m) { refreshCrBadge(m.matrix_id); });
  }

  function refreshCrBadge(matrixId) {
    const resp = currentRespondent();
    if (!resp) return;
    const answers = resp.answers[matrixId] || {};
    const m = grid.matrices.find(function (x) { return x.matrix_id === matrixId; });
    const badge = document.querySelector('[data-cr-badge="' + matrixId + '"]');
    if (!badge || !m) return;
    if (m.children.length <= 2) {
      badge.textContent = '비교 불필요';
      badge.className = 'badge muted';
      return;
    }
    if (Object.keys(answers).length < m.pairs.length) {
      badge.textContent = '미완료 (' + Object.keys(answers).length + '/' + m.pairs.length + ')';
      badge.className = 'badge muted';
      return;
    }
    // 서버가 PUT 응답으로 CR을 주므로, 재조회 없이 마지막 저장 결과를 badge dataset에 캐시
    const cached = badge.dataset.cr;
    if (cached !== undefined) {
      const cr = Number(cached);
      badge.textContent = 'CR ' + cr.toFixed(3);
      badge.className = 'badge ' + (cr <= 0.1 ? 'ok' : 'danger');
    }
  }

  async function loadGrid() {
    grid = await ahpApi('/api/entry/' + collectionId + '/grid');
    if (!selectedRespondentId && grid.respondents.length) selectedRespondentId = grid.respondents[0].id;
    renderRespondents();
    renderMatrices();
  }

  async function saveCell(matrixId, uuidA, uuidB, value) {
    try {
      const res = await ahpApi('/api/entry/' + collectionId + '/answers', {
        method: 'PUT',
        body: { respondent_id: selectedRespondentId, matrix_id: matrixId, uuid_a: uuidA, uuid_b: uuidB, value: value },
      });
      const badge = document.querySelector('[data-cr-badge="' + matrixId + '"]');
      if (badge) {
        if (res.complete) {
          badge.dataset.cr = res.cr;
          badge.textContent = 'CR ' + res.cr.toFixed(3);
          badge.className = 'badge ' + (res.cr <= 0.1 ? 'ok' : 'danger');
        } else {
          badge.textContent = '미완료 (' + (grid.matrices.find(function (m) { return m.matrix_id === matrixId; }).pairs.length - res.missing) +
            '/' + grid.matrices.find(function (m) { return m.matrix_id === matrixId; }).pairs.length + ')';
          badge.className = 'badge muted';
        }
      }
      const resp = currentRespondent();
      if (resp) {
        resp.answers[matrixId] = resp.answers[matrixId] || {};
        const pid = [uuidA, uuidB].sort().join(':');
        const lo = [uuidA, uuidB].sort()[0];
        resp.answers[matrixId][pid] = uuidA === lo ? value : 1 / value;
      }
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    }
  }

  async function addRespondent() {
    const label = prompt('응답자 이름 또는 번호(비워두면 자동 지정)') || '';
    try {
      const r = await ahpApi('/api/entry/' + collectionId + '/respondent', { method: 'POST', body: { label: label } });
      selectedRespondentId = r.id;
      await loadGrid();
    } catch (e) {
      ahpToast(e.message || '추가에 실패했습니다', true);
    }
  }

  async function importCsv(file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('/api/entry/' + collectionId + '/import', { method: 'POST', body: formData, credentials: 'include' });
      const data = await res.json();
      if (data.status === 'error') {
        ahpToast(data.error_count + '건 오류: ' + data.errors.slice(0, 3).join(' / '), true);
        return;
      }
      ahpToast(data.created.length + '명의 응답을 반입했습니다');
      await loadGrid();
    } catch (e) {
      ahpToast('CSV 반입에 실패했습니다', true);
    }
  }

  async function init() {
    try {
      const collection = await ahpApi('/api/collections/' + collectionId);
      document.getElementById('collLabel').textContent = collection.label + ' · 오프라인 입력';
      document.getElementById('backToCollect').href = '/collect/' + collection.project_id;
      if (window.AHPShell) window.AHPShell.setActiveProject(collection.project_id);
    } catch (e) {
      ahpToast('수집 정보를 불러오지 못했습니다', true);
      return;
    }

    await loadGrid();

    document.getElementById('addRespondentBtn').addEventListener('click', addRespondent);
    document.getElementById('respondentList').addEventListener('click', async function (e) {
      const del = e.target.closest('.er-del');
      if (del) {
        if (!confirm('이 응답자를 삭제할까요?')) return;
        await ahpApi('/api/entry/' + collectionId + '/respondents/' + del.dataset.id, { method: 'DELETE' });
        if (selectedRespondentId === del.dataset.id) selectedRespondentId = null;
        await loadGrid();
        return;
      }
      const item = e.target.closest('.entry-resp-item');
      if (item) {
        selectedRespondentId = item.dataset.id;
        renderRespondents();
        renderMatrices();
      }
    });

    document.getElementById('matricesForm').addEventListener('change', function (e) {
      if (e.target.tagName !== 'SELECT') return;
      const row = e.target.closest('.entry-pair-row');
      saveCell(row.dataset.matrix, row.dataset.a, row.dataset.b, Number(e.target.value));
    });

    document.getElementById('csvFile').addEventListener('change', function (e) {
      if (e.target.files.length) importCsv(e.target.files[0]);
      e.target.value = '';
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
