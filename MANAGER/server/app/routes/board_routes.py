from fastapi import APIRouter
from app.models.board_model import AddVersionDto, AddBugDto, AddPostDto
from app.services.board_service import (
    add_version, get_version, get_version_list, delete_version,
    add_bug, get_bug, get_bug_list, delete_bug,
    add_post, get_post, get_post_list, delete_post, edit_post
)

router = APIRouter()

# ---------------- Version ----------------

@router.post("/version/add")
def create_version(data: AddVersionDto):
    return add_version(data)

@router.get("/version/{uid}")
def read_version(uid: str):
    return get_version(uid)

@router.get("/version")
def list_versions():
    return get_version_list()

@router.delete("/version/{uid}")
def remove_version(uid: str):
    return delete_version(uid)

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

@router.post("/free/add")
def create_post(data: AddPostDto):
    return add_post(data)

@router.get("/free/{uid}")
def read_post(uid: str):
    return get_post(uid)

@router.get("/free")
def list_posts():
    return get_post_list()

@router.delete("/free/{uid}")
def remove_post(uid: str):
    return delete_post(uid)

@router.put("/free/{uid}")
def update_post(uid: str, data: AddPostDto):
    return edit_post(uid, data)
