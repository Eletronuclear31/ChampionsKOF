# ChampionsKOF Lura Linux VPS

Target server profile:

- AMD Ryzen 9 7950X
- 3 vCore
- 8 GB RAM
- 60 GB NVMe
- Linux
- Sao Paulo
- 1 Gbps

This host is intended to run:

- matchmaking API;
- realtime UDP relay;
- one external BOT client for KOF2002 labs;
- avatar storage with an initial 5 GB operational budget;
- MySQL database.

## Safety boundary

BOT services must stay external to the netplay core. They may use the public HTTP API, launch a normal match client and send inputs through the same public player path. They must not read rollback snapshots, save states, jitter buffers, UDP internals or private input queues.

## First boot

Run as root:

```bash
bash /tmp/bootstrap_lura_championskof.sh
```

Recommended OS in the panel:

```text
Ubuntu Server 24.04 LTS Minimal
```

Use `America/Sao_Paulo` as timezone.

Then copy only the deploy/backend files to:

```text
/opt/championskof/current
```

The bootstrap creates:

```text
/opt/championskof/current
/opt/championskof/shared/data
/opt/championskof/shared/avatars
/opt/championskof/shared/logs
/opt/championskof/shared/bots
/opt/championskof/backups
```

## Environment

Copy and edit:

```bash
cp /opt/championskof/current/deploy/lura/championskof.env.example /etc/championskof/championskof.env
chmod 600 /etc/championskof/championskof.env
```

Important values:

```text
YZKOF_DATABASE_URL=mysql+pymysql://championskof:REPLACE_DB_PASSWORD@127.0.0.1:3306/championskof?charset=utf8mb4
YZKOF_PUBLIC_BASE_URLS=http://SERVER_IP:8080/
YZKOF_PUBLIC_RELAY_HOST=SERVER_IP
YZKOF_PUBLIC_RELAY_PORT=7000
YZKOF_ADMIN_TOKEN=replace-with-secret
YZKOF_FIELD_TELEMETRY_TOKEN=replace-with-secret
```

For a fresh MySQL setup:

```bash
apt-get install -y mysql-server
systemctl enable --now mysql
mysql
```

Inside MySQL:

```sql
CREATE DATABASE championskof CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'championskof'@'127.0.0.1' IDENTIFIED BY 'REPLACE_DB_PASSWORD';
GRANT ALL PRIVILEGES ON championskof.* TO 'championskof'@'127.0.0.1';
FLUSH PRIVILEGES;
```

## Services

Install service files:

```bash
cp /opt/championskof/current/deploy/lura/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable championskof-api.service
systemctl enable championskof-realtime-relay.service
systemctl start championskof-api.service
systemctl start championskof-realtime-relay.service
```

BOT service installation is intentionally separate. Install it only after the match client runtime is ready on Linux:

```bash
cp /opt/championskof/current/deploy/lura/systemd/championskof-bot-kof2002.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable championskof-bot-kof2002.service
systemctl start championskof-bot-kof2002.service
```

## Health checks

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/api/bootstrap
systemctl status championskof-api --no-pager
systemctl status championskof-realtime-relay --no-pager
journalctl -u championskof-api -n 80 --no-pager
journalctl -u championskof-realtime-relay -n 80 --no-pager
```

## Capacity target

Initial target:

- 1 KOF2002 BOT v0/v1/v2 canary;
- API and relay on the same VPS;
- 5 GB avatar budget;
- long relay/P2P labs with telemetry enabled.

Scale only after gates stay clean:

- desync = 0;
- audio underrun = 0;
- frame p95/p99 without regression;
- update p95 without regression;
- no BOT-caused stall.
