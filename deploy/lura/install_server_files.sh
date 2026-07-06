#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHAMPIONS_ROOT="${CHAMPIONS_ROOT:-/opt/championskof}"
CHAMPIONS_USER="${CHAMPIONS_USER:-championskof}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on the VPS." >&2
  exit 1
fi

mkdir -p "$CHAMPIONS_ROOT/current"

rsync -a --delete \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude 'data_*' \
  --exclude 'logs' \
  --exclude '*.log' \
  --exclude '__pycache__' \
  "$PROJECT_ROOT/online_server/" "$CHAMPIONS_ROOT/current/online_server/"

rsync -a --delete \
  --exclude '__pycache__' \
  "$PROJECT_ROOT/bots/" "$CHAMPIONS_ROOT/current/bots/"

rsync -a --delete \
  "$PROJECT_ROOT/deploy/" "$CHAMPIONS_ROOT/current/deploy/"

chown -R "$CHAMPIONS_USER:$CHAMPIONS_USER" "$CHAMPIONS_ROOT/current"

cd "$CHAMPIONS_ROOT/current/online_server"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m py_compile server.py realtime_relay.py ../bots/champions_bot_runner.py

echo "Install OK."
