import json
import os
import random
import sys

from bson import json_util

from _conn import get_client

BACKUP_ROOT = os.path.expanduser("~/knpu_db_backup")

# manifest 기준 (구) 위치 -> 검증할 (신) 위치. migrate.py의 매핑과 1:1로 맞춘다.
CHECKS = [
    # (구 db, 구 collection, 신 db, 신 collection)
    ("homepage", "users", "systems", "users"),
    ("homepage", "auth_codes", "systems", "auth-codes"),
    ("homepage", "discord_link_requests", "systems", "discord-link-requests"),
    ("homepage", "webauthn_credentials", "systems", "webauthn-credentials"),
    ("homepage", "webauthn_challenges", "systems", "webauthn-challenges"),
    ("manager", "user-logs", "systems", "user-logs"),
    ("manager", "user-bugs", "systems", "user-bugs"),
    ("manager", "sessions", "systems", "sessions"),
    ("manager", "auth", "systems", "legacy-auth-codes"),
    ("manager", "auth_config", "systems", "bot-config"),
    ("manager", "users", "systems", "legacy-users"),
    ("audit", "logs", "systems", "audit-logs"),
    ("audit", "identities", "systems", "identities"),
    ("discord", "notifications", "systems", "discord-notifications"),
    ("manager", "network-projects", "network", "projects"),
    ("manager", "network-folders", "network", "folders"),
    ("manager", "kemkim-projects", "kemkim", "projects"),
    ("manager", "kemkim-folders", "kemkim", "folders"),
    ("manager", "statistics-projects", "statistics", "projects"),
    ("manager", "statistics-folders", "statistics", "folders"),
    ("crawler", "youtube_api", "crawler", "youtube-api"),
    ("manager_dev", "user-logs", "systems_dev", "user-logs"),
    ("manager_dev", "user-bugs", "systems_dev", "user-bugs"),
    ("manager_dev", "sessions", "systems_dev", "sessions"),
    ("manager_dev", "auth", "systems_dev", "legacy-auth-codes"),
    ("manager_dev", "auth_config", "systems_dev", "bot-config"),
    ("manager_dev", "users", "systems_dev", "legacy-users"),
    ("crawler_dev", "youtube_api", "crawler_dev", "youtube-api"),
]

# 위치가 전혀 바뀌지 않은 것들 — manifest 수치와 현재 수치가 그대로 같은지만 확인.
UNCHANGED = [
    ("crawler", "db-list"),
    ("crawler", "log-list"),
    ("crawler", "job-queue"),
    ("crawler", "ip-list"),
    ("crawler_dev", "db-list"),
    ("crawler_dev", "log-list"),
    ("crawler_dev", "job-queue"),
    ("crawler_dev", "ip-list"),
    ("manager", "version-board"),
    ("manager", "bug-board"),
    ("manager", "free-board"),
    ("manager_dev", "version-board"),
    ("manager_dev", "bug-board"),
    ("manager_dev", "free-board"),
    ("homepage", "members"),
    ("homepage", "news"),
    ("homepage", "papers"),
    ("homepage", "gallery"),
    ("homepage", "popups"),
]

SAMPLE_SIZE = 5


def latest_backup_dir() -> str:
    runs = sorted(os.listdir(BACKUP_ROOT))
    if not runs:
        raise SystemExit(f"백업이 없습니다: {BACKUP_ROOT}")
    return os.path.join(BACKUP_ROOT, runs[-1])


def load_manifest(backup_dir: str) -> dict:
    with open(os.path.join(backup_dir, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def load_backup_docs(backup_dir: str, db: str, coll: str) -> list[dict]:
    path = os.path.join(backup_dir, db, f"{coll}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json_util.loads(f.read())


def main():
    backup_dir = sys.argv[1] if len(sys.argv) > 1 else latest_backup_dir()
    print(f"기준 백업: {backup_dir}\n")

    manifest = load_manifest(backup_dir)
    client = get_client()

    ok = True

    print("=== 이관된 컬렉션 ===")
    for src_db, src_coll, dst_db, dst_coll in CHECKS:
        expected = manifest.get("databases", {}).get(src_db, {}).get(src_coll)
        if expected is None:
            print(
                f"[skip] {src_db}.{src_coll}: manifest에 없음 (백업 시점에 DB가 없었음)"
            )
            continue

        actual = client[dst_db][dst_coll].estimated_document_count()
        status = "OK" if actual == expected else "MISMATCH"
        if status == "MISMATCH":
            ok = False
        print(
            f"[{status}] {src_db}.{src_coll} ({expected}) -> {dst_db}.{dst_coll} ({actual})"
        )

        if status == "OK" and expected > 0:
            backup_docs = load_backup_docs(backup_dir, src_db, src_coll)
            sample = random.sample(backup_docs, min(SAMPLE_SIZE, len(backup_docs)))
            missing = 0
            for doc in sample:
                if not client[dst_db][dst_coll].find_one({"_id": doc["_id"]}):
                    missing += 1
            if missing:
                ok = False
                print(f"    [FAIL] 표본 {len(sample)}건 중 {missing}건이 대상에 없음")

    print("\n=== 위치 변경 없는 컬렉션 (그대로인지만 확인) ===")
    for db, coll in UNCHANGED:
        expected = manifest.get("databases", {}).get(db, {}).get(coll)
        if expected is None:
            print(f"[skip] {db}.{coll}: manifest에 없음")
            continue
        actual = client[db][coll].estimated_document_count()
        status = "OK" if actual == expected else "MISMATCH"
        if status == "MISMATCH":
            ok = False
        print(f"[{status}] {db}.{coll}: {expected} -> {actual}")

    print(
        "\n"
        + ("전체 검증 통과" if ok else "검증 실패 항목 있음 — 위 MISMATCH/FAIL 확인")
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
