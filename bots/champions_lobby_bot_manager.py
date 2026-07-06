from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque

try:
    from .champions_bot_runner import BotAccount
    from .champions_bot_runner import ChampionsApiClient
    from .champions_bot_runner import bot_account_for
    from .champions_bot_runner import login_or_register
    from .champions_native_bot import JsonlMetricsWriter
except ImportError:  # pragma: no cover - direct script execution on the VPS
    from champions_bot_runner import BotAccount
    from champions_bot_runner import ChampionsApiClient
    from champions_bot_runner import bot_account_for
    from champions_bot_runner import login_or_register
    from champions_native_bot import JsonlMetricsWriter


DEFAULT_LOBBY_BOT_NAMES = (
    "Rugal08",
    "Kyo_Vortex",
    "Iori33",
    "Orochi",
    "MestreKOF",
    "AshCrisonX",
    "Dona Maria",
    "Bozo",
    "Cipher",
    "Vítima",
    "Carrasco",
    "Zero",
)


@dataclass(frozen=True)
class LobbyBotProfile:
    index: int
    slot: int
    nick: str


@dataclass(frozen=True)
class LobbyBotConfig:
    base_url: str
    driver: str
    names: tuple[str, ...]
    active_count: int
    rotation_batch_size: int
    rotation_interval_seconds: float
    rotation_gap_seconds: float
    stagger_seconds: float
    heartbeat_seconds: float
    metrics_path: Path
    account_namespace: str
    slot_offset: int
    build_label: str
    once: bool
    max_heartbeats: int
    logout_on_exit: bool


@dataclass
class LobbyBotSession:
    profile: LobbyBotProfile
    token: str
    user_id: int
    username: str
    last_heartbeat_at: float = 0.0


def parse_names(raw_names: str) -> tuple[str, ...]:
    names = tuple(name.strip() for name in raw_names.split(",") if name.strip())
    if not names:
        raise ValueError("at least one lobby bot name is required")
    if len(set(names)) != len(names):
        raise ValueError("lobby bot names must be unique")
    return names


def make_profiles(names: tuple[str, ...], slot_offset: int) -> tuple[LobbyBotProfile, ...]:
    return tuple(
        LobbyBotProfile(index=index, slot=slot_offset + index + 1, nick=nick)
        for index, nick in enumerate(names)
    )


class LobbyBotManager:
    def __init__(
        self,
        config: LobbyBotConfig,
        api: ChampionsApiClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.api = api if api is not None else ChampionsApiClient(config.base_url)
        self.metrics = JsonlMetricsWriter(config.metrics_path)
        self.sleep = sleep
        self.profiles = make_profiles(config.names, config.slot_offset)
        self.active_profiles: Deque[LobbyBotProfile] = deque(self.profiles[: config.active_count])
        self.standby_profiles: Deque[LobbyBotProfile] = deque(self.profiles[config.active_count :])
        self.sessions: dict[str, LobbyBotSession] = {}
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def _account_for(self, profile: LobbyBotProfile) -> BotAccount:
        base_account = bot_account_for(profile.slot, namespace=self.config.account_namespace)
        return BotAccount(
            slot=base_account.slot,
            nick=profile.nick,
            email=base_account.email,
            password=base_account.password,
            hardware_id=base_account.hardware_id,
        )

    def login_profile(self, profile: LobbyBotProfile) -> LobbyBotSession:
        existing = self.sessions.get(profile.nick)
        if existing is not None:
            return existing

        account = self._account_for(profile)
        token, user = login_or_register(self.api, account)
        session = LobbyBotSession(
            profile=profile,
            token=token,
            user_id=int(user.get("id", 0) or 0),
            username=str(user.get("nick") or user.get("username") or account.nick),
        )
        self.sessions[profile.nick] = session
        self.metrics.write(
            "lobby_bot_login",
            nick=session.username,
            user_id=session.user_id,
            slot=profile.slot,
            active_count=len(self.sessions),
        )
        return session

    def logout_profile(self, profile: LobbyBotProfile) -> None:
        session = self.sessions.pop(profile.nick, None)
        if session is None:
            return
        try:
            self.api.request("POST", "api/auth/logout", token=session.token)
            ok = True
            error = ""
        except Exception as exc:
            ok = False
            error = str(exc)
        self.metrics.write(
            "lobby_bot_logout",
            nick=session.username,
            user_id=session.user_id,
            slot=profile.slot,
            ok=ok,
            error=error,
            active_count=len(self.sessions),
        )

    def touch_presence(self, session: LobbyBotSession) -> None:
        started = time.perf_counter()
        self.api.request(
            "GET",
            "api/presence",
            token=session.token,
            query={
                "driver": self.config.driver,
                "touch_lobby": 1,
                "build": self.config.build_label,
            },
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        session.last_heartbeat_at = time.monotonic()
        self.metrics.write(
            "lobby_bot_heartbeat",
            nick=session.username,
            user_id=session.user_id,
            slot=session.profile.slot,
            driver=self.config.driver,
            request_ms=elapsed_ms,
        )

    def start_initial_active(self) -> None:
        for profile in list(self.active_profiles):
            session = self.login_profile(profile)
            self.touch_presence(session)
            self._stagger()
        self.metrics.write(
            "lobby_rotation_state",
            active=[profile.nick for profile in self.active_profiles],
            standby=[profile.nick for profile in self.standby_profiles],
        )

    def heartbeat_active(self) -> None:
        for profile in list(self.active_profiles):
            if self._stop_requested:
                return
            session = self.login_profile(profile)
            self.touch_presence(session)

    def rotate_once(self) -> None:
        if not self.standby_profiles:
            return
        outgoing_count = min(self.config.rotation_batch_size, len(self.active_profiles), len(self.standby_profiles))
        outgoing = [self.active_profiles.popleft() for _ in range(outgoing_count)]
        incoming = [self.standby_profiles.popleft() for _ in range(outgoing_count)]

        self.metrics.write(
            "lobby_rotation_begin",
            outgoing=[profile.nick for profile in outgoing],
            incoming=[profile.nick for profile in incoming],
        )

        for profile in outgoing:
            if self._stop_requested:
                return
            self.logout_profile(profile)
            self._stagger()

        if self.config.rotation_gap_seconds > 0:
            self.sleep(self.config.rotation_gap_seconds)

        for profile in incoming:
            if self._stop_requested:
                return
            session = self.login_profile(profile)
            self.touch_presence(session)
            self.active_profiles.append(profile)
            self._stagger()

        for profile in outgoing:
            self.standby_profiles.append(profile)

        self.metrics.write(
            "lobby_rotation_complete",
            active=[profile.nick for profile in self.active_profiles],
            standby=[profile.nick for profile in self.standby_profiles],
        )

    def logout_all(self) -> None:
        for profile in list(self.active_profiles) + list(self.standby_profiles):
            self.logout_profile(profile)

    def run(self) -> None:
        self.start_initial_active()
        heartbeat_count = 0
        next_heartbeat_at = time.monotonic() + self.config.heartbeat_seconds
        next_rotation_at = time.monotonic() + self.config.rotation_interval_seconds

        try:
            while not self._stop_requested:
                now = time.monotonic()
                if now >= next_heartbeat_at:
                    self.heartbeat_active()
                    heartbeat_count += 1
                    next_heartbeat_at = now + self.config.heartbeat_seconds
                    if self.config.once:
                        return
                    if self.config.max_heartbeats > 0 and heartbeat_count >= self.config.max_heartbeats:
                        return

                if now >= next_rotation_at:
                    self.rotate_once()
                    next_rotation_at = time.monotonic() + self.config.rotation_interval_seconds
                    next_heartbeat_at = min(next_heartbeat_at, time.monotonic() + self.config.heartbeat_seconds)

                self.sleep(0.25)
        finally:
            if self.config.logout_on_exit:
                self.logout_all()

    def _stagger(self) -> None:
        if self.config.stagger_seconds > 0:
            self.sleep(self.config.stagger_seconds)


def parse_args(argv: list[str]) -> LobbyBotConfig:
    parser = argparse.ArgumentParser(description="ChampionsKOF lobby-only BOT rotation manager.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--driver", choices=("kof98", "kof2002", "sf2ce"), default="kof2002")
    parser.add_argument("--names", default=",".join(DEFAULT_LOBBY_BOT_NAMES))
    parser.add_argument("--active-count", type=int, default=8)
    parser.add_argument("--rotation-batch-size", type=int, default=4)
    parser.add_argument("--rotation-interval-seconds", type=float, default=6 * 60 * 60)
    parser.add_argument("--rotation-gap-seconds", type=float, default=5 * 60)
    parser.add_argument("--stagger-seconds", type=float, default=15.0)
    parser.add_argument("--heartbeat-seconds", type=float, default=10.0)
    parser.add_argument("--metrics-path", type=Path, required=True)
    parser.add_argument("--account-namespace", default="championskof-lobby")
    parser.add_argument("--slot-offset", type=int, default=100)
    parser.add_argument("--build-label", default="lobby-bot-v0")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-heartbeats", type=int, default=0)
    parser.add_argument("--logout-on-exit", action="store_true")
    args = parser.parse_args(argv)

    names = parse_names(str(args.names))
    active_count = max(1, min(len(names), int(args.active_count)))
    rotation_batch_size = max(1, min(active_count, int(args.rotation_batch_size)))
    standby_count = len(names) - active_count
    if standby_count > 0:
        rotation_batch_size = min(rotation_batch_size, standby_count)

    return LobbyBotConfig(
        base_url=str(args.base_url).strip(),
        driver=str(args.driver).strip().lower(),
        names=names,
        active_count=active_count,
        rotation_batch_size=rotation_batch_size,
        rotation_interval_seconds=max(1.0, float(args.rotation_interval_seconds)),
        rotation_gap_seconds=max(0.0, float(args.rotation_gap_seconds)),
        stagger_seconds=max(0.0, float(args.stagger_seconds)),
        heartbeat_seconds=max(1.0, float(args.heartbeat_seconds)),
        metrics_path=args.metrics_path,
        account_namespace=str(args.account_namespace).strip() or "championskof-lobby",
        slot_offset=max(0, int(args.slot_offset)),
        build_label=str(args.build_label).strip() or "lobby-bot-v0",
        once=bool(args.once),
        max_heartbeats=max(0, int(args.max_heartbeats)),
        logout_on_exit=bool(args.logout_on_exit),
    )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(list(argv or sys.argv[1:]))
    manager = LobbyBotManager(config)

    def handle_stop(signum: int, frame: Any) -> None:
        manager.request_stop()

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    try:
        manager.run()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"lobby_bot_manager_error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
