// 첫 페인트 전에 테마 적용. 다른 KNPU 사이트와 공유하는 ui_theme_mode 쿠키를 쓰고,
// 없으면 OS 설정을 따른다. 개인정보 보호를 위해 이 사이트는 localStorage를 쓰지 않는다.
(function () {
  var mode = null;
  try {
    var m = document.cookie.match(/(?:^|; )ui_theme_mode=([^;]*)/);
    mode = m ? decodeURIComponent(m[1]) : null;
  } catch (e) {}
  if (mode !== 'dark' && mode !== 'light') {
    mode = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', mode);
})();
