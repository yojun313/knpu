// 공용 네비게이션 — 모든 페이지에서 동일한 메뉴 구성을 유지하기 위한 단일 소스
(function () {
    const NAV_ITEMS = [
        { page: 'about', label: 'ABOUT', href: '/about' },
        { page: 'admission', label: 'ADMISSION', href: '/admission' },
        { page: 'publications', label: 'PUBLICATIONS', href: '/publications' },
        { page: 'news', label: 'NEWS', href: '/news' },
        { page: 'team', label: 'PEOPLE', href: '/people' },
        { page: 'gallery', label: 'GALLERY', href: '/gallery' },
        { page: 'systems', label: 'SYSTEMS', href: '/systems' },
    ];

    const currentPage = document.body.dataset.page || '';

    const navItemsHtml = NAV_ITEMS.map(item => {
        const activeClass = item.page === currentPage ? ' active' : '';
        return `<li class="nav-item"><a class="nav-link${activeClass}" href="${item.href}">${item.label}</a></li>`;
    }).join('');

    // 스크롤 위치를 삽입 시점에 미리 반영해, scripts.js의 scroll 리스너가
    // 뒤늦게 navbar-shrink를 붙이며 첫 화면에서 네비게이션 크기가 한 번 더
    // 바뀌는(점프하는) 현상을 방지한다.
    const shrinkClass = window.scrollY > 0 ? ' navbar-shrink' : '';

    const navHtml = `
    <nav class="navbar navbar-expand-lg navbar-dark fixed-top${shrinkClass}" id="mainNav">
        <div class="container">
            <a class="navbar-brand" href="/"><img src="assets/imgs/lab_logo.png" alt="..." /></a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarResponsive"
                aria-controls="navbarResponsive" aria-expanded="false" aria-label="Toggle navigation">
                Menu
                <i class="fas fa-bars ms-1"></i>
            </button>
            <div class="collapse navbar-collapse" id="navbarResponsive">
                <ul class="navbar-nav text-uppercase ms-auto py-4 py-lg-0">
                    ${navItemsHtml}
                </ul>
            </div>
        </div>
    </nav>`;

    const placeholder = document.getElementById('nav-placeholder');
    if (placeholder) {
        placeholder.outerHTML = navHtml;
    }

    // 일부 모바일 브라우저에서 position:fixed 요소가 세로 스크롤바 유무에 따라
    // document.documentElement.clientWidth보다 넓게(또는 좁게) 계산되어
    // 네비게이션 바 폭이 새로고침마다 들쑥날쑥해지는 현상을 방지하기 위해,
    // 실제 뷰포트 폭을 JS로 직접 고정해준다.
    const navEl = document.getElementById('mainNav');
    if (navEl) {
        const syncNavWidth = () => {
            navEl.style.width = document.documentElement.clientWidth + 'px';
        };
        syncNavWidth();
        window.addEventListener('resize', syncNavWidth);
        window.addEventListener('orientationchange', syncNavWidth);
    }
})();
