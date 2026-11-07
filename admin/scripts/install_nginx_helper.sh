#!/usr/bin/env bash
# Domains 페이지용 root 헬퍼를 설치한다. 대시보드를 실행하는 계정을 인자로 준다.
#   sudo bash admin/scripts/install_nginx_helper.sh lab
# 헬퍼를 고친 뒤에도 다시 실행해야 적용된다. 지우려면 --uninstall.
set -euo pipefail

TARGET=/usr/local/sbin/knpu-nginx
SUDOERS=/etc/sudoers.d/knpu-nginx

if [ "$(id -u)" -ne 0 ]; then
  echo "sudo 로 실행해 주세요." >&2
  exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$SUDOERS" "$TARGET"
  echo "헬퍼와 sudo 권한을 지웠습니다."
  exit 0
fi

OWNER="${1:-}"
if ! [[ "$OWNER" =~ ^[a-z_][a-z0-9_-]*$ ]] || [ "$OWNER" = root ] || ! id "$OWNER" > /dev/null 2>&1; then
  echo "사용법: sudo bash $0 <대시보드를 실행하는 계정>" >&2
  exit 1
fi
SOURCE="$(cd "$(dirname "$0")/.." && pwd)/app/services/nginx_helper.py"

TEMP="$(mktemp)"
trap 'rm -f "$TEMP"' EXIT
echo "$OWNER ALL=(root) NOPASSWD: $TARGET" > "$TEMP"
visudo -cf "$TEMP" > /dev/null

install -o root -g root -m 0755 "$SOURCE" "$TARGET"
install -o root -g root -m 0440 "$TEMP" "$SUDOERS"
echo "설치했습니다. 기존 도메인에 보안 설정을 적용하려면: sudo $TARGET harden"
echo
echo "꼭 확인: 이전 방식의 sudo 권한이 남아 있으면 이 헬퍼로 줄어든 권한이 의미가 없습니다."
echo "  sudo -l -U $OWNER"
echo "위 목록에 $TARGET 외의 NOPASSWD 규칙(ALL, bash, tee, certbot 등)이 있으면 지워 주세요."
