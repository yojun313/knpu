import json
import os
from datetime import datetime

from bson import json_util

from _conn import get_client

TARGET_DBS = [
    "manager",
    "manager_dev",
    "homepage",
    "crawler",
    "crawler_dev",
    "discord",
    "audit",
]

BACKUP_ROOT = os.path.expanduser("~/knpu_db_backup")


def dump_collection(coll, out_path: str) -> int:
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        for doc in coll.find({}):
            if not first:
                f.write(",\n")
            f.write(json_util.dumps(doc, ensure_ascii=False))
            first = False
            count += 1
        f.write("\n]\n")
    return count


def dump_indexes(coll, out_path: str) -> None:
    try:
        info = coll.index_information()
    except Exception as e:
        info = {"_error": str(e)}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2, default=str)


def main():
    client = get_client()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(BACKUP_ROOT, ts)
    os.makedirs(run_dir, exist_ok=True)

    manifest = {"timestamp": ts, "databases": {}}
    existing_dbs = set(client.list_database_names())

    for db_name in TARGET_DBS:
        if db_name not in existing_dbs:
            print(f"[skip] db not found: {db_name}")
            continue

        db = client[db_name]
        db_dir = os.path.join(run_dir, db_name)
        os.makedirs(db_dir, exist_ok=True)

        db_manifest = {}
        for coll_name in sorted(db.list_collection_names()):
            coll = db[coll_name]
            out_path = os.path.join(db_dir, f"{coll_name}.json")
            idx_path = os.path.join(db_dir, f"{coll_name}.indexes.json")

            count = dump_collection(coll, out_path)
            dump_indexes(coll, idx_path)

            db_manifest[coll_name] = count
            print(f"  {db_name}.{coll_name}: {count} docs -> {out_path}")

        manifest["databases"][db_name] = db_manifest

    manifest_path = os.path.join(run_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n백업 완료: {run_dir}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
