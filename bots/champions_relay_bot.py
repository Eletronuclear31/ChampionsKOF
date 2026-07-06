from __future__ import annotations

import json
import hashlib
import socket
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RelayBotConfig:
    relay_host: str
    relay_port: int
    room_id: str
    token: str
    seat: int
    app_version: str
    app_build: int
    netplay_protocol: int
    neutral_input: int = 0
    input_profile: str = "neutral"
    frame_hz: float = 60.0
    hello_interval_seconds: float = 2.0
    ping_interval_seconds: float = 1.0
    bootstrap_ready_interval_seconds: float = 0.5


@dataclass
class RelayBotStats:
    hello_sent: int = 0
    hello_ack_received: int = 0
    ping_sent: int = 0
    ping_received: int = 0
    pong_sent: int = 0
    pong_received: int = 0
    frames_sent: int = 0
    frames_received: int = 0
    bootstrap_ready_sent: int = 0
    bootstrap_ready_received: int = 0
    bootstrap_go_received: int = 0
    non_json_datagrams_ignored: int = 0
    errors_received: int = 0


class RelayBotClient:
    def __init__(self, config: RelayBotConfig, udp_socket: socket.socket | None = None) -> None:
        self.config = config
        self.stats = RelayBotStats()
        self.ready = False
        self.bootstrap_complete = False
        self.room_epoch = 0
        self.current_frame = 0
        self.sequence = 0
        self.ping_sequence = 0
        self.newest_remote_frame = -1
        self.player_count = 0
        self.spectator_count = 0
        self.peer_seat = 0
        self.peer_username = ""
        self.latest_live_frame = -1
        self.last_error = ""
        self._last_hello_at = 0.0
        self._last_ping_at = 0.0
        self._last_frame_at = 0.0
        self._last_bootstrap_ready_at = -self.config.bootstrap_ready_interval_seconds
        self._socket = udp_socket if udp_socket is not None else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)
        self._relay_address = (config.relay_host, int(config.relay_port))

    def close(self) -> None:
        self._socket.close()

    def pump(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        self._receive_pending()
        if (current - self._last_hello_at) >= self.config.hello_interval_seconds:
            self.send_hello()
            self._last_hello_at = current
        if self.ready and (current - self._last_ping_at) >= self.config.ping_interval_seconds:
            self.send_ping()
            self._last_ping_at = current
        if self.ready and self.room_epoch > 0 and not self.bootstrap_complete:
            self.maybe_send_consensus_bootstrap_ready(current)
        frame_interval = 1.0 / max(1.0, float(self.config.frame_hz))
        if self.ready and self.bootstrap_complete and (current - self._last_frame_at) >= frame_interval:
            self.send_frame()
            self._last_frame_at = current

    def send_hello(self) -> None:
        self._send(
            {
                "t": "hello",
                "room": self.config.room_id,
                "token": self.config.token,
                "local_port": self._local_port(),
                "seat": self.config.seat,
                "local_candidates": [],
                "public_candidates": [],
                "p2p": False,
                "direct_ready": False,
                "app_version": self.config.app_version,
                "app_build": self.config.app_build,
                "netplay_protocol": self.config.netplay_protocol,
                "spectator": False,
            }
        )
        self.stats.hello_sent += 1

    def send_ping(self) -> None:
        self.ping_sequence += 1
        self._send(
            {
                "t": "ping",
                "room": self.config.room_id,
                "seq": self.ping_sequence,
                "sent_ms": int(time.time() * 1000),
                "from_seat": self.config.seat,
                "current_frame": self.current_frame,
            }
        )
        self.stats.ping_sent += 1

    def send_pong(self, sequence: int, sent_ms: Any) -> None:
        self._send(
            {
                "t": "pong",
                "room": self.config.room_id,
                "seq": int(sequence),
                "sent_ms": sent_ms,
                "from_seat": self.config.seat,
                "current_frame": self.current_frame,
            }
        )
        self.stats.pong_sent += 1

    def send_bootstrap_ready(self, epoch: int, state_hash: str, current_frame: int = 0) -> None:
        if epoch <= 0 or not state_hash:
            return
        self._send(
            {
                "t": "bootstrap-ready",
                "room": self.config.room_id,
                "from_seat": self.config.seat,
                "epoch": int(epoch),
                "current_frame": max(0, int(current_frame)),
                "state_hash": state_hash,
            }
        )
        self.stats.bootstrap_ready_sent += 1

    def maybe_send_consensus_bootstrap_ready(self, current: float | None = None) -> None:
        now = time.monotonic() if current is None else current
        if (now - self._last_bootstrap_ready_at) < self.config.bootstrap_ready_interval_seconds:
            return
        self._last_bootstrap_ready_at = now
        self.send_bootstrap_ready(self.room_epoch, self.consensus_bootstrap_hash(self.room_epoch), self.current_frame)

    def consensus_bootstrap_hash(self, epoch: int) -> str:
        material = f"{self.config.room_id}:{int(epoch)}:relay-bootstrap-ready".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def send_frame(self) -> None:
        self.sequence += 1
        input_value = self.input_for_frame(self.stats.frames_sent)
        packet = {
            "t": "frame",
            "room": self.config.room_id,
            "room_epoch": int(self.room_epoch),
            "frame": int(self.current_frame),
            "input": int(input_value),
            "from_seat": int(self.config.seat),
            "current_frame": int(self.current_frame),
            "seq": int(self.sequence),
            "ack_frame": int(self.newest_remote_frame),
            "telemetry_valid": False,
            "telemetry_match_active": False,
        }
        self._send(packet)
        self.stats.frames_sent += 1
        self.current_frame += 1

    def input_for_frame(self, bot_frame: int) -> int:
        normalized_profile = self.config.input_profile.strip().lower()
        if normalized_profile in {"neutral", "v0"}:
            return int(self.config.neutral_input)

        # Deterministic P1 mask bits from FbneoBridge::DeterministicInputBit.
        p1_coin = 1 << 0
        p1_start = 1 << 1
        p1_up = 1 << 3
        p1_down = 1 << 4
        p1_left = 1 << 5
        p1_right = 1 << 6
        p1_fire1 = 1 << 7
        p1_fire2 = 1 << 8
        p1_fire3 = 1 << 9
        p1_fire4 = 1 << 10

        frame = max(0, int(bot_frame))
        if frame % 180 in {5, 6, 7, 8, 45, 46, 47, 48}:
            return p1_coin
        if frame % 180 in {20, 21, 22, 23, 60, 61, 62, 63}:
            return p1_start
        if normalized_profile in {"beginner", "opening"}:
            if 90 <= frame % 240 <= 96:
                return p1_fire1
            if 120 <= frame % 240 <= 126:
                return p1_fire2
            return int(self.config.neutral_input)

        cycle = frame % 360
        if 90 <= cycle <= 108:
            return p1_right
        if 120 <= cycle <= 130:
            return p1_fire1
        if 150 <= cycle <= 168:
            return p1_left
        if 190 <= cycle <= 202:
            return p1_down | p1_right
        if 203 <= cycle <= 210:
            return p1_fire3
        if 245 <= cycle <= 256:
            return p1_up
        if 285 <= cycle <= 294:
            return p1_fire4
        return int(self.config.neutral_input)

    def handle_packet(self, packet: dict[str, Any]) -> None:
        packet_type = str(packet.get("t", "")).strip()
        if packet_type == "hello-ack":
            self.stats.hello_ack_received += 1
            self.ready = bool(packet.get("ready", False))
            new_epoch = int(packet.get("room_bootstrap_epoch", self.room_epoch) or self.room_epoch)
            if new_epoch != self.room_epoch:
                self.bootstrap_complete = False
                self._last_bootstrap_ready_at = -self.config.bootstrap_ready_interval_seconds
            self.room_epoch = new_epoch
            self.player_count = int(packet.get("player_count", self.player_count) or 0)
            self.spectator_count = int(packet.get("spectator_count", self.spectator_count) or 0)
            self.peer_seat = int(packet.get("peer_seat", self.peer_seat) or 0)
            self.peer_username = str(packet.get("peer_username", self.peer_username) or "")
            self.latest_live_frame = int(packet.get("latest_live_frame", self.latest_live_frame) or -1)
            if self.ready and self.room_epoch > 0 and not self.bootstrap_complete:
                self.maybe_send_consensus_bootstrap_ready(0.0)
            return
        if packet_type == "ping":
            self.stats.ping_received += 1
            self.send_pong(int(packet.get("seq", 0) or 0), packet.get("sent_ms", "0"))
            return
        if packet_type == "pong":
            self.stats.pong_received += 1
            return
        if packet_type == "bootstrap-ready":
            self.stats.bootstrap_ready_received += 1
            epoch = int(packet.get("epoch", 0) or 0)
            state_hash = str(packet.get("state_hash", "") or "").strip()
            peer_frame = int(packet.get("current_frame", 0) or 0)
            self.room_epoch = epoch or self.room_epoch
            self.send_bootstrap_ready(epoch, state_hash or self.consensus_bootstrap_hash(epoch), peer_frame)
            return
        if packet_type == "bootstrap-go":
            self.stats.bootstrap_go_received += 1
            self.ready = True
            self.bootstrap_complete = True
            self.room_epoch = int(packet.get("epoch", self.room_epoch) or self.room_epoch)
            self.current_frame = max(self.current_frame, int(packet.get("current_frame", self.current_frame) or self.current_frame))
            return
        if packet_type == "frame":
            self.stats.frames_received += 1
            self.newest_remote_frame = max(self.newest_remote_frame, int(packet.get("frame", -1) or -1))
            return
        if packet_type == "error":
            self.stats.errors_received += 1
            self.last_error = str(packet.get("error", "") or "")

    def _receive_pending(self) -> None:
        while True:
            try:
                payload, _address = self._socket.recvfrom(4096)
            except BlockingIOError:
                return
            except socket.timeout:
                return
            try:
                packet = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.stats.non_json_datagrams_ignored += 1
                continue
            if isinstance(packet, dict):
                self.handle_packet(packet)

    def _send(self, packet: dict[str, Any]) -> None:
        payload = json.dumps(packet, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        self._socket.sendto(payload, self._relay_address)

    def _local_port(self) -> int:
        try:
            return int(self._socket.getsockname()[1])
        except OSError:
            return 0
