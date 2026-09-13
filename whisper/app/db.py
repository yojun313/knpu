from system.db import client, user_db, user_logs_db

whisper_db = client["whisper"]
notes_db = whisper_db["notes"]

__all__ = ["client", "whisper_db", "notes_db", "user_db", "user_logs_db"]
