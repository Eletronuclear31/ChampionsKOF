from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .champions_bot_runner import ApiError
from .champions_lobby_bot_manager import DEFAULT_LOBBY_BOT_NAMES
from .champions_lobby_bot_manager import LobbyBotConfig
from .champions_lobby_bot_manager import LobbyBotManager
from .champions_lobby_bot_manager import parse_args


class FakeLobbyApi:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None, str, dict | None]] = []
        self.users_by_nick: dict[str, dict] = {}
        self.next_user_id = 1000

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        token: str = "",
        query: dict | None = None,
    ) -> dict:
        self.requests.append((method, path, payload, token, query))
        if method == "POST" and path == "api/auth/login":
            nick = str(payload["login"])
            if nick not in self.users_by_nick:
                raise ApiError("credenciais_invalidas", 401)
            user = self.users_by_nick[nick]
            return {"token": f"token-{nick}", "user": user}
        if method == "POST" and path == "api/auth/register":
            nick = str(payload["nick"])
            user = {"id": self.next_user_id, "nick": nick}
            self.next_user_id += 1
            self.users_by_nick[nick] = user
            return {"token": f"token-{nick}", "user": user}
        if method == "GET" and path == "api/presence":
            return {"players": []}
        if method == "POST" and path == "api/auth/logout":
            return {"ok": True}
        raise AssertionError(f"unexpected request {method} {path}")


def make_config(metrics_path: Path) -> LobbyBotConfig:
    return LobbyBotConfig(
        base_url="http://127.0.0.1:8080/",
        driver="kof2002",
        names=DEFAULT_LOBBY_BOT_NAMES,
        active_count=8,
        rotation_batch_size=4,
        rotation_interval_seconds=6 * 60 * 60,
        rotation_gap_seconds=0.0,
        stagger_seconds=0.0,
        heartbeat_seconds=10.0,
        metrics_path=metrics_path,
        account_namespace="championskof-lobby",
        slot_offset=100,
        build_label="lobby-bot-v0",
        once=False,
        max_heartbeats=0,
        logout_on_exit=False,
    )


class LobbyBotManagerTests(unittest.TestCase):
    def test_default_names_match_requested_lobby_pool(self) -> None:
        self.assertEqual(
            DEFAULT_LOBBY_BOT_NAMES,
            (
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
            ),
        )

    def test_parse_args_uses_eight_active_and_four_standby_by_default(self) -> None:
        config = parse_args(
            [
                "--base-url",
                "http://127.0.0.1:8080/",
                "--metrics-path",
                "metrics.jsonl",
            ]
        )
        self.assertEqual(config.active_count, 8)
        self.assertEqual(config.rotation_batch_size, 4)
        self.assertEqual(len(config.names), 12)
        self.assertNotIn("Matador", config.names)

    def test_initial_active_bots_touch_only_lobby_presence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            api = FakeLobbyApi()
            manager = LobbyBotManager(make_config(Path(temp_dir) / "metrics.jsonl"), api=api, sleep=lambda seconds: None)  # type: ignore[arg-type]
            manager.start_initial_active()

            self.assertEqual(set(manager.sessions.keys()), set(DEFAULT_LOBBY_BOT_NAMES[:8]))
            requested_paths = [request[1] for request in api.requests]
            self.assertIn("api/presence", requested_paths)
            self.assertNotIn("api/rooms", requested_paths)
            self.assertTrue(all("relay" not in path for path in requested_paths))

    def test_rotation_swaps_four_active_bots_after_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_path = Path(temp_dir) / "metrics.jsonl"
            api = FakeLobbyApi()
            manager = LobbyBotManager(make_config(metrics_path), api=api, sleep=lambda seconds: None)  # type: ignore[arg-type]
            manager.start_initial_active()
            manager.rotate_once()

            self.assertEqual(
                [profile.nick for profile in manager.active_profiles],
                [
                    "MestreKOF",
                    "AshCrisonX",
                    "Dona Maria",
                    "Bozo",
                    "Cipher",
                    "Vítima",
                    "Carrasco",
                    "Zero",
                ],
            )
            self.assertEqual(
                [profile.nick for profile in manager.standby_profiles],
                ["Rugal08", "Kyo_Vortex", "Iori33", "Orochi"],
            )
            logout_count = sum(1 for request in api.requests if request[0:2] == ("POST", "api/auth/logout"))
            self.assertEqual(logout_count, 4)
            events = [json.loads(line)["event"] for line in metrics_path.read_text(encoding="utf-8").splitlines()]
            self.assertIn("lobby_rotation_begin", events)
            self.assertIn("lobby_rotation_complete", events)


if __name__ == "__main__":
    unittest.main()
