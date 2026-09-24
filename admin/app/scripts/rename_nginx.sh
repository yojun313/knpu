#!/bin/bash
# 이미 존재하는 도메인의 이름만 바꾼다. 경로/포트(location 블록)는 그대로 유지된다.
# 새 설정 파일 내용은 stdin으로 받는다 (NginxService.build_renamed_config가 생성).
#
# 실패하면 원래 설정으로 되돌린다.

set -e

OLD_DOMAIN=$1
NEW_DOMAIN=$2
EMAIL=$3

if [ -z "$OLD_DOMAIN" ] || [ -z "$NEW_DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "사용법: $0 [기존도메인] [새도메인] [이메일]  (새 설정 내용은 stdin)"
    exit 1
fi

AVAILABLE="/etc/nginx/sites-available"
ENABLED="/etc/nginx/sites-enabled"
OLD_CONF="$AVAILABLE/$OLD_DOMAIN"
NEW_CONF="$AVAILABLE/$NEW_DOMAIN"

if [ ! -f "$OLD_CONF" ]; then
    echo "기존 도메인 설정을 찾을 수 없습니다: $OLD_CONF"
    exit 1
fi

if [ -e "$NEW_CONF" ]; then
    echo "이미 존재하는 도메인입니다: $NEW_DOMAIN"
    exit 1
fi

BACKUP=$(mktemp /tmp/nginx-rename-XXXXXX.bak)
cp "$OLD_CONF" "$BACKUP"

restore() {
    echo "!! 실패했습니다. 원래 설정으로 되돌립니다: $OLD_DOMAIN"
    rm -f "$ENABLED/$NEW_DOMAIN" "$NEW_CONF"
    cp "$BACKUP" "$OLD_CONF"
    ln -sf "$OLD_CONF" "$ENABLED/$OLD_DOMAIN"
    nginx -t && systemctl reload nginx
    rm -f "$BACKUP"
    echo "되돌리기 완료."
}
trap restore ERR

echo "[1/5] 새 설정 작성 중: $OLD_DOMAIN -> $NEW_DOMAIN (경로/포트 유지)"
tee "$NEW_CONF" > /dev/null

echo "[2/5] 심볼릭 링크 교체 및 기존 설정 제거..."
ln -sf "$NEW_CONF" "$ENABLED/$NEW_DOMAIN"
rm -f "$ENABLED/$OLD_DOMAIN"
rm -f "$OLD_CONF"

echo "[3/5] Nginx 설정 테스트 및 재시작..."
nginx -t
systemctl reload nginx

echo "[4/5] Certbot SSL 인증서 발급 중: $NEW_DOMAIN (대기 시간이 발생할 수 있습니다)..."
echo "      (새 도메인의 DNS A 레코드가 이 서버를 가리키고 있어야 합니다)"
certbot --nginx -d "$NEW_DOMAIN" --non-interactive --agree-tos -m "$EMAIL"

# 여기까지 왔으면 새 도메인은 정상 동작한다. 이후 실패는 되돌리지 않는다.
trap - ERR

echo "[5/5] 기존 도메인 인증서 정리: $OLD_DOMAIN"
certbot delete --cert-name "$OLD_DOMAIN" --non-interactive || \
    echo "      (기존 인증서가 없거나 이미 삭제되었습니다 - 무시합니다)"

rm -f "$BACKUP"
echo "도메인 이름 변경이 완료되었습니다. https://$NEW_DOMAIN"
