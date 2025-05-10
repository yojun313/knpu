import bcrypt

# 평문 비밀번호
password = "kingsman"

# 해시 생성 (salt 포함)
hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

# 결과는 바이트 형태 → 문자열로 저장하려면 decode()
hashed_str = hashed.decode("utf-8")
print("해시된 비밀번호:", hashed_str)
