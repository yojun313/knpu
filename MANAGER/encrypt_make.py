from cryptography.fernet import Fernet

# 암호화 키 로드
def load_key():
    with open("source/env.key", "rb") as key_file:
        return key_file.read()

# .env 파일 암호화
def encrypt_env_file(env_file_path):
    key = load_key()
    fernet = Fernet(key)

    with open(env_file_path, "rb") as file:
        original_data = file.read()

    encrypted_data = fernet.encrypt(original_data)

    # 암호화된 데이터를 새로운 파일에 저장
    with open("source/encrypted_env", "wb") as encrypted_file:
        encrypted_file.write(encrypted_data)

# .env 파일 암호화
encrypt_env_file("lock.env")
print(".env 파일이 암호화되어 'encrypted_env_file'로 저장되었습니다.")
