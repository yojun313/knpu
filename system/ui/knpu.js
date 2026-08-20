/**
 * 프론트에서 쓰는 KNPU 주소 유틸 — 값은 전부 /shared-ui/services.js(=knpu/services.json)에서 온다.
 * 이 파일에도, 이 파일을 쓰는 페이지에도 도메인을 적지 않는다.
 *
 * 사용법
 *   KNPU.url('manager')                 → 현재 모드에 맞는 매니저 주소
 *   KNPU.loginUrl()                     → 지금 페이지로 돌아오는 로그인 주소
 *   KNPU.logoutUrl()                    → 로그아웃 API 주소
 *   <a data-knpu-service="homepage">    → href를 자동으로 채워준다
 *
 * 링크 처리 규칙
 *   - data-knpu-service 가 붙은 링크: 현재 모드에 맞는 주소로 채운다.
 *     (dev에서 HOME은 dev 홈페이지로 간다)
 *   - 그냥 하드코딩된 서비스 링크: dev에서 보고 있을 때만 dev 쪽으로 돌려준다.
 *     단 홈페이지는 제외한다 — 로그인 링크나 이미지 주소로 쓰인 것까지 바뀌면 곤란하다.
 *   - 로그인/로그아웃: 계정이 dev/prod 공통이므로 항상 운영 홈페이지
 *     (services.json의 login_service). dev 홈페이지가 죽어도 로그인은 되어야 한다.
 */
(function () {
  var cfg = window.KNPU_SERVICES;
  if (!cfg || !cfg.services) {
    console.error('[KNPU] /shared-ui/services.js 를 먼저 로드해야 합니다.');
    return;
  }

  function svc(name) {
    var s = cfg.services[name];
    if (!s) throw new Error('[KNPU] services.json에 없는 서비스: ' + name);
    return s;
  }

  function domain(name) {
    var s = svc(name);
    return (cfg.isDev && s.devDomain) || s.prodDomain;
  }

  function url(name, path) {
    return 'https://' + domain(name) + (svc(name).publicPath || '') + (path || '');
  }

  var KNPU = {
    isDev: !!cfg.isDev,
    domain: domain,
    url: url,
    loginUrl: function (redirect) {
      var back = redirect || window.location.href;
      return cfg.loginOrigin + '/login?redirect=' + encodeURIComponent(back);
    },
    logoutUrl: function () {
      return cfg.loginOrigin + '/api/auth/logout';
    },
    homeUrl: function () {
      return cfg.loginOrigin;
    },
  };
  window.KNPU = KNPU;

  // prod 도메인 -> dev 도메인 (중앙 로그인을 맡은 홈페이지는 제외)
  var DEV_MAP = {};
  Object.keys(cfg.services).forEach(function (name) {
    var s = cfg.services[name];
    if (!s.devDomain || !s.prodDomain || s.devDomain === s.prodDomain) return;
    if (name === 'homepage') return;
    DEV_MAP[s.prodDomain.toLowerCase()] = s.devDomain;
  });

  function isDevHost() {
    var host = location.hostname.toLowerCase();
    return Object.keys(cfg.services).some(function (name) {
      var d = cfg.services[name].devDomain;
      return d && d.toLowerCase() === host;
    });
  }

  function apply() {
    // 1) data-knpu-service 가 붙은 링크는 JSON에서 주소를 채운다.
    document.querySelectorAll('a[data-knpu-service]').forEach(function (a) {
      try {
        a.setAttribute(
          'href',
          url(a.getAttribute('data-knpu-service'), a.getAttribute('data-knpu-path') || '')
        );
      } catch (e) {
        /* 알 수 없는 서비스명이면 원래 href를 그대로 둔다 */
      }
    });

    // 2) dev 사이트에서 보고 있으면, 남아 있는 운영 서비스 링크도 dev 쪽으로 돌린다.
    if (!isDevHost()) return;
    document.querySelectorAll('a[href^="https://"]').forEach(function (a) {
      var u;
      try {
        u = new URL(a.getAttribute('href'), location.href);
      } catch (e) {
        return;
      }
      var dev = DEV_MAP[u.hostname.toLowerCase()];
      if (!dev) return;
      u.hostname = dev;
      a.setAttribute('href', u.toString());
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }
})();
