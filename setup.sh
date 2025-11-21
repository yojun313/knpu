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
echo "가상환경 활성화 완료"

pip install -r requirements.txt
echo "필수 패키지 설치 완료"
