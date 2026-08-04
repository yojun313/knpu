from system.db import (
    client,
    user_logs_db as user_logs_col,
    user_bugs_db as user_bugs_col,
    bug_board_db as bug_board_col,
    crawlList_db as db_list_col,
    crawlLog_db as crawler_log_col,
    user_db as homepage_users_col,
    legacy_users_db as manager_users_col,
    identities_db as identity_history_col,
    discord_notifications_db as discord_notifications_col,
)

admin_settings_col = client["admin"]["settings"]

__all__ = [
    "user_logs_col",
    "user_bugs_col",
    "bug_board_col",
    "db_list_col",
    "crawler_log_col",
    "homepage_users_col",
    "manager_users_col",
    "identity_history_col",
    "discord_notifications_col",
    "admin_settings_col",
]
