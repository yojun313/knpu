(function () {
  var dz = document.getElementById('dropzone');
  var input = document.getElementById('fileInput');
  var statusEl = document.getElementById('status');
  var listEl = document.getElementById('networkList');

  function setStatus(msg, cls) {
    statusEl.textContent = msg || '';
    statusEl.className = 'status' + (cls ? ' ' + cls : '');
  }

  function upload(file) {
    if (!file) return;
    if (!/\.zip$/i.test(file.name)) {
      setStatus('zip 파일만 업로드할 수 있습니다.', 'err');
      return;
    }
    setStatus('업로드 및 분석 중...');
    listEl.hidden = true;
    listEl.innerHTML = '';

    var fd = new FormData();
    fd.append('file', file);

    fetch('/api/upload', { method: 'POST', body: fd })
      .then(function (res) {
        return res.json().then(function (body) {
          if (!res.ok) throw new Error(body.detail || '업로드에 실패했습니다.');
          return body;
        });
      })
      .then(function (meta) {
        setStatus('완료! ' + meta.networks.length + '개 네트워크를 찾았습니다.', 'ok');
        if (meta.networks.length === 1) {
          location.href = '/viewer/' + meta.session_id + '?tag=' + encodeURIComponent(meta.networks[0].tag);
          return;
        }
        listEl.hidden = false;
        meta.networks.forEach(function (nw) {
          var a = document.createElement('a');
          a.className = 'network-item';
          a.href = '/viewer/' + meta.session_id + '?tag=' + encodeURIComponent(nw.tag);
          a.innerHTML =
            '<div><div class="nl-name">' + esc(nw.label) + '</div>' +
            '<div class="nl-meta">노드 ' + nw.nodes.toLocaleString() + '개 · 엣지 ' + nw.edges.toLocaleString() + '개</div></div>' +
            '<div class="nl-go">열기 →</div>';
          listEl.appendChild(a);
        });
      })
      .catch(function (err) {
        setStatus(err.message || String(err), 'err');
      });
  }

  function esc(s) {
    return String(s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; });
  }

  dz.addEventListener('click', function () { input.click(); });
  input.addEventListener('change', function () { upload(input.files[0]); });

  ['dragenter', 'dragover'].forEach(function (evt) {
    dz.addEventListener(evt, function (e) { e.preventDefault(); dz.classList.add('drag'); });
  });
  ['dragleave', 'drop'].forEach(function (evt) {
    dz.addEventListener(evt, function (e) { e.preventDefault(); dz.classList.remove('drag'); });
  });
  dz.addEventListener('drop', function (e) {
    var f = e.dataTransfer.files && e.dataTransfer.files[0];
    upload(f);
  });
})();
