from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_GAMES = ("kof98", "kof2002", "sf2ce")
DEFAULT_ROOM_PREFIX = "BOT"
DEFAULT_POLL_SECONDS = 5.0


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class BotAccount:
    slot: int
    nick: str
    email: str
    password: str
    hardware_id: str


@dataclass(frozen=True)
class BotConfig:
    base_url: str
    exe_path: Path
    rom_dir: Path
    game_zip: Path
    bios_zip: Path
    driver: str
    slot: int
    mode: str
    room_prefix: str
    room_name: str
    target_score: int
    force_relay: bool
    poll_seconds: float
    config_dir: Path | None
    log_dir: Path | None
    dry_run: bool
    once: bool


@dataclass
class BotSession:
    account: BotAccount
    token: str
    user_id: int
    username: str
    room_id: str
    room_name: str
    seat: int
    relay_host: str
    relay_port: int
    process: subprocess.Popen[str] | None = None


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip()
    if not normalized:
        raise ValueError("base_url is required")
    return normalized if normalized.endswith("/") else f"{normalized}/"


def room_name_for(driver: str, slot: int, room_prefix: str = DEFAULT_ROOM_PREFIX, explicit_name: str = "") -> str:
    if explicit_name.strip():
        return explicit_name.strip()
    normalized_prefix = room_prefix.strip() or DEFAULT_ROOM_PREFIX
    if normalized_prefix.upper() in {"PUBLIC", "LOBBY"}:
        public_names = {
            "kof98": "KOF 98 Room No.{slot}",
            "kof2002": "KOF 2002 Room No.{slot}",
            "sf2ce": "SF2CE Room No.{slot}",
        }
        template = public_names.get(driver.strip().lower())
        if template is not None:
            return template.format(slot=max(1, int(slot)))
    return f"{normalized_prefix} {driver.upper()} {slot:02d}"


def bot_account_for(slot: int, namespace: str = "championskof") -> BotAccount:
    normalized_slot = max(1, int(slot))
    nick = f"CKBot{normalized_slot:02d}"
    hardware_id = hashlib.sha256(f"{namespace}:bot:{normalized_slot:02d}".encode("utf-8")).hexdigest()
    return BotAccount(
        slot=normalized_slot,
        nick=nick,
        email=f"{nick.lower()}@bots.championskof.local",
        password=f"{namespace}-bot-{normalized_slot:02d}",
        hardware_id=hardware_id,
    )


def bot_environment(mode: str, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    normalized_mode = mode.strip().lower()
    env["CHAMPIONS_BOT_CLIENT"] = "1"
    env["CHAMPIONS_BOT_MODE"] = normalized_mode
    if normalized_mode in {"v1", "scripted"}:
        env["CHAMPIONS_NETPLAY_SCRIPTED_INPUTS"] = "1"
    else:
        env["CHAMPIONS_NETPLAY_SCRIPTED_INPUTS"] = "0"
    return env


class ChampionsApiClient:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = normalize_base_url(base_url)
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        token: str = "",
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        relative_path = path.lstrip("/")
        url = urllib.parse.urljoin(self.base_url, relative_path)
        if query:
            encoded_query = urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
            url = f"{url}?{encoded_query}"

        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"

        request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
                if not response_body:
                    return {}
                return json.loads(response_body)
        except urllib.error.HTTPError as exc:
            response_text = exc.read().decode("utf-8", errors="replace")
            try:
                response_json = json.loads(response_text)
                message = str(response_json.get("error") or response_json.get("message") or response_text)
            except json.JSONDecodeError:
                message = response_text or str(exc)
            raise ApiError(message, exc.code) from exc
        except urllib.error.URLError as exc:
            raise ApiError(str(exc.reason)) from exc


def login_or_register(api: ChampionsApiClient, account: BotAccount) -> tuple[str, dict[str, Any]]:
    login_payload = {
        "login": account.nick,
        "password": account.password,
        "id_hardware": account.hardware_id,
    }
    try:
        response = api.request("POST", "api/auth/login", login_payload)
        return str(response["token"]), dict(response["user"])
    except ApiError as exc:
        if exc.status not in {400, 401, 403, 404}:
            raise

    register_payload = {
        "full_name": f"ChampionsKOF Bot {account.slot:02d}",
        "nick": account.nick,
        "email": account.email,
        "whatsapp": "11999999999",
        "birth_date": "1990-01-01",
        "password": account.password,
        "id_hardware": account.hardware_id,
    }
    response = api.request("POST", "api/auth/register", register_payload)
    return str(response["token"]), dict(response["user"])


def preferred_relay(infrastructure_payload: dict[str, Any]) -> tuple[str, int]:
    primary = infrastructure_payload.get("primary_relay")
    relays = infrastructure_payload.get("relays")
    relay: dict[str, Any] | None = primary if isinstance(primary, dict) else None
    if relay is None and isinstance(relays, list) and relays:
        first = relays[0]
        relay = first if isinstance(first, dict) else None
    if relay is None:
        relay = {}
    host = str(relay.get("host") or infrastructure_payload.get("relay_host") or "").strip()
    port = int(relay.get("port") or infrastructure_payload.get("relay_port") or 7000)
    if not host:
        raise ApiError("server did not advertise a relay host")
    return host, port


def find_existing_bot_room(rooms: list[dict[str, Any]], driver: str, room_name: str) -> dict[str, Any] | None:
    for room in rooms:
        if str(room.get("driver", "")).strip().lower() != driver:
            continue
        if str(room.get("name", "")).strip() != room_name:
            continue
        return room
    return None


def room_has_user(room: dict[str, Any], user_id: int) -> bool:
    members = room.get("members") or room.get("members_preview") or []
    if not isinstance(members, list):
        return False
    return any(int(member.get("user_id", 0) or 0) == user_id for member in members if isinstance(member, dict))


def room_seat_for_user(room: dict[str, Any], user_id: int, fallback: int = 1) -> int:
    members = room.get("members") or room.get("members_preview") or []
    if isinstance(members, list):
        for member in members:
            if not isinstance(member, dict):
                continue
            if int(member.get("user_id", 0) or 0) == user_id:
                return max(1, int(member.get("seat", fallback) or fallback))
    return fallback


def ensure_bot_room(
    api: ChampionsApiClient,
    token: str,
    user_id: int,
    driver: str,
    room_name: str,
    target_score: int,
) -> dict[str, Any]:
    rooms_payload = api.request("GET", "api/rooms", token=token)
    rooms = rooms_payload.get("rooms", [])
    if not isinstance(rooms, list):
        rooms = []
    existing_room = find_existing_bot_room(rooms, driver, room_name)
    if existing_room is not None:
        room_id = str(existing_room.get("id", ""))
        room = api.request("GET", f"api/rooms/{room_id}", token=token)
        if room_has_user(room, user_id):
            return room
        return api.request("POST", f"api/rooms/{room_id}/join", {"seat": 1}, token=token)

    return api.request(
        "POST",
        "api/rooms",
        {
            "name": room_name,
            "driver": driver,
            "max_players": 2,
            "seat": 1,
            "target_score": target_score,
            "show_lobby_score": False,
            "allow_spectators": True,
        },
        token=token,
    )


def launch_arguments(config: BotConfig, session: BotSession) -> list[str]:
    args = [
        "--match-window",
        "--driver",
        config.driver,
        "--game-zip",
        str(config.game_zip),
        "--bios-zip",
        str(config.bios_zip),
        "--rom-dir",
        str(config.rom_dir),
        "--netplay-room",
        session.room_id,
        "--netplay-room-label",
        session.room_name,
        "--netplay-token",
        session.token,
        "--netplay-local-username",
        session.username,
        "--netplay-user-id",
        str(session.user_id),
        "--netplay-seat",
        str(session.seat),
        "--netplay-target-score",
        str(config.target_score),
        "--netplay-relay-host",
        session.relay_host,
        "--netplay-relay-port",
        str(session.relay_port),
    ]
    if config.force_relay:
        args.append("--netplay-force-relay")
    if config.config_dir is not None:
        args.extend(["--config-dir", str(config.config_dir)])
    if config.log_dir is not None:
        args.extend(["--log-dir", str(config.log_dir)])
    return args


def launch_bot_process(config: BotConfig, session: BotSession) -> subprocess.Popen[str] | None:
    args = launch_arguments(config, session)
    if config.dry_run:
        print(json.dumps({"exe": str(config.exe_path), "args": args}, indent=2), flush=True)
        return None

    if not config.exe_path.exists():
        raise FileNotFoundError(f"ChampionsKOF executable not found: {config.exe_path}")
    if config.config_dir is not None:
        config.config_dir.mkdir(parents=True, exist_ok=True)
    if config.log_dir is not None:
        config.log_dir.mkdir(parents=True, exist_ok=True)

    return subprocess.Popen(
        [str(config.exe_path), *args],
        cwd=str(config.exe_path.parent),
        env=bot_environment(config.mode),
        text=True,
    )


def ensure_session(config: BotConfig, api: ChampionsApiClient) -> BotSession:
    account = bot_account_for(config.slot)
    token, user = login_or_register(api, account)
    user_id = int(user.get("id", 0) or 0)
    username = str(user.get("nick") or user.get("username") or account.nick)
    room = ensure_bot_room(api, token, user_id, config.driver, config.room_name, config.target_score)
    relay_host, relay_port = preferred_relay(room)
    room_id = str(room["id"])
    room_name = str(room.get("name") or config.room_name)
    seat = room_seat_for_user(room, user_id, fallback=1)
    return BotSession(
        account=account,
        token=token,
        user_id=user_id,
        username=username,
        room_id=room_id,
        room_name=room_name,
        seat=seat,
        relay_host=relay_host,
        relay_port=relay_port,
    )


def run_once(config: BotConfig) -> BotSession:
    api = ChampionsApiClient(config.base_url)
    session = ensure_session(config, api)
    session.process = launch_bot_process(config, session)
    print(
        json.dumps(
            {
                "event": "bot_started" if session.process is not None else "bot_ready",
                "driver": config.driver,
                "mode": config.mode,
                "room_id": session.room_id,
                "room_name": session.room_name,
                "seat": session.seat,
                "user_id": session.user_id,
                "nick": session.username,
                "relay": f"{session.relay_host}:{session.relay_port}",
            },
            ensure_ascii=True,
        ),
        flush=True,
    )
    return session


def run_forever(config: BotConfig) -> None:
    session: BotSession | None = None
    while True:
        if session is None or session.process is None or session.process.poll() is not None:
            session = run_once(config)
        time.sleep(max(1.0, config.poll_seconds))


def parse_args(argv: list[str]) -> BotConfig:
    parser = argparse.ArgumentParser(description="External ChampionsKOF bot supervisor.")
    parser.add_argument("--base-url", required=True, help="Matchmaking API base URL.")
    parser.add_argument("--exe", required=True, type=Path, help="Path to the ChampionsKOF executable.")
    parser.add_argument("--rom-dir", required=True, type=Path)
    parser.add_argument("--game-zip", required=True, type=Path)
    parser.add_argument("--bios-zip", required=True, type=Path)
    parser.add_argument("--driver", required=True, choices=SUPPORTED_GAMES)
    parser.add_argument("--slot", type=int, default=1)
    parser.add_argument("--mode", choices=("v0", "v1", "scripted"), default="v0")
    parser.add_argument("--room-prefix", default=DEFAULT_ROOM_PREFIX)
    parser.add_argument("--room-name", default="")
    parser.add_argument("--target-score", type=int, default=0)
    parser.add_argument("--allow-p2p", action="store_true", help="Do not force relay-only launch.")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true", help="Start once and exit supervisor.")
    args = parser.parse_args(argv)

    driver = str(args.driver).strip().lower()
    room_name = room_name_for(driver, int(args.slot), str(args.room_prefix), str(args.room_name))
    return BotConfig(
        base_url=normalize_base_url(str(args.base_url)),
        exe_path=args.exe,
        rom_dir=args.rom_dir,
        game_zip=args.game_zip,
        bios_zip=args.bios_zip,
        driver=driver,
        slot=max(1, int(args.slot)),
        mode=str(args.mode),
        room_prefix=str(args.room_prefix),
        room_name=room_name,
        target_score=max(0, min(99, int(args.target_score))),
        force_relay=not bool(args.allow_p2p),
        poll_seconds=max(1.0, float(args.poll_seconds)),
        config_dir=args.config_dir,
        log_dir=args.log_dir,
        dry_run=bool(args.dry_run),
        once=bool(args.once),
    )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(list(argv or sys.argv[1:]))
    try:
        if config.once or config.dry_run:
            run_once(config)
        else:
            run_forever(config)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"bot_runner_error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
