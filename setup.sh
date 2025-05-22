#!/bin/bash

echo "🐍 Python 가상환경을 생성하고 필수 패키지를 설치합니다..."

# 가상환경 생성
python3 -m venv venv
if [ $? -ne 0 ]; then
  echo "❌ 가상환경 생성 실패. Python이 설치되어 있는지 확인하세요."
  exit 1
fi

# 가상환경 활성화
source venv/bin/activate
pip install --upgrade pip
echo "✅ 가상환경 활성화 완료"

# 패키지 목록 정의
packages=(
  rich
  aiohttp
  bs4
  urllib3
  requests
  user_agent
  chardet
  pymongo
  dotenv
  google-api-python-client
  pandas
  google_auth_oauthlib
  kiwipiepy
  lxml
  uvicorn
  fastapi
  pymysql
  PyJWT
  matplotlib
  seaborn
  psutil
  python-multipart
  PyQT5
  wordcloud
  googletrans
  openai
  bcrypt
  PyQtWebEngine
  websockets
  pyarrow
)

echo "📦 패키지 설치 중..."
for pkg in "${packages[@]}"; do
  echo "➡️  $pkg 설치 중..."
  pip install "$pkg"
done

echo "🎉 모든 패키지가 성공적으로 설치되었습니다!"
