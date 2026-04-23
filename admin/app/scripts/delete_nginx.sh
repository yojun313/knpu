#!/bin/bash
# 파일 경로: /home/lab/bash/delete_nginx.sh

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo "사용법: $0 [도메인]"
    exit 1
fi

echo "[1/3] Certbot 인증서 삭제 중: $DOMAIN"
sudo certbot delete --cert-name "$DOMAIN" --non-interactive || echo "⚠️ 인증서가 없거나 이미 삭제되었습니다."

echo "[2/3] Nginx 설정 파일 제거 중..."
sudo rm -f "/etc/nginx/sites-enabled/$DOMAIN"
sudo rm -f "/etc/nginx/sites-available/$DOMAIN"

echo "[3/3] Nginx 설정 검사 및 Reload..."
sudo nginx -t && sudo systemctl reload nginx

echo "$DOMAIN 삭제 완료!"