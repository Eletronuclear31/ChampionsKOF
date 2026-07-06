#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8080}"

echo "== HTTP health =="
curl -fsS "$BASE_URL/health"
echo

echo "== Bootstrap =="
curl -fsS "$BASE_URL/api/bootstrap" | python3 -m json.tool

echo "== Services =="
systemctl is-active championskof-api.service
systemctl is-active championskof-realtime-relay.service

echo "== Disk =="
df -h /opt/championskof || true
du -sh /opt/championskof/shared/avatars 2>/dev/null || true
du -sh /opt/championskof/shared/data 2>/dev/null || true

echo "== Memory =="
free -h
