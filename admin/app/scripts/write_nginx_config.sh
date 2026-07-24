#!/bin/bash
# 파일 경로: /home/lab/bash/write_nginx_config.sh
# 이미 존재하는 도메인의 설정 파일 전체 내용을 stdin으로 받아 덮어쓰고 reload 한다.
# (certbot을 다시 호출하지 않는 "경로 추가/수정/삭제" 전용 스크립트)

set -e

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo "사용법: $0 [도메인]  (설정 파일 내용은 stdin으로 전달)"
    exit 1
fi

CONFIG_PATH="/etc/nginx/sites-available/$DOMAIN"

echo "[1/3] Nginx 설정 갱신 중: $DOMAIN"
sudo tee "$CONFIG_PATH" > /dev/null

echo "[2/3] Nginx 설정 테스트..."
sudo nginx -t

echo "[3/3] Nginx 재시작..."
sudo systemctl reload nginx

echo "설정이 갱신되었습니다: $DOMAIN"
