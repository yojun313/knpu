from fastapi import APIRouter, Request
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from app.services.board_service import (
    add_version,
    edit_version,
    get_version,
    get_version_list,
    delete_version,
    check_newest_version,
    add_bug,
    get_bug,
    get_bug_list,
    delete_bug,
    add_post,
    get_post,
    get_post_list,
    delete_post,
    edit_post,
)
from app.routes.dependencies import get_uid

router = APIRouter()

# ---------------- Version ----------------


@router.get("/version/newest")
def create_version():
    return check_newest_version()


@router.post("/version/add")
def create_version(data: AddVersionDto, request: Request):
    return add_version(data, get_uid(request))


@router.get("/version/{versionName}")
def read_version(versionName: str):
    return get_version(versionName)


@router.put("/version/{versionName}")
def update_version(versionName: str, data: AddVersionDto, request: Request):
    return edit_version(versionName, data, get_uid(request))


@router.get("/version")
def list_versions():
    return get_version_list()


@router.delete("/version/{versionName}")
def remove_version(versionName: str, request: Request):
    return delete_version(versionName, get_uid(request))


# ---------------- Bug ----------------


@router.post("/bug/add")
def create_bug(data: AddBugDto, request: Request):
    return add_bug(data, get_uid(request))


@router.get("/bug/{uid}")
def read_bug(uid: str, request: Request):
    return get_bug(uid, get_uid(request))


@router.get("/bug")
def list_bugs():
    return get_bug_list()


@router.delete("/bug/{uid}")
def remove_bug(uid: str, request: Request):
    return delete_bug(uid, get_uid(request))


# ---------------- Free Board ----------------


@router.post("/post/add")
def create_post(data: AddPostDto, request: Request):
    return add_post(data, get_uid(request))


@router.get("/post/{uid}")
def read_post(uid: str, request: Request):
    return get_post(uid, get_uid(request))


@router.get("/post")
def list_posts():
    return get_post_list()


@router.delete("/post/{uid}")
def remove_post(uid: str, request: Request):
    return delete_post(uid, get_uid(request))


@router.put("/post/{uid}")
def update_post(uid: str, data: AddPostDto, request: Request):
    return edit_post(uid, data, get_uid(request))
