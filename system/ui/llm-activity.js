/* Shared server backed AI activity; no prompts or answers are shown here. */
(function () {
  'use strict';
  if (window.KNPULLMActivity) return;
  var refreshSeq = 0;
  var items = [], timer, scope = 'mine', admin = false, sidebar, nav, dialog;
  function el(tag, cls, text) { var n = document.createElement(tag); n.className = cls || ''; if (text) n.textContent = text; return n; }
  function href(j) {
    var cfg = window.KNPU_SERVICES, s = cfg && cfg.services[j.service];
    if (!s) return null;
    return 'https://' + ((cfg.isDev && s.devDomain) || s.prodDomain) + (s.publicPath || '') + (j.path || '/');
  }
  function row(j) {
    var a = el('a', 'kla-row'); var url = href(j); if (url) a.href = url;
    a.appendChild(el('span', 'kla-dot'));
    var text = el('span', 'kla-text');
    text.appendChild(el('b', '', j.title));
    var elapsed = Math.max(0, Math.floor((Date.now() / 1000 - j.created_ts) / 60));
    text.appendChild(el('small', '', (j.service || '').toUpperCase() + ' · ' + (j.stage || '실행 중') + ' · ' + elapsed + '분'));
    a.appendChild(text); return a;
  }
  function ensure() {
    if (!nav) {
      var header = document.querySelector('.top-header, .knpu-service-header, .app-header-inner, #mainNav .container, #siteNav .container');
      if (header) { nav = el('button', 'kla-nav', 'AI 작업'); nav.type = 'button'; nav.hidden = true; nav.onclick = open;
        header.insertBefore(nav, header.querySelector('.theme-settings-btn, #themeBtn')); }
    }
    if (!sidebar) {
      var rail = document.querySelector('#rail, .rail');
      var top = rail && rail.querySelector('.sb-top');
      if (top) { sidebar = el('section', 'kla-sidebar'); sidebar.hidden = true; top.insertAdjacentElement('afterend', sidebar); }
    }
  }
  function render() {
    ensure();
    if (nav) { nav.hidden = !items.length; nav.textContent = 'AI 작업 ' + items.length; }
    if (sidebar) {
      sidebar.hidden = !items.length; sidebar.replaceChildren();
      var title = el('button', 'kla-heading', 'AI 작업 · ' + items.length + '개 진행 중'); title.type = 'button'; title.onclick = open; sidebar.appendChild(title);
      var list = el('div', 'kla-list'); items.forEach(function (j) { list.appendChild(row(j)); }); sidebar.appendChild(list);
    }
    if (dialog && dialog.open) {
      var body = dialog.querySelector('.kla-dialog-list'); body.replaceChildren();
      if (!items.length) body.appendChild(el('p', '', '진행 중인 AI 작업이 없습니다.'));
      items.forEach(function (j) { body.appendChild(row(j)); });
    }
    document.dispatchEvent(new CustomEvent('knpu:llm-activity', { detail: { items: items, scope: scope } }));
  }
  function refresh() {
    clearTimeout(timer);
    var seq = ++refreshSeq;
    return fetch('/shared-ui/llm-activity?scope=' + scope, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { if (r.status === 401) return { items: [], is_admin: false }; if (!r.ok) throw new Error('AI 상태 조회 실패'); return r.json(); })
      .then(function (data) { if (seq !== refreshSeq) return; items = data.items || []; admin = !!data.is_admin; render(); })
      .catch(function () { /* Keep the last known running state during connection loss. */ })
      .finally(function () { if (seq !== refreshSeq) return; timer = setTimeout(refresh, document.hidden ? 10000 : 3000); });
  }
  function open() {
    if (!dialog) {
      dialog = el('dialog', 'kla-dialog modal-card'); var head = el('div', 'kla-dialog-head'); head.appendChild(el('b', '', 'AI 작업 진행 상황'));
      var close = el('button', '', '×'); close.type = 'button'; close.setAttribute('aria-label', '닫기'); close.onclick = function () { dialog.close(); }; head.appendChild(close); dialog.appendChild(head);
      if (admin) { var label = el('label', 'kla-admin'); var checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.onchange = function () { scope = checkbox.checked ? 'all' : 'mine'; refresh(); }; label.appendChild(checkbox); label.appendChild(document.createTextNode('모든 사용자 AI 작업 보기')); dialog.appendChild(label); }
      dialog.appendChild(el('div', 'kla-dialog-list')); document.body.appendChild(dialog);
      dialog.addEventListener('click', function (e) { if (e.target === dialog) { var r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } });
    }
    if (!dialog.open) dialog.showModal(); render();
  }
  window.KNPULLMActivity = { refresh: refresh, items: function () { return items; }, open: open };
  document.addEventListener('visibilitychange', function () { if (!document.hidden) refresh(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh); else refresh();
})();
