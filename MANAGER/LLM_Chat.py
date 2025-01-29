print("[ LLM Chat Booting Process ]")
print()
print("Importing Libraries...", end='')
import pymysql
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import platform
import requests
import os
import sys
import json
import random
import socket
from datetime import datetime
print("Done")

SERVER_IP = '121.152.225.232'

class LLM_Chat:
    def __init__(self):

        self.api_url = f"http://{SERVER_IP}:3333/api/process"
        self.log = ''

        print("Checking Internet Connection... ", end='')
        self.check_internet_connection()
        print("Done")

        print("Connecting to server... ", end='')
        self.mySQL_obj = mySQL(host=SERVER_IP, user='admin', password='bigmaclab2022!', port=3306)
        print("Done")

        print("Authorizing user...", end='')
        print("Done") if self.login() == True else print("실패")

        self.clear_console()

        self.model_selection()
        self.model_chat()

    def login(self):
        self.mySQL_obj.connectDB('user_db')
        userDF = self.mySQL_obj.TableToDataframe('user_info')
        user_data = [(name, email, key) for _, name, email, key in userDF.itertuples(index=False, name=None)]
        self.userNameList = [name for name, _, key in user_data]
        self.userMailList = [email for _, email, key in user_data]

        self.mySQL_obj.connectDB('bigmaclab_manager_db')
        userDF = self.mySQL_obj.TableToDataframe('device_list')
        device_data = [(user, device) for _, device, user in userDF.itertuples(index=False, name=None)]
        device_data = sorted(device_data, key=lambda x: (not x[0][0].isalpha(), x[0]))

        # userNameList 및 userKeyList 업데이트
        self.device_list = [device for name, device in device_data]
        self.user_list = [name for name, device in device_data]

        current_device = socket.gethostname()
        self.user_device = current_device
        if current_device in self.device_list:
            self.user = self.user_list[self.device_list.index(current_device)]
            self.usermail = self.userMailList[self.userNameList.index(self.user)]
            return True
        else:
            self.clear_console()
            answer = input("Device is not registered. Would you register this device? (Y/n) ")
            if answer.lower() == 'y':
                self.clear_console()
                print("[ Login Process ]")
                username = input("User Name: ")

                if username not in self.userNameList:
                    print('\nUser name is not registered\nQuit program')
                    return False

                self.user = username
                self.usermail = self.userMailList[self.userNameList.index(username)]

                print("\nSending authorization code...")
                random_pw = ''.join(random.choices('0123456789', k=6))
                msg = (
                    f"사용자: {self.user}\n"
                    f"디바이스: {current_device}\n"
                     f"인증 번호 '{random_pw}'를 입력하십시오"
                )
                self.send_email(self.usermail, "LLM Chat 디바이스 등록 인증번호", msg)
                print(f"\nAuthorization code was sent to {self.user}'s {self.usermail}\nCheck your code and type here")
                pw = input("Code: ")
                if pw == random_pw:
                    self.mySQL_obj.insertToTable('device_list', [[current_device, username]])
                    self.mySQL_obj.commit()
                    print("Device is registered")
                    return True
                else:
                    print('\nAuthorization number is not correct\n\nQuit program')
                    return False

    def model_selection(self):
        print("Importing LLM model list...")
        self.mySQL_obj.connectDB('bigmaclab_manager_db')
        configDF = self.mySQL_obj.TableToDataframe('configuration')
        self.CONFIG = dict(zip(configDF[configDF.columns[1]], configDF[configDF.columns[2]]))

        # LLM 모델 이름 설정
        LLM_json = json.loads(self.CONFIG['LLM_model'])
        self.LLM_list = [(value, key) for key, value in LLM_json.items()]
        self.LLM_list = sorted(self.LLM_list, key=lambda x: x[0])

        self.LLM_list.remove(('ChatGPT 4', 'ChatGPT'))

        print("\nChoose LLM model: ")
        for index, model in enumerate(self.LLM_list, start=1):
            print(f"{index}. {model[0]}")

        while True:
            num = int(input("\nEnter model number: "))
            if num in range(1, len(self.LLM_list) + 1):
                break
            else:
                print("\nInvalid number")

        self.LLM_model_name = self.LLM_list[num - 1][0]
        self.LLM_model = self.LLM_list[num - 1][1]

    def model_chat(self):

        def add_to_log(message):
            """출력 메시지를 로그에 추가"""
            self.log += f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n"

        def see_help():
            print()
            help = (
                "Available Commands:\n"
                "  /model                      Change LLM model\n"
                "  /save                       Save chat history\n"
                "  /clear                      Delete chat history\n"
                "  /quit                       Quit Program\n"
            )
            print(help)


        self.clear_console()
        print(f"[ {self.LLM_model_name} Chat ]\n")
        print("Type '/?' to see available commands\n")

        while True:
            query = input(f"User >>> ")

            if query == '/?':
                see_help()
                continue

            if self.commands(query) == True:
                continue

            add_to_log(f"User >>> {query}\n")

            print()

            print(f"{self.LLM_model_name} >>> Generating...", end='\r')
            answer = self.model_answer(query)
            print(f"{self.LLM_model_name} >>> {answer}\n")
            add_to_log(f"{self.LLM_model_name} >>> {answer}\n")

    def commands(self, query):
        if query == '/model':
            prev_model_name = self.LLM_model_name
            self.model_selection()

            print()
            if self.LLM_model_name == prev_model_name:
                print("Model not changed")
            else:
                print(f"Model Changed: {prev_model_name} -> {self.LLM_model_name}\n")
            return True

        elif query == '/save':
            print()
            directory = self.select_directory()
            if directory is not None:
                file_path = os.path.join(directory, f"{datetime.now().strftime("%Y%m%d_%H%M")}_LLM_log.txt")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log)
                print("Log successfully saved\n")
            return True
        elif query == '/clear':
            self.clear_console()
            return True
        elif query == '/quit':
            sys.exit()

        return False

    def select_directory(self):
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()  # Tkinter 기본 창 숨기기
        directory = filedialog.askdirectory(title="Select Directory")  # 디렉토리 선택 창 열기

        if directory:
            return directory
        else:
            return None

    def model_answer(self, query):
        # 전송할 데이터
        data = {
            "model_name": self.LLM_model,
            "question": query
        }

        try:
            # POST 요청 보내기
            response = requests.post(self.api_url, json=data)

            # 응답 확인
            if response.status_code == 200:
                result = response.json()['result']
                result = result.replace('<think>', '').replace('</think>', '').replace('\n\n', '')
                return result
            else:
                return f"Failed to get a valid response: {response.status_code} {response.text}"

        except requests.exceptions.RequestException as e:
            return "Error communicating with the server: {e}"

    def send_email(self, receiver, title, text):
        sender = "knpubigmac2024@gmail.com"
        MailPassword = 'vygn nrmh erpf trji'

        msg = MIMEMultipart()
        msg['Subject'] = title
        msg['From'] = sender
        msg['To'] = receiver

        msg.attach(MIMEText(text, 'plain'))

        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        # SMTP 연결 및 메일 보내기
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, MailPassword)
            server.sendmail(sender, receiver, msg.as_string())

    def clear_console(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")


    def check_internet_connection(self):
        while True:
            try:
                # Google을 기본으로 확인 (URL은 다른 사이트로 변경 가능)
                response = requests.get("http://www.google.com", timeout=5)
                return response.status_code == 200
            except requests.ConnectionError:
                answer = input("You are not connected to Internet\nConnect to Internet and retry\nRetry? (Y/n) ")
                if answer.lower() == 'y':
                    continue
                else:
                    sys.exit()

class mySQL:
    def __init__(self, host, user, password, port, database=None):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.database = database
        self.conn = pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            port=self.port,
            database=database  # 데이터베이스 지정
        )

    def connectDB(self, database_name=None):
        try:
            self.disconnectDB()
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

            self.conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                port=self.port
            )
        except Exception as e:
            pass

    def commit(self):
        self.conn.commit()

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

if __name__ == '__main__':
    LLM_Chat_obj = LLM_Chat()