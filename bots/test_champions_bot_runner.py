from __future__ import annotations

import os
import unittest
from pathlib import Path

from .champions_bot_runner import BotConfig
from .champions_bot_runner import BotSession
from .champions_bot_runner import bot_account_for
from .champions_bot_runner import bot_environment
from .champions_bot_runner import ensure_bot_room
from .champions_bot_runner import launch_arguments
from .champions_bot_runner import preferred_relay
from .champions_bot_runner import room_name_for


class FakeApi:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None, str]] = []
        self.rooms: dict[str, dict] = {}

    def request(self, method: str, path: str, payload: dict | None = None, token: str = "", query: dict | None = None) -> dict:
        self.requests.append((method, path, payload, token))
        if method == "GET" and path == "api/rooms":
            return {"rooms": list(self.rooms.values())}
        if method == "GET" and path.startswith("api/rooms/"):
            room_id = path.split("/")[-1]
            return self.rooms[room_id]
        if method == "POST" and path == "api/rooms":
            room = {
                "id": "roombot01",
                "name": payload["name"],
                "driver": payload["driver"],
                "members": [{"user_id": 42, "seat": payload["seat"]}],
                "primary_relay": {"host": "127.0.0.1", "port": 7000},
            }
            self.rooms[room["id"]] = room
            return room
        if method == "POST" and path.endswith("/join"):
            room_id = path.split("/")[-2]
            self.rooms[room_id].setdefault("members", []).append({"user_id": 42, "seat": payload["seat"]})
            return self.rooms[room_id]
        raise AssertionError(f"unexpected request {method} {path}")


class BotRunnerTests(unittest.TestCase):
    def test_bot_account_is_stable_per_slot(self) -> None:
        account = bot_account_for(3)
        self.assertEqual(account.nick, "CKBot03")
        self.assertEqual(account.email, "ckbot03@bots.championskof.local")
        self.assertEqual(len(account.hardware_id), 64)
        self.assertTrue(all(character in "0123456789abcdef" for character in account.hardware_id))

    def test_room_name_defaults_to_driver_and_slot(self) -> None:
        self.assertEqual(room_name_for("kof2002", 7), "BOT KOF2002 07")
        self.assertEqual(room_name_for("kof98", 1, explicit_name="Arena"), "Arena")

    def test_public_room_names_match_launcher_slots(self) -> None:
        self.assertEqual(room_name_for("kof98", 1, "PUBLIC"), "KOF 98 Room No.1")
        self.assertEqual(room_name_for("kof2002", 1, "PUBLIC"), "KOF 2002 Room No.1")
        self.assertEqual(room_name_for("sf2ce", 3, "PUBLIC"), "SF2CE Room No.3")

    def test_v0_environment_keeps_scripted_inputs_off(self) -> None:
        env = bot_environment("v0", {"PATH": os.environ.get("PATH", "")})
        self.assertEqual(env["CHAMPIONS_BOT_CLIENT"], "1")
        self.assertEqual(env["CHAMPIONS_NETPLAY_SCRIPTED_INPUTS"], "0")

    def test_v1_environment_uses_existing_scripted_input_surface(self) -> None:
        env = bot_environment("v1", {})
        self.assertEqual(env["CHAMPIONS_NETPLAY_SCRIPTED_INPUTS"], "1")

    def test_preferred_relay_uses_primary_relay(self) -> None:
        host, port = preferred_relay({"primary_relay": {"host": "relay.example", "port": 7777}})
        self.assertEqual((host, port), ("relay.example", 7777))

    def test_ensure_bot_room_creates_room_when_missing(self) -> None:
        api = FakeApi()
        room = ensure_bot_room(api, "token", 42, "kof2002", "BOT KOF2002 01", 0)
        self.assertEqual(room["id"], "roombot01")
        self.assertEqual(api.requests[-1][0:2], ("POST", "api/rooms"))

    def test_ensure_bot_room_joins_existing_room_when_bot_missing(self) -> None:
        api = FakeApi()
        api.rooms["roombot01"] = {
            "id": "roombot01",
            "name": "BOT KOF2002 01",
            "driver": "kof2002",
            "members_preview": [],
            "members": [],
            "primary_relay": {"host": "127.0.0.1", "port": 7000},
        }
        room = ensure_bot_room(api, "token", 42, "kof2002", "BOT KOF2002 01", 0)
        self.assertEqual(room["members"][0]["user_id"], 42)
        self.assertEqual(api.requests[-1][0:2], ("POST", "api/rooms/roombot01/join"))

    def test_launch_arguments_use_public_match_window_surface(self) -> None:
        config = BotConfig(
            base_url="http://127.0.0.1:8080/",
            exe_path=Path("ChampionsKOF.exe"),
            rom_dir=Path("roms"),
            game_zip=Path("roms/kof2002.zip"),
            bios_zip=Path("roms/neogeo.zip"),
            driver="kof2002",
            slot=1,
            mode="v0",
            room_prefix="BOT",
            room_name="BOT KOF2002 01",
            target_score=0,
            force_relay=True,
            poll_seconds=5.0,
            config_dir=Path("bot-config"),
            log_dir=Path("bot-logs"),
            dry_run=True,
            once=True,
        )
        session = BotSession(
            account=bot_account_for(1),
            token="token",
            user_id=42,
            username="CKBot01",
            room_id="roombot01",
            room_name="BOT KOF2002 01",
            seat=1,
            relay_host="127.0.0.1",
            relay_port=7000,
        )
        args = launch_arguments(config, session)
        self.assertIn("--match-window", args)
        self.assertIn("--netplay-room", args)
        self.assertIn("--netplay-token", args)
        self.assertIn("--netplay-force-relay", args)


if __name__ == "__main__":
    unittest.main()
