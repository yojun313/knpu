(function () {
  'use strict';

  const collectionId = location.pathname.split('/')[2];
  let grid = { matrices: [], respondents: [] };
  let selectedRespondentId = null;
  let scaleMax = 9;

  // currentAOverB가 null이면 "아직 응답하지 않음" — 맨 앞에 비활성 플레이스홀더를
  // 넣어 어떤 척도도 선택되지 않은 상태로 보여준다. 이게 없으면 네이티브 select가
  // 첫 옵션(가장 강한 A쪽)을 시각적으로 선택된 것처럼 보여줘서 "동일하게 중요"를
  // 실제로 고른 것과 구별이 안 됐다(요청사항 — console.js의 섹션 그리드가 이미
  // 쓰는 "(미응답)" 패턴을 그대로 재사용).
  function scaleOptionsHtml(nameA, nameB, currentAOverB) {
    const opts = [];
    for (let n = scaleMax; n >= 2; n--) {
      opts.push({ v: n, label: ahpEsc(nameA) + '가(이) ' + n + '배 더 중요' });
    }
    opts.push({ v: 1, label: '동일하게 중요' });
    for (let n = 2; n <= scaleMax; n++) {
      opts.push({ v: 1 / n, label: ahpEsc(nameB) + '가(이) ' + n + '배 더 중요' });
    }
    const placeholder = currentAOverB === null
      ? '<option value="" selected disabled hidden>(미응답)</option>' : '';
    return placeholder + opts.map(function (o) {
      const sel = currentAOverB !== null && Math.abs(o.v - currentAOverB) < 1e-6 ? ' selected' : '';
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

  // 배지 상태를 한 곳에서만 결정한다 — 예전엔 저장 직후 badge.dataset에 CR을
  // 캐시해뒀다가 재사용했는데, renderMatrices()가 매번 innerHTML을 통째로
  // 새로 그려서(응답자 전환·재조회 시) 배지가 새 DOM이 되며 그 캐시가 사라져
  // "완료된 매트릭스인데도 CR이 안 보이는" 문제로 이어졌다. 이제는 서버가
  // 계산해 준 cr_by_matrix를 매번 그대로 쓴다. n<=2(단일 비교)는 CR이 수학적으로
  // 정의되지 않아 cr이 null로 오므로 .toFixed()를 직접 호출하면 안 된다
  // (Cannot read properties of null (reading 'toFixed') 크래시의 원인이었음).
  function crBadgeState(m, cr, answeredCount) {
    if (m.children.length <= 2) return { text: '비교 불필요', cls: 'badge muted' };
    if (answeredCount < m.pairs.length) return { text: '미완료 (' + answeredCount + '/' + m.pairs.length + ')', cls: 'badge muted' };
    if (cr === null || cr === undefined) return { text: '완료 (CR 없음)', cls: 'badge muted' };
    return { text: 'CR ' + cr.toFixed(3), cls: 'badge ' + (cr <= 0.1 ? 'ok' : 'danger') };
  }

  function applyCrBadge(matrixId, cr, answeredCount) {
    const m = grid.matrices.find(function (x) { return x.matrix_id === matrixId; });
    const badge = document.querySelector('[data-cr-badge="' + matrixId + '"]');
    if (!badge || !m) return;
    const state = crBadgeState(m, cr, answeredCount);
    badge.textContent = state.text;
    badge.className = state.cls;
  }

  function updateSubmitButton() {
    const btn = document.getElementById('markSubmittedBtn');
    const resp = currentRespondent();
    if (!resp) { btn.disabled = true; btn.textContent = '제출 완료로 표시'; return; }
    const done = resp.status === 'submitted';
    btn.disabled = done;
    btn.textContent = done ? '제출 완료됨' : '제출 완료로 표시';
  }

  function renderMatrices() {
    const box = document.getElementById('matricesForm');
    const resp = currentRespondent();
    updateSubmitButton();
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
        const current = pid in answers ? answers[pid] : null;
        return '<div class="entry-pair-row" data-matrix="' + m.matrix_id + '" data-a="' + p.uuid_a + '" data-b="' + p.uuid_b + '">' +
          '<span class="ep-label">' + ahpEsc(nameA) + ' vs ' + ahpEsc(nameB) + '</span>' +
          '<select>' + scaleOptionsHtml(nameA, nameB, current) + '</select></div>';
      }).join('');
      return '<div class="entry-matrix" data-matrix-block="' + m.matrix_id + '">' +
        '<div class="entry-matrix-head"><h4>' + (m.is_alternative ? '<span class="badge ok" style="margin-right:6px">대안</span>' : '') +
        ahpEsc(m.parent_name) + '</h4>' +
        '<span class="badge muted" data-cr-badge="' + m.matrix_id + '">-</span></div>' +
        rows + '</div>';
    }).join('');

    grid.matrices.forEach(function (m) {
      const answeredCount = Object.keys(resp.answers[m.matrix_id] || {}).length;
      applyCrBadge(m.matrix_id, (resp.cr_by_matrix || {})[m.matrix_id], answeredCount);
    });
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
      const resp = currentRespondent();
      if (resp) {
        resp.answers[matrixId] = resp.answers[matrixId] || {};
        const pid = [uuidA, uuidB].sort().join(':');
        const lo = [uuidA, uuidB].sort()[0];
        resp.answers[matrixId][pid] = uuidA === lo ? value : 1 / value;
        resp.cr_by_matrix = resp.cr_by_matrix || {};
        if (res.complete) {
          resp.cr_by_matrix[matrixId] = res.cr;  // n<=2면 res.cr이 null일 수 있음 — crBadgeState가 안전하게 처리
        } else {
          delete resp.cr_by_matrix[matrixId];
        }
        const answeredCount = Object.keys(resp.answers[matrixId]).length;
        applyCrBadge(matrixId, resp.cr_by_matrix[matrixId], answeredCount);
      }
    } catch (e) {
      ahpToast(e.message || '저장에 실패했습니다', true);
    }
  }

  async function markSubmitted() {
    const resp = currentRespondent();
    if (!resp || resp.status === 'submitted') return;
    if (!confirm(resp.label + '의 응답을 제출 완료로 표시할까요?')) return;
    try {
      await ahpApi('/api/entry/' + collectionId + '/respondents/' + resp.id + '/submit', { method: 'POST' });
      resp.status = 'submitted';
      renderRespondents();
      updateSubmitButton();
      ahpToast('제출 완료로 표시했습니다');
    } catch (e) {
      ahpToast(e.message || '처리에 실패했습니다', true);
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
      document.getElementById('downloadTemplateBtn').href = '/api/export/' + collection.project_id + '/import-template.csv';
      if (window.AHPShell) window.AHPShell.setActiveProject(collection.project_id);
    } catch (e) {
      ahpToast('수집 정보를 불러오지 못했습니다', true);
      return;
    }

    await loadGrid();

    document.getElementById('addRespondentBtn').addEventListener('click', addRespondent);
    document.getElementById('markSubmittedBtn').addEventListener('click', markSubmitted);
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
