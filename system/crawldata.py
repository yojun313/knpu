import os

from dotenv import load_dotenv

load_dotenv()

# 크롤러와 같은 값을 본다 (crawler/app/config.py 의 CRAWLDATA_PATH)
CRAWL_DATA_PATH = os.getenv("CRAWLDATA_PATH") or "./crawldata"

# CSV 로 흘려 쓸 때 한 번에 처리할 행 수. 크면 메모리, 작으면 오버헤드가 늘어난다.
CSV_STREAM_ROWS = 50_000


class CrawlDataError(Exception):
    """로컬에서 읽을 수 없을 때(폴더/파일 없음, 손상 등)."""


def available() -> bool:
    """크롤 데이터를 이 서버에서 직접 읽을 수 있는지."""
    return os.path.isdir(CRAWL_DATA_PATH) and os.access(
        CRAWL_DATA_PATH, os.R_OK | os.X_OK
    )


def db_doc(uid: str) -> dict | None:
    """크롤링 DB 문서(uid → name/status). 같은 Mongo 를 쓰므로 직접 조회한다."""
    from system.db import crawler_db

    return crawler_db["db-list"].find_one({"uid": uid}, {"name": 1, "status": 1})


def _folder(uid: str) -> tuple[str, str]:
    doc = db_doc(uid)
    if not doc:
        raise CrawlDataError("해당 DB를 찾을 수 없습니다")
    if doc.get("status") != "completed":
        raise CrawlDataError("완료된 크롤링만 분석에 사용할 수 있습니다")
    folder = os.path.join(CRAWL_DATA_PATH, doc["name"])
    if not os.path.isdir(folder):
        raise CrawlDataError("데이터 폴더를 찾을 수 없습니다")
    return folder, doc["name"]


def list_files(uid: str) -> dict:
    """크롤러 /db-list/{uid}/files 와 같은 모양으로 파일 목록을 돌려준다."""
    folder, db_name = _folder(uid)
    files = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".parquet"):
            continue
        try:
            size = os.path.getsize(os.path.join(folder, name))
        except OSError:
            size = None
        files.append(
            {
                "name": name,
                "type": "token" if name.startswith("token_") else "raw",
                "size": size,
                "csv_name": name.rsplit(".", 1)[0] + ".csv",
            }
        )
    return {"uid": uid, "db_name": db_name, "files": files}


def parquet_path(uid: str, name: str) -> str:
    """요청한 parquet 의 실제 경로. 경로 탈출(../)과 확장자를 검사한다."""
    folder, _ = _folder(uid)
    safe = os.path.basename(name)
    if safe != name or not safe.endswith(".parquet"):
        raise CrawlDataError("잘못된 파일명입니다")
    path = os.path.join(folder, safe)
    if not os.path.isfile(path):
        raise CrawlDataError("파일을 찾을 수 없습니다")
    return path


def write_csv(uid: str, name: str, dest_path: str) -> int:
    """parquet 을 dest_path 에 CSV(utf-8-sig)로 흘려 쓴다. 쓴 바이트 수를 돌려준다.

    row group 단위로 처리하므로 1GB 파일이어도 메모리는 수십 MB 수준이다.
    """
    import pyarrow.parquet as pq

    src = parquet_path(uid, name)
    try:
        pf = pq.ParquetFile(src)
    except Exception as e:
        raise CrawlDataError(f"파일을 읽지 못했습니다: {e}") from e

    tmp = dest_path + ".part"
    written = 0
    try:
        with open(tmp, "wb") as out:
            out.write(b"\xef\xbb\xbf")  # 엑셀 호환 BOM — 맨 앞에 한 번만
            written += 3
            first = True
            for batch in pf.iter_batches(batch_size=CSV_STREAM_ROWS):
                chunk = (
                    batch.to_pandas().to_csv(index=False, header=first).encode("utf-8")
                )
                out.write(chunk)
                written += len(chunk)
                first = False
        os.replace(tmp, dest_path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise
    return written
