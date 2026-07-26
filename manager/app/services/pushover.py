from services.api import Request


def sendAdminPushOver(msg, kind="ops"):
    Request("post", "/users/admin/pushover", json={"message": msg, "kind": kind})
