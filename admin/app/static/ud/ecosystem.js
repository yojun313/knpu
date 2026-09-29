// UnivDash server.js 의 Ecosystem 부분을 KNPU 관리자 대시보드(/process)용으로 옮김
// ── ecosystem.config.js: 등록된 앱 목록 · 새 앱 추가 · 시작 ─────────────────────
(function () {
  'use strict';
  const list = document.getElementById('ecoList');
  if (!list) return;
  const { escapeHtml, api } = window.UnivDash;
  const ui = () => window.UnivDashUI;
  let apps = [];
  let ecoFile = 'ecosystem.config.js';

  function statusBadge(status) {
    if (status === 'online') return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/25"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>ONLINE</span>';
    if (status) return `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-red-500/10 text-red-400 border border-red-500/25">${escapeHtml(String(status).toUpperCase())}</span>`;
    return '<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-white/10 text-white/40 border border-white/10">미실행</span>';
  }

  function render(data) {
    ecoFile = (data.path || '').split('/').pop() || ecoFile;
    document.getElementById('ecoPath').textContent = data.path + (data.exists ? '' : ' (아직 없음 — 첫 앱을 추가하면 만들어집니다)');
    if (data.error) {
      list.innerHTML = `<div class="p-5 text-xs text-red-300">${escapeHtml(data.error)}</div>`;
      return;
    }
    apps = data.apps;
    if (!apps.length) {
      list.innerHTML = '<div class="p-5 text-xs text-white/40">등록된 앱이 없습니다. <b>새 앱</b>으로 추가하세요.</div>';
      return;
    }
    list.innerHTML = apps.map((app) => `
      <article class="flex items-center gap-3 px-4 py-3">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 min-w-0"><span class="truncate text-sm font-bold text-white/90">${escapeHtml(app.name)}</span>${statusBadge(app.status)}${app.watch ? '<i class="fas fa-eye text-[10px] text-white/35" title="watch"></i>' : ''}</div>
          <p class="mt-0.5 truncate font-mono text-[10px] text-white/40">${escapeHtml([app.cwd, [app.interpreter ? app.interpreter.split('/').pop() : '', app.script, app.args || ''].filter(Boolean).join(' ')].filter(Boolean).join(' · '))}</p>
        </div>
        ${app.status ? '' : `<button type="button" data-eco-start="${escapeHtml(app.name)}" class="flex-shrink-0 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-3 py-2 text-xs font-bold text-white"><i class="fas fa-play mr-1"></i>시작</button>`}
      </article>`).join('');
  }

  async function load() {
    try { render(await api('/process/api/ecosystem')); } catch (error) { list.innerHTML = `<div class="p-5 text-xs text-red-300">${escapeHtml(error.message)}</div>`; }
  }

  async function start(name) {
    if (!await ui().confirmSheet({ title: `${name} 시작`, message: `pm2 start ${ecoFile} --only ${name}`, confirmLabel: '시작' })) return;
    try {
      await api(`/process/api/ecosystem/apps/${encodeURIComponent(name)}/start`, { method: 'POST' });
      ui().toast(`${name} 을(를) 시작했습니다. 새로고침하면 프로세스 목록에 보입니다.`, 'ok', { label: '새로고침', onClick: () => location.reload() }, 6000);
      load();
    } catch (error) { ui().toast(error.message, 'error', null, 8000); }
  }
  list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-eco-start]');
    if (button) start(button.dataset.ecoStart);
  });

  document.getElementById('ecoAddBtn').addEventListener('click', () => {
    ui().formSheet({
      title: 'ecosystem 에 새 앱 추가',
      subtitle: '파일 끝에 항목을 추가합니다. 원본은 .bak 으로 백업됩니다.',
      fields: [
        { name: 'cwd', label: '작업 폴더 (cwd)', placeholder: '/home/user/my-app', maxlength: 1024 },
        { name: 'name', label: '앱 이름', placeholder: 'my-app', maxlength: 64 },
        { name: 'script', label: '실행 파일 (script)', placeholder: 'run.py / index.js', maxlength: 500 },
        { name: 'interpreter', label: '인터프리터 (비우면 pm2 기본값)', placeholder: '/home/user/my-app/.venv/bin/python', maxlength: 500 },
        { name: 'args', label: '실행 인자 (선택)', placeholder: '--port 9000', maxlength: 500 },
      ],
      extraHtml: `
        <label>환경 변수 (선택, 한 줄에 KEY=VALUE)<textarea name="env" rows="3" maxlength="20000" placeholder="PORT=9000" autocapitalize="off" spellcheck="false"></textarea></label>
        <div class="grid gap-2">
          <label class="check-row"><input type="checkbox" name="watch"> 파일이 바뀌면 자동 재시작 (watch)</label>
          <label class="check-row"><input type="checkbox" name="time" checked> 로그에 시간 표시 (time)</label>
          <label class="check-row"><input type="checkbox" name="start" checked> 추가한 뒤 바로 pm2 로 시작</label>
        </div>
        <p data-eco-hint class="text-[11px] opacity-60"></p>`,
      submitLabel: '추가',
      onMount(body) {
        const field = (name) => body.querySelector(`[name="${name}"]`);
        const touched = new Set();
        ['name', 'script', 'interpreter'].forEach((name) => field(name).addEventListener('input', () => touched.add(name)));
        let timer = null;
        field('cwd').addEventListener('input', () => {
          clearTimeout(timer);
          timer = setTimeout(async () => {
            const hint = body.querySelector('[data-eco-hint]');
            if (!field('cwd').value.trim()) { hint.textContent = ''; return; }
            try {
              const info = await api(`/process/api/ecosystem/inspect?cwd=${encodeURIComponent(field('cwd').value.trim())}`);
              if (!info.exists) { hint.textContent = '폴더를 찾을 수 없습니다.'; return; }
              hint.textContent = `✓ ${info.cwd}`;
              ['name', 'script', 'interpreter'].forEach((name) => { if (!touched.has(name) && info[name]) field(name).value = info[name]; });
            } catch (error) { /* 무시 */ }
          }, 350);
        });
      },
      async onSubmit(values) {
        const payload = {
          name: values.name.trim(), cwd: values.cwd.trim(), script: values.script.trim(),
          interpreter: values.interpreter.trim(), args: values.args.trim(), env: values.env || '',
          watch: values.watch === 'on', time: values.time === 'on', start: values.start === 'on',
        };
        const result = await api('/process/api/ecosystem/apps', { method: 'POST', body: payload });
        if (result.started === false) ui().toast(`추가했지만 시작하지 못했습니다:\n${result.output || ''}`, 'error', null, 9000);
        else ui().toast(`${payload.name} 을(를) ecosystem 에 추가했습니다${result.started ? ' · pm2 시작됨' : ''}.`, 'ok', result.started ? { label: '새로고침', onClick: () => location.reload() } : null, 6000);
        load();
      },
    });
  });

  load();
})();
