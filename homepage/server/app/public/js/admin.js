// 콘텐츠 관리 대시보드(/admin) — 논문/멤버/뉴스/갤러리/팝업/입시 FAQ CRUD.
// manager 데스크톱 앱의 WEB 탭(page_web.py)이 쓰는 것과 동일한 /api/* 엔드포인트를 그대로 호출한다.
(function () {
  'use strict';

  // ---------------------------------------------------------------
  // 공통 유틸
  // ---------------------------------------------------------------
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c];
    });
  }
  function escAttr(s) { return esc(s).replace(/"/g, '&quot;'); }
  function $(id) { return document.getElementById(id); }

  function api(path, opts) {
    return fetch(path, Object.assign({ credentials: 'include' }, opts)).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (body) {
          throw new Error(body.detail || res.statusText);
        });
      }
      if (res.status === 204) return null;
      return res.json();
    });
  }
  function apiGet(path) { return api(path); }
  function apiPost(path, json) {
    return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(json) });
  }
  function apiDelete(path) { return api(path, { method: 'DELETE' }); }

  function objectNameFromUrl(url) {
    try { return new URL(url).pathname.replace(/^\//, ''); } catch (e) { return url; }
  }

  function randomName() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID().replace(/-/g, '');
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
  }

  function uploadImage(file, folder, objectName) {
    var fd = new FormData();
    fd.append('file', file);
    fd.append('folder', folder);
    fd.append('object_name', objectName || (folder + '/' + randomName()));
    return fetch('/api/image/', { method: 'POST', credentials: 'include', body: fd }).then(function (res) {
      if (!res.ok) return res.json().then(function (b) { throw new Error(b.detail || '업로드 실패'); });
      return res.json();
    }).then(function (data) { return data.url; });
  }

  function deleteImageByUrl(url) {
    if (!url) return Promise.resolve();
    return fetch('/api/image/?object_name=' + encodeURIComponent(objectNameFromUrl(url)), {
      method: 'DELETE', credentials: 'include',
    }).catch(function () { /* 이미지 삭제 실패는 콘텐츠 저장을 막지 않는다 */ });
  }

  function setTabCount(id, n) {
    var el = $('count-' + id);
    if (el) el.textContent = n;
  }

  function thumbCell(url, round) {
    var r = round ? ' round' : '';
    return url
      ? '<img class="row-thumb' + r + '" src="' + escAttr(url) + '" alt="" loading="lazy">'
      : '<div class="row-thumb-placeholder' + r + '"><i class="fa-solid fa-' + (round ? 'user' : 'image') + '"></i></div>';
  }

  function linkCell(url) {
    if (!url) return '<span class="cell-muted">—</span>';
    var label = url.replace(/^https?:\/\//, '').replace(/\/$/, '');
    return '<a class="cell-link" href="' + escAttr(url) + '" target="_blank" rel="noopener" title="' + escAttr(url) + '">'
      + '<i class="fa-solid fa-arrow-up-right-from-square"></i>' + esc(label) + '</a>';
  }

  function actionButtons(editFn, deleteFn) {
    return '<button class="icon-btn" title="수정" onclick="' + editFn + '"><i class="fa-solid fa-pen"></i></button>'
      + '<button class="icon-btn danger" title="삭제" onclick="' + deleteFn + '"><i class="fa-solid fa-trash"></i></button>';
  }

  // 행 전체를 눌러 편집 — data-edit 에 편집 함수 호출 정보를 담는다.
  function rowAttrs(editFn, uid, filterValue, extraClass) {
    return ' class="row-click' + (extraClass ? ' ' + extraClass : '') + '" data-row data-edit="' + editFn + '" data-uid="' + escAttr(uid)
      + '" data-fv="' + escAttr(filterValue == null ? '' : filterValue) + '"';
  }

  function emptyRow(colspan, icon, text) {
    return '<tr><td colspan="' + colspan + '"><div class="admin-empty"><i class="fa-solid fa-' + icon + '"></i>' + text + '</div></td></tr>';
  }

  function toast(msg, kind) {
    var box = $('adm-toasts');
    if (!box) return;
    var t = document.createElement('div');
    t.className = 'adm-toast ' + (kind || 'ok');
    t.innerHTML = '<i class="fa-solid fa-' + (kind === 'err' ? 'circle-exclamation' : 'circle-check') + '"></i><span></span>';
    t.lastChild.textContent = msg;
    box.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }, kind === 'err' ? 5000 : 2600);
  }

  function showModalError(id, msg) {
    var el = $(id);
    el.textContent = msg;
    el.style.display = 'block';
    var body = el.closest('.modal-body');
    if (body) body.scrollTop = 0;
  }
  function hideModalError(id) {
    $(id).style.display = 'none';
  }
  function closeModal(id) {
    var el = $(id);
    var instance = bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el);
    instance.hide();
  }
  function openModal(id) {
    var el = $(id);
    (bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el)).show();
  }

  // 저장 중에는 저장 버튼을 잠그고 스피너를 보여 중복 저장을 막는다. 끝나면 done() 호출.
  function setBusy(modalId) {
    var btn = document.querySelector('#' + modalId + ' .btn-save');
    if (!btn) return function () { };
    if (btn.disabled) return null;
    var html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i>저장 중';
    return function () { btn.disabled = false; btn.innerHTML = html; };
  }

  function splitLines(v) {
    return v.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
  }

  // 이미지 필드(미리보기 + 상태 문구 + 제거 버튼)
  function setImageField(prefix, url, status) {
    var pv = $(prefix + '-image-preview');
    if (pv) {
      pv.style.backgroundImage = url ? 'url("' + url.replace(/"/g, '%22') + '")' : '';
      pv.classList.toggle('has-img', !!url);
    }
    var rm = $(prefix + '-image-remove');
    if (rm) rm.hidden = !url;
    $(prefix + '-image-status').textContent = status || (url ? '현재 이미지가 등록되어 있습니다.' : '이미지 없음');
  }

  function uploadInto(prefix, file, folder, objectName, onUrl) {
    if (!file) return;
    if (file.type && file.type.indexOf('image/') !== 0) {
      setImageField(prefix, null, '이미지 파일만 올릴 수 있습니다.');
      return;
    }
    var pv = $(prefix + '-image-preview');
    var local = URL.createObjectURL(file);
    if (pv) { pv.style.backgroundImage = 'url("' + local + '")'; pv.classList.add('has-img'); }
    $(prefix + '-image-status').textContent = '업로드 중...';
    uploadImage(file, folder, objectName).then(function (url) {
      onUrl(url);
      setImageField(prefix, url, '업로드 완료 — 저장하면 반영됩니다.');
    }).catch(function (err) {
      $(prefix + '-image-status').textContent = '업로드 실패: ' + (err.message || '');
    });
  }

  function yearOf(s) {
    var m = String(s || '').match(/(\d{4})/);
    return m ? m[1] : '';
  }

  // ---------------------------------------------------------------
  // 검색 · 필터 (각 패널의 [data-search] / [data-filter])
  // ---------------------------------------------------------------
  var FILTER_LABELS = {
    papers: '전체 연도', members: '전체 구분', news: '전체 연도', gallery: '전체 연도', popups: '전체 상태', faq: '전체 분류',
  };

  function panel(key) { return document.querySelector('[data-panel="' + key + '"]'); }

  // 필터 선택지를 현재 데이터로 다시 채운다(선택값 유지).
  function setFilterOptions(key, values, sortDesc) {
    var p = panel(key);
    var sel = p && p.querySelector('[data-filter]');
    if (!sel) return;
    var cur = sel.value;
    var uniq = values.filter(function (v, i, a) { return v && a.indexOf(v) === i; });
    if (sortDesc) uniq.sort().reverse();
    sel.innerHTML = '<option value="">' + FILTER_LABELS[key] + '</option>'
      + uniq.map(function (v) { return '<option value="' + escAttr(v) + '">' + esc(v) + '</option>'; }).join('');
    sel.value = uniq.indexOf(cur) >= 0 ? cur : '';
  }

  function applyFilters(key) {
    var p = panel(key);
    if (!p) return;
    var q = ((p.querySelector('[data-search]') || {}).value || '').trim().toLowerCase();
    var fv = (p.querySelector('[data-filter]') || {}).value || '';
    var rows = p.querySelectorAll('tbody tr[data-row]');
    var shown = 0;
    Array.prototype.forEach.call(rows, function (tr) {
      var ok = (!fv || tr.getAttribute('data-fv') === fv) && (!q || tr.textContent.toLowerCase().indexOf(q) >= 0);
      tr.hidden = !ok;
      if (ok) shown++;
    });
    // FAQ 그룹 머리행: 아래에 보이는 행이 없으면 숨긴다
    Array.prototype.forEach.call(p.querySelectorAll('tbody tr[data-group]'), function (g) {
      var n = g.nextElementSibling, any = false;
      while (n && !n.hasAttribute('data-group')) { if (n.hasAttribute('data-row') && !n.hidden) { any = true; break; } n = n.nextElementSibling; }
      g.hidden = !any;
    });
    var tbody = p.querySelector('tbody');
    var none = tbody.querySelector('tr[data-noresult]');
    if (rows.length && !shown) {
      if (!none) {
        var cols = p.querySelectorAll('thead th').length;
        tbody.insertAdjacentHTML('beforeend', '<tr data-noresult><td colspan="' + cols + '"><div class="admin-empty"><i class="fa-solid fa-magnifying-glass"></i>조건에 맞는 항목이 없습니다.</div></td></tr>');
      }
    } else if (none) {
      none.remove();
    }
    var res = p.querySelector('[data-result]');
    if (res) res.textContent = rows.length ? (shown === rows.length ? rows.length + '건' : shown + ' / ' + rows.length + '건') : '';
  }

  function bindPanelControls() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-panel]'), function (p) {
      var key = p.getAttribute('data-panel');
      var s = p.querySelector('[data-search]');
      var f = p.querySelector('[data-filter]');
      if (s) s.addEventListener('input', function () { applyFilters(key); });
      if (f) f.addEventListener('change', function () { applyFilters(key); });
      // 행 클릭 → 편집 (버튼·링크를 누른 경우는 제외)
      var tbody = p.querySelector('tbody');
      if (tbody) tbody.addEventListener('click', function (e) {
        if (e.target.closest('button, a, input, label')) return;
        var tr = e.target.closest('tr[data-edit]');
        if (!tr) return;
        var fn = window[tr.getAttribute('data-edit')];
        if (typeof fn === 'function') fn(tr.getAttribute('data-uid'));
      });
    });
  }

  // ---------------------------------------------------------------
  // 탭 기억(#papers 같은 주소 해시) · 단축키
  // ---------------------------------------------------------------
  function activeTabKey() {
    var a = document.querySelector('#adminTabs .nav-link.active');
    return a ? a.getAttribute('data-tab') : 'papers';
  }

  function bindTabs() {
    Array.prototype.forEach.call(document.querySelectorAll('#adminTabs .nav-link'), function (btn) {
      btn.addEventListener('shown.bs.tab', function () {
        var key = btn.getAttribute('data-tab');
        if (history.replaceState) history.replaceState(null, '', '#' + key);
        if (window.innerWidth < 992) btn.scrollIntoView({ block: 'nearest', inline: 'center' });
      });
    });
    var want = (location.hash || '').replace('#', '');
    var target = want && document.querySelector('#adminTabs [data-tab="' + want + '"]');
    if (target) bootstrap.Tab.getOrCreateInstance(target).show();
  }

  document.addEventListener('keydown', function (e) {
    var openModalEl = document.querySelector('.modal.show');
    if (openModalEl && (e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      var fn = window[openModalEl.getAttribute('data-save')];
      if (typeof fn === 'function') fn();
      return;
    }
    if (!openModalEl && e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName)) {
      var key = activeTabKey();
      var p = panel(key);
      var s = p && p.querySelector('[data-search]');
      if (s) { e.preventDefault(); s.focus(); }
    }
  });

  // 모달이 열리면 첫 입력칸에 커서
  document.addEventListener('shown.bs.modal', function (e) {
    var first = e.target.querySelector('.modal-body input:not([type=file]):not([type=checkbox]), .modal-body textarea, .modal-body select');
    if (first) first.focus();
  });

  // ---------------------------------------------------------------
  // 인증 확인
  // ---------------------------------------------------------------
  fetch('/api/auth/me', { credentials: 'include' }).then(function (res) {
    return res.ok ? res.json() : null;
  }).then(function (user) {
    if (!user) {
      window.location.href = '/login?redirect=' + encodeURIComponent('/admin');
      return;
    }
    if (user.role !== 'admin') {
      window.location.href = '/account';
      return;
    }
    $('admin-loading').style.display = 'none';
    $('admin-content').style.display = 'block';
    bindPanelControls();
    bindTabs();
    bindGalleryDrop();
    loadMemberOptions();
    loadPapers();
    loadMembers();
    loadNews();
    loadGallery();
    loadPopups();
    loadFaqCategories();
    loadFaq();
  }).catch(function () {
    window.location.href = '/login?redirect=' + encodeURIComponent('/admin');
  });

  function loadFailed(what) {
    return function (err) { toast(what + ' 목록을 불러오지 못했습니다: ' + (err.message || ''), 'err'); };
  }

  // ============================================================
  // 논문
  // ============================================================
  var papersData = [];
  var paperEditingUid = null;
  var paperCrawledRecord = {};

  function loadPapers() {
    return apiGet('/api/papers/').then(function (groups) {
      papersData = [];
      (groups || []).forEach(function (g) {
        (g.papers || []).forEach(function (p) { p.year = g.year; papersData.push(p); });
      });
      renderPapers();
    }).catch(loadFailed('논문'));
  }

  function renderPapers() {
    var tbody = $('papers-tbody');
    setTabCount('papers', papersData.length);
    setFilterOptions('papers', papersData.map(function (p) { return String(p.year || ''); }), true);
    if (!papersData.length) {
      tbody.innerHTML = emptyRow(6, 'file-lines', '등록된 논문이 없습니다. 오른쪽 위 \'논문 추가\'로 시작하세요.');
      applyFilters('papers');
      return;
    }
    tbody.innerHTML = papersData.map(function (p) {
      var authors = (p.authors || []).join(', ');
      var type = (p.journal_type || '').toUpperCase();
      return '<tr' + rowAttrs('openPaperModal', p.uid, String(p.year || '')) + '>'
        + '<td class="col-num">' + esc(p.year) + '</td>'
        + '<td><div class="cell-main" title="' + escAttr(p.title) + '">' + esc(p.title) + '</div>'
        + '<div class="cell-sub">' + esc(authors || '저자 미입력') + '</div></td>'
        + '<td class="hide-md cell-muted">' + esc(p.venue || '—') + '</td>'
        + '<td class="col-narrow hide-sm">' + (type ? '<span class="badge-soft ' + type.toLowerCase() + '">' + esc(type) + '</span>' : '') + '</td>'
        + '<td class="col-narrow hide-md">' + (p.url ? '<a class="icon-btn" href="' + escAttr(p.url) + '" target="_blank" rel="noopener" title="논문 열기"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>' : '<span class="cell-muted">—</span>') + '</td>'
        + '<td class="col-actions">' + actionButtons("openPaperModal('" + p.uid + "')", "deletePaper('" + p.uid + "')") + '</td></tr>';
    }).join('');
    applyFilters('papers');
  }

  window.openPaperModal = function (uid) {
    hideModalError('paper-error');
    var data = uid ? papersData.find(function (p) { return p.uid === uid; }) : null;
    paperEditingUid = uid || null;
    paperCrawledRecord = data ? Object.assign({}, data) : {};
    $('paperModalTitle').textContent = uid ? '논문 수정' : '논문 추가';
    $('paper-title').value = data ? (data.title || '') : '';
    $('paper-year').value = data ? (data.year || '') : new Date().getFullYear();
    $('paper-authors').value = data ? (data.authors || []).join(', ') : '';
    $('paper-venue').value = data ? (data.venue || '') : '';
    $('paper-url').value = data ? (data.url || '') : '';
    $('paper-journal-type').value = (data && data.journal_type) || 'KCI';
    openModal('paperModal');
  };

  window.crawlPaperMetadata = function () {
    var title = $('paper-title').value.trim();
    if (!title) { showModalError('paper-error', '제목을 먼저 입력해주세요.'); return; }
    var type = $('paper-journal-type').value;
    var btn = $('paper-crawl-btn');
    var html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i>가져오는 중...';
    hideModalError('paper-error');
    apiGet('/api/papers/crawl?title=' + encodeURIComponent(title) + '&type=' + encodeURIComponent(type))
      .then(function (record) {
        paperCrawledRecord = record || {};
        $('paper-year').value = record.year || '';
        $('paper-title').value = record.title || title;
        $('paper-authors').value = (record.authors || []).join(', ');
        $('paper-venue').value = record.venue || '';
        $('paper-url').value = record.url || '';
        toast('메타데이터를 채웠습니다. 확인 후 저장하세요.');
      })
      .catch(function (err) { showModalError('paper-error', err.message || '메타데이터를 가져오지 못했습니다.'); })
      .then(function () { btn.disabled = false; btn.innerHTML = html; });
  };

  window.savePaper = function () {
    if (!$('paper-title').value.trim()) { showModalError('paper-error', '제목을 입력해주세요.'); return; }
    var year = parseInt($('paper-year').value, 10);
    if (!year) { showModalError('paper-error', '연도는 숫자로 입력해주세요.'); return; }
    var done = setBusy('paperModal');
    if (!done) return;
    var authors = $('paper-authors').value.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    var payload = Object.assign({}, paperCrawledRecord, {
      uid: paperEditingUid || paperCrawledRecord.uid || undefined,
      title: $('paper-title').value.trim(),
      authors: authors,
      year: year,
      venue: $('paper-venue').value.trim(),
      url: $('paper-url').value.trim(),
      journal_type: $('paper-journal-type').value,
    });
    apiPost('/api/papers/', payload).then(function () {
      closeModal('paperModal');
      toast(paperEditingUid ? '논문을 수정했습니다.' : '논문을 추가했습니다.');
      loadPapers();
    }).catch(function (err) { showModalError('paper-error', err.message || '저장에 실패했습니다.'); })
      .then(done);
  };

  window.deletePaper = function (uid) {
    var p = papersData.find(function (x) { return x.uid === uid; });
    if (!confirm('이 논문을 삭제하시겠습니까?' + (p ? '\n\n' + p.title : ''))) return;
    apiDelete('/api/papers/?uid=' + encodeURIComponent(uid)).then(function () {
      toast('논문을 삭제했습니다.');
      loadPapers();
    }).catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'err'); });
  };

  // ============================================================
  // 멤버
  // ============================================================
  var membersData = [];
  var memberEditingUid = null;
  var memberImage = '';
  var memberOptions = { positions: [], sections: [] };

  function loadMemberOptions() {
    apiGet('/api/members/options').then(function (opts) {
      memberOptions = opts || { positions: [], sections: [] };
      var posSel = $('member-position');
      var secSel = $('member-section');
      posSel.innerHTML = memberOptions.positions.map(function (p) { return '<option value="' + escAttr(p) + '">' + esc(p) + '</option>'; }).join('');
      secSel.innerHTML = memberOptions.sections.map(function (s) { return '<option value="' + escAttr(s) + '">' + esc(s) + '</option>'; }).join('');
    }).catch(function () { });
  }

  function loadMembers() {
    return apiGet('/api/members/').then(function (docs) {
      membersData = docs || [];
      renderMembers();
    }).catch(loadFailed('멤버'));
  }

  function renderMembers() {
    var tbody = $('members-tbody');
    setTabCount('members', membersData.length);
    setFilterOptions('members', (memberOptions.sections || []).concat(membersData.map(function (m) { return m.section || ''; })));
    if (!membersData.length) {
      tbody.innerHTML = emptyRow(6, 'users', '등록된 멤버가 없습니다.');
      applyFilters('members');
      return;
    }
    tbody.innerHTML = membersData.map(function (m) {
      return '<tr' + rowAttrs('openMemberModal', m.uid, m.section || '') + '>'
        + '<td class="col-narrow">' + thumbCell(m.image, true) + '</td>'
        + '<td><div class="cell-main">' + esc(m.name) + '</div><div class="cell-sub">' + esc(m.email || '이메일 없음') + '</div></td>'
        + '<td><span class="badge-soft">' + esc(m.section || '—') + '</span></td>'
        + '<td class="hide-sm cell-muted">' + esc(m.position || '—') + '</td>'
        + '<td class="hide-md cell-muted">' + esc(m.affiliation || '—') + '</td>'
        + '<td class="col-actions">' + actionButtons(
          "openMemberModal('" + m.uid + "')",
          escAttr("deleteMember('" + m.uid + "', " + JSON.stringify(m.name) + ")")
        ) + '</td></tr>';
    }).join('');
    applyFilters('members');
  }

  function listToText(v) {
    if (Array.isArray(v)) return v.join('\n');
    return v ? String(v) : '';
  }

  window.openMemberModal = function (uid) {
    hideModalError('member-error');
    var data = uid ? membersData.find(function (m) { return m.uid === uid; }) : null;
    memberEditingUid = uid || null;
    memberImage = data ? (data.image || '') : '';
    $('memberModalTitle').textContent = uid ? '멤버 수정 — ' + (data ? data.name : '') : '멤버 추가';
    $('member-name').value = data ? (data.name || '') : '';
    $('member-affiliation').value = data ? (data.affiliation || '') : '';
    $('member-email').value = data ? (data.email || '') : '';
    $('member-homepage').value = data ? (data.homepage || '') : '';
    $('member-school').value = data ? listToText(data['학력']) : '';
    $('member-career').value = data ? listToText(data['경력']) : '';
    $('member-research').value = data ? listToText(data['연구']) : '';
    $('member-awards').value = data ? listToText(data['수상']) : '';
    $('member-position').value = (data && data.position) || (memberOptions.positions[0] || '');
    $('member-section').value = (data && data.section) || (memberOptions.sections[0] || '');
    $('member-image-input').value = '';
    setImageField('member', memberImage);
    openModal('memberModal');
  };

  window.uploadMemberImage = function (file) {
    var name = $('member-name').value.trim() || 'member';
    uploadInto('member', file, 'members', 'members/' + name.replace(/[^\w가-힣-]/g, '_') + '_' + randomName(),
      function (url) { memberImage = url; });
    $('member-image-input').value = '';
  };

  window.removeMemberImage = function () {
    memberImage = '';
    setImageField('member', '', '이미지를 뺐습니다 — 저장하면 반영됩니다.');
  };

  window.saveMember = function () {
    var name = $('member-name').value.trim();
    if (!name) { showModalError('member-error', '이름을 입력해주세요.'); return; }
    var done = setBusy('memberModal');
    if (!done) return;
    var payload = {
      uid: memberEditingUid || undefined,
      name: name,
      position: $('member-position').value,
      affiliation: $('member-affiliation').value.trim(),
      section: $('member-section').value,
      email: $('member-email').value.trim(),
      homepage: $('member-homepage').value.trim(),
      '학력': splitLines($('member-school').value),
      '경력': splitLines($('member-career').value),
      '연구': splitLines($('member-research').value),
      '수상': splitLines($('member-awards').value),
      image: memberImage || '',
    };
    apiPost('/api/members/', payload).then(function () {
      closeModal('memberModal');
      toast(memberEditingUid ? name + ' 님 정보를 수정했습니다.' : name + ' 님을 추가했습니다.');
      loadMembers();
    }).catch(function (err) { showModalError('member-error', err.message || '저장에 실패했습니다.'); })
      .then(done);
  };

  window.deleteMember = function (uid, name) {
    if (!confirm('[' + name + '] 멤버를 정말 삭제하시겠습니까?')) return;
    var confirmName = prompt('삭제 확인을 위해 멤버의 이름(' + name + ')을 정확히 입력해주세요.');
    if (confirmName === null) return;
    if (confirmName !== name) { toast('이름이 일치하지 않아 삭제를 취소했습니다.', 'err'); return; }
    apiDelete('/api/members/?uid=' + encodeURIComponent(uid)).then(function () {
      toast(name + ' 님을 삭제했습니다.');
      loadMembers();
    }).catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'err'); });
  };

  // ============================================================
  // 뉴스
  // ============================================================
  var newsData = [];
  var newsEditingUid = null;
  var newsImage = '';

  function loadNews() {
    return apiGet('/api/news/').then(function (docs) {
      newsData = docs || [];
      renderNews();
    }).catch(loadFailed('뉴스'));
  }

  function renderNews() {
    var tbody = $('news-tbody');
    setTabCount('news', newsData.length);
    setFilterOptions('news', newsData.map(function (n) { return yearOf(n.date); }), true);
    if (!newsData.length) {
      tbody.innerHTML = emptyRow(5, 'newspaper', '등록된 뉴스가 없습니다.');
      applyFilters('news');
      return;
    }
    tbody.innerHTML = newsData.map(function (n) {
      return '<tr' + rowAttrs('openNewsModal', n.uid, yearOf(n.date)) + '>'
        + '<td class="col-narrow">' + thumbCell(n.image) + '</td>'
        + '<td><div class="cell-main" title="' + escAttr(n.title) + '">' + esc(n.title) + '</div>'
        + (n.content ? '<div class="cell-sub">' + esc(n.content) + '</div>' : '') + '</td>'
        + '<td class="col-num hide-sm">' + esc(n.date || '—') + '</td>'
        + '<td class="hide-md">' + linkCell(n.url) + '</td>'
        + '<td class="col-actions">' + actionButtons("openNewsModal('" + n.uid + "')", "deleteNews('" + n.uid + "')") + '</td></tr>';
    }).join('');
    applyFilters('news');
  }

  window.openNewsModal = function (uid) {
    hideModalError('news-error');
    var data = uid ? newsData.find(function (n) { return n.uid === uid; }) : null;
    newsEditingUid = uid || null;
    newsImage = data ? (data.image || '') : '';
    $('newsModalTitle').textContent = uid ? '뉴스 수정' : '뉴스 추가';
    $('news-title').value = data ? (data.title || '') : '';
    $('news-content').value = data ? (data.content || '') : '';
    $('news-date').value = data ? (data.date || '') : todayDot();
    $('news-url').value = data ? (data.url || '') : '';
    $('news-image-input').value = '';
    setImageField('news', newsImage);
    openModal('newsModal');
  };

  window.uploadNewsImage = function (file) {
    uploadInto('news', file, 'news', null, function (url) { newsImage = url; });
    $('news-image-input').value = '';
  };

  window.removeNewsImage = function () {
    newsImage = '';
    setImageField('news', '', '이미지를 뺐습니다 — 저장하면 반영됩니다.');
  };

  window.saveNews = function () {
    var title = $('news-title').value.trim();
    if (!title) { showModalError('news-error', '제목을 입력해주세요.'); return; }
    var done = setBusy('newsModal');
    if (!done) return;
    var payload = {
      uid: newsEditingUid || undefined,
      title: title,
      content: $('news-content').value.trim(),
      date: $('news-date').value.trim(),
      url: $('news-url').value.trim(),
      image: newsImage || '',
    };
    apiPost('/api/news/', payload).then(function () {
      closeModal('newsModal');
      toast(newsEditingUid ? '뉴스를 수정했습니다.' : '뉴스를 추가했습니다.');
      loadNews();
    }).catch(function (err) { showModalError('news-error', err.message || '저장에 실패했습니다.'); })
      .then(done);
  };

  window.deleteNews = function (uid) {
    var n = newsData.find(function (x) { return x.uid === uid; });
    if (!confirm('이 뉴스를 삭제하시겠습니까?' + (n ? '\n\n' + n.title : ''))) return;
    apiDelete('/api/news/?uid=' + encodeURIComponent(uid)).then(function () {
      toast('뉴스를 삭제했습니다.');
      loadNews();
    }).catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'err'); });
  };

  // ============================================================
  // 갤러리
  // ============================================================
  var galleryData = [];
  var galleryEditingUid = null;
  var galleryExistingPhotos = [];   // 유지 중인 기존 사진 URL
  var galleryRemovedPhotos = [];    // 저장 시 R2에서 지울 기존 사진 URL
  var galleryNewFiles = [];         // 아직 업로드 안 한 새 파일

  function loadGallery() {
    return apiGet('/api/gallery/').then(function (docs) {
      galleryData = docs || [];
      renderGallery();
    }).catch(loadFailed('갤러리'));
  }

  function renderGallery() {
    var tbody = $('gallery-tbody');
    setTabCount('gallery', galleryData.length);
    setFilterOptions('gallery', galleryData.map(function (g) { return yearOf(g.date); }), true);
    if (!galleryData.length) {
      tbody.innerHTML = emptyRow(5, 'images', '등록된 게시글이 없습니다.');
      applyFilters('gallery');
      return;
    }
    tbody.innerHTML = galleryData.map(function (g) {
      return '<tr' + rowAttrs('openGalleryModal', g.uid, yearOf(g.date)) + '>'
        + '<td class="col-narrow">' + thumbCell((g.photos || [])[0]) + '</td>'
        + '<td><div class="cell-main" title="' + escAttr(g.title) + '">' + esc(g.title) + '</div>'
        + (g.content ? '<div class="cell-sub">' + esc(g.content) + '</div>' : '') + '</td>'
        + '<td class="col-num">' + esc(g.date || '—') + '</td>'
        + '<td class="col-num">' + ((g.photos || []).length) + '장</td>'
        + '<td class="col-actions">' + actionButtons("openGalleryModal('" + g.uid + "')", "deleteGallery('" + g.uid + "')") + '</td></tr>';
    }).join('');
    applyFilters('gallery');
  }

  function renderGalleryPhotoGrid() {
    var grid = $('gallery-photo-grid');
    var html = '';
    var i = 0;
    galleryExistingPhotos.forEach(function (url, idx) {
      html += '<div class="photo-thumb"><img src="' + escAttr(url) + '" alt="">' + (i++ === 0 ? '<span class="cover-tag">대표</span>' : '')
        + '<button type="button" class="remove-btn" title="빼기" onclick="removeGalleryExistingPhoto(' + idx + ')">&times;</button></div>';
    });
    galleryNewFiles.forEach(function (file, idx) {
      html += '<div class="photo-thumb"><img src="' + URL.createObjectURL(file) + '" alt="">' + (i++ === 0 ? '<span class="cover-tag">대표</span>' : '')
        + '<button type="button" class="remove-btn" title="빼기" onclick="removeGalleryNewPhoto(' + idx + ')">&times;</button></div>';
    });
    grid.innerHTML = html || '<div class="text-muted small">아직 사진이 없습니다.</div>';
  }

  window.removeGalleryExistingPhoto = function (idx) {
    galleryRemovedPhotos.push(galleryExistingPhotos[idx]);
    galleryExistingPhotos.splice(idx, 1);
    renderGalleryPhotoGrid();
  };
  window.removeGalleryNewPhoto = function (idx) {
    galleryNewFiles.splice(idx, 1);
    renderGalleryPhotoGrid();
  };
  window.addGalleryPhotos = function (files) {
    var imgs = Array.from(files || []).filter(function (f) { return !f.type || f.type.indexOf('image/') === 0; });
    galleryNewFiles = galleryNewFiles.concat(imgs);
    renderGalleryPhotoGrid();
    $('gallery-image-input').value = '';
  };

  function bindGalleryDrop() {
    var drop = $('gallery-drop');
    if (!drop) return;
    ['dragenter', 'dragover'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('drag'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('drag'); });
    });
    drop.addEventListener('drop', function (e) { addGalleryPhotos(e.dataTransfer.files); });
  }

  function todayDot() {
    var d = new Date();
    return d.getFullYear() + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + String(d.getDate()).padStart(2, '0');
  }

  window.openGalleryModal = function (uid) {
    hideModalError('gallery-error');
    var data = uid ? galleryData.find(function (g) { return g.uid === uid; }) : null;
    galleryEditingUid = uid || null;
    galleryExistingPhotos = data ? (data.photos || []).slice() : [];
    galleryRemovedPhotos = [];
    galleryNewFiles = [];
    $('galleryModalTitle').textContent = uid ? '갤러리 게시글 수정' : '갤러리 게시글 추가';
    $('gallery-title').value = data ? (data.title || '') : '';
    $('gallery-content').value = data ? (data.content || '') : '';
    $('gallery-date').value = data ? (data.date || '') : todayDot();
    $('gallery-image-input').value = '';
    renderGalleryPhotoGrid();
    openModal('galleryModal');
  };

  window.saveGallery = function () {
    var title = $('gallery-title').value.trim();
    if (!title) { showModalError('gallery-error', '제목을 입력해주세요.'); return; }
    if (galleryExistingPhotos.length + galleryNewFiles.length < 1) {
      showModalError('gallery-error', '사진을 최소 1장 이상 등록해야 합니다.');
      return;
    }
    hideModalError('gallery-error');
    var done = setBusy('galleryModal');
    if (!done) return;

    Promise.all(galleryNewFiles.map(function (f) { return uploadImage(f, 'gallery'); }))
      .then(function (uploadedUrls) {
        var payload = {
          uid: galleryEditingUid || undefined,
          title: title,
          content: $('gallery-content').value.trim(),
          date: $('gallery-date').value.trim(),
          photos: galleryExistingPhotos.concat(uploadedUrls),
        };
        return apiPost('/api/gallery/', payload);
      })
      .then(function () {
        return Promise.all(galleryRemovedPhotos.map(deleteImageByUrl));
      })
      .then(function () {
        closeModal('galleryModal');
        toast(galleryEditingUid ? '게시글을 수정했습니다.' : '게시글을 추가했습니다.');
        loadGallery();
      })
      .catch(function (err) { showModalError('gallery-error', err.message || '저장에 실패했습니다.'); })
      .then(done);
  };

  window.deleteGallery = function (uid) {
    var g = galleryData.find(function (x) { return x.uid === uid; });
    if (!confirm('이 게시글을 삭제하시겠습니까? 사진도 모두 함께 삭제됩니다.' + (g ? '\n\n' + g.title : ''))) return;
    apiDelete('/api/gallery/?uid=' + encodeURIComponent(uid)).then(function () {
      toast('게시글을 삭제했습니다.');
      loadGallery();
    }).catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'err'); });
  };

  // ============================================================
  // 팝업
  // ============================================================
  var popupsData = [];
  var popupEditingUid = null;
  var popupImage = '';

  function loadPopups() {
    return apiGet('/api/popups/').then(function (docs) {
      popupsData = docs || [];
      renderPopups();
    }).catch(loadFailed('팝업'));
  }

  // 게시 상태: 비활성 / 예정 / 게시 중 / 종료
  function popupStatus(p) {
    if (!p.is_active) return ['off', '비활성'];
    var today = todayDash();
    if (p.start_date && toDash(p.start_date) > today) return ['wait', '게시 예정'];
    if (p.end_date && toDash(p.end_date) < today) return ['off', '기간 종료'];
    return ['on', '게시 중'];
  }

  function renderPopups() {
    var tbody = $('popups-tbody');
    setTabCount('popups', popupsData.length);
    setFilterOptions('popups', ['게시 중', '게시 예정', '기간 종료', '비활성'].filter(function (s) {
      return popupsData.some(function (p) { return popupStatus(p)[1] === s; });
    }));
    if (!popupsData.length) {
      tbody.innerHTML = emptyRow(5, 'bullhorn', '등록된 팝업이 없습니다.');
      applyFilters('popups');
      return;
    }
    tbody.innerHTML = popupsData.map(function (p) {
      var st = popupStatus(p);
      return '<tr' + rowAttrs('openPopupModal', p.uid, st[1]) + '>'
        + '<td class="col-narrow">' + thumbCell(p.image) + '</td>'
        + '<td><div class="cell-main" title="' + escAttr(p.title) + '">' + esc(p.title) + '</div>'
        + (p.content ? '<div class="cell-sub">' + esc(p.content) + '</div>' : '') + '</td>'
        + '<td class="hide-sm cell-muted" style="white-space:nowrap">' + esc(p.start_date || '—') + ' ~ ' + esc(p.end_date || '—') + '</td>'
        + '<td class="col-narrow"><span class="status-pill ' + st[0] + '">' + st[1] + '</span></td>'
        + '<td class="col-actions">' + actionButtons("openPopupModal('" + p.uid + "')", "deletePopup('" + p.uid + "')") + '</td></tr>';
    }).join('');
    applyFilters('popups');
  }

  function todayDash() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function plusDaysDash(days) {
    var d = new Date();
    d.setDate(d.getDate() + days);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  // 날짜 입력칸(type=date)은 YYYY-MM-DD 만 받으므로 2026.9.1 같은 예전 값도 맞춰 준다.
  function toDash(s) {
    var m = String(s || '').match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
    return m ? m[1] + '-' + m[2].padStart(2, '0') + '-' + m[3].padStart(2, '0') : String(s || '');
  }

  window.openPopupModal = function (uid) {
    hideModalError('popup-error');
    var data = uid ? popupsData.find(function (p) { return p.uid === uid; }) : null;
    popupEditingUid = uid || null;
    popupImage = data ? (data.image || '') : '';
    $('popupModalTitle').textContent = uid ? '팝업 수정' : '팝업 추가';
    $('popup-title').value = data ? (data.title || '') : '';
    $('popup-content').value = data ? (data.content || '') : '';
    $('popup-start').value = data ? toDash(data.start_date || todayDash()) : todayDash();
    $('popup-end').value = data ? toDash(data.end_date || plusDaysDash(30)) : plusDaysDash(30);
    $('popup-link').value = data ? (data.link_url || '') : '';
    $('popup-active').checked = data ? !!data.is_active : true;
    $('popup-image-input').value = '';
    setImageField('popup', popupImage);
    openModal('popupModal');
  };

  window.uploadPopupImage = function (file) {
    uploadInto('popup', file, 'popup', null, function (url) { popupImage = url; });
    $('popup-image-input').value = '';
  };

  window.removePopupImage = function () {
    popupImage = '';
    setImageField('popup', '', '이미지를 뺐습니다 — 저장하면 반영됩니다.');
  };

  window.savePopup = function () {
    var title = $('popup-title').value.trim();
    if (!title) { showModalError('popup-error', '제목을 입력해주세요.'); return; }
    var start = $('popup-start').value.trim(), end = $('popup-end').value.trim();
    if (start && end && end < start) { showModalError('popup-error', '종료일이 시작일보다 빠릅니다.'); return; }
    var done = setBusy('popupModal');
    if (!done) return;
    var payload = {
      uid: popupEditingUid || undefined,
      title: title,
      content: $('popup-content').value.trim(),
      start_date: start,
      end_date: end,
      link_url: $('popup-link').value.trim(),
      is_active: $('popup-active').checked,
      image: popupImage || '',
    };
    apiPost('/api/popups/', payload).then(function () {
      closeModal('popupModal');
      toast(popupEditingUid ? '팝업을 수정했습니다.' : '팝업을 추가했습니다.');
      loadPopups();
    }).catch(function (err) { showModalError('popup-error', err.message || '저장에 실패했습니다.'); })
      .then(done);
  };

  window.deletePopup = function (uid) {
    var p = popupsData.find(function (x) { return x.uid === uid; });
    if (!confirm('이 팝업을 삭제하시겠습니까?' + (p ? '\n\n' + p.title : ''))) return;
    apiDelete('/api/popups/?uid=' + encodeURIComponent(uid)).then(function () {
      toast('팝업을 삭제했습니다.');
      loadPopups();
    }).catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'err'); });
  };

  // ============================================================
  // 입시 FAQ (admission 페이지)
  // ============================================================
  var faqData = [];
  var faqCategoriesData = [];
  var faqEditingUid = null;
  var faqCategoryEditingUid = null;

  function loadFaqCategories() {
    return apiGet('/api/faq/categories').then(function (docs) {
      faqCategoriesData = (docs || []).slice().sort(function (a, b) {
        return (a.order || 0) - (b.order || 0);
      });
      renderFaqCategories();
      populateFaqCategorySelect();
    }).catch(loadFailed('FAQ 카테고리'));
  }

  function loadFaq() {
    return apiGet('/api/faq/').then(function (docs) {
      // 서버가 (카테고리 순서, 항목 순서)로 이미 정렬해 내려준다.
      faqData = docs || [];
      renderFaq();
      renderFaqCategories(); // FAQ 수 갱신
    }).catch(loadFailed('FAQ'));
  }

  function faqCountByCategory(name) {
    return faqData.filter(function (f) { return (f.category || '') === name; }).length;
  }

  // ---- 카테고리 ----
  function renderFaqCategories() {
    var tbody = $('faq-category-tbody');
    if (!tbody) return;
    if (!faqCategoriesData.length) {
      tbody.innerHTML = emptyRow(4, 'folder-tree', '등록된 카테고리가 없습니다.');
      return;
    }
    tbody.innerHTML = faqCategoriesData.map(function (c, idx) {
      var count = faqCountByCategory(c.name);
      var upDisabled = idx === 0 ? ' disabled' : '';
      var downDisabled = idx === faqCategoriesData.length - 1 ? ' disabled' : '';
      var moveBtns =
        '<button class="icon-btn" title="위로" onclick="moveFaqCategory(\'' + c.uid + '\',-1)"' + upDisabled + '><i class="fa-solid fa-arrow-up"></i></button>'
        + '<button class="icon-btn" title="아래로" onclick="moveFaqCategory(\'' + c.uid + '\',1)"' + downDisabled + '><i class="fa-solid fa-arrow-down"></i></button>';
      return '<tr class="row-click" data-edit="openFaqCategoryModal" data-uid="' + escAttr(c.uid) + '">'
        + '<td class="col-num">' + esc(c.order != null ? c.order : '') + '</td>'
        + '<td><div class="cell-main">' + esc(c.name) + '</div></td>'
        + '<td class="col-num">' + count + '개</td>'
        + '<td class="col-actions">' + moveBtns + actionButtons("openFaqCategoryModal('" + c.uid + "')", "deleteFaqCategory('" + c.uid + "')") + '</td></tr>';
    }).join('');
  }

  function populateFaqCategorySelect() {
    var sel = $('faq-category');
    if (!sel) return;
    var current = sel.value;
    var opts = ['<option value="">(분류 없음)</option>'];
    faqCategoriesData.forEach(function (c) {
      opts.push('<option value="' + escAttr(c.name) + '">' + esc(c.name) + '</option>');
    });
    sel.innerHTML = opts.join('');
    sel.value = current;
  }

  window.openFaqCategoryModal = function (uid) {
    hideModalError('faq-category-error');
    var data = uid ? faqCategoriesData.find(function (c) { return c.uid === uid; }) : null;
    faqCategoryEditingUid = uid || null;
    $('faqCategoryModalTitle').textContent = uid ? '카테고리 수정' : '카테고리 추가';
    $('faq-category-name').value = data ? (data.name || '') : '';
    var nextOrder = data ? data.order
      : (faqCategoriesData.reduce(function (m, c) { return Math.max(m, c.order || 0); }, 0) + 10);
    $('faq-category-order').value = (nextOrder != null ? nextOrder : '');
    openModal('faqCategoryModal');
  };

  window.saveFaqCategory = function () {
    var name = $('faq-category-name').value.trim();
    if (!name) { showModalError('faq-category-error', '이름을 입력해주세요.'); return; }
    var order = parseInt($('faq-category-order').value, 10);
    if (isNaN(order)) { showModalError('faq-category-error', '순서는 숫자로 입력해주세요.'); return; }
    var done = setBusy('faqCategoryModal');
    if (!done) return;
    apiPost('/api/faq/categories', {
      uid: faqCategoryEditingUid || undefined,
      name: name,
      order: order,
    }).then(function () {
      closeModal('faqCategoryModal');
      toast(faqCategoryEditingUid ? '카테고리를 수정했습니다.' : '카테고리를 추가했습니다.');
      // 이름 변경 시 FAQ 항목의 분류도 서버에서 바뀌므로 둘 다 다시 불러온다.
      return Promise.all([loadFaqCategories(), loadFaq()]);
    }).catch(function (err) { showModalError('faq-category-error', err.message || '저장에 실패했습니다.'); })
      .then(done);
  };

  window.deleteFaqCategory = function (uid) {
    var c = faqCategoriesData.find(function (x) { return x.uid === uid; });
    if (!c) return;
    if (!confirm('["' + c.name + '"] 카테고리를 삭제하시겠습니까?')) return;
    apiDelete('/api/faq/categories?uid=' + encodeURIComponent(uid))
      .then(function () { toast('카테고리를 삭제했습니다.'); return loadFaqCategories(); })
      .catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'err'); });
  };

  window.moveFaqCategory = function (uid, dir) {
    var idx = faqCategoriesData.findIndex(function (c) { return c.uid === uid; });
    if (idx < 0) return;
    var other = faqCategoriesData[idx + dir];
    var cur = faqCategoriesData[idx];
    if (!other || !cur) return;
    var a = { uid: cur.uid, name: cur.name, order: other.order };
    var b = { uid: other.uid, name: other.name, order: cur.order };
    apiPost('/api/faq/categories', a)
      .then(function () { return apiPost('/api/faq/categories', b); })
      .then(function () { return Promise.all([loadFaqCategories(), loadFaq()]); })
      .catch(function (err) { toast(err.message || '순서 변경에 실패했습니다.', 'err'); });
  };

  // ---- FAQ 항목 ----
  function renderFaq() {
    var tbody = $('faq-tbody');
    setTabCount('faq', faqData.length);
    setFilterOptions('faq', faqData.map(function (f) { return (f.category || '').trim() || '(분류 없음)'; }));

    if (!faqData.length) {
      tbody.innerHTML = emptyRow(3, 'circle-question', '등록된 FAQ가 없습니다.');
      applyFilters('faq');
      return;
    }

    var lastCategory = null;
    tbody.innerHTML = faqData.map(function (f, idx) {
      var cat = (f.category || '').trim();
      var groupRow = '';
      if (cat !== lastCategory) {
        groupRow = '<tr class="group-row" data-group><td colspan="3"><i class="fa-solid fa-folder-open me-2"></i>' + (cat ? esc(cat) : '(분류 없음)') + '</td></tr>';
        lastCategory = cat;
      }
      return groupRow + '<tr' + rowAttrs('openFaqModal', f.uid, cat || '(분류 없음)') + '>'
        + '<td class="col-num">' + esc(f.order != null ? f.order : '') + '</td>'
        + '<td><div class="cell-main" title="' + escAttr(f.question) + '">Q' + (idx + 1) + '. ' + esc(f.question) + '</div>'
        + (f.answer ? '<div class="cell-sub">' + esc(f.answer) + '</div>' : '<div class="cell-sub">답변 없음</div>') + '</td>'
        + '<td class="col-actions">' + actionButtons("openFaqModal('" + f.uid + "')", "deleteFaq('" + f.uid + "')") + '</td></tr>';
    }).join('');
    applyFilters('faq');
  }

  window.openFaqModal = function (uid) {
    hideModalError('faq-error');
    var data = uid ? faqData.find(function (f) { return f.uid === uid; }) : null;
    faqEditingUid = uid || null;
    $('faqModalTitle').textContent = uid ? 'FAQ 수정' : 'FAQ 추가';

    var sel = $('faq-category');
    populateFaqCategorySelect();
    var wantCat = data ? (data.category || '') : (faqData.length ? faqData[faqData.length - 1].category || '' : '');
    // 목록에 없는 (레거시) 분류면 임시 옵션을 추가해 유실을 막는다.
    if (wantCat && !Array.prototype.some.call(sel.options, function (o) { return o.value === wantCat; })) {
      sel.insertAdjacentHTML('beforeend', '<option value="' + escAttr(wantCat) + '">' + esc(wantCat) + ' (목록에 없음)</option>');
    }
    sel.value = wantCat;

    $('faq-question').value = data ? (data.question || '') : '';
    $('faq-answer').value = data ? (data.answer || '') : '';
    var sameCat = faqData.filter(function (f) { return (f.category || '') === wantCat; });
    var nextOrder = data ? data.order
      : (sameCat.reduce(function (m, f) { return Math.max(m, f.order || 0); }, 0) + 10);
    $('faq-order').value = (nextOrder != null ? nextOrder : '');
    openModal('faqModal');
  };

  window.saveFaq = function () {
    var question = $('faq-question').value.trim();
    if (!question) { showModalError('faq-error', '질문을 입력해주세요.'); return; }
    var order = parseInt($('faq-order').value, 10);
    if (isNaN(order)) { showModalError('faq-error', '순서는 숫자로 입력해주세요.'); return; }
    var done = setBusy('faqModal');
    if (!done) return;
    var payload = {
      uid: faqEditingUid || undefined,
      category: $('faq-category').value.trim(),
      question: question,
      answer: $('faq-answer').value.replace(/\r\n/g, '\n'),
      order: order,
    };
    apiPost('/api/faq/', payload).then(function () {
      closeModal('faqModal');
      toast(faqEditingUid ? 'FAQ를 수정했습니다.' : 'FAQ를 추가했습니다.');
      return Promise.all([loadFaq(), loadFaqCategories()]);
    }).catch(function (err) { showModalError('faq-error', err.message || '저장에 실패했습니다.'); })
      .then(done);
  };

  window.deleteFaq = function (uid) {
    if (!confirm('이 FAQ 항목을 정말 삭제하시겠습니까?')) return;
    apiDelete('/api/faq/?uid=' + encodeURIComponent(uid))
      .then(function () { toast('FAQ를 삭제했습니다.'); return Promise.all([loadFaq(), loadFaqCategories()]); })
      .catch(function (err) { toast(err.message || '삭제에 실패했습니다.', 'err'); });
  };

})();
