from __future__ import annotations

import json
import unittest

from .champions_relay_bot import RelayBotClient
from .champions_relay_bot import RelayBotConfig


class FakeUdpSocket:
    def __init__(self) -> None:
        self.sent: list[tuple[dict, tuple[str, int]]] = []
        self.incoming: list[dict | bytes] = []
        self.blocking = True

    def setblocking(self, value: bool) -> None:
        self.blocking = value

    def getsockname(self) -> tuple[str, int]:
        return ("0.0.0.0", 45678)

    def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
        self.sent.append((json.loads(payload.decode("utf-8")), address))

    def recvfrom(self, _size: int) -> tuple[bytes, tuple[str, int]]:
        if not self.incoming:
            raise BlockingIOError()
        packet = self.incoming.pop(0)
        if isinstance(packet, bytes):
            return packet, ("relay.example", 7000)
        return json.dumps(packet).encode("utf-8"), ("relay.example", 7000)

    def close(self) -> None:
        pass


def make_client() -> tuple[RelayBotClient, FakeUdpSocket]:
    udp = FakeUdpSocket()
    config = RelayBotConfig(
        relay_host="relay.example",
        relay_port=7000,
        room_id="room1",
        token="token",
        seat=1,
        app_version="1.0.18",
        app_build=215,
        netplay_protocol=215,
    )
    return RelayBotClient(config, udp_socket=udp), udp  # type: ignore[arg-type]


def make_client_with_profile(profile: str) -> tuple[RelayBotClient, FakeUdpSocket]:
    udp = FakeUdpSocket()
    config = RelayBotConfig(
        relay_host="relay.example",
        relay_port=7000,
        room_id="room1",
        token="token",
        seat=1,
        app_version="1.0.18",
        app_build=215,
        netplay_protocol=215,
        input_profile=profile,
    )
    return RelayBotClient(config, udp_socket=udp), udp  # type: ignore[arg-type]


class RelayBotClientTests(unittest.TestCase):
    def test_send_hello_uses_public_relay_contract(self) -> None:
        client, udp = make_client()
        client.send_hello()
        packet, address = udp.sent[-1]
        self.assertEqual(address, ("relay.example", 7000))
        self.assertEqual(packet["t"], "hello")
        self.assertEqual(packet["room"], "room1")
        self.assertEqual(packet["token"], "token")
        self.assertEqual(packet["seat"], 1)
        self.assertFalse(packet["p2p"])
        self.assertEqual(packet["app_build"], 215)
        self.assertEqual(packet["netplay_protocol"], 215)

    def test_ping_is_answered_with_pong(self) -> None:
        client, udp = make_client()
        client.handle_packet({"t": "ping", "room": "room1", "seq": 7, "sent_ms": 123})
        packet, _address = udp.sent[-1]
        self.assertEqual(packet["t"], "pong")
        self.assertEqual(packet["seq"], 7)
        self.assertEqual(packet["sent_ms"], 123)

    def test_bootstrap_ready_accepts_peer_state_hash(self) -> None:
        client, udp = make_client()
        client.handle_packet(
            {
                "t": "bootstrap-ready",
                "room": "room1",
                "epoch": 3,
                "current_frame": 0,
                "state_hash": "abcd",
            }
        )
        packet, _address = udp.sent[-1]
        self.assertEqual(packet["t"], "bootstrap-ready")
        self.assertEqual(packet["epoch"], 3)
        self.assertEqual(packet["state_hash"], "abcd")

    def test_hello_ack_sends_consensus_bootstrap_ready(self) -> None:
        client, udp = make_client()
        client.handle_packet(
            {
                "t": "hello-ack",
                "room": "room1",
                "ready": True,
                "room_bootstrap_epoch": 3,
                "player_count": 2,
                "peer_seat": 2,
                "peer_username": "Eletro",
            }
        )
        packet, _address = udp.sent[-1]
        self.assertEqual(packet["t"], "bootstrap-ready")
        self.assertEqual(packet["epoch"], 3)
        self.assertEqual(
            packet["state_hash"],
            "c7ef1621a8190cae43290389ddba187c7d42431ccdd6fc06cbccbc85f929593b",
        )
        self.assertEqual(client.player_count, 2)
        self.assertEqual(client.peer_username, "Eletro")

    def test_ready_before_bootstrap_go_does_not_send_frames(self) -> None:
        client, udp = make_client()
        client.handle_packet({"t": "hello-ack", "room": "room1", "ready": True, "room_bootstrap_epoch": 3})
        sent_count = len(udp.sent)
        client.pump(10.0)
        self.assertTrue(all(packet["t"] != "frame" for packet, _address in udp.sent[sent_count:]))

    def test_sends_neutral_frame_after_ready(self) -> None:
        client, udp = make_client()
        client.handle_packet({"t": "hello-ack", "room": "room1", "ready": True, "room_bootstrap_epoch": 3})
        client.handle_packet({"t": "bootstrap-go", "room": "room1", "epoch": 3, "current_frame": 0})
        client.send_frame()
        packet, _address = udp.sent[-1]
        self.assertEqual(packet["t"], "frame")
        self.assertEqual(packet["room_epoch"], 3)
        self.assertEqual(packet["frame"], 0)
        self.assertEqual(packet["input"], 0)
        self.assertEqual(packet["ack_frame"], -1)

    def test_ignores_fast_binary_datagrams(self) -> None:
        client, udp = make_client()
        udp.incoming.append(b"YZFF\x01\x01\xff\x00not-json")
        client.pump(1.0)
        self.assertEqual(client.stats.non_json_datagrams_ignored, 1)

    def test_beginner_profile_presses_coin_and_start(self) -> None:
        client, _udp = make_client_with_profile("beginner")
        self.assertEqual(client.input_for_frame(5), 1)
        self.assertEqual(client.input_for_frame(20), 2)


if __name__ == "__main__":
    unittest.main()
