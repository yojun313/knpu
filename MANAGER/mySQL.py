import pymysql
import csv
import os
import pandas as pd

DB_IP = '121.152.225.232'
LOCAL_IP = '192.168.0.3'

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

    def TableLastRow(self, tableName):
        try:
            with self.conn.cursor() as cursor:
                # 테이블의 전체 행 개수를 구합니다.
                cursor.execute(f"SELECT COUNT(*) FROM `{tableName}`")
                row_count = cursor.fetchone()[0]

                # 테이블이 비어 있는지 확인합니다.
                if row_count == 0:
                    return ()  # 테이블이 비어 있을 경우 빈 튜플 반환

                # 마지막 행을 가져오기 위해 OFFSET을 사용합니다.
                query = f"SELECT * FROM `{tableName}` LIMIT 1 OFFSET {row_count - 1}"
                cursor.execute(query)
                last_row = cursor.fetchone()
                return last_row

        except Exception as e:
            print(f"Failed to fetch the last row from table {tableName}")
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

    import pymysql

    def updateTableCell(self, tableName, row_number, column_name, new_value, add=False):
        try:
            with self.conn.cursor() as cursor:
                # row_number가 -1이면 마지막 행을 가리키게 설정
                if row_number == -1:
                    # 전체 행 개수 가져오기
                    cursor.execute(f"SELECT COUNT(*) FROM `{tableName}`")
                    total_rows = cursor.fetchone()[0]
                    # 마지막 행의 OFFSET을 total_rows - 1로 설정
                    row_number = total_rows - 1

                # OFFSET을 이용해서 n번째 행의 id를 찾음
                query_get_id = f"SELECT id FROM `{tableName}` ORDER BY id ASC LIMIT 1 OFFSET %s"
                cursor.execute(query_get_id, (row_number,))
                result = cursor.fetchone()

                if result:
                    row_id = result[0]  # 해당 row_number의 실제 id

                    # add=True인 경우 기존 값을 가져와 추가
                    if add:
                        query_get_current_value = f"SELECT `{column_name}` FROM `{tableName}` WHERE id = %s"
                        cursor.execute(query_get_current_value, (row_id,))
                        current_value = cursor.fetchone()[0] or ""  # None일 경우 빈 문자열로 처리
                        new_value = current_value + str(new_value)  # 기존 값에 새 값을 추가

                    # 업데이트 쿼리 실행
                    query_update = f"UPDATE `{tableName}` SET `{column_name}` = %s WHERE id = %s"
                    cursor.execute(query_update, (new_value, row_id))
                    self.conn.commit()
                else:
                    print(f"No row found at position {row_number} in table {tableName}")

        except pymysql.MySQLError as e:
            print(f"Failed to update row {row_number} in column {column_name} of table {tableName}")
            print(f"MySQL Error: {str(e)}")
        except Exception as e:
            print(f"An unexpected error occurred: {str(e)}")

    def updateTableCellByCondition(self, tableName, search_column, search_value, target_column, new_value, add=False):
        try:
            with self.conn.cursor() as cursor:
                # search_column에서 search_value를 가진 행을 찾음
                query_get_id = f"SELECT id FROM `{tableName}` WHERE `{search_column}` = %s LIMIT 1"
                cursor.execute(query_get_id, (search_value,))
                result = cursor.fetchone()

                if result:
                    row_id = result[0]  # 해당 조건을 만족하는 행의 id

                    # add=True인 경우 기존 값을 가져와 추가
                    if add:
                        query_get_current_value = f"SELECT `{target_column}` FROM `{tableName}` WHERE id = %s"
                        cursor.execute(query_get_current_value, (row_id,))
                        current_value = cursor.fetchone()[0] or ""  # None일 경우 빈 문자열로 처리
                        new_value = current_value + str(new_value)  # 기존 값에 새 값을 추가

                    # 업데이트 쿼리 실행
                    query_update = f"UPDATE `{tableName}` SET `{target_column}` = %s WHERE id = %s"
                    cursor.execute(query_update, (new_value, row_id))
                    self.conn.commit()
                else:
                    print(f"No row found with {search_column} = {search_value} in table {tableName}")

        except pymysql.MySQLError as e:
            print(
                f"Failed to update row where {search_column} = {search_value} in column {target_column} of table {tableName}")
            print(f"MySQL Error: {str(e)}")
        except Exception as e:
            print(f"An unexpected error occurred: {str(e)}")

    # DB 데이터가 날아갔을 때를 대비한 셋업 코드
    def manager_setup(self):

        self.newDB('bigmaclab_manager_db_test')
        self.newTable('device_list', ['device_name', 'user_name'])
        self.newTable('free_board', ['User', 'Title', 'DateTime', 'ViewCount', 'Text', 'PW'])
        self.newTable('version_bug', ['User', 'Version Num', 'Bug Title', 'DateTime', 'Bug Detail', 'Program Log'])
        self.newTable('version_info',['Version Num', 'Release Date', 'ChangeLog', 'Version Features', 'Version Status', 'Version Detail'])
        self.commit()

        self.newDB('crawler_db_test')
        self.newTable('db_list',
                           ['DBname', 'Option', 'Starttime', 'Endtime', 'Requester', 'Keyword', 'DBSize', 'Crawlcom',
                            'CrawlSpeed', 'Datainfo'])
        self.newTable('crawl_log', ['DB', 'Log'])

        self.newDB('user_db_test')
        self.newTable('user_info', ['Name', 'Email', 'PushOver'])
        self.insertToTable('user_info', [
            ['admin', 'moonyojun@naver.com', 'uvz7oczixno7daxvgxmq65g2gbnsd5'],
            ['4', '노승국', 'science2200@naver.com', 'uxjkfr6cjx6bpcdx4oybq9xi51fjhz'],
            ['이정우', 'wjddn_1541@naver.com', 'uqkbhuy1e1752ryxnjp3hy5g67467m'],
            ['최우철', 'woc0633@gmail.com', 'uz9rj99t6a4fnb8euqsxez3z79sxyc'],
            ['한승혁', 'hankyeul80@naver.com', 'ugxc5xrg2jmhm85uuymsam2ge1uhyv'],
            ['배시웅', 'silverwolves0415@gmail.com', 'uryj88brmquqmtmm6c2ouwpzxtpdy9'],
            ['public', 'moonyojun@naver.com', 'n'],
            ['이진원', 'nevermean@empas.com', 'n']
        ])
        self.commit()

        self.newTable('youtube_api', ['API code'])
        self.insertToTable('youtube_api', [
            ['AIzaSyBP90vCq6xn3Og4N4EFqODcmti-F74rYXU'],
            ['AIzaSyCkOqcZlTING7t6XqZV9M-aoTR8jHBDPTs'],
            ['AIzaSyCf6Ud2qaXsnAJ1zYw-2sbYNCoBvNjQ1Io'],
            ['AIzaSyDpjsooOwgSk2tkq4GJ30jKFmyTFgpWfLs'],
            ['AIzaSyAGVnvf-u0rGWtaaKMU_vUo6CN0QTHklC4'],
            ['AIzaSyD1pTe0tevj1WhzbsC8NO6sXC6X4ztF7a0'],
            ['AIzaSyDz8NVKiTkQVzJf-eCloKEfL6DWxjInYjo'],
            ['AIzaSyByxep-pVr7eM5Z-wvL1u-Iy_6q7iUrtWk'],
            ['AIzaSyC5i2IcG0ntpD0ZbO_8sRomMq8LbHEWnGk'],
            ['AIzaSyAmO8mi1lX1KwUsMRQl6fI6YFp7Gxy2eLk'],
            ['AIzaSyAzh54hQhYQK-qsLJBVAp1SPyGXcntGn1M'],
            ['AIzaSyBGISnI-0eBKuNYBeUko-Jj_avVSbdXLrU'],
            ['AIzaSyAE0vxDo2CUIn0SsTYeCaV2HzdCJfhO4l4']
        ])
        self.commit()

        for name in ['admin', '노승국', '이정우', '최우철', '한승혁', '배시웅', 'public', '이진원']:
            self.newDB(name+'_db_test')
            self.newTable('manager_record', ['Date', 'Bug', 'Log', 'D_Log'])
            self.newTable('keyword_eng', ['korean', 'english'])
            self.newTable('제외어 사전', ['word'])

    def tokenization(self, DBname):
        import re
        from kiwipiepy import Kiwi

        def tokenization(data):
            kiwi = Kiwi(num_workers=8)
            for column in data.columns.tolist():
                if 'Text' in column:
                    textColumn_name = column

            text_list = list(data[textColumn_name])
            tokenized_data = []

            for index, text in enumerate(text_list):
                try:
                    if not isinstance(text, str):
                        tokenized_data.append([])
                        continue  # 문자열이 아니면 넘어감

                    text = re.sub(r'[^가-힣a-zA-Z\s]', '', text)
                    tokens = kiwi.tokenize(text)
                    tokenized_text = [token.form for token in tokens if token.tag in ('NNG', 'NNP')]

                    # 리스트를 쉼표로 구분된 문자열로 변환
                    tokenized_text_str = ", ".join(tokenized_text)
                    tokenized_data.append(tokenized_text_str)

                    progress_value = round((index + 1) / len(text_list) * 100, 2)
                    print(f'\r{textColumn_name.split(' ')[0]} Tokenization Progress: {progress_value}%', end='')
                except:
                    tokenized_data.append([])

            data[textColumn_name] = tokenized_data
            return data

        self.connectDB(DBname)
        tablelist = [table for table in self.showAllTable(DBname) if 'info' not in table]

        for table in tablelist:
            data_df = self.TableToDataframe(table)
            token_df = tokenization(data_df)
            print(f'\r{table} DB Inserting...', end='')
            self.DataframeToTable(token_df, 'token_' + table)


if __name__ == "__main__":
    import re
    from kiwipiepy import Kiwi

    def test():
        mySQL_obj = mySQL(host=LOCAL_IP, user='admin', password='bigmaclab2022!', port=3306)
        DBname = "navernews_문재인_20170510_20220509_1201_0022"

        def tokenization(data):
            kiwi = Kiwi(num_workers=8)
            for column in data.columns.tolist():
                if 'Text' in column:
                    textColumn_name = column

            text_list = list(data[textColumn_name])
            tokenized_data = []

            for index, text in enumerate(text_list):
                try:
                    if not isinstance(text, str):
                        tokenized_data.append([])
                        continue  # 문자열이 아니면 넘어감

                    text = re.sub(r'[^가-힣a-zA-Z\s]', '', text)
                    tokens = kiwi.tokenize(text)
                    tokenized_text = [token.form for token in tokens if token.tag in ('NNG', 'NNP')]

                    # 리스트를 쉼표로 구분된 문자열로 변환
                    tokenized_text_str = ", ".join(tokenized_text)
                    tokenized_data.append(tokenized_text_str)

                    progress_value = round((index + 1) / len(text_list) * 100, 2)
                    print(f'\r{textColumn_name.split(' ')[0]} Tokenization Progress: {progress_value}%', end='')
                except:
                    tokenized_data.append([])

            data[textColumn_name] = tokenized_data
            return data

        mySQL_obj.connectDB(DBname)
        tablelist = [table for table in mySQL_obj.showAllTable(DBname) if 'info' not in table]

        for table in tablelist:
            data_df = mySQL_obj.TableToDataframe(table)
            token_df = tokenization(data_df)
            print(f'\r{table} DB Inserting...', end='')
            mySQL_obj.DataframeToTable(token_df, 'token_' + table)

    test()



