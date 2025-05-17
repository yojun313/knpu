from datetime import datetime
from zoneinfo import ZoneInfo

def clean_doc(doc: dict, stringify_id=True) -> dict:
    if "_id" in doc:
        del doc["_id"]

    # datetime 처리
    if "datetime" in doc and isinstance(doc["datetime"], datetime):
        dt = doc["datetime"]

        # naive datetime이면 UTC로 간주
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        # KST로 변환 후 문자열 포맷
        dt_kst = dt.astimezone(ZoneInfo("Asia/Seoul"))
        doc["datetime"] = dt_kst.strftime("%m-%d %H:%M")

    return doc
