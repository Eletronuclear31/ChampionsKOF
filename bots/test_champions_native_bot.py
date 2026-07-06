from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .champions_native_bot import NativeBotClient
from .champions_native_bot import NativeBotConfig
from .champions_native_bot import parse_args


class FakeNativeApi:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None, str]] = []
        self.user = {"id": 42, "nick": "CKBot01"}
        self.room = {
            "id": "roombot01",
            "name": "BOT KOF2002 01",
            "driver": "kof2002",
            "current_players": 1,
            "relay_player_count": 0,
            "members": [{"user_id": 42, "seat": 1}],
            "primary_relay": {"host": "127.0.0.1", "port": 7000},
        }

    def request(self, method: str, path: str, payload: dict | None = None, token: str = "", query: dict | None = None) -> dict:
        self.requests.append((method, path, payload, token))
        if method == "POST" and path == "api/auth/login":
            return {"token": "token", "user": self.user}
        if method == "GET" and path == "api/rooms":
            return {"rooms": [self.room]}
        if method == "GET" and path == "api/rooms/roombot01":
            return self.room
        if method == "GET" and path == "api/presence":
            return {"players": [self.user]}
        if method == "POST" and path == "api/rooms/roombot01/signals":
            return {"seq": 1, "kind": payload["kind"], "payload": payload["payload"]}
        raise AssertionError(f"unexpected request {method} {path}")


def make_config(metrics_path: Path, once: bool = True, status_signal_seconds: float = 0.0) -> NativeBotConfig:
    return NativeBotConfig(
        base_url="http://127.0.0.1:8080/",
        driver="kof2002",
        slot=1,
        room_prefix="BOT",
        room_name="BOT KOF2002 01",
        nick="",
        target_score=0,
        profile="neutral",
        level=0,
        heartbeat_seconds=1.0,
        status_signal_seconds=status_signal_seconds,
        metrics_path=metrics_path,
        enable_relay=False,
        app_version="1.0.18",
        app_build=215,
        neutral_input=0,
        relay_frame_hz=60.0,
        once=once,
        max_heartbeats=0,
    )


class NativeBotTests(unittest.TestCase):
    def test_parse_args_defaults_room_name(self) -> None:
        config = parse_args(
            [
                "--base-url",
                "http://127.0.0.1:8080/",
                "--driver",
                "kof2002",
                "--slot",
                "2",
                "--metrics-path",
                "metrics.jsonl",
            ]
        )
        self.assertEqual(config.room_name, "BOT KOF2002 02")
        self.assertEqual(config.profile, "neutral")

    def test_parse_args_can_use_public_lobby_room_name(self) -> None:
        config = parse_args(
            [
                "--base-url",
                "http://127.0.0.1:8080/",
                "--driver",
                "kof2002",
                "--slot",
                "1",
                "--room-prefix",
                "PUBLIC",
                "--metrics-path",
                "metrics.jsonl",
            ]
        )
        self.assertEqual(config.room_name, "KOF 2002 Room No.1")

    def test_parse_args_accepts_custom_nick(self) -> None:
        config = parse_args(
            [
                "--base-url",
                "http://127.0.0.1:8080/",
                "--driver",
                "kof2002",
                "--metrics-path",
                "metrics.jsonl",
                "--nick",
                "Matador",
            ]
        )
        self.assertEqual(config.nick, "Matador")

    def test_parse_args_accepts_relay_options(self) -> None:
        config = parse_args(
            [
                "--base-url",
                "http://127.0.0.1:8080/",
                "--driver",
                "kof2002",
                "--metrics-path",
                "metrics.jsonl",
                "--enable-relay",
                "--app-build",
                "215",
                "--neutral-input",
                "4",
            ]
        )
        self.assertTrue(config.enable_relay)
        self.assertEqual(config.app_build, 215)
        self.assertEqual(config.neutral_input, 4)

    def test_once_run_creates_session_and_heartbeat_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_path = Path(temp_dir) / "native-bot.jsonl"
            api = FakeNativeApi()
            bot = NativeBotClient(make_config(metrics_path), api=api)  # type: ignore[arg-type]
            bot.run()
            events = [json.loads(line)["event"] for line in metrics_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events, ["bot_session_ready", "bot_heartbeat"])
            self.assertIn(("GET", "api/rooms/roombot01", None, "token"), api.requests)
            self.assertTrue(any(request[0:2] == ("GET", "api/presence") for request in api.requests))

    def test_status_signal_is_optional_public_room_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_path = Path(temp_dir) / "native-bot.jsonl"
            api = FakeNativeApi()
            bot = NativeBotClient(make_config(metrics_path, status_signal_seconds=1.0), api=api)  # type: ignore[arg-type]
            bot.run()
            self.assertTrue(any(request[0:2] == ("POST", "api/rooms/roombot01/signals") for request in api.requests))
            metric_events = [json.loads(line)["event"] for line in metrics_path.read_text(encoding="utf-8").splitlines()]
            self.assertIn("bot_status_signal", metric_events)


if __name__ == "__main__":
    unittest.main()
