"""
갤러리 컬렉션을 구 스키마({url, caption, date})에서
신 스키마({title, content, date, photos: [...], schema_version: 2})로 옮기는 1회성 마이그레이션 스크립트.

사용법 (homepage/server 디렉터리에서 실행):
    python scripts/migrate_gallery_to_posts.py --dry-run   # 변경 없이 대상만 확인
    python scripts/migrate_gallery_to_posts.py              # 실제 마이그레이션 실행

실행 전 반드시 gallery 컬렉션을 mongodump로 백업해둘 것.
schema_version 필드가 이미 있는 문서는 대상에서 제외되므로, 재실행해도 안전함(대상 0건).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import gallery_db  # noqa: E402


def find_legacy_docs():
    return list(gallery_db.find({"schema_version": {"$exists": False}}))


def migrate(dry_run: bool):
    legacy_docs = find_legacy_docs()

    if not legacy_docs:
        print("대상 문서가 없습니다 (이미 모두 마이그레이션됨).")
        return

    print(f"대상 문서 {len(legacy_docs)}건 발견:")
    for doc in legacy_docs[:5]:
        print(f"  - uid={doc.get('uid')} caption={doc.get('caption')!r}")
    if len(legacy_docs) > 5:
        print(f"  ... 외 {len(legacy_docs) - 5}건")

    if dry_run:
        print("\n--dry-run 모드: 실제 변경은 수행하지 않았습니다.")
        return

    migrated = 0
    for doc in legacy_docs:
        title = doc.get("caption") or "(제목 없음)"
        url = doc.get("url")
        gallery_db.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "title": title,
                    "content": "",
                    "photos": [url] if url else [],
                    "schema_version": 2,
                },
                "$unset": {"url": "", "caption": ""},
            },
        )
        migrated += 1

    print(f"\n마이그레이션 완료: {migrated}건 처리됨.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="실제 변경 없이 대상만 출력"
    )
    args = parser.parse_args()

    migrate(dry_run=args.dry_run)
