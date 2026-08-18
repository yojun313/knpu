(function () {
  'use strict';

  async function api(path, opts) {
    opts = opts || {};
    opts.credentials = 'include';
    opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
    if (opts.body && typeof opts.body !== 'string') opts.body = JSON.stringify(opts.body);
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try { const d = await res.json(); detail = d.detail || detail; } catch (e) { /* noop */ }
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    if (res.status === 204) return null;
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
  }
  window.ahpApi = api;

  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  window.ahpEsc = escHtml;

  function toast(msg, isError) {
    let box = document.getElementById('ahpToast');
    if (!box) {
      box = document.createElement('div');
      box.id = 'ahpToast';
      box.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);' +
        'z-index:400;display:flex;flex-direction:column;gap:8px;align-items:center';
      document.body.appendChild(box);
    }
    const el = document.createElement('div');
    el.textContent = msg;
    el.style.cssText = 'padding:10px 18px;border-radius:10px;font-size:12.5px;font-weight:700;' +
      'box-shadow:0 8px 24px rgba(0,0,0,.2);color:#fff;background:' + (isError ? '#E74C3C' : '#2c3e50');
    box.appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0';
      el.style.transition = 'opacity .3s';
      setTimeout(function () { el.remove(); }, 300);
    }, 2600);
  }
  window.ahpToast = toast;

  let activeProjectId = null;

  function renderProjects(projects) {
    const list = document.getElementById('railList');
    const empty = document.getElementById('railEmpty');
    if (!list) return;
    if (!projects.length) {
      list.innerHTML = '';
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    list.innerHTML = projects.map(function (p) {
      const initial = (p.title || '?').trim().slice(0, 1).toUpperCase();
      const active = p.id === activeProjectId ? ' active' : '';
      return '<a class="rail-item' + active + '" href="/design/' + p.id + '" data-project-id="' + p.id + '">' +
        '<span class="ri-dot">' + escHtml(initial) + '</span>' +
        '<div class="ri-main"><div class="ri-name">' + escHtml(p.title) + '</div>' +
        '<div class="ri-meta">' + escHtml(p.status_label || p.status || '') + '</div></div></a>';
    }).join('');
  }

  async function refreshProjects() {
    try {
      const projects = await api('/api/projects');
      renderProjects(projects);
      return projects;
    } catch (e) {
      console.error('프로젝트 목록을 불러오지 못했습니다', e);
      return [];
    }
  }

  window.AHPShell = {
    setActiveProject: function (id) {
      activeProjectId = id;
      document.querySelectorAll('.rail-item').forEach(function (el) {
        el.classList.toggle('active', el.getAttribute('data-project-id') === id);
      });
    },
    refreshProjects: refreshProjects,
  };

  async function loadMe() {
    try {
      const me = await api('/api/me');
      const el = document.getElementById('railUserName');
      if (el) el.textContent = me.name || me.uid || '';
    } catch (e) { /* 비로그인 상태는 미들웨어가 이미 리다이렉트했을 것 */ }
  }

  function init() {
    refreshProjects();
    loadMe();

    const toggle = document.getElementById('railToggle');
    const rail = document.getElementById('rail');
    if (toggle && rail) {
      toggle.addEventListener('click', function () { rail.classList.toggle('collapsed'); });
    }

    const logoutBtn = document.getElementById('railLogout');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () {
        fetch('https://knpu.re.kr/api/auth/logout', { method: 'POST', credentials: 'include' })
          .then(function () {
            location.href = 'https://knpu.re.kr/login?redirect=' + encodeURIComponent(window.location.href);
          });
      });
    }

    const newBtn = document.getElementById('railNewProjectBtn');
    const modal = document.getElementById('newProjectModal');
    const closeBtn = document.getElementById('newProjectClose');
    const submitBtn = document.getElementById('newProjectSubmit');
    if (newBtn && modal) {
      newBtn.addEventListener('click', function () {
        modal.hidden = false;
        document.getElementById('newProjectTitle').focus();
      });
      closeBtn.addEventListener('click', function () { modal.hidden = true; });
      modal.addEventListener('click', function (e) { if (e.target === modal) modal.hidden = true; });
      submitBtn.addEventListener('click', async function () {
        const title = document.getElementById('newProjectTitle').value.trim();
        const desc = document.getElementById('newProjectDesc').value.trim();
        if (!title) { toast('제목을 입력해 주세요', true); return; }
        submitBtn.disabled = true;
        try {
          const project = await api('/api/projects', { method: 'POST', body: { title: title, description: desc } });
          modal.hidden = true;
          document.getElementById('newProjectTitle').value = '';
          document.getElementById('newProjectDesc').value = '';
          await refreshProjects();
          location.href = '/design/' + project.id;
        } catch (e) {
          toast(e.message || '프로젝트 생성에 실패했습니다', true);
        } finally {
          submitBtn.disabled = false;
        }
      });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
