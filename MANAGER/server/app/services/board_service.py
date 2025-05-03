import uuid
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from app.db import version_board, bug_board, free_board
from app.models.board_model import AddVersionDto, VersionBoardSchema, AddBugDto, BugBoardSchema, AddPostDto, FreeBoardSchema
from app.utils.mongo import clean_doc
from app.libs.exceptions import NotFoundException

# ----------- Version Board -----------

def add_version(data: AddVersionDto):
    doc = data.model_dump()
    doc["uid"] = str(uuid.uuid4())
    doc["releaseDate"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    version_board.insert_one(doc)
    return JSONResponse(status_code=201, content={"message": "Version post created", "data": clean_doc(doc)})

def get_version(uid: str):
    doc = version_board.find_one({"uid": uid})
    if not doc:
        raise NotFoundException("Version not found")
    return JSONResponse(status_code=200, content={"message": "Version post retrieved", "data": clean_doc(doc)})

def get_version_list():
    docs = [clean_doc(d) for d in version_board.find()]
    return JSONResponse(status_code=200, content={"message": "Version list retrieved", "data": docs})

def delete_version(uid: str):
    result = version_board.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Version not found")
    return JSONResponse(status_code=200, content={"message": "Version post deleted"})

# ----------- Bug Board -----------

def add_bug(data: AddBugDto):
    doc = data.model_dump()
    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = datetime.now(timezone.utc)
    bug_board.insert_one(doc)
    return JSONResponse(status_code=201, content={"message": "Bug post created", "data": clean_doc(doc)})

def get_bug(uid: str):
    doc = bug_board.find_one({"uid": uid})
    if not doc:
        raise NotFoundException("Bug post not found")
    return JSONResponse(status_code=200, content={"message": "Bug post retrieved", "data": clean_doc(doc)})

def get_bug_list():
    docs = [clean_doc(d) for d in bug_board.find()]
    return JSONResponse(status_code=200, content={"message": "Bug list retrieved", "data": docs})

def delete_bug(uid: str):
    result = bug_board.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Bug post not found")
    return JSONResponse(status_code=200, content={"message": "Bug post deleted"})

# ----------- Free Board -----------

def add_post(data: AddPostDto):
    doc = data.model_dump()
    doc["uid"] = str(uuid.uuid4())
    doc["datetime"] = datetime.now(timezone.utc)
    doc["viewCnt"] = 0
    free_board.insert_one(doc)
    return JSONResponse(status_code=201, content={"message": "Post created", "data": clean_doc(doc)})

def get_post(uid: str):
    doc = free_board.find_one({"uid": uid})
    if not doc:
        raise NotFoundException("Post not found")
    return JSONResponse(status_code=200, content={"message": "Post retrieved", "data": clean_doc(doc)})

def get_post_list():
    docs = [clean_doc(d) for d in free_board.find()]
    return JSONResponse(status_code=200, content={"message": "Post list retrieved", "data": docs})

def delete_post(uid: str):
    result = free_board.delete_one({"uid": uid})
    if result.deleted_count == 0:
        raise NotFoundException("Post not found")
    return JSONResponse(status_code=200, content={"message": "Post deleted"})

def edit_post(postUid: str, data: AddPostDto):
    update_fields = data.model_dump()

    result = free_board.update_one(
        {"uid": postUid},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise NotFoundException("Post not found")

    updated_doc = free_board.find_one({"uid": uid})
    return JSONResponse(
        status_code=200,
        content={"message": "Post updated", "data": clean_doc(updated_doc)},
    )
