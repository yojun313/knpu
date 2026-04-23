#!/bin/bash
# 파일 경로: /home/lab/bash/view_nginx.sh

ENABLED_PATH="/etc/nginx/sites-enabled"

echo "현재 활성화된 Nginx 도메인 목록"
echo "-------------------------------------------------------------------------------"
printf "%-30s | %-10s | %-20s\n" "Domain (server_name)" "Port" "Config File"
echo "-------------------------------------------------------------------------------"

for file in $ENABLED_PATH/*; do
    if [ -f "$file" ]; then
        DOMAIN=$(grep -E '^\s*server_name' "$file" | awk '{print $2}' | sed 's/;//' | head -n 1)
        PORT=$(grep -E '^\s*proxy_pass' "$file" | grep -oE '[0-9]+' | head -n 1)
        
        if [ -z "$DOMAIN" ]; then DOMAIN="N/A"; fi
        if [ -z "$PORT" ]; then PORT="N/A"; fi
        
        FILENAME=$(basename "$file")
        printf "%-30s | %-10s | %-20s\n" "$DOMAIN" "$PORT" "$FILENAME"
    fi
done
echo "-------------------------------------------------------------------------------"