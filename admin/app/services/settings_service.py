from app.db import admin_settings_col

# 사이드바에 실제로 존재하는 메뉴 전체 — 여기 없는 id는 저장된 순서에 있어도 무시되고,
# 여기 있는데 저장된 순서에 없는 id(새로 추가된 탭)는 끝에 자동으로 붙는다.
NAV_ITEMS = [
    {"id": "overview", "label": "Overview", "href": "/"},
    {"id": "logs", "label": "User Logs", "href": "/logs"},
    {"id": "audit_logs", "label": "Audit Logs", "href": "/audit-logs"},
    {"id": "user_bugs", "label": "User Bugs", "href": "/bugs"},
    {"id": "crawlers", "label": "Crawler DB", "href": "/crawlers"},
    {"id": "bugs", "label": "Bug Reports", "href": "/bug-reports"},
    {"id": "users", "label": "Users", "href": "/users"},
    {"id": "process", "label": "Servers", "href": "/process"},
    {"id": "nginx", "label": "Domains", "href": "/nginx"},
    {"id": "ports", "label": "Ports", "href": "/ports"},
    {"id": "claude_usage", "label": "Claude", "href": "/claude-usage"},
    {"id": "git", "label": "Git", "href": "/git"},
    {"id": "versions", "label": "Versions", "href": "/versions"},
]

_ITEMS_BY_ID = {item["id"]: item for item in NAV_ITEMS}
DEFAULT_ORDER = [item["id"] for item in NAV_ITEMS]

_SETTINGS_ID = "nav_order"


def _normalize(order: list) -> list:
    ordered = [i for i in order if i in _ITEMS_BY_ID]
    missing = [i for i in DEFAULT_ORDER if i not in ordered]
    return ordered + missing


def get_nav_order_ids() -> list[str]:
    doc = admin_settings_col.find_one({"_id": _SETTINGS_ID})
    stored = doc.get("order") if doc else None
    return _normalize(stored) if stored else list(DEFAULT_ORDER)


def get_nav_items_ordered() -> list[dict]:
    return [_ITEMS_BY_ID[i] for i in get_nav_order_ids()]


def save_nav_order(order: list[str]) -> list[dict]:
    final = _normalize(order)
    admin_settings_col.update_one(
        {"_id": _SETTINGS_ID}, {"$set": {"order": final}}, upsert=True
    )
    return [_ITEMS_BY_ID[i] for i in final]
