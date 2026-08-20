import uuid

from app.db import admin_settings_col

_SETTINGS_ID = "nginx_folders"
MAX_NAME_LEN = 40


def _load() -> list[dict]:
    doc = admin_settings_col.find_one({"_id": _SETTINGS_ID})
    folders = (doc or {}).get("folders") or []
    cleaned = []
    for f in folders:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        cleaned.append(
            {
                "id": str(f["id"]),
                "name": str(f.get("name") or "이름 없음"),
                "domains": [str(d) for d in (f.get("domains") or [])],
            }
        )
    return cleaned


def _save(folders: list[dict]) -> None:
    admin_settings_col.update_one(
        {"_id": _SETTINGS_ID}, {"$set": {"folders": folders}}, upsert=True
    )


def list_folders() -> list[dict]:
    return _load()


def create_folder(name: str) -> tuple[bool, str, dict | None]:
    name = (name or "").strip()
    if not name:
        return False, "폴더 이름을 입력하세요.", None
    if len(name) > MAX_NAME_LEN:
        return False, f"폴더 이름은 {MAX_NAME_LEN}자 이하여야 합니다.", None

    folders = _load()
    if any(f["name"] == name for f in folders):
        return False, "같은 이름의 폴더가 이미 있습니다.", None

    folder = {"id": uuid.uuid4().hex[:12], "name": name, "domains": []}
    folders.append(folder)
    _save(folders)
    return True, "폴더를 만들었습니다.", folder


def rename_folder(folder_id: str, name: str) -> tuple[bool, str]:
    name = (name or "").strip()
    if not name:
        return False, "폴더 이름을 입력하세요."
    if len(name) > MAX_NAME_LEN:
        return False, f"폴더 이름은 {MAX_NAME_LEN}자 이하여야 합니다."

    folders = _load()
    target = next((f for f in folders if f["id"] == folder_id), None)
    if target is None:
        return False, "폴더를 찾을 수 없습니다."
    if any(f["name"] == name and f["id"] != folder_id for f in folders):
        return False, "같은 이름의 폴더가 이미 있습니다."

    target["name"] = name
    _save(folders)
    return True, "폴더 이름을 바꿨습니다."


def delete_folder(folder_id: str) -> tuple[bool, str]:
    folders = _load()
    remaining = [f for f in folders if f["id"] != folder_id]
    if len(remaining) == len(folders):
        return False, "폴더를 찾을 수 없습니다."
    _save(remaining)
    return True, "폴더를 삭제했습니다. 안에 있던 도메인은 미분류로 이동합니다."


def assign_domain(domain: str, folder_id: str | None) -> tuple[bool, str]:
    domain = (domain or "").strip()
    if not domain:
        return False, "도메인이 지정되지 않았습니다."

    folders = _load()
    # 어느 폴더에 있든 먼저 빼고, 지정된 폴더에만 넣는다.
    for f in folders:
        f["domains"] = [d for d in f["domains"] if d != domain]

    if folder_id:
        target = next((f for f in folders if f["id"] == folder_id), None)
        if target is None:
            return False, "폴더를 찾을 수 없습니다."
        target["domains"].append(domain)
        _save(folders)
        return True, f"'{target['name']}' 폴더로 옮겼습니다."

    _save(folders)
    return True, "미분류로 옮겼습니다."


def group_domains(domains: list[dict]) -> list[dict]:
    by_domain = {d["domain"]: d for d in domains}
    grouped = []
    claimed: set[str] = set()

    for f in _load():
        members = []
        for name in f["domains"]:
            d = by_domain.get(name)
            if d is None or name in claimed:
                continue
            members.append(d)
            claimed.add(name)
        grouped.append(
            {
                "id": f["id"],
                "name": f["name"],
                "domains": members,
                "ports": collect_ports(members),
            }
        )

    unfiled = [d for d in domains if d["domain"] not in claimed]
    grouped.append(
        {
            "id": None,
            "name": "미분류",
            "domains": unfiled,
            "ports": collect_ports(unfiled),
        }
    )
    return grouped


def collect_ports(domains: list[dict]) -> list[int]:
    ports: set[int] = set()
    for d in domains:
        for p in d.get("paths") or []:
            try:
                ports.add(int(p["port"]))
            except (TypeError, ValueError, KeyError):
                continue
    return sorted(ports)
