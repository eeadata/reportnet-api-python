"""download() only replaces `dest` once the whole body has arrived."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient

BASE_URL = "https://api.reportnet.europa.eu"


class _BrokenStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"partial"
        raise httpx.ReadError("connection dropped")


class _AsyncBrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"partial"
        raise httpx.ReadError("connection dropped")


def _leftovers(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir() if p.name.endswith(".part"))


def test_failed_download_keeps_the_old_file(tmp_path: Path) -> None:
    dest = tmp_path / "export.zip"
    dest.write_bytes(b"previous good export")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/f").mock(return_value=httpx.Response(200, stream=_BrokenStream()))
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(httpx.ReadError),
        ):
            client.download("GET", "/f", dest=dest)
    assert dest.read_bytes() == b"previous good export"
    assert _leftovers(tmp_path) == []


def test_async_failed_download_keeps_the_old_file(tmp_path: Path) -> None:
    dest = tmp_path / "export.zip"
    dest.write_bytes(b"previous good export")

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/f").mock(return_value=httpx.Response(200, stream=_AsyncBrokenStream()))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.download("GET", "/f", dest=dest)

    with pytest.raises(httpx.ReadError):
        asyncio.run(run())
    assert dest.read_bytes() == b"previous good export"
    assert _leftovers(tmp_path) == []


def test_successful_download_replaces_the_file(tmp_path: Path) -> None:
    dest = tmp_path / "export.zip"
    dest.write_bytes(b"old")
    (tmp_path / "export.zip.part").write_bytes(b"someone else's file")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/f").mock(return_value=httpx.Response(200, content=b"new"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.download("GET", "/f", dest=dest)
    assert dest.read_bytes() == b"new"
    assert (tmp_path / "export.zip.part").read_bytes() == b"someone else's file"
    assert _leftovers(tmp_path) == ["export.zip.part"]
