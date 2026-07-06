from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .champions_bot_runner import ChampionsApiClient
    from .champions_bot_runner import BotAccount
    from .champions_bot_runner import bot_account_for
    from .champions_bot_runner import ensure_bot_room
    from .champions_bot_runner import login_or_register
    from .champions_bot_runner import preferred_relay
    from .champions_bot_runner import room_name_for
    from .champions_bot_runner import room_seat_for_user
    from .champions_relay_bot import RelayBotClient
    from .champions_relay_bot import RelayBotConfig
except ImportError:  # pragma: no cover - direct script execution on the VPS
    from champions_bot_runner import ChampionsApiClient
    from champions_bot_runner import BotAccount
    from champions_bot_runner import bot_account_for
    from champions_bot_runner import ensure_bot_room
    from champions_bot_runner import login_or_register
    from champions_bot_runner import preferred_relay
    from champions_bot_runner import room_name_for
    from champions_bot_runner import room_seat_for_user
    from champions_relay_bot import RelayBotClient
    from champions_relay_bot import RelayBotConfig


SUPPORTED_PROFILES = ("neutral", "beginner", "defensive", "aggressive", "balanced", "lab-stress")


@dataclass(frozen=True)
class NativeBotConfig:
    base_url: str
    driver: str
    slot: int
    room_prefix: str
    room_name: str
    nick: str
    target_score: int
    profile: str
    level: int
    heartbeat_seconds: float
    status_signal_seconds: float
    metrics_path: Path
    enable_relay: bool
    app_version: str
    app_build: int
    neutral_input: int
    relay_frame_hz: float
    once: bool
    max_heartbeats: int


@dataclass(frozen=True)
class NativeBotSession:
    token: str
    user_id: int
    username: str
    room_id: str
    room_name: str
    seat: int
    relay_host: str
    relay_port: int


class JsonlMetricsWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        payload = {
            "ts_ms": int(time.time() * 1000),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            stream.write("\n")


class NativeBotClient:
    def __init__(self, config: NativeBotConfig, api: ChampionsApiClient | None = None) -> None:
        self.config = config
        self.api = api if api is not None else ChampionsApiClient(config.base_url)
        self.metrics = JsonlMetricsWriter(config.metrics_path)
        self.session: NativeBotSession | None = None
        self.relay: RelayBotClient | None = None
        self._last_status_signal_at = 0.0
        self._last_relay_metric_at = 0.0

    def ensure_session(self) -> NativeBotSession:
        if self.session is not None:
            return self.session

        base_account = bot_account_for(self.config.slot)
        account = BotAccount(
            slot=base_account.slot,
            nick=self.config.nick or base_account.nick,
            email=base_account.email,
            password=base_account.password,
            hardware_id=base_account.hardware_id,
        )
        token, user = login_or_register(self.api, account)
        user_id = int(user.get("id", 0) or 0)
        username = str(user.get("nick") or user.get("username") or account.nick)
        room = ensure_bot_room(
            self.api,
            token,
            user_id,
            self.config.driver,
            self.config.room_name,
            self.config.target_score,
        )
        relay_payload = room
        try:
            relay_payload = {**room, **self.api.request("GET", "api/bootstrap")}
        except Exception:
            relay_payload = room
        relay_host, relay_port = preferred_relay(relay_payload)
        session = NativeBotSession(
            token=token,
            user_id=user_id,
            username=username,
            room_id=str(room["id"]),
            room_name=str(room.get("name") or self.config.room_name),
            seat=room_seat_for_user(room, user_id, fallback=1),
            relay_host=relay_host,
            relay_port=relay_port,
        )
        self.session = session
        self.metrics.write(
            "bot_session_ready",
            driver=self.config.driver,
            profile=self.config.profile,
            level=self.config.level,
            room_id=session.room_id,
            room_name=session.room_name,
            seat=session.seat,
            user_id=session.user_id,
            username=session.username,
            relay=f"{session.relay_host}:{session.relay_port}",
        )
        return session

    def ensure_relay(self) -> RelayBotClient | None:
        if not self.config.enable_relay:
            return None
        if self.relay is not None:
            return self.relay
        session = self.ensure_session()
        config = RelayBotConfig(
            relay_host=session.relay_host,
            relay_port=session.relay_port,
            room_id=session.room_id,
            token=session.token,
            seat=session.seat,
            app_version=self.config.app_version,
            app_build=self.config.app_build,
            netplay_protocol=self.config.app_build,
            neutral_input=self.config.neutral_input,
            input_profile=self.config.profile,
            frame_hz=self.config.relay_frame_hz,
        )
        self.relay = RelayBotClient(config)
        self.metrics.write(
            "bot_relay_client_ready",
            room_id=session.room_id,
            seat=session.seat,
            relay=f"{session.relay_host}:{session.relay_port}",
            app_version=self.config.app_version,
            app_build=self.config.app_build,
            neutral_input=self.config.neutral_input,
            input_profile=self.config.profile,
        )
        return self.relay

    def heartbeat(self) -> dict[str, Any]:
        session = self.ensure_session()
        started = time.perf_counter()
        room = self.api.request("GET", f"api/rooms/{session.room_id}", token=session.token)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        current_players = int(room.get("current_players", 0) or 0)
        relay_players = int(room.get("relay_player_count", 0) or 0)
        self.metrics.write(
            "bot_heartbeat",
            driver=self.config.driver,
            profile=self.config.profile,
            level=self.config.level,
            room_id=session.room_id,
            seat=session.seat,
            user_id=session.user_id,
            request_ms=elapsed_ms,
            current_players=current_players,
            relay_player_count=relay_players,
            native_v0=True,
        )
        self._touch_lobby_presence(session)
        self._post_status_signal_if_due(session, current_players, relay_players)
        return room

    def _touch_lobby_presence(self, session: NativeBotSession) -> None:
        try:
            self.api.request(
                "GET",
                "api/presence",
                token=session.token,
                query={
                    "driver": self.config.driver,
                    "touch_lobby": 1,
                    "build": "native-bot-v0",
                },
            )
        except Exception as exc:
            self.metrics.write("bot_presence_touch_failed", room_id=session.room_id, error=str(exc))

    def _post_status_signal_if_due(self, session: NativeBotSession, current_players: int, relay_players: int) -> None:
        if self.config.status_signal_seconds <= 0:
            return
        now = time.monotonic()
        if (now - self._last_status_signal_at) < self.config.status_signal_seconds:
            return
        self._last_status_signal_at = now
        payload = {
            "bot": True,
            "native": True,
            "phase": "v0",
            "driver": self.config.driver,
            "profile": self.config.profile,
            "level": self.config.level,
            "seat": session.seat,
            "current_players": current_players,
            "relay_player_count": relay_players,
        }
        self.api.request("POST", f"api/rooms/{session.room_id}/signals", {"kind": "bot_status", "payload": payload}, token=session.token)
        self.metrics.write("bot_status_signal", room_id=session.room_id, user_id=session.user_id)

    def run(self) -> None:
        heartbeat_count = 0
        self.ensure_session()
        self.ensure_relay()
        last_heartbeat_at = 0.0
        while True:
            now = time.monotonic()
            relay = self.ensure_relay()
            if relay is not None:
                relay.pump(now)
                self._write_relay_metrics_if_due(relay, now)
            if (now - last_heartbeat_at) >= self.config.heartbeat_seconds:
                self.heartbeat()
                heartbeat_count += 1
                last_heartbeat_at = now
            if self.config.once:
                return
            if self.config.max_heartbeats > 0 and heartbeat_count >= self.config.max_heartbeats:
                return
            time.sleep(0.01 if self.config.enable_relay else max(1.0, self.config.heartbeat_seconds))

    def _write_relay_metrics_if_due(self, relay: RelayBotClient, now: float) -> None:
        if (now - self._last_relay_metric_at) < 5.0:
            return
        self._last_relay_metric_at = now
        self.metrics.write(
            "bot_relay_metrics",
            room_id=relay.config.room_id,
            ready=relay.ready,
            bootstrap_complete=relay.bootstrap_complete,
            room_epoch=relay.room_epoch,
            current_frame=relay.current_frame,
            newest_remote_frame=relay.newest_remote_frame,
            player_count=relay.player_count,
            spectator_count=relay.spectator_count,
            peer_seat=relay.peer_seat,
            peer_username=relay.peer_username,
            latest_live_frame=relay.latest_live_frame,
            hello_sent=relay.stats.hello_sent,
            hello_ack_received=relay.stats.hello_ack_received,
            ping_sent=relay.stats.ping_sent,
            ping_received=relay.stats.ping_received,
            pong_sent=relay.stats.pong_sent,
            pong_received=relay.stats.pong_received,
            frames_sent=relay.stats.frames_sent,
            frames_received=relay.stats.frames_received,
            bootstrap_ready_sent=relay.stats.bootstrap_ready_sent,
            bootstrap_ready_received=relay.stats.bootstrap_ready_received,
            bootstrap_go_received=relay.stats.bootstrap_go_received,
            errors_received=relay.stats.errors_received,
            non_json_datagrams_ignored=relay.stats.non_json_datagrams_ignored,
            last_error=relay.last_error,
        )


def parse_args(argv: list[str]) -> NativeBotConfig:
    parser = argparse.ArgumentParser(description="Native lightweight ChampionsKOF BOT client.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--driver", choices=("kof98", "kof2002", "sf2ce"), default="kof2002")
    parser.add_argument("--slot", type=int, default=1)
    parser.add_argument("--room-prefix", default="BOT")
    parser.add_argument("--room-name", default="")
    parser.add_argument("--nick", default="")
    parser.add_argument("--target-score", type=int, default=0)
    parser.add_argument("--profile", choices=SUPPORTED_PROFILES, default="neutral")
    parser.add_argument("--level", type=int, default=0)
    parser.add_argument("--heartbeat-seconds", type=float, default=10.0)
    parser.add_argument("--status-signal-seconds", type=float, default=60.0)
    parser.add_argument("--metrics-path", type=Path, required=True)
    parser.add_argument("--enable-relay", action="store_true")
    parser.add_argument("--app-version", default="1.0.18")
    parser.add_argument("--app-build", type=int, default=215)
    parser.add_argument("--neutral-input", type=int, default=0)
    parser.add_argument("--relay-frame-hz", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-heartbeats", type=int, default=0)
    args = parser.parse_args(argv)

    driver = str(args.driver).strip().lower()
    return NativeBotConfig(
        base_url=str(args.base_url).strip(),
        driver=driver,
        slot=max(1, int(args.slot)),
        room_prefix=str(args.room_prefix),
        room_name=room_name_for(driver, int(args.slot), str(args.room_prefix), str(args.room_name)),
        nick=str(args.nick).strip(),
        target_score=max(0, min(99, int(args.target_score))),
        profile=str(args.profile),
        level=max(0, min(10, int(args.level))),
        heartbeat_seconds=max(1.0, float(args.heartbeat_seconds)),
        status_signal_seconds=max(0.0, float(args.status_signal_seconds)),
        metrics_path=args.metrics_path,
        enable_relay=bool(args.enable_relay),
        app_version=str(args.app_version).strip() or "1.0.18",
        app_build=max(0, int(args.app_build)),
        neutral_input=max(0, int(args.neutral_input)),
        relay_frame_hz=max(1.0, float(args.relay_frame_hz)),
        once=bool(args.once),
        max_heartbeats=max(0, int(args.max_heartbeats)),
    )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(list(argv or sys.argv[1:]))
    try:
        NativeBotClient(config).run()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"native_bot_error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
