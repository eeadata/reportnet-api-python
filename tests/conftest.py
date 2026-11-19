"""Shared test setup: unit tests must never reach a real server."""

import socket
from typing import Any

import pytest

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that opens a non-loopback connection (respx mocks never do)."""
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> None:
        host = address[0] if isinstance(address, tuple) else address
        if self.family != socket.AF_UNIX and host not in _LOOPBACK:
            raise RuntimeError(f"Unit test tried to open a network connection to {address!r}")
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
