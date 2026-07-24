#!/bin/bash
# 파일 경로: /home/lab/bash/add_nginx.sh

set -e

# 인자 확인
DOMAIN=$1
EMAIL=$2
PORT=$3
ROUTE_PATH=${4:-/}

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ] || [ -z "$PORT" ]; then
    echo "사용법: $0 [도메인] [이메일] [포트] [경로(선택, 기본 /)]"
    exit 1
fi

echo "[1/4] Nginx 설정 작성 중: $DOMAIN$ROUTE_PATH -> localhost:$PORT"
CONFIG_PATH="/etc/nginx/sites-available/$DOMAIN"

if [ "$ROUTE_PATH" = "/" ]; then
    LOCATION_BLOCK=$(cat <<EOF
    location / {
        proxy_pass http://localhost:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
EOF
)
else
    ROUTE_PATH="/${ROUTE_PATH#/}"
    ROUTE_PATH="${ROUTE_PATH%/}"
    LOCATION_BLOCK=$(cat <<EOF
    location $ROUTE_PATH/ {
        proxy_pass http://localhost:$PORT/;
        proxy_redirect / $ROUTE_PATH/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
EOF
)
fi

sudo tee $CONFIG_PATH > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

$LOCATION_BLOCK
}
EOF

echo "[2/4] Nginx 설정 활성화 및 테스트..."
sudo ln -sf $CONFIG_PATH /etc/nginx/sites-enabled/
sudo nginx -t

echo "[3/4] Nginx 재시작..."
sudo systemctl reload nginx

echo "[4/4] Certbot SSL 인증서 발급 중 (대기 시간이 발생할 수 있습니다)..."
# --non-interactive 옵션으로 입력을 기다리지 않게 함
sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL

echo "모든 작업이 완료되었습니다. https://$DOMAIN"