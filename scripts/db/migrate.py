import argparse

from _conn import get_client

# (source_db, source_collection, target_db, target_collection)
PROD_MAPPING = [
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
]

# dev 모드 전용 (systems_dev/network_dev/kemkim_dev/statistics_dev로).
# manager_dev에는 kemkim/network/statistics-projects/folders가 애초에 없으므로
# (아직 웹 서비스가 분리되기 전 dev 환경에서 만들어진 적이 없다) 그 매핑은 뺀다.
DEV_MAPPING = [
    ("manager_dev", "user-logs", "systems_dev", "user-logs"),
    ("manager_dev", "user-bugs", "systems_dev", "user-bugs"),
    ("manager_dev", "sessions", "systems_dev", "sessions"),
    ("manager_dev", "auth", "systems_dev", "legacy-auth-codes"),
    ("manager_dev", "auth_config", "systems_dev", "bot-config"),
    ("manager_dev", "users", "systems_dev", "legacy-users"),
    ("crawler_dev", "youtube_api", "crawler_dev", "youtube-api"),
]


def migrate_one(client, src_db, src_coll, dst_db, dst_coll, apply: bool, force: bool):
    source = client[src_db][src_coll]
    target = client[dst_db][dst_coll]

    src_count = source.estimated_document_count()
    dst_count = target.estimated_document_count()

    label = f"{src_db}.{src_coll} -> {dst_db}.{dst_coll}"

    if dst_count > 0 and not force:
        print(f"[skip] {label}: 대상에 이미 {dst_count}건 있음 (--force로 덮어쓰기)")
        return

    if not apply:
        print(f"[dry-run] {label}: {src_count}건 복사 예정")
        return

    if force and dst_count > 0:
        target.delete_many({})

    docs = list(source.find({}))
    if docs:
        # 원본 _id를 그대로 보존 — 다른 컬렉션이 이 _id를 참조하는 경우를 대비
        target.insert_many(docs, ordered=False)

    # 인덱스도 그대로 재현 (기본 _id 인덱스는 제외)
    for idx_name, idx_info in source.index_information().items():
        if idx_name == "_id_":
            continue
        keys = idx_info["key"]
        options = {k: v for k, v in idx_info.items() if k not in ("key", "v", "ns")}
        try:
            target.create_index(keys, name=idx_name, **options)
        except Exception as e:
            print(f"    [warn] 인덱스 {idx_name} 재현 실패: {e}")

    new_count = target.estimated_document_count()
    status = "OK" if new_count == src_count else "MISMATCH"
    print(f"[{status}] {label}: {src_count} -> {new_count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="실제로 복사를 수행한다")
    parser.add_argument(
        "--force", action="store_true", help="대상이 비어있지 않아도 지우고 덮어쓴다"
    )
    parser.add_argument(
        "--skip-dev", action="store_true", help="dev DB(manager_dev 등)는 건너뛴다"
    )
    args = parser.parse_args()

    client = get_client()
    existing_dbs = set(client.list_database_names())

    mapping = list(PROD_MAPPING)
    if not args.skip_dev:
        mapping += DEV_MAPPING

    if not args.apply:
        print("=== DRY RUN (--apply 없이 실행 중, 아무것도 쓰지 않음) ===\n")

    for src_db, src_coll, dst_db, dst_coll in mapping:
        if src_db not in existing_dbs:
            print(f"[skip] {src_db}.{src_coll}: 원본 DB 없음")
            continue
        if src_coll not in client[src_db].list_collection_names():
            print(f"[skip] {src_db}.{src_coll}: 원본 컬렉션 없음")
            continue
        migrate_one(client, src_db, src_coll, dst_db, dst_coll, args.apply, args.force)

    print("\n완료.")


if __name__ == "__main__":
    main()
