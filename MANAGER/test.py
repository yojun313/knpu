import time

class MySQLDatabase:
    def __init__(self, connection):
        self.conn = connection

    def showAllDB(self):
        try:
            with self.conn.cursor() as cursor:
                start_time = time.time()
                cursor.execute("SHOW DATABASES")
                databases = cursor.fetchall()
                elapsed_time = time.time() - start_time


                # 불필요한 데이터베이스를 제거하면서 리스트로 변환
                remove_list = {'information_schema', 'mysql', 'performance_schema', 'user_db'}
                database_list = [db[0] for db in databases if db[0] not in remove_list]
                print(f"SHOW DATABASES took {elapsed_time:.4f} seconds")
                print(database_list)
                return database_list
        except Exception as e:
            print("Failed to retrieve databases")
            print(str(e))
            return []

    def showAllTable(self, database_name):
        try:
            with self.conn.cursor() as cursor:
                start_time = time.time()
                cursor.execute(f"SHOW TABLES FROM `{database_name}`")
                tables = cursor.fetchall()
                elapsed_time = time.time() - start_time
                print(f"SHOW TABLES FROM {database_name} took {elapsed_time:.4f} seconds")

                # 테이블 이름을 리스트로 변환
                table_list = [table[0] for table in tables]
                return table_list
        except Exception as e:
            print(f"Failed to retrieve tables from database {database_name}")
            print(str(e))
            return []

# Usage example
if __name__ == "__main__":
    import pymysql

    # Replace with your actual database connection details
    connection = pymysql.connect(
        host='121.152.225.232',
        user='admin',
        password='bigmaclab2022!',
        port=3306
    )

    db = MySQLDatabase(connection)

    # Compare performance of SHOW DATABASES and SHOW TABLES
    db_list = db.showAllDB()
    for database_name in db_list:
        table_list = db.showAllTable(database_name)

    connection.close()
