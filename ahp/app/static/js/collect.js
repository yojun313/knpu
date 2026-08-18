(function () {
  'use strict';

  const projectId = location.pathname.split('/')[2];
  const MODE_LABEL = { offline: '오프라인', online: '온라인', realtime: '실시간' };
  let activeCollectionForCodes = null;

  async function load() {
    let collections;
    try {
      collections = await ahpApi('/api/projects/' + projectId + '/collections');
    } catch (e) {
      ahpToast(e.message || '수집 목록을 불러오지 못했습니다', true);
      return;
    }
    render(collections);
  }

  function respondLink(token) {
    return location.origin + '/r/' + token;
  }

  function render(collections) {
    const grid = document.getElementById('collectionsList');
    const empty = document.getElementById('collectionsEmpty');
    if (!collections.length) {
      grid.innerHTML = '';
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    grid.innerHTML = collections.map(function (c) {
      const openBtn = c.mode === 'offline'
        ? '<a class="btn sm" href="/entry/' + c.id + '">입력 화면</a>'
        : c.mode === 'realtime'
          ? '<a class="btn sm" href="/console/' + c.id + '">콘솔 열기</a>'
          : '';
      const linkBtn = c.access_token
        ? '<button class="btn sm" data-act="copy-link" data-token="' + c.access_token + '">링크 복사</button>'
        : '';
      const codesBtn = c.mode !== 'offline'
        ? '<button class="btn sm" data-act="codes" data-id="' + c.id + '">코드 발급</button>' : '';
      const toggleBtn = c.status === 'open'
        ? '<button class="btn sm" data-act="close" data-id="' + c.id + '">종료</button>'
        : '<button class="btn sm" data-act="reopen" data-id="' + c.id + '">재개</button>';
      return '<div class="coll-card">' +
        '<div class="cc-head"><div><h3>' + ahpEsc(c.label) + '</h3>' +
        '<span class="cc-mode ' + c.mode + '">' + MODE_LABEL[c.mode] + '</span></div>' +
        '<span class="badge ' + (c.status === 'open' ? 'ok' : 'muted') + '">' + ahpEsc(c.status_label) + '</span></div>' +
        '<div class="cc-stats"><span>응답자 <b>' + c.respondent_count + '</b></span>' +
        '<span>제출 완료 <b>' + c.submitted_count + '</b></span>' +
        (c.mode === 'realtime' ? '<span>라운드 <b>' + c.round + '</b></span>' : '') + '</div>' +
        '<div class="cc-actions">' + openBtn + linkBtn + codesBtn + toggleBtn +
        '<button class="btn sm danger" data-act="delete" data-id="' + c.id + '">삭제</button></div>' +
        '</div>';
    }).join('');
  }

  async function createCollection() {
    const mode = document.getElementById('newCollectionMode').value;
    const label = document.getElementById('newCollectionLabel').value.trim();
    const btn = document.getElementById('newCollectionSubmit');
    btn.disabled = true;
    try {
      await ahpApi('/api/collections', { method: 'POST', body: { project_id: projectId, mode: mode, label: label } });
      document.getElementById('newCollectionModal').hidden = true;
      document.getElementById('newCollectionLabel').value = '';
      ahpToast('수집을 시작했습니다');
      await load();
    } catch (e) {
      ahpToast(e.message || '수집 시작에 실패했습니다', true);
    } finally {
      btn.disabled = false;
    }
  }

  async function issueCodes() {
    const count = Number(document.getElementById('codesCount').value);
    const btn = document.getElementById('codesIssueBtn');
    btn.disabled = true;
    try {
      const res = await ahpApi('/api/collections/' + activeCollectionForCodes + '/codes', {
        method: 'POST', body: { count: count },
      });
      document.getElementById('codesIssueForm').hidden = true;
      const resultBox = document.getElementById('codesResult');
      resultBox.hidden = false;
      document.getElementById('codesTableBody').innerHTML = res.issued.map(function (r) {
        return '<tr><td style="padding:6px">' + ahpEsc(r.label) + '</td>' +
          '<td style="padding:6px;font-family:monospace">' + ahpEsc(r.code) + '</td></tr>';
      }).join('');
      resultBox.dataset.text = res.issued.map(function (r) { return r.label + '\t' + r.code; }).join('\n');
      await load();
    } catch (e) {
      ahpToast(e.message || '코드 발급에 실패했습니다', true);
    } finally {
      btn.disabled = false;
    }
  }

  function init() {
    load();
    ahpApi('/api/projects/' + projectId).then(function (p) {
      document.getElementById('projTitle').textContent = p.title + ' · 수집 관리';
      if (window.AHPShell) window.AHPShell.setActiveProject(projectId);
    }).catch(function () {});

    document.querySelectorAll('#stageTabs .stage-tab').forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        e.preventDefault();
        const stage = tab.dataset.stage;
        if (stage === 'collect') return;
        location.href = '/' + stage + '/' + projectId;
      });
    });

    document.getElementById('newCollectionBtn').addEventListener('click', function () {
      document.getElementById('newCollectionModal').hidden = false;
    });
    document.getElementById('newCollectionClose').addEventListener('click', function () {
      document.getElementById('newCollectionModal').hidden = true;
    });
    document.getElementById('newCollectionSubmit').addEventListener('click', createCollection);

    document.getElementById('collectionsList').addEventListener('click', async function (e) {
      const btn = e.target.closest('button');
      if (!btn) return;
      const act = btn.dataset.act;
      const id = btn.dataset.id;
      if (act === 'copy-link') {
        const link = respondLink(btn.dataset.token);
        await navigator.clipboard.writeText(link).catch(function () {});
        ahpToast('링크를 복사했습니다: ' + link);
      } else if (act === 'codes') {
        activeCollectionForCodes = id;
        document.getElementById('codesIssueForm').hidden = false;
        document.getElementById('codesResult').hidden = true;
        document.getElementById('codesModal').hidden = false;
      } else if (act === 'close') {
        await ahpApi('/api/collections/' + id + '/close', { method: 'POST' });
        await load();
      } else if (act === 'reopen') {
        await ahpApi('/api/collections/' + id + '/reopen', { method: 'POST' });
        await load();
      } else if (act === 'delete') {
        if (!confirm('이 수집과 관련 응답 데이터를 모두 삭제할까요? 되돌릴 수 없습니다.')) return;
        await ahpApi('/api/collections/' + id, { method: 'DELETE' });
        await load();
      }
    });

    document.getElementById('codesClose').addEventListener('click', function () {
      document.getElementById('codesModal').hidden = true;
    });
    document.getElementById('codesIssueBtn').addEventListener('click', issueCodes);
    document.getElementById('codesCopyAllBtn').addEventListener('click', async function () {
      const text = document.getElementById('codesResult').dataset.text || '';
      await navigator.clipboard.writeText(text).catch(function () {});
      ahpToast('전체 코드를 복사했습니다');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
