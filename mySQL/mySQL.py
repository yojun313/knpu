import pymysql
import csv
import os

class mySQL:
    def __init__(self, host, user, password, port, database=None):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.database = database
        self.connectDB()

    def connectDB(self, database_name):
        try:
            self.conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                port=self.port,
                database=database_name  # 데이터베이스 지정
            )
            self.database = database_name
        except Exception as e:
            if self.database:
                print(f"Failed to connect to database {self.database} on host:{self.host} with user:{self.user}")
            else:
                print(f"Failed to connect to MySQL server on host:{self.host} with user:{self.user}")
            print(str(e))

    def commit(self):
        self.conn.commit()

    def newDB(self, database_name):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")
                self.conn.commit()

                # 데이터베이스 생성 후 다시 연결
                self.database = database_name
                self.connectDB(database_name)
        except Exception as e:
            print(f"Failed to create database {database_name}")
            print(str(e))

    def dropDB(self, database_name):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS {database_name}")
                self.conn.commit()
        except Exception as e:
            print(f"Failed to drop database {database_name}")
            print(str(e))

    def showAllDB(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SHOW DATABASES")
                databases = cursor.fetchall()
                # 데이터베이스 이름을 리스트로 변환
                database_list = [db[0] for db in databases]

                remove_list = ['information_schema', 'mysql', 'performance_schema']
                for remove_target in remove_list:
                    database_list.remove(remove_target)

                return database_list

        except Exception as e:
            print("Failed to retrieve databases")
            print(str(e))
            return []

    def newTable(self, tableName, column_list):
        try:
            with self.conn.cursor() as cursor:
                query = f"CREATE TABLE IF NOT EXISTS `{tableName}` (id INT AUTO_INCREMENT PRIMARY KEY, "
                for column in column_list:
                    query += f"`{column}` LONGTEXT, "
                query = query.rstrip(', ')  # 마지막 쉼표와 공백 제거
                query += ")"

                cursor.execute(query)
                self.conn.commit()
        except Exception as e:
            print(f"Failed to create table {tableName}")
            print(str(e))

    def dropTable(self, tableName):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {tableName}")
                self.conn.commit()
                print(f"Table {tableName} dropped successfully")
        except Exception as e:
            print(f"Failed to drop table {tableName}")
            print(str(e))

    def showAllTable(self, database_name):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"SHOW TABLES FROM `{database_name}`")
                tables = cursor.fetchall()
                # 테이블 이름을 리스트로 변환
                table_list = [table[0] for table in tables]
                return table_list
        except Exception as e:
            print(f"Failed to retrieve tables from database {database_name}")
            print(str(e))
            return []

    def insertToTable(self, tableName, data_list):
        try:
            with self.conn.cursor() as cursor:
                # 테이블의 열 이름을 가져오기 위한 쿼리 실행
                cursor.execute(f"SHOW COLUMNS FROM `{tableName}`")
                columns = [column[0] for column in cursor.fetchall()]

                # 'id' 열을 제외한 열 이름 리스트 생성
                columns = [col for col in columns if col != 'id']

                # 열 개수 확인
                num_columns = len(columns)

                # 데이터 리스트가 2차원 리스트인지 1차원 리스트인지 확인
                if isinstance(data_list[0], list):
                    if any(len(data) != num_columns for data in data_list):
                        raise ValueError("Data length does not match number of columns")
                    values = [tuple(data) for data in data_list]
                else:
                    if len(data_list) != num_columns:
                        raise ValueError("Data length does not match number of columns")
                    values = [tuple(data_list)]

                # 열 이름을 문자열로 변환
                columns_str = ', '.join([f'`{col}`' for col in columns])

                # VALUES 부분의 자리표시자 생성
                placeholders = ', '.join(['%s'] * num_columns)

                # INSERT 쿼리 생성
                query = f"INSERT INTO `{tableName}` ({columns_str}) VALUES ({placeholders})"

                cursor.executemany(query, values)

        except Exception as e:
            print(f"Failed to insert data into {tableName}")
            print(str(e))

    def TableToCSV(self, tableName, csv_path):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM `{tableName}`")
                rows = cursor.fetchall()
                fieldnames = [desc[0] for desc in cursor.description]

                with open(os.path.join(csv_path, tableName + '.csv'), 'w', newline='', encoding='utf-8-sig', errors='ignore') as csvfile:
                    csvwriter = csv.writer(csvfile)
                    csvwriter.writerow(fieldnames)
                    csvwriter.writerows(rows)

        except Exception as e:
            print(f"Failed to save table {tableName} to CSV")
            print(str(e))


if __name__ == "__main__":
    # 사용 예제
    mySQL_obj = mySQL(host='localhost', user='root', password='kingsman', port=3306)
    print(mySQL_obj.showAllTable('NaverCafe_포항공대_20230101_20230131_0802_1900'))

