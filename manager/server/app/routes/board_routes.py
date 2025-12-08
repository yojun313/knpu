from fastapi import APIRouter, Depends
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from app.services.board_service import (
    add_version, edit_version, get_version, get_version_list, delete_version, check_newest_version,
    add_bug, get_bug, get_bug_list, delete_bug,
    add_post, get_post, get_post_list, delete_post, edit_post
)
from app.libs.jwt import verify_token

router = APIRouter()

# ---------------- Version ----------------

@router.get("/version/newest")
def create_version():
    return check_newest_version()


@router.post("/version/add")
def create_version(data: AddVersionDto, userUid: str = Depends(verify_token)):
    return add_version(data, userUid)

@router.get("/version/{versionName}")
def read_version(versionName: str):
    return get_version(versionName)

@router.put("/version/{versionName}")
def update_version(versionName: str, data: AddVersionDto, userUid: str = Depends(verify_token)):
    return edit_version(versionName, data, userUid)

@router.get("/version")
def list_versions():
    return get_version_list()

@router.delete("/version/{versionName}")
def remove_version(versionName: str, userUid: str = Depends(verify_token)):
    return delete_version(versionName, userUid)

# ---------------- Bug ----------------

@router.post("/bug/add")
def create_bug(data: AddBugDto, userUid: str = Depends(verify_token)):
    return add_bug(data, userUid)

@router.get("/bug/{uid}")
def read_bug(uid: str, userUid: str = Depends(verify_token)):
    return get_bug(uid, userUid)

@router.get("/bug")
def list_bugs():
    return get_bug_list()

@router.delete("/bug/{uid}")
def remove_bug(uid: str, userUid: str = Depends(verify_token)):
    return delete_bug(uid, userUid)

# ---------------- Free Board ----------------

@router.post("/post/add")
def create_post(data: AddPostDto, userUid: str = Depends(verify_token)):
    return add_post(data, userUid)

@router.get("/post/{uid}")
def read_post(uid: str, userUid = Depends(verify_token)):
    return get_post(uid, userUid)

@router.get("/post")
def list_posts():
    return get_post_list()

@router.delete("/post/{uid}")
def remove_post(uid: str, userUid: str = Depends(verify_token)):
    return delete_post(uid, userUid)

@router.put("/post/{uid}")
def update_post(uid: str, data: AddPostDto, userUid: str = Depends(verify_token)):
    return edit_post(uid, data, userUid)
