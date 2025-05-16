from fastapi import APIRouter
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from app.services.board_service import (
    add_version, get_version, get_version_list, delete_version, check_newest_version, check_newest_version_info,
    add_bug, get_bug, get_bug_list, delete_bug,
    add_post, get_post, get_post_list, delete_post, edit_post
)

router = APIRouter()

# ---------------- Version ----------------
@router.get("/version/newest")
def create_version():
    return check_newest_version()

@router.get("/version/newest/info")
def create_version():
    return check_newest_version_info()


@router.post("/version/add")
def create_version(data: AddVersionDto):
    return add_version(data)

@router.get("/version/{versionName}")
def read_version(versionName: str):
    return get_version(versionName)

@router.get("/version")
def list_versions():
    return get_version_list()

@router.delete("/version/{versionName}")
def remove_version(versionName: str):
    return delete_version(versionName)

# ---------------- Bug ----------------

@router.post("/bug/add")
def create_bug(data: AddBugDto):
    return add_bug(data)

@router.get("/bug/{uid}")
def read_bug(uid: str):
    return get_bug(uid)

@router.get("/bug")
def list_bugs():
    return get_bug_list()

@router.delete("/bug/{uid}")
def remove_bug(uid: str):
    return delete_bug(uid)

# ---------------- Free Board ----------------

@router.post("/post/add")
def create_post(data: AddPostDto):
    return add_post(data)

@router.get("/post/{uid}")
def read_post(uid: str):
    return get_post(uid)

@router.get("/post")
def list_posts():
    return get_post_list()

@router.delete("/post/{uid}")
def remove_post(uid: str):
    return delete_post(uid)

@router.put("/post/{uid}")
def update_post(uid: str, data: AddPostDto):
    return edit_post(uid, data)
