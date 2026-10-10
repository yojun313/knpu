"""Same-origin unread board notifications for every shared navigation host."""

from fastapi import Request
from fastapi.responses import JSONResponse
from system.account import _session_user


def register(app):
    @app.get("/shared-ui/board/api/unread", include_in_schema=False)
    def unread_posts(request: Request):
        from system.db import free_board_db

        user = _session_user(request)
        query = {"viewCnt": {"$ne": user["uid"]}, "writerUid": {"$ne": user["uid"]}}
        docs = list(
            free_board_db.find(
                query,
                {
                    "_id": 0,
                    "uid": 1,
                    "title": 1,
                    "writerName": 1,
                    "datetime_kst": 1,
                },
            )
            .sort("datetime", -1)
            .limit(5)
        )
        return JSONResponse(
            {"data": docs, "total": free_board_db.count_documents(query)},
            headers={"cache-control": "no-store"},
        )
