(function () {
  if (window.__knpuBoardNotices) return;
  window.__knpuBoardNotices = true;
  var dismissed = new Set(), notice, timer;
  function links() { return document.querySelectorAll('[data-knpu-board-link], #mainNav a[href$="/board"]'); }
  function load() {
    if (document.hidden || !links().length) return;
    // Like KNPU.me(), read shared account data through the central login host.
    fetch(window.KNPU_SERVICES.loginOrigin + '/shared-ui/board/api/unread', {credentials:'include', cache:'no-store'})
      .then(function (res) { if (res.status === 401) return null; if (!res.ok) throw new Error('Unavailable'); return res.json(); })
      .then(function (payload) {
        if (!payload) return;
        links().forEach(function (link) {
          var b = link.querySelector('.knpu-board-unread');
          if (!b) { b=document.createElement('span'); b.className='knpu-board-unread'; link.appendChild(b); }
          b.hidden = !payload.total; b.textContent = payload.total > 99 ? '99+' : payload.total;
          b.setAttribute('aria-label', '읽지 않은 게시글 ' + payload.total + '개');
        });
        var posts = payload.data.filter(function (p) { return !dismissed.has(p.uid); }).slice(0,3);
        if (!posts.length) { if (notice) notice.hidden=true; return; }
        if (!notice) {
          notice=document.createElement('aside'); notice.className='knpu-board-notice'; notice.setAttribute('aria-label','읽지 않은 게시글 알림');
          document.body.appendChild(notice);
        }
        notice.replaceChildren(); notice.hidden=false;
        var head=document.createElement('header'), label=document.createElement('strong'), close=document.createElement('button');
        label.textContent='새로운 자유게시판 글 · ' + payload.total + '개'; close.textContent='×'; close.setAttribute('aria-label','알림 닫기');
        close.onclick=function () { payload.data.forEach(function(p){dismissed.add(p.uid);}); notice.hidden=true; };
        head.append(label,close); notice.appendChild(head);
        posts.forEach(function (p) {
          var link=document.createElement('a'), title=document.createElement('span'), meta=document.createElement('small');
          link.href=KNPU.url('manager','/board?tab=post&uid='+encodeURIComponent(p.uid));
          title.textContent=p.title; meta.textContent=(p.writerName || '사용자') + ' · ' + (p.datetime_kst || '');
          link.append(title,meta); notice.appendChild(link);
        });
      }).catch(function () {});
  }
  function start() {
    if (!links().length || !window.KNPU) return;
    var css=document.createElement('link'); css.rel='stylesheet'; css.href='/shared-ui/board-notices.css'; document.head.appendChild(css);
    KNPU.me().then(function(user){if(!user)return; load(); timer=setInterval(load,60000);}).catch(function(){});
    document.addEventListener('visibilitychange',load);
    window.addEventListener('focus',load);
    window.addEventListener('knpu-board-read',load);
    window.addEventListener('pagehide',function(){clearInterval(timer);});
    window.addEventListener('pageshow',function(event){if(event.persisted){clearInterval(timer);load();timer=setInterval(load,60000);}});
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',start); else start();
})();
