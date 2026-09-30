#!/usr/bin/env bash
# 관리자 템플릿/JS의 Tailwind 클래스를 정적 CSS로 빌드하고 URL 해시를 갱신한다.
set -euo pipefail
cd "$(dirname "$0")/.."

BIN=.tools/tailwindcss
if [ ! -x "$BIN" ]; then
  mkdir -p .tools
  ARCH=$(uname -m)
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  case "$ARCH" in x86_64) ARCH=x64;; aarch64|arm64) ARCH=arm64;; esac
  [ "$OS" = "darwin" ] && OS=macos
  curl -fsSL -o "$BIN" "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-$OS-$ARCH"
  chmod +x "$BIN"
fi

"$BIN" -c tailwind.config.js -i tailwind.input.css -o app/static/css/tailwind.css --minify
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path
import re

css = Path('app/static/css/tailwind.css')
template = Path('app/templates/base.html')
version = sha256(css.read_bytes()).hexdigest()[:8]
html = template.read_text()
updated, count = re.subn(r'(/static/css/tailwind\.css\?v=)[0-9a-f]+', rf'\g<1>{version}', html)
if count != 1:
    raise SystemExit('base.html Tailwind URL을 찾지 못했습니다.')
template.write_text(updated)
print(f'Tailwind CSS version: {version}')
PY
