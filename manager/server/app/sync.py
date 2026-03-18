from app.db import sync_manager_databases

sync_manager_databases(
    src_db_name='manager', 
    target_db_name='manager_dev'
)

sync_manager_databases(
    src_db_name='crawler', 
    target_db_name='crawler_dev'
)