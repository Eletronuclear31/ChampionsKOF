#!/usr/bin/env bash
set -euo pipefail

CHAMPIONS_USER="${CHAMPIONS_USER:-championskof}"
CHAMPIONS_ROOT="${CHAMPIONS_ROOT:-/opt/championskof}"
ENV_DIR="${ENV_DIR:-/etc/championskof}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  jq \
  logrotate \
  python3 \
  python3-venv \
  python3-pip \
  rsync \
  ufw \
  unzip

if ! id "$CHAMPIONS_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$CHAMPIONS_ROOT" --shell /usr/sbin/nologin "$CHAMPIONS_USER"
fi

install -d -o "$CHAMPIONS_USER" -g "$CHAMPIONS_USER" "$CHAMPIONS_ROOT"
install -d -o "$CHAMPIONS_USER" -g "$CHAMPIONS_USER" "$CHAMPIONS_ROOT/current"
install -d -o "$CHAMPIONS_USER" -g "$CHAMPIONS_USER" "$CHAMPIONS_ROOT/shared/data"
install -d -o "$CHAMPIONS_USER" -g "$CHAMPIONS_USER" "$CHAMPIONS_ROOT/shared/avatars"
install -d -o "$CHAMPIONS_USER" -g "$CHAMPIONS_USER" "$CHAMPIONS_ROOT/shared/logs"
install -d -o "$CHAMPIONS_USER" -g "$CHAMPIONS_USER" "$CHAMPIONS_ROOT/shared/bots"
install -d -o "$CHAMPIONS_USER" -g "$CHAMPIONS_USER" "$CHAMPIONS_ROOT/backups"
install -d -m 0750 -o root -g root "$ENV_DIR"

cat >/etc/logrotate.d/championskof <<'EOF'
/opt/championskof/shared/logs/*.log
/opt/championskof/shared/data/*.jsonl
/opt/championskof/shared/data/**/*.jsonl {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
EOF

ufw allow OpenSSH
ufw allow 8080/tcp
ufw allow 7000/udp
ufw --force enable

echo "Bootstrap OK."
echo "Next: copy project to $CHAMPIONS_ROOT/current and configure $ENV_DIR/championskof.env."
