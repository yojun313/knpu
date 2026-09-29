// 오른쪽 패널(#side) 접기/펼치기 · 너비 조절 · 기본 폭 복귀 — UnivDash 워크스페이스와 같은 동작.
//   KNPUSide.right({ key, defaultWidth, min, max, label, icon, onChange, onToggle })
//   * 머리에 [기본 폭] [접기 »] 버튼을 넣고, 접으면 44px 세로 막대만 남긴다(누르면 펼침).
//   * 왼쪽 경계를 끌어 너비를 바꾸고, 경계를 더블클릭하거나 [기본 폭]을 누르면 처음 폭으로.
//   * 상태는 브라우저(localStorage)에 기억한다. 휴대폰/태블릿(≤1100px)은 각 사이트의 서랍 동작을 쓴다.
(function () {
  'use strict';

  function svg(d) {
    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>';
  }
  var ICON = {
    reset: svg('<path d="M12 4v16M3 12h6M6 9l3 3-3 3M21 12h-6M18 9l-3 3 3 3"/>'),
    right: svg('<path d="M13 17l5-5-5-5M6 17l5-5-5-5"/>'),
    left: svg('<path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/>'),
  };

  function ls(k, v) {
    try {
      if (v === undefined) return localStorage.getItem(k);
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
    } catch (e) { return null; }
    return null;
  }

  var mq = window.matchMedia('(max-width:1100px)');
  function onMq(fn) { if (mq.addEventListener) mq.addEventListener('change', fn); else mq.addListener(fn); }

  function right(o) {
    var side = document.querySelector(o.el || '#side');
    if (!side) return null;
    var key = o.key || 'knpu_side';
    var min = o.min || 300, max = o.max || 680, def = o.defaultWidth || 360;
    var width = parseInt(ls(key + '_width'), 10);
    if (!(width >= min && width <= max)) width = def;
    var collapsed = ls(key + '_collapsed') === '1';

    // 머리 버튼: 기존 ✕(휴대폰 서랍 닫기) 앞에 둔다
    var closeBtn = side.querySelector(o.closeBtn || '#sideCloseBtn');
    var box = document.createElement('span');
    box.className = 'side-head-btns';
    box.innerHTML =
      '<button type="button" class="side-hbtn" data-side-reset title="기본 폭으로" aria-label="오른쪽 패널 기본 폭으로">' + ICON.reset + '</button>' +
      '<button type="button" class="side-hbtn" data-side-collapse title="패널 접기" aria-label="오른쪽 패널 접기">' + ICON.right + '</button>';
    if (closeBtn) {
      closeBtn.classList.add('side-close-mobile');
      closeBtn.parentNode.insertBefore(box, closeBtn);
    }

    // 접혔을 때 남는 세로 막대
    var strip = document.createElement('button');
    strip.type = 'button';
    strip.className = 'side-strip';
    strip.title = (o.label || '패널') + ' 펼치기';
    strip.setAttribute('aria-label', strip.title);
    strip.innerHTML = ICON.left + '<span class="side-strip-label">' + (o.icon ? '<span class="side-strip-icon">' + o.icon + '</span>' : '') +
      '<span>' + (o.label || '패널') + '</span></span>';
    side.appendChild(strip);

    // 너비 조절 손잡이 (없으면 만든다)
    var rz = side.querySelector('.side-resizer');
    if (!rz) { rz = document.createElement('div'); rz.className = 'side-resizer'; side.appendChild(rz); }
    rz.title = '드래그해서 너비 조절 · 더블클릭하면 기본 폭';

    function applyWidth() {
      side.style.setProperty('--side-w', width + 'px');
      side.style.width = (!mq.matches && !collapsed) ? width + 'px' : '';
    }
    function changed() { if (o.onChange) setTimeout(o.onChange, 30); }
    function setCollapsed(on, silent) {
      collapsed = !!on;
      ls(key + '_collapsed', collapsed ? '1' : '0');
      side.classList.toggle('side-strip-mode', collapsed && !mq.matches);
      applyWidth();
      if (!silent) changed();
      if (o.onToggle) o.onToggle(!(collapsed && !mq.matches));
    }
    function reset() {
      width = def;
      ls(key + '_width', null);
      setCollapsed(false);
    }

    box.querySelector('[data-side-reset]').addEventListener('click', reset);
    box.querySelector('[data-side-collapse]').addEventListener('click', function () { setCollapsed(true); });
    strip.addEventListener('click', function () { setCollapsed(false); });
    rz.addEventListener('dblclick', reset);
    rz.addEventListener('mousedown', function (e) {
      if (mq.matches || collapsed) return;
      e.preventDefault();
      rz.classList.add('active');
      document.documentElement.classList.add('side-resizing');
      var startX = e.clientX, startW = side.getBoundingClientRect().width;
      function move(ev) {
        width = Math.max(min, Math.min(max, Math.round(startW + (startX - ev.clientX))));
        applyWidth();
      }
      function up() {
        rz.classList.remove('active');
        document.documentElement.classList.remove('side-resizing');
        document.removeEventListener('mousemove', move);
        document.removeEventListener('mouseup', up);
        ls(key + '_width', String(width));
        changed();
      }
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', up);
    });
    onMq(function () { setCollapsed(collapsed, true); changed(); });
    setCollapsed(collapsed, true);

    return {
      collapse: function (on) { setCollapsed(on); },
      isCollapsed: function () { return collapsed && !mq.matches; },
      reset: reset,
    };
  }

  window.KNPUSide = { right: right, icons: ICON };
})();
