from fastapi import APIRouter, Request
from app.models.board_model import (
    AddVersionDto,
    AddBugDto,
    AddPostDto,
    BugReplyDto,
    CommentDto,
    AddSuggestionDto,
    SuggestionStatusDto,
)
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
    edit_bug,
    add_bug_reply,
    add_comment,
    edit_comment,
    delete_comment,
    edit_suggestion_status,
)
from app.routes.dependencies import get_uid, get_current_user

router = APIRouter()


@router.get("/me")
def board_identity(request: Request):
    return get_current_user(request)


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
def list_bugs(request: Request):
    return get_bug_list(get_uid(request))


@router.put("/bug/{uid}")
def update_bug(uid: str, data: AddBugDto, request: Request):
    return edit_bug(uid, data, get_uid(request))


@router.post("/bug/{uid}/replies")
def create_bug_reply(uid: str, data: BugReplyDto, request: Request):
    return add_bug_reply(uid, data, get_uid(request))


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
def list_posts(request: Request):
    return get_post_list(get_uid(request))


@router.delete("/post/{uid}")
def remove_post(uid: str, request: Request):
    return delete_post(uid, get_uid(request))


@router.put("/post/{uid}")
def update_post(uid: str, data: AddPostDto, request: Request):
    return edit_post(uid, data, get_uid(request))


@router.post("/post/{uid}/comments")
def create_comment(uid: str, data: CommentDto, request: Request):
    return add_comment(uid, data, get_uid(request))


@router.put("/post/{uid}/comments/{comment_uid}")
def update_comment(uid: str, comment_uid: str, data: CommentDto, request: Request):
    return edit_comment(uid, comment_uid, data, get_uid(request))


@router.delete("/post/{uid}/comments/{comment_uid}")
def remove_comment(uid: str, comment_uid: str, request: Request):
    return delete_comment(uid, comment_uid, get_uid(request))


# ---------------- Suggestions ----------------


@router.post("/suggestion/add")
def create_suggestion(data: AddSuggestionDto, request: Request):
    return add_post(data, get_uid(request), "suggestion")


@router.get("/suggestion")
def list_suggestions(request: Request):
    return get_post_list(get_uid(request), "suggestion")


@router.get("/suggestion/{uid}")
def read_suggestion(uid: str, request: Request):
    return get_post(uid, get_uid(request), "suggestion")


@router.put("/suggestion/{uid}")
def update_suggestion(uid: str, data: AddSuggestionDto, request: Request):
    return edit_post(uid, data, get_uid(request), "suggestion")


@router.delete("/suggestion/{uid}")
def remove_suggestion(uid: str, request: Request):
    return delete_post(uid, get_uid(request), "suggestion")


@router.put("/suggestion/{uid}/status")
def update_suggestion_status(uid: str, data: SuggestionStatusDto, request: Request):
    return edit_suggestion_status(uid, data, get_uid(request))


@router.post("/suggestion/{uid}/comments")
def create_suggestion_comment(uid: str, data: CommentDto, request: Request):
    return add_comment(uid, data, get_uid(request), "suggestion")


@router.put("/suggestion/{uid}/comments/{comment_uid}")
def update_suggestion_comment(
    uid: str, comment_uid: str, data: CommentDto, request: Request
):
    return edit_comment(uid, comment_uid, data, get_uid(request), "suggestion")


@router.delete("/suggestion/{uid}/comments/{comment_uid}")
def remove_suggestion_comment(uid: str, comment_uid: str, request: Request):
    return delete_comment(uid, comment_uid, get_uid(request), "suggestion")


@router.post("/suggestion/{uid}/replies")
def create_suggestion_reply(uid: str, data: BugReplyDto, request: Request):
    return add_bug_reply(uid, data, get_uid(request), "suggestion")
