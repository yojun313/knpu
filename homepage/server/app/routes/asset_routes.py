"""Keep published asset URLs working after consolidating homepage images."""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from system.endpoints import public_url

router = APIRouter()

_LEGACY_ASSETS = {
    "lab_logo.png": "/assets/imgs/branding/logo.png",
    "lab_logo2.png": "/assets/imgs/branding/logo-social.png",
    "lab_logo_black.png": "/assets/imgs/branding/logo-dark.png",
    "fpei_logo.png": "/assets/imgs/branding/logo.png",
    "fpei_logo2.png": "/assets/imgs/branding/logo-social.png",
    "lab_logo_favicon.ico": "/shared-ui/favicon.ico",
    "fpei_logo_favicon.ico": "/shared-ui/favicon.ico",
    "apple-touch-icon.png": "/shared-ui/apple-touch-icon.png",
    "icon-192.png": "/shared-ui/icon-192.png",
    "icon-512.png": "/shared-ui/icon-512.png",
    "header-bg.jpg": "/assets/imgs/backgrounds/home.jpg",
    "header-bg-paper.jpg": "/assets/imgs/backgrounds/publications.jpg",
    "map-image.png": "/assets/imgs/backgrounds/contact-map.png",
    "about_bus.jpg": "/assets/imgs/about/shuttle-bus.jpg",
    **{f"about_{n}.jpg": f"/assets/imgs/about/about_{n}.jpg" for n in range(1, 7)},
    "[웹용] 2027 치안대학원 신입생 모집요강(2M).pdf": "/assets/documents/admission/2027-admissions-guide.pdf",
    "20260729_admission_briefing.pdf": "/assets/documents/admission/20260729-admission-briefing.pdf",
}


def _redirect(target: str, *, manager: bool = False):
    def endpoint():
        location = public_url("manager") + target if manager else target
        return RedirectResponse(
            location, status_code=308, headers={"cache-control": "no-cache"}
        )

    return endpoint


for old_path, target in _LEGACY_ASSETS.items():
    router.add_api_route(
        "/assets/imgs/" + old_path,
        _redirect(target),
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )

# Documentation belongs to MANAGER; its original files are still served there.
for filename in (
    "database.png",
    "crawler.png",
    "analysis.png",
    "board.png",
    "web.png",
    "user.png",
    "settings.png",
):
    router.add_api_route(
        "/assets/imgs/manager/" + filename,
        _redirect("/assets/imgs/manager/" + filename, manager=True),
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
