"""Discord bot async database and collection bindings."""

from types import SimpleNamespace
from .connection import get_async_client
from .names import DATABASE_NAMES


def get_bot_storage():
    client = get_async_client(
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=20000,
    )
    systems = client[DATABASE_NAMES["systems"]]
    return SimpleNamespace(
        mongo_client=client,
        systems_db=systems,
        crawler_db=client[DATABASE_NAMES["crawler"]],
        homepage_db=systems,  # Historical alias used for account verification.
        notifications_db=systems["discord-notifications"],
        auth_config_db=systems["bot-config"],
        user_bugs_db=systems["user-bugs"],
        legacy_users_db=systems["legacy-users"],
        discord_link_requests_db=systems["discord-link-requests"],
    )
