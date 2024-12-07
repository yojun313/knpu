import os
import speech_recognition as sr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import requests
import pandas as pd
import traceback
from gtts import gTTS
from playsound import playsound
import tempfile
import sounddevice as sd


class ToolModule:
    def __init__(self):
        pass
    def decrypt_process(self):
        current_position = os.path.dirname(__file__)

        # 암호화 키 로드
        def load_key():
            try:
                with open(os.path.join(current_position, 'source', 'env.key'), "rb") as key_file:
                    return key_file.read()
            except:
                secret_key = os.getenv("SECRET_KEY")
                return secret_key

        def decrypt_env_file(encrypted_file_path):
            key = load_key()
            fernet = Fernet(key)

            # 암호화된 파일 읽기
            with open(encrypted_file_path, "rb") as file:
                encrypted_data = file.read()

            # 파일 복호화 및 .decrypted_env 파일로 저장
            decrypted_data = fernet.decrypt(encrypted_data).decode("utf-8")
            with open(os.path.join(current_position, 'decrypted_env'), "w", encoding="utf-8") as dec_file:
                dec_file.write(decrypted_data)

        decrypt_env_file(os.path.join(current_position, 'source', 'encrypted_env'))
        load_dotenv(os.path.join(current_position, 'decrypted_env'))

        self.admin_password = os.getenv('ADMIN_PASSWORD')
        self.public_password = os.getenv('PUBLIC_PASSWORD')
        self.admin_pushoverkey = os.getenv('ADMIN_PUSHOVER')
        self.db_ip = os.getenv('DB_IP')

        if os.path.exists(os.path.join(current_position, 'decrypted_env')):
            os.remove(os.path.join(current_position, 'decrypted_env'))

    def send_pushOver(self, msg, user_key, image_path=False):
        app_key_list = ["a22qabchdf25zzkd1vjn12exjytsjx"]

        for app_key in app_key_list:
            try:
                # Pushover API 설정
                url = 'https://api.pushover.net/1/messages.json'
                # 메시지 내용
                message = {
                    'token': app_key,
                    'user': user_key,
                    'message': msg
                }
                # Pushover에 요청을 보냄
                if image_path == False:
                    response = requests.post(url, data=message)
                else:
                    response = requests.post(url, data=message, files={
                        "attachment": (
                            "image.png", open(image_path, "rb"),
                            "image/png")
                    })
                break
            except:
                continue

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

    def csvReader(self, csvPath):
        csv_data = pd.read_csv(csvPath, low_memory=False, index_col=0)
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
        return csv_data

    def microphone(self):
        with sr.Microphone() as source:
            audio = self.recognizer.listen(source)

        # Google Web Speech API를 사용하여 음성 인식
        try:
            return self.recognizer.recognize_google(audio, language='ko-KR')
        except sr.UnknownValueError:
            print(f"오류 발생\n{traceback.format_exc()}")
            return "음성 인식 실패"
        except sr.RequestError as e:
            print(f"오류 발생\n{traceback.format_exc()}")
            return "음성 인식 실패"

    def speecher(self, text):
        try:
            # 임시 파일 생성 (delete=False로 설정)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_file_name = temp_file.name  # 파일 경로 저장
                # gTTS를 사용해 텍스트를 음성으로 변환
                tts = gTTS(text=text, lang='ko')
                tts.save(temp_file_name)  # 임시 파일에 저장

            # 음성 파일 재생
            playsound(temp_file_name)

        except Exception as e:
            print(f"오류가 발생했습니다: {e}")

        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_file_name):
                os.remove(temp_file_name)