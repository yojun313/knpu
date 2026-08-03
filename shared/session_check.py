def revalidate_session(payload: dict | None, users_col) -> dict | None:
    if not payload:
        return None
    uid = payload.get("sub")
    if not uid:
        return None

    user = users_col.find_one(
        {"uid": uid}, {"role": 1, "status": 1, "token_version": 1, "name": 1}
    )
    if not user or user.get("status") != "approved":
        return None

    if user.get("token_version", 1) != payload.get("tv", 1):
        return None

    live = dict(payload)
    live["role"] = user.get("role")
    live["name"] = user.get("name", payload.get("name"))
    return live
