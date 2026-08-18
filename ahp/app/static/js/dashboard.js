(function () {
  'use strict';

  const STATUS_BADGE = { draft: 'muted', active: 'ok', closed: 'warn' };

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
      return '<div class="proj-card" data-id="' + p.id + '">' +
        '<div class="pc-actions">' +
        '<button data-act="rename" data-id="' + p.id + '" title="이름 변경">✎</button>' +
        '<button data-act="delete" data-id="' + p.id + '" class="danger" title="삭제">🗑</button>' +
        '</div>' +
        '<a class="pc-link" href="/design/' + p.id + '">' +
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">' +
        '<h3>' + ahpEsc(p.title) + '</h3>' +
        '<span class="badge ' + badgeCls + '">' + ahpEsc(p.status_label) + '</span></div>' +
        '<p>' + ahpEsc(p.description || '설명 없음') + '</p>' +
        '<p style="margin-top:10px;font-size:10.5px;opacity:.7">업데이트 ' + fmtDate(p.updated_at) +
        (p.owner_name ? ' · ' + ahpEsc(p.owner_name) : '') + '</p>' +
        '</a></div>';
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
