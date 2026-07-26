from services.api import Request


def sendAdminNotify(msg, kind="ops"):
    Request("post", "/users/admin/notify", json={"message": msg, "kind": kind})
