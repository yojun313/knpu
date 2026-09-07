(function () {
  'use strict';

  const STATUS_BADGE = { draft: 'muted', active: 'ok', closed: 'warn' };
  const STAGES = [['design', '설계'], ['collect', '수집'], ['analysis', '분석'], ['closed', '종료']];

  function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.getFullYear() + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' +
      String(d.getDate()).padStart(2, '0');
  }

  async function load() {
    const statusFilter = document.getElementById('statusFilter').value;
    const all = document.getElementById('allToggle') && document.getElementById('allToggle').checked;
    let projects = await ahpApi('/api/projects' + (all ? '?all=1' : ''));
    if (statusFilter) projects = projects.filter(function (p) { return p.status === statusFilter; });
    render(projects);
    if (window.AHPShell) window.AHPShell.refreshProjects();
  }

  function render(projects) {
    const grid = document.getElementById('dashGrid');
    const empty = document.getElementById('dashEmpty');
    if (!projects.length) {
      grid.innerHTML = '';
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    grid.innerHTML = projects.map(function (p) {
      const badgeCls = STATUS_BADGE[p.status] || 'muted';
      const si = typeof p.stage_index === 'number' ? p.stage_index : 0;
      const stepper = STAGES.map(function (s, i) {
        const cls = i < si ? 'done' : (i === si ? 'now' : '');
        return '<span class="pcs-step ' + cls + '">' + s[1] + '</span>';
      }).join('<span class="pcs-sep">›</span>');
      const prog = p.progress || { respondents: 0, submitted: 0 };
      const closed = p.status === 'closed';
      return '<div class="proj-card' + (p.pinned ? ' pinned' : '') + '" data-id="' + p.id + '">' +
        '<a class="pc-link" href="/design/' + p.id + '">' +
        '<div class="pc-top">' +
        '<h3>' + (p.pinned ? '<span class="pc-pin-mark">★</span> ' : '') + ahpEsc(p.title) + '</h3>' +
        '<span class="badge ' + badgeCls + '">' + ahpEsc(p.status_label) + '</span></div>' +
        '<p class="pc-desc">' + ahpEsc(p.description || '설명 없음') + '</p>' +
        '<div class="pc-stepper">' + stepper + '</div>' +
        '<div class="pc-meta"><span>진행 ' + prog.submitted + '/' + prog.respondents + '명</span>' +
        '<span>업데이트 ' + fmtDate(p.updated_at) +
        (p.owner_name ? ' · ' + ahpEsc(p.owner_name) : '') + '</span></div>' +
        '</a>' +
        '<div class="pc-actions">' +
        '<button data-act="pin" data-id="' + p.id + '" title="중요 표시">' + (p.pinned ? '★' : '☆') + '</button>' +
        '<button data-act="rename" data-id="' + p.id + '" title="이름 변경">✎</button>' +
        '<button data-act="close" data-id="' + p.id + '" title="' + (closed ? '다시 열기' : '프로젝트 종료') + '">' +
        (closed ? '↺ 재개' : '■ 종료') + '</button>' +
        '<button data-act="delete" data-id="' + p.id + '" class="danger" title="삭제">🗑</button>' +
        '</div></div>';
    }).join('');
  }

  async function renameProject(id) {
    const card = document.querySelector('.proj-card[data-id="' + id + '"]');
    const current = card ? card.querySelector('h3').textContent : '';
    const next = prompt('새 프로젝트 이름', current);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed || trimmed === current) return;
    try {
      await ahpApi('/api/projects/' + id, { method: 'PUT', body: { title: trimmed } });
      ahpToast('이름을 변경했습니다');
      await load();
    } catch (e) {
      ahpToast(e.message || '이름 변경에 실패했습니다', true);
    }
  }

  async function togglePin(id) {
    const card = document.querySelector('.proj-card[data-id="' + id + '"]');
    const pinned = !!(card && card.classList.contains('pinned'));
    try {
      await ahpApi('/api/projects/' + id, { method: 'PUT', body: { pinned: !pinned } });
      await load();
    } catch (e) {
      ahpToast(e.message || '변경에 실패했습니다', true);
    }
  }

  async function toggleClose(id) {
    const card = document.querySelector('.proj-card[data-id="' + id + '"]');
    const title = card ? card.querySelector('h3').textContent.replace(/^★\s*/, '') : '이 프로젝트';
    const badge = card ? card.querySelector('.badge').textContent : '';
    const closed = badge.indexOf('종료') !== -1;
    const next = closed ? 'active' : 'closed';
    if (!closed && !confirm('"' + title + '"을(를) 종료할까요? 결과는 그대로 보이지만 완료된 프로젝트로 표시됩니다.')) return;
    try {
      await ahpApi('/api/projects/' + id, { method: 'PUT', body: { status: next } });
      ahpToast(closed ? '프로젝트를 다시 열었습니다' : '프로젝트를 종료했습니다');
      await load();
    } catch (e) {
      ahpToast(e.message || '변경에 실패했습니다', true);
    }
  }

  async function deleteProject(id) {
    const card = document.querySelector('.proj-card[data-id="' + id + '"]');
    const title = card ? card.querySelector('h3').textContent : '이 프로젝트';
    if (!confirm('"' + title + '"을(를) 삭제할까요?\n계층·설문지·수집된 모든 응답이 함께 삭제되며 되돌릴 수 없습니다.')) return;
    try {
      await ahpApi('/api/projects/' + id, { method: 'DELETE' });
      ahpToast('삭제했습니다');
      await load();
    } catch (e) {
      ahpToast(e.message || '삭제에 실패했습니다', true);
    }
  }

  async function checkAdmin() {
    try {
      const me = await ahpApi('/api/me');
      if (me.role === 'admin') {
        document.getElementById('allToggleWrap').hidden = false;
      }
    } catch (e) { /* noop */ }
  }

  function init() {
    checkAdmin();
    load();
    document.getElementById('dashGrid').addEventListener('click', function (e) {
      const btn = e.target.closest('button[data-act]');
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      const id = btn.dataset.id;
      if (btn.dataset.act === 'rename') renameProject(id);
      else if (btn.dataset.act === 'delete') deleteProject(id);
      else if (btn.dataset.act === 'pin') togglePin(id);
      else if (btn.dataset.act === 'close') toggleClose(id);
    });
    document.getElementById('statusFilter').addEventListener('change', load);
    const allToggle = document.getElementById('allToggle');
    if (allToggle) allToggle.addEventListener('change', load);
    const newBtn = document.getElementById('dashNewProjectBtn');
    if (newBtn) newBtn.addEventListener('click', function () {
      document.getElementById('railNewProjectBtn').click();
    });
    // 새 프로젝트 생성 후(레일 모달) 대시보드도 갱신되도록
    const modalSubmit = document.getElementById('newProjectSubmit');
    if (modalSubmit) modalSubmit.addEventListener('click', function () {
      setTimeout(load, 300);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
