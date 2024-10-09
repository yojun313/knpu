import pymysql
import csv
import os
import pandas as pd

class mySQL:
    def __init__(self, host, user, password, port, database=None):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.database = database
        self.connectDB(database)

    def connectDB(self, database_name=None):
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
    
    def disconnectDB(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception as e:
            print(f"Failed to close the connection to database {self.database}")
            print(str(e))
        finally:
            self.conn = None

    def resetServer(self):
        DBlist = self.showAllDB()
        for DB in DBlist:
            self.dropDB(DB)

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
            self.disconnectDB()
            self.connectDB()
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

                # 불필요한 데이터베이스를 제거하면서 리스트로 변환
                remove_list = {'information_schema', 'mysql', 'performance_schema'}
                database_list = [db[0] for db in databases if db[0] not in remove_list]

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
                # 테이블 이름을 백틱으로 감싸기
                cursor.execute(f"DROP TABLE IF EXISTS `{tableName}`")
                self.conn.commit()
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

    def showDBSize(self, database_name):
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT 
                        ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS `SizeMB`
                    FROM 
                        information_schema.tables 
                    WHERE 
                        table_schema = %s
                    """
                cursor.execute(query, (database_name,))
                size_mb = cursor.fetchone()[0]  # MB 단위로 반환된 크기

                # 기가바이트로 변환 (GB = MB / 1024)
                size_gb = float(round(size_mb / 1024, 2))  # 기가바이트로 변환하여 소수점 두 자리까지

                # 메가바이트는 정수로 변환 (소수점 표시 X)
                size_mb_int = int(size_mb)

                # 리스트로 반환 [기가단위, 메가단위]
                return [size_gb, size_mb_int]
        except Exception as e:
            print(f"Failed to retrieve size for database {database_name}")
            print(str(e))
            return None

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

    def TableToCSV(self, tableName, csv_path, filename = ''):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM `{tableName}`")
                rows = cursor.fetchall()
                fieldnames = [desc[0] for desc in cursor.description]

                if filename == '':
                    with open(os.path.join(csv_path, tableName + '.csv'), 'w', newline='', encoding='utf-8-sig', errors='ignore') as csvfile:
                        csvwriter = csv.writer(csvfile)
                        csvwriter.writerow(fieldnames)
                        csvwriter.writerows(rows)
                else:
                    with open(os.path.join(csv_path, filename + '.csv'), 'w', newline='', encoding='utf-8-sig', errors='ignore') as csvfile:
                        csvwriter = csv.writer(csvfile)
                        csvwriter.writerow(fieldnames)
                        csvwriter.writerows(rows)

        except Exception as e:
            print(f"Failed to save table {tableName} to CSV")
            print(str(e))

    def TableToDataframe(self, tableName, index_range=None):
        try:
            with self.conn.cursor() as cursor:
                if index_range:
                    parts = index_range.split(':')
                    start = parts[0].strip()
                    end = parts[1].strip() if len(parts) > 1 else ''

                    if start == '' and end != '':  # ":100" or ":-100" 형태
                        end = int(end)
                        if end > 0:
                            query = f"SELECT * FROM `{tableName}` LIMIT {end}"
                        elif end < 0:  # ":-100" 형태
                            limit = abs(end)
                            query = f"""
                            SELECT * FROM (
                                SELECT * FROM `{tableName}` ORDER BY id DESC LIMIT {limit}
                            ) subquery ORDER BY id ASC
                            """

                    elif start != '' and end == '':  # "100:" 형태
                        start = int(start)
                        if start >= 0:
                            query = f"SELECT * FROM `{tableName}` LIMIT {start}, 18446744073709551615"

                    elif start != '' and end != '':  # "100:200" 형태
                        start = int(start)
                        end = int(end)
                        if start >= 0 and end > 0 and end > start:
                            limit = end - start
                            query = f"SELECT * FROM `{tableName}` LIMIT {start}, {limit}"
                        else:
                            raise ValueError("Invalid index range: end must be greater than start.")

                    elif start == '' and end == '':  # ":" 형태, 모든 데이터 가져오기
                        query = f"SELECT * FROM `{tableName}`"

                    else:
                        raise ValueError("Unsupported index range format.")
                else:
                    query = f"SELECT * FROM `{tableName}`"

                cursor.execute(query)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                dataframe = pd.DataFrame(rows, columns=columns)
                return dataframe

        except Exception as e:
            print(f"Failed to convert table {tableName} to DataFrame")
            print(str(e))
            return None

    def TableToDataframeByDate(self, tableName, start_date, end_date):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"SHOW COLUMNS FROM {tableName}")
                columns = cursor.fetchall()
                date_column = [column[0] for column in columns if 'date' in column[0].lower()][0]

            query = f"""
                    SELECT * FROM `{tableName}`
                    WHERE `{date_column}` BETWEEN %s AND %s;
                    """
            with self.conn.cursor() as cursor:
                cursor.execute(query, (start_date, end_date))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                dataframe = pd.DataFrame(rows, columns=columns)
                return dataframe
        except Exception as e:
            print(f"Failed to retrieve data from {tableName} between {start_date} and {end_date}")
            print(str(e))
            return None

    def TableToList(self, tableName):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM `{tableName}`")
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                # 데이터프레임으로 변환
                dataframe = pd.DataFrame(rows, columns=columns)

                # 첫 번째 행과 첫 번째 열 제외
                sub_dataframe = dataframe.iloc[:, 1:]

                # 2차원 리스트로 변환하여 반환
                result = sub_dataframe.values.tolist()
                return result
        except Exception as e:
            print(f"Failed to convert table {tableName} to 2D list")
            print(str(e))
            return None

    def CSVToTable(self, csv_path, tableName):
        try:
            # CSV 파일을 읽어서 데이터프레임으로 변환
            df = pd.read_csv(csv_path)

            # NaN 값을 None (SQL의 NULL에 해당)으로 변환
            df = df.where(pd.notnull(df), None)

            # 데이터프레임의 열 이름을 가져오기
            columns = df.columns.tolist()

            # 테이블 생성 쿼리 생성
            if 'id' in columns:
                create_table_query = f"CREATE TABLE IF NOT EXISTS `{tableName}` ("
            else:
                create_table_query = f"CREATE TABLE IF NOT EXISTS `{tableName}` (id INT AUTO_INCREMENT PRIMARY KEY, "

            for column in columns:
                create_table_query += f"`{column}` LONGTEXT, "
            create_table_query = create_table_query.rstrip(', ')  # 마지막 쉼표와 공백 제거
            create_table_query += ")"

            with self.conn.cursor() as cursor:
                # 테이블 생성
                cursor.execute(create_table_query)
                self.conn.commit()

                # 데이터프레임의 데이터를 리스트로 변환
                data_list = df.values.tolist()

                # 열 이름을 문자열로 변환
                columns_str = ', '.join([f'`{col}`' for col in columns])

                # VALUES 부분의 자리표시자 생성
                placeholders = ', '.join(['%s'] * len(columns))

                # INSERT 쿼리 생성
                insert_query = f"INSERT INTO `{tableName}` ({columns_str}) VALUES ({placeholders})"

                # 여러 행의 데이터를 한 번에 삽입
                cursor.executemany(insert_query, data_list)
                self.conn.commit()

        except Exception as e:
            print(f"Failed to convert CSV file {csv_path} to table {tableName}")
            print(str(e))

    def DataframeToTable(self, dataframe, tableName):
        try:
            # 데이터프레임에서 'id' 열이 있을 경우 제거
            if 'id' in dataframe.columns:
                dataframe = dataframe.drop(columns=['id'])

            # 데이터프레임의 열 이름을 가져오기
            columns = dataframe.columns.tolist()

            # 테이블 생성 쿼리 생성
            create_table_query = f"CREATE TABLE IF NOT EXISTS `{tableName}` (id INT AUTO_INCREMENT PRIMARY KEY, "
            for column in columns:
                create_table_query += f"`{column}` LONGTEXT, "
            create_table_query = create_table_query.rstrip(', ')  # 마지막 쉼표와 공백 제거
            create_table_query += ")"

            with self.conn.cursor() as cursor:
                # 테이블 생성
                cursor.execute(create_table_query)
                self.conn.commit()

                # 데이터프레임의 데이터를 리스트로 변환
                data_list = dataframe.values.tolist()

                # 열 이름을 문자열로 변환
                columns_str = ', '.join([f'`{col}`' for col in columns])

                # VALUES 부분의 자리표시자 생성
                placeholders = ', '.join(['%s'] * len(columns))

                # INSERT 쿼리 생성
                insert_query = f"INSERT INTO `{tableName}` ({columns_str}) VALUES ({placeholders})"

                # 여러 행의 데이터를 한 번에 삽입
                cursor.executemany(insert_query, data_list)
                self.conn.commit()

        except Exception as e:
            print(f"Failed to insert DataFrame into table {tableName}")
            print(str(e))

    def deleteTableRowByColumn(self, tableName, target, columnName):
        try:
            with self.conn.cursor() as cursor:
                # DELETE 쿼리 생성
                query = f"DELETE FROM `{tableName}` WHERE `{columnName}` = %s"
                cursor.execute(query, (target,))
                self.conn.commit()
        except Exception as e:
            print(f"Failed to delete row with {columnName} = {target} from table {tableName}")
            print(str(e))

    def updateTableCell(self, tableName, row_number, column_name, new_value):
        try:
            with self.conn.cursor() as cursor:
                # OFFSET을 이용해서 n번째 행의 id를 찾음
                query_get_id = f"SELECT id FROM `{tableName}` ORDER BY id ASC LIMIT 1 OFFSET %s"
                cursor.execute(query_get_id, (row_number,))
                result = cursor.fetchone()

                row_id = result[0]  # 해당 row_number의 실제 id

                # 해당 id로 업데이트
                query_update = f"UPDATE `{tableName}` SET `{column_name}` = %s WHERE id = %s"
                cursor.execute(query_update, (new_value, row_id))
                self.conn.commit()

        except pymysql.MySQLError as e:
            print(f"Failed to update row {row_number} in column {column_name} of table {tableName}")
            print(f"MySQL Error: {str(e)}")
        except Exception as e:
            print(f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    # 사용 예제
    mySQL_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306, database='bigmaclab_manager_db')
    mySQL_obj.connectDB('navernews_대리모_20010101_20240930_1001_2014')
    print(mySQL_obj.showDBSize('navernews_대리모_20010101_20240930_1001_2014'))
