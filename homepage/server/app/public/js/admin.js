// 콘텐츠 관리 대시보드(/admin) — 논문/멤버/뉴스/갤러리/팝업 CRUD.
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
    var el = document.getElementById('count-' + id);
    if (el) el.textContent = n;
  }

  function thumbCell(url) {
    return url
      ? '<img class="row-thumb" src="' + escAttr(url) + '">'
      : '<div class="row-thumb-placeholder"><i class="fa-solid fa-image"></i></div>';
  }

  function actionButtons(editFn, deleteFn) {
    return '<button class="icon-btn" title="수정" onclick="' + editFn + '"><i class="fa-solid fa-pen"></i></button>'
      + '<button class="icon-btn danger" title="삭제" onclick="' + deleteFn + '"><i class="fa-solid fa-trash"></i></button>';
  }

  function showModalError(id, msg) {
    var el = document.getElementById(id);
    el.textContent = msg;
    el.style.display = 'block';
  }
  function hideModalError(id) {
    document.getElementById(id).style.display = 'none';
  }
  function closeModal(id) {
    var el = document.getElementById(id);
    var instance = bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el);
    instance.hide();
  }
  function openModal(id) {
    new bootstrap.Modal(document.getElementById(id)).show();
  }

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
    document.getElementById('admin-loading').style.display = 'none';
    document.getElementById('admin-content').style.display = 'block';
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

  // ============================================================
  // 논문
  // ============================================================
  var papersData = [];
  var paperEditingUid = null;
  var paperCrawledRecord = {};

  function loadPapers() {
    apiGet('/api/papers/').then(function (groups) {
      papersData = [];
      (groups || []).forEach(function (g) {
        (g.papers || []).forEach(function (p) { p.year = g.year; papersData.push(p); });
      });
      renderPapers();
    }).catch(function () { });
  }

  function renderPapers() {
    var tbody = document.getElementById('papers-tbody');
    setTabCount('papers', papersData.length);
    if (!papersData.length) {
      tbody.innerHTML = '<tr><td colspan="5"><div class="admin-empty"><i class="fa-solid fa-file-lines"></i>등록된 논문이 없습니다.</div></td></tr>';
      return;
    }
    tbody.innerHTML = papersData.map(function (p) {
      var authors = (p.authors || []).join(', ');
      return '<tr>'
        + '<td>' + esc(p.year) + '</td>'
        + '<td class="cell-truncate" title="' + escAttr(p.title) + '">' + esc(p.title) + '</td>'
        + '<td class="cell-truncate" title="' + escAttr(authors) + '">' + esc(authors) + '</td>'
        + '<td class="cell-truncate">' + esc(p.venue || '') + '</td>'
        + '<td class="col-actions">' + actionButtons("openPaperModal('" + p.uid + "')", "deletePaper('" + p.uid + "')") + '</td></tr>';
    }).join('');
  }

  window.openPaperModal = function (uid) {
    hideModalError('paper-error');
    var data = uid ? papersData.find(function (p) { return p.uid === uid; }) : null;
    paperEditingUid = uid || null;
    paperCrawledRecord = data ? Object.assign({}, data) : {};
    document.getElementById('paperModalTitle').textContent = uid ? '논문 수정' : '논문 추가';
    document.getElementById('paper-title').value = data ? (data.title || '') : '';
    document.getElementById('paper-year').value = data ? (data.year || '') : '';
    document.getElementById('paper-authors').value = data ? (data.authors || []).join(', ') : '';
    document.getElementById('paper-venue').value = data ? (data.venue || '') : '';
    document.getElementById('paper-url').value = data ? (data.url || '') : '';
    document.getElementById('paper-journal-type').value = (data && data.journal_type) || 'KCI';
    openModal('paperModal');
  };

  window.crawlPaperMetadata = function () {
    var title = document.getElementById('paper-title').value.trim();
    if (!title) { showModalError('paper-error', '제목을 먼저 입력해주세요.'); return; }
    var type = document.getElementById('paper-journal-type').value;
    hideModalError('paper-error');
    apiGet('/api/papers/crawl?title=' + encodeURIComponent(title) + '&type=' + encodeURIComponent(type))
      .then(function (record) {
        paperCrawledRecord = record || {};
        document.getElementById('paper-year').value = record.year || '';
        document.getElementById('paper-title').value = record.title || title;
        document.getElementById('paper-authors').value = (record.authors || []).join(', ');
        document.getElementById('paper-venue').value = record.venue || '';
        document.getElementById('paper-url').value = record.url || '';
      })
      .catch(function (err) { showModalError('paper-error', err.message || '메타데이터를 가져오지 못했습니다.'); });
  };

  window.savePaper = function () {
    var year = parseInt(document.getElementById('paper-year').value, 10);
    if (!year) { showModalError('paper-error', '연도는 숫자로 입력해주세요.'); return; }
    var authors = document.getElementById('paper-authors').value.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    var payload = Object.assign({}, paperCrawledRecord, {
      uid: paperEditingUid || paperCrawledRecord.uid || undefined,
      title: document.getElementById('paper-title').value.trim(),
      authors: authors,
      year: year,
      venue: document.getElementById('paper-venue').value.trim(),
      url: document.getElementById('paper-url').value.trim(),
      journal_type: document.getElementById('paper-journal-type').value,
    });
    apiPost('/api/papers/', payload).then(function () {
      closeModal('paperModal');
      loadPapers();
    }).catch(function (err) { showModalError('paper-error', err.message || '저장에 실패했습니다.'); });
  };

  window.deletePaper = function (uid) {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    apiDelete('/api/papers/?uid=' + encodeURIComponent(uid)).then(loadPapers)
      .catch(function (err) { alert(err.message || '삭제에 실패했습니다.'); });
  };

  // ============================================================
  // 멤버
  // ============================================================
  var membersData = [];
  var memberEditingUid = null;
  var memberNewImageUrl = null;
  var memberOptions = { positions: [], sections: [] };

  function loadMemberOptions() {
    apiGet('/api/members/options').then(function (opts) {
      memberOptions = opts || { positions: [], sections: [] };
      var posSel = document.getElementById('member-position');
      var secSel = document.getElementById('member-section');
      posSel.innerHTML = memberOptions.positions.map(function (p) { return '<option value="' + escAttr(p) + '">' + esc(p) + '</option>'; }).join('');
      secSel.innerHTML = memberOptions.sections.map(function (s) { return '<option value="' + escAttr(s) + '">' + esc(s) + '</option>'; }).join('');
    }).catch(function () { });
  }

  function loadMembers() {
    apiGet('/api/members/').then(function (docs) {
      membersData = docs || [];
      renderMembers();
    }).catch(function () { });
  }

  function renderMembers() {
    var tbody = document.getElementById('members-tbody');
    setTabCount('members', membersData.length);
    if (!membersData.length) {
      tbody.innerHTML = '<tr><td colspan="6"><div class="admin-empty"><i class="fa-solid fa-users"></i>등록된 멤버가 없습니다.</div></td></tr>';
      return;
    }
    tbody.innerHTML = membersData.map(function (m) {
      return '<tr>'
        + '<td>' + thumbCell(m.image) + '</td>'
        + '<td>' + esc(m.name) + '</td>'
        + '<td>' + esc(m.section || '') + '</td>'
        + '<td>' + esc(m.position || '') + '</td>'
        + '<td class="cell-truncate">' + esc(m.email || '') + '</td>'
        + '<td class="col-actions">' + actionButtons(
          "openMemberModal('" + m.uid + "')",
          "deleteMember('" + m.uid + "', " + JSON.stringify(m.name) + ")"
        ) + '</td></tr>';
    }).join('');
  }

  function listToText(v) {
    if (Array.isArray(v)) return v.join('\n');
    return v ? String(v) : '';
  }

  window.openMemberModal = function (uid) {
    hideModalError('member-error');
    var data = uid ? membersData.find(function (m) { return m.uid === uid; }) : null;
    memberEditingUid = uid || null;
    memberNewImageUrl = null;
    document.getElementById('memberModalTitle').textContent = uid ? '멤버 수정' : '멤버 추가';
    document.getElementById('member-name').value = data ? (data.name || '') : '';
    document.getElementById('member-affiliation').value = data ? (data.affiliation || '') : '';
    document.getElementById('member-email').value = data ? (data.email || '') : '';
    document.getElementById('member-school').value = data ? listToText(data['학력']) : '';
    document.getElementById('member-career').value = data ? listToText(data['경력']) : '';
    document.getElementById('member-research').value = data ? listToText(data['연구']) : '';
    document.getElementById('member-awards').value = data ? listToText(data['수상']) : '';
    document.getElementById('member-position').value = (data && data.position) || (memberOptions.positions[0] || '');
    document.getElementById('member-section').value = (data && data.section) || (memberOptions.sections[0] || '');
    document.getElementById('member-image-input').value = '';
    document.getElementById('member-image-status').textContent = data && data.image ? '현재 이미지 있음' : '이미지 없음';
    openModal('memberModal');
  };

  window.uploadMemberImage = function (file) {
    if (!file) return;
    var name = document.getElementById('member-name').value.trim() || 'member';
    document.getElementById('member-image-status').textContent = '업로드 중...';
    uploadImage(file, 'members', 'members/' + name.replace(/[^\w가-힣-]/g, '_') + '_' + randomName())
      .then(function (url) {
        memberNewImageUrl = url;
        document.getElementById('member-image-status').textContent = '업로드 완료';
      })
      .catch(function (err) {
        document.getElementById('member-image-status').textContent = '업로드 실패: ' + (err.message || '');
      });
  };

  window.saveMember = function () {
    var name = document.getElementById('member-name').value.trim();
    if (!name) { showModalError('member-error', '이름을 입력해주세요.'); return; }
    var editing = memberEditingUid ? membersData.find(function (m) { return m.uid === memberEditingUid; }) : null;
    var payload = {
      uid: memberEditingUid || undefined,
      name: name,
      position: document.getElementById('member-position').value,
      affiliation: document.getElementById('member-affiliation').value.trim(),
      section: document.getElementById('member-section').value,
      email: document.getElementById('member-email').value.trim(),
      '학력': document.getElementById('member-school').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean),
      '경력': document.getElementById('member-career').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean),
      '연구': document.getElementById('member-research').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean),
      '수상': document.getElementById('member-awards').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean),
      image: memberNewImageUrl || (editing ? editing.image || '' : ''),
    };
    apiPost('/api/members/', payload).then(function () {
      closeModal('memberModal');
      loadMembers();
    }).catch(function (err) { showModalError('member-error', err.message || '저장에 실패했습니다.'); });
  };

  window.deleteMember = function (uid, name) {
    if (!confirm('[' + name + '] 멤버를 정말 삭제하시겠습니까?')) return;
    var confirmName = prompt('삭제 확인을 위해 멤버의 이름(' + name + ')을 정확히 입력해주세요.');
    if (confirmName === null) return;
    if (confirmName !== name) { alert('이름이 일치하지 않습니다. 삭제를 취소합니다.'); return; }
    apiDelete('/api/members/?uid=' + encodeURIComponent(uid)).then(loadMembers)
      .catch(function (err) { alert(err.message || '삭제에 실패했습니다.'); });
  };

  // ============================================================
  // 뉴스
  // ============================================================
  var newsData = [];
  var newsEditingUid = null;
  var newsNewImageUrl = null;

  function loadNews() {
    apiGet('/api/news/').then(function (docs) {
      newsData = docs || [];
      renderNews();
    }).catch(function () { });
  }

  function renderNews() {
    var tbody = document.getElementById('news-tbody');
    setTabCount('news', newsData.length);
    if (!newsData.length) {
      tbody.innerHTML = '<tr><td colspan="5"><div class="admin-empty"><i class="fa-solid fa-newspaper"></i>등록된 뉴스가 없습니다.</div></td></tr>';
      return;
    }
    tbody.innerHTML = newsData.map(function (n) {
      return '<tr>'
        + '<td>' + thumbCell(n.image) + '</td>'
        + '<td class="cell-truncate" title="' + escAttr(n.title) + '">' + esc(n.title) + '</td>'
        + '<td>' + esc(n.date || '') + '</td>'
        + '<td class="cell-truncate">' + esc(n.url || '') + '</td>'
        + '<td class="col-actions">' + actionButtons("openNewsModal('" + n.uid + "')", "deleteNews('" + n.uid + "')") + '</td></tr>';
    }).join('');
  }

  window.openNewsModal = function (uid) {
    hideModalError('news-error');
    var data = uid ? newsData.find(function (n) { return n.uid === uid; }) : null;
    newsEditingUid = uid || null;
    newsNewImageUrl = null;
    document.getElementById('newsModalTitle').textContent = uid ? '뉴스 수정' : '뉴스 추가';
    document.getElementById('news-title').value = data ? (data.title || '') : '';
    document.getElementById('news-content').value = data ? (data.content || '') : '';
    document.getElementById('news-date').value = data ? (data.date || '') : '';
    document.getElementById('news-url').value = data ? (data.url || '') : '';
    document.getElementById('news-image-input').value = '';
    document.getElementById('news-image-status').textContent = data && data.image ? '현재 이미지 있음' : '이미지 없음';
    openModal('newsModal');
  };

  window.uploadNewsImage = function (file) {
    if (!file) return;
    document.getElementById('news-image-status').textContent = '업로드 중...';
    uploadImage(file, 'news').then(function (url) {
      newsNewImageUrl = url;
      document.getElementById('news-image-status').textContent = '업로드 완료';
    }).catch(function (err) {
      document.getElementById('news-image-status').textContent = '업로드 실패: ' + (err.message || '');
    });
  };

  window.saveNews = function () {
    var title = document.getElementById('news-title').value.trim();
    if (!title) { showModalError('news-error', '제목을 입력해주세요.'); return; }
    var editing = newsEditingUid ? newsData.find(function (n) { return n.uid === newsEditingUid; }) : null;
    var payload = {
      uid: newsEditingUid || undefined,
      title: title,
      content: document.getElementById('news-content').value.trim(),
      date: document.getElementById('news-date').value.trim(),
      url: document.getElementById('news-url').value.trim(),
      image: newsNewImageUrl || (editing ? editing.image || '' : ''),
    };
    apiPost('/api/news/', payload).then(function () {
      closeModal('newsModal');
      loadNews();
    }).catch(function (err) { showModalError('news-error', err.message || '저장에 실패했습니다.'); });
  };

  window.deleteNews = function (uid) {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    apiDelete('/api/news/?uid=' + encodeURIComponent(uid)).then(loadNews)
      .catch(function (err) { alert(err.message || '삭제에 실패했습니다.'); });
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
    apiGet('/api/gallery/').then(function (docs) {
      galleryData = docs || [];
      renderGallery();
    }).catch(function () { });
  }

  function renderGallery() {
    var tbody = document.getElementById('gallery-tbody');
    setTabCount('gallery', galleryData.length);
    if (!galleryData.length) {
      tbody.innerHTML = '<tr><td colspan="5"><div class="admin-empty"><i class="fa-solid fa-images"></i>등록된 게시글이 없습니다.</div></td></tr>';
      return;
    }
    tbody.innerHTML = galleryData.map(function (g) {
      return '<tr>'
        + '<td>' + thumbCell((g.photos || [])[0]) + '</td>'
        + '<td class="cell-truncate" title="' + escAttr(g.title) + '">' + esc(g.title) + '</td>'
        + '<td>' + esc(g.date || '') + '</td>'
        + '<td>' + ((g.photos || []).length) + '</td>'
        + '<td class="col-actions">' + actionButtons("openGalleryModal('" + g.uid + "')", "deleteGallery('" + g.uid + "')") + '</td></tr>';
    }).join('');
  }

  function renderGalleryPhotoGrid() {
    var grid = document.getElementById('gallery-photo-grid');
    var html = '';
    galleryExistingPhotos.forEach(function (url, idx) {
      html += '<div class="photo-thumb"><img src="' + escAttr(url) + '">'
        + '<button type="button" class="remove-btn" onclick="removeGalleryExistingPhoto(' + idx + ')">&times;</button></div>';
    });
    galleryNewFiles.forEach(function (file, idx) {
      html += '<div class="photo-thumb"><img src="' + URL.createObjectURL(file) + '">'
        + '<button type="button" class="remove-btn" onclick="removeGalleryNewPhoto(' + idx + ')">&times;</button></div>';
    });
    grid.innerHTML = html || '<div class="text-muted small">등록된 사진이 없습니다.</div>';
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
    galleryNewFiles = galleryNewFiles.concat(Array.from(files));
    renderGalleryPhotoGrid();
    document.getElementById('gallery-image-input').value = '';
  };

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
    document.getElementById('galleryModalTitle').textContent = uid ? '갤러리 게시글 수정' : '갤러리 게시글 추가';
    document.getElementById('gallery-title').value = data ? (data.title || '') : '';
    document.getElementById('gallery-content').value = data ? (data.content || '') : '';
    document.getElementById('gallery-date').value = data ? (data.date || '') : todayDot();
    document.getElementById('gallery-image-input').value = '';
    renderGalleryPhotoGrid();
    openModal('galleryModal');
  };

  window.saveGallery = function () {
    var title = document.getElementById('gallery-title').value.trim();
    if (!title) { showModalError('gallery-error', '제목을 입력해주세요.'); return; }
    if (galleryExistingPhotos.length + galleryNewFiles.length < 1) {
      showModalError('gallery-error', '사진을 최소 1장 이상 등록해야 합니다.');
      return;
    }
    hideModalError('gallery-error');

    Promise.all(galleryNewFiles.map(function (f) { return uploadImage(f, 'gallery'); }))
      .then(function (uploadedUrls) {
        var payload = {
          uid: galleryEditingUid || undefined,
          title: title,
          content: document.getElementById('gallery-content').value.trim(),
          date: document.getElementById('gallery-date').value.trim(),
          photos: galleryExistingPhotos.concat(uploadedUrls),
        };
        return apiPost('/api/gallery/', payload);
      })
      .then(function () {
        return Promise.all(galleryRemovedPhotos.map(deleteImageByUrl));
      })
      .then(function () {
        closeModal('galleryModal');
        loadGallery();
      })
      .catch(function (err) { showModalError('gallery-error', err.message || '저장에 실패했습니다.'); });
  };

  window.deleteGallery = function (uid) {
    if (!confirm('정말 삭제하시겠습니까? (사진도 모두 함께 삭제됩니다)')) return;
    apiDelete('/api/gallery/?uid=' + encodeURIComponent(uid)).then(loadGallery)
      .catch(function (err) { alert(err.message || '삭제에 실패했습니다.'); });
  };

  // ============================================================
  // 팝업
  // ============================================================
  var popupsData = [];
  var popupEditingUid = null;
  var popupNewImageUrl = null;

  function loadPopups() {
    apiGet('/api/popups/').then(function (docs) {
      popupsData = docs || [];
      renderPopups();
    }).catch(function () { });
  }

  function renderPopups() {
    var tbody = document.getElementById('popups-tbody');
    setTabCount('popups', popupsData.length);
    if (!popupsData.length) {
      tbody.innerHTML = '<tr><td colspan="6"><div class="admin-empty"><i class="fa-solid fa-bullhorn"></i>등록된 팝업이 없습니다.</div></td></tr>';
      return;
    }
    tbody.innerHTML = popupsData.map(function (p) {
      return '<tr>'
        + '<td>' + thumbCell(p.image) + '</td>'
        + '<td class="cell-truncate" title="' + escAttr(p.title) + '">' + esc(p.title) + '</td>'
        + '<td>' + esc(p.start_date || '') + '</td>'
        + '<td>' + esc(p.end_date || '') + '</td>'
        + '<td>' + (p.is_active ? '<span class="status-pill on">활성</span>' : '<span class="status-pill off">비활성</span>') + '</td>'
        + '<td class="col-actions">' + actionButtons("openPopupModal('" + p.uid + "')", "deletePopup('" + p.uid + "')") + '</td></tr>';
    }).join('');
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

  window.openPopupModal = function (uid) {
    hideModalError('popup-error');
    var data = uid ? popupsData.find(function (p) { return p.uid === uid; }) : null;
    popupEditingUid = uid || null;
    popupNewImageUrl = null;
    document.getElementById('popupModalTitle').textContent = uid ? '팝업 수정' : '팝업 추가';
    document.getElementById('popup-title').value = data ? (data.title || '') : '';
    document.getElementById('popup-content').value = data ? (data.content || '') : '';
    document.getElementById('popup-start').value = data ? (data.start_date || todayDash()) : todayDash();
    document.getElementById('popup-end').value = data ? (data.end_date || plusDaysDash(30)) : plusDaysDash(30);
    document.getElementById('popup-link').value = data ? (data.link_url || '') : '';
    document.getElementById('popup-active').checked = data ? !!data.is_active : true;
    document.getElementById('popup-image-input').value = '';
    document.getElementById('popup-image-status').textContent = data && data.image ? '현재 이미지 있음' : '이미지 없음';
    openModal('popupModal');
  };

  window.uploadPopupImage = function (file) {
    if (!file) return;
    document.getElementById('popup-image-status').textContent = '업로드 중...';
    uploadImage(file, 'popup').then(function (url) {
      popupNewImageUrl = url;
      document.getElementById('popup-image-status').textContent = '업로드 완료';
    }).catch(function (err) {
      document.getElementById('popup-image-status').textContent = '업로드 실패: ' + (err.message || '');
    });
  };

  window.savePopup = function () {
    var title = document.getElementById('popup-title').value.trim();
    if (!title) { showModalError('popup-error', '제목을 입력해주세요.'); return; }
    var editing = popupEditingUid ? popupsData.find(function (p) { return p.uid === popupEditingUid; }) : null;
    var payload = {
      uid: popupEditingUid || undefined,
      title: title,
      content: document.getElementById('popup-content').value.trim(),
      start_date: document.getElementById('popup-start').value.trim(),
      end_date: document.getElementById('popup-end').value.trim(),
      link_url: document.getElementById('popup-link').value.trim(),
      is_active: document.getElementById('popup-active').checked,
      image: popupNewImageUrl || (editing ? editing.image || '' : ''),
    };
    apiPost('/api/popups/', payload).then(function () {
      closeModal('popupModal');
      loadPopups();
    }).catch(function (err) { showModalError('popup-error', err.message || '저장에 실패했습니다.'); });
  };

  window.deletePopup = function (uid) {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    apiDelete('/api/popups/?uid=' + encodeURIComponent(uid)).then(loadPopups)
      .catch(function (err) { alert(err.message || '삭제에 실패했습니다.'); });
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
    }).catch(function () { });
  }

  function loadFaq() {
    return apiGet('/api/faq/').then(function (docs) {
      // 서버가 (카테고리 순서, 항목 순서)로 이미 정렬해 내려준다.
      faqData = docs || [];
      renderFaq();
      renderFaqCategories(); // FAQ 수 갱신
    }).catch(function () { });
  }

  function faqCountByCategory(name) {
    return faqData.filter(function (f) { return (f.category || '') === name; }).length;
  }

  // ---- 카테고리 ----
  function renderFaqCategories() {
    var tbody = document.getElementById('faq-category-tbody');
    if (!tbody) return;
    if (!faqCategoriesData.length) {
      tbody.innerHTML = '<tr><td colspan="4"><div class="admin-empty"><i class="fa-solid fa-folder-tree"></i>등록된 카테고리가 없습니다.</div></td></tr>';
      return;
    }
    tbody.innerHTML = faqCategoriesData.map(function (c, idx) {
      var count = faqCountByCategory(c.name);
      var upDisabled = idx === 0 ? ' disabled' : '';
      var downDisabled = idx === faqCategoriesData.length - 1 ? ' disabled' : '';
      var moveBtns =
        '<button class="icon-btn" title="위로" onclick="moveFaqCategory(\'' + c.uid + '\',-1)"' + upDisabled + '><i class="fa-solid fa-arrow-up"></i></button>'
        + '<button class="icon-btn" title="아래로" onclick="moveFaqCategory(\'' + c.uid + '\',1)"' + downDisabled + '><i class="fa-solid fa-arrow-down"></i></button>';
      return '<tr>'
        + '<td>' + esc(c.order != null ? c.order : '') + '</td>'
        + '<td class="cell-truncate">' + esc(c.name) + '</td>'
        + '<td>' + count + '</td>'
        + '<td class="col-actions">' + moveBtns + actionButtons("openFaqCategoryModal('" + c.uid + "')", "deleteFaqCategory('" + c.uid + "')") + '</td></tr>';
    }).join('');
  }

  function populateFaqCategorySelect() {
    var sel = document.getElementById('faq-category');
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
    document.getElementById('faqCategoryModalTitle').textContent = uid ? '카테고리 수정' : '카테고리 추가';
    document.getElementById('faq-category-name').value = data ? (data.name || '') : '';
    var nextOrder = data ? data.order
      : (faqCategoriesData.reduce(function (m, c) { return Math.max(m, c.order || 0); }, 0) + 10);
    document.getElementById('faq-category-order').value = (nextOrder != null ? nextOrder : '');
    openModal('faqCategoryModal');
  };

  window.saveFaqCategory = function () {
    var name = document.getElementById('faq-category-name').value.trim();
    if (!name) { showModalError('faq-category-error', '이름을 입력해주세요.'); return; }
    var order = parseInt(document.getElementById('faq-category-order').value, 10);
    if (isNaN(order)) { showModalError('faq-category-error', '순서는 숫자로 입력해주세요.'); return; }
    apiPost('/api/faq/categories', {
      uid: faqCategoryEditingUid || undefined,
      name: name,
      order: order,
    }).then(function () {
      closeModal('faqCategoryModal');
      // 이름 변경 시 FAQ 항목의 분류도 서버에서 바뀌므로 둘 다 다시 불러온다.
      return Promise.all([loadFaqCategories(), loadFaq()]);
    }).catch(function (err) { showModalError('faq-category-error', err.message || '저장에 실패했습니다.'); });
  };

  window.deleteFaqCategory = function (uid) {
    var c = faqCategoriesData.find(function (x) { return x.uid === uid; });
    if (!c) return;
    if (!confirm('["' + c.name + '"] 카테고리를 삭제하시겠습니까?')) return;
    apiDelete('/api/faq/categories?uid=' + encodeURIComponent(uid))
      .then(function () { return loadFaqCategories(); })
      .catch(function (err) { alert(err.message || '삭제에 실패했습니다.'); });
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
      .catch(function (err) { alert(err.message || '순서 변경에 실패했습니다.'); });
  };

  // ---- FAQ 항목 ----
  function renderFaq() {
    var tbody = document.getElementById('faq-tbody');
    setTabCount('faq', faqData.length);

    if (!faqData.length) {
      tbody.innerHTML = '<tr><td colspan="4"><div class="admin-empty"><i class="fa-solid fa-circle-question"></i>등록된 FAQ가 없습니다.</div></td></tr>';
      return;
    }

    var lastCategory = null;
    tbody.innerHTML = faqData.map(function (f, idx) {
      var cat = (f.category || '').trim();
      var groupRow = '';
      if (cat !== lastCategory) {
        groupRow = '<tr><td colspan="4" class="fw-bold small text-secondary bg-light">' + (cat ? esc(cat) : '<span class="text-muted">(분류 없음)</span>') + '</td></tr>';
        lastCategory = cat;
      }
      return groupRow + '<tr>'
        + '<td>' + esc(f.order != null ? f.order : '') + '</td>'
        + '<td class="cell-truncate">' + esc(cat) + '</td>'
        + '<td class="cell-truncate" title="' + escAttr(f.question) + '">Q' + (idx + 1) + '. ' + esc(f.question) + '</td>'
        + '<td class="col-actions">' + actionButtons("openFaqModal('" + f.uid + "')", "deleteFaq('" + f.uid + "')") + '</td></tr>';
    }).join('');
  }

  window.openFaqModal = function (uid) {
    hideModalError('faq-error');
    var data = uid ? faqData.find(function (f) { return f.uid === uid; }) : null;
    faqEditingUid = uid || null;
    document.getElementById('faqModalTitle').textContent = uid ? 'FAQ 수정' : 'FAQ 추가';

    var sel = document.getElementById('faq-category');
    populateFaqCategorySelect();
    var wantCat = data ? (data.category || '') : (faqData.length ? faqData[faqData.length - 1].category || '' : '');
    // 목록에 없는 (레거시) 분류면 임시 옵션을 추가해 유실을 막는다.
    if (wantCat && !Array.prototype.some.call(sel.options, function (o) { return o.value === wantCat; })) {
      sel.insertAdjacentHTML('beforeend', '<option value="' + escAttr(wantCat) + '">' + esc(wantCat) + ' (목록에 없음)</option>');
    }
    sel.value = wantCat;

    document.getElementById('faq-question').value = data ? (data.question || '') : '';
    document.getElementById('faq-answer').value = data ? (data.answer || '') : '';
    var sameCat = faqData.filter(function (f) { return (f.category || '') === wantCat; });
    var nextOrder = data ? data.order
      : (sameCat.reduce(function (m, f) { return Math.max(m, f.order || 0); }, 0) + 10);
    document.getElementById('faq-order').value = (nextOrder != null ? nextOrder : '');
    openModal('faqModal');
  };

  window.saveFaq = function () {
    var question = document.getElementById('faq-question').value.trim();
    if (!question) { showModalError('faq-error', '질문을 입력해주세요.'); return; }
    var order = parseInt(document.getElementById('faq-order').value, 10);
    if (isNaN(order)) { showModalError('faq-error', '순서는 숫자로 입력해주세요.'); return; }
    var payload = {
      uid: faqEditingUid || undefined,
      category: document.getElementById('faq-category').value.trim(),
      question: question,
      answer: document.getElementById('faq-answer').value.replace(/\r\n/g, '\n'),
      order: order,
    };
    apiPost('/api/faq/', payload).then(function () {
      closeModal('faqModal');
      return Promise.all([loadFaq(), loadFaqCategories()]);
    }).catch(function (err) { showModalError('faq-error', err.message || '저장에 실패했습니다.'); });
  };

  window.deleteFaq = function (uid) {
    if (!confirm('이 FAQ 항목을 정말 삭제하시겠습니까?')) return;
    apiDelete('/api/faq/?uid=' + encodeURIComponent(uid))
      .then(function () { return Promise.all([loadFaq(), loadFaqCategories()]); })
      .catch(function (err) { alert(err.message || '삭제에 실패했습니다.'); });
  };

})();
