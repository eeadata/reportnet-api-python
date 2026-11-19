"""The autouse guard in conftest.py: real network access fails, loopback does not."""

import socket

import pytest


@pytest.mark.parametrize("call", ["connect", "connect_ex"])
def test_remote_connections_are_refused(call: str) -> None:
    with socket.socket() as s, pytest.raises(RuntimeError, match="network connection"):
        getattr(s, call)(("192.0.2.1", 443))  # TEST-NET-1, never routed


def test_udp_sendto_is_refused() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s,
        pytest.raises(RuntimeError, match="network connection"),
    ):
        s.sendto(b"x", ("192.0.2.1", 53))


def test_resolving_a_public_name_is_refused() -> None:
    with pytest.raises(RuntimeError, match="resolve the host name"):
        socket.getaddrinfo("api.reportnet.europa.eu", 443)


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "localhost"])
def test_loopback_is_allowed(host: str) -> None:
    with socket.socket() as s:
        s.settimeout(1)
        assert s.connect_ex((host, 9)) != 0  # refused by the OS, not by the guard


def test_loopback_names_resolve() -> None:
    assert socket.getaddrinfo("localhost", 80)
