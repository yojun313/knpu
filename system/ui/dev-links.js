/**
 * dev 사이트에서 다른 서비스로 가는 링크를 같은 dev 쪽으로 돌려준다.
 *
 * dev.knpu.re.kr / dev-kemkim.knpu.re.kr 등에서 상단 네비게이션의 MANAGER·NETWORK
 * 링크를 누르면 운영 사이트로 빠져나가 버리는 문제를 막는다. 원래 theme.js 안에
 * 있었는데, 홈페이지(dev.knpu.re.kr)는 theme.js를 쓰지 않아 그 페이지의 링크만
 * 계속 운영으로 나갔다. 그래서 별도 파일로 분리해 양쪽이 같이 쓴다.
 *
 * 로그인/홈(knpu.re.kr)은 dev/prod가 계정을 공유하므로 일부러 건드리지 않는다.
 */
(function () {
  if (window.__knpuDevLinksApplied) return;
  window.__knpuDevLinksApplied = true;

  var CROSS_SERVICE_SUBDOMAINS = [
    'manager', 'crawler', 'network', 'kemkim', 'statistics', 'ahp', 'dashboard',
    'complaint',
  ];

  function fixCrossServiceNavLinks() {
    // dev 홈페이지는 "dev-xxx"가 아니라 그냥 "dev.knpu.re.kr"라서 두 형태를 모두 본다.
    var host = location.hostname.toLowerCase();
    var isDev =
      host === 'dev.knpu.re.kr' || /^dev-[a-z0-9-]+\.knpu\.re\.kr$/.test(host);
    if (!isDev) return;

    document.querySelectorAll('a[href^="https://"]').forEach(function (a) {
      var url;
      try {
        url = new URL(a.getAttribute('href'), location.href);
      } catch (e) {
        return;
      }
      var hm = /^([a-z0-9-]+)\.knpu\.re\.kr$/i.exec(url.hostname);
      if (!hm) return;
      var sub = hm[1].toLowerCase();
      if (CROSS_SERVICE_SUBDOMAINS.indexOf(sub) === -1) return;
      url.hostname = 'dev-' + sub + '.knpu.re.kr';
      a.setAttribute('href', url.toString());
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fixCrossServiceNavLinks);
  } else {
    fixCrossServiceNavLinks();
  }
})();
