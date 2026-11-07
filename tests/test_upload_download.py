import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, NotFoundError, ReportnetClient

BASE_URL = "https://api.reportnet.europa.eu"


def test_upload_streams_file_as_multipart(tmp_path: Path) -> None:
    src = tmp_path / "data.csv"
    src.write_text("a,b\n1,2\n")

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/v1/1/importFileData").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.import_file_data(dataset_id=1, file=src)

    sent_body = route.calls.last.request.content
    assert b"a,b\n1,2\n" in sent_body
    assert b'filename="data.csv"' in sent_body


def test_async_upload_streams_file_as_multipart(tmp_path: Path) -> None:
    src = tmp_path / "data.csv"
    src.write_text("a,b\n1,2\n")

    async def run() -> respx.Route:
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post("/dataset/v1/1/importFileData").mock(return_value=httpx.Response(200))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.datasets.import_file_data(dataset_id=1, file=src)
            return route

    route = asyncio.run(run())
    sent_body = route.calls.last.request.content
    assert b"a,b\n1,2\n" in sent_body
    assert b'filename="data.csv"' in sent_body


def test_download_streams_response_to_dest(tmp_path: Path) -> None:
    dest = tmp_path / "out.csv"
    content = b"col1,col2\n1,2\n" * 1000

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/snapshot/downloadHistoricReleases/1").mock(
            return_value=httpx.Response(200, content=content)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.dataset_snapshot.download_historic_releases_csv(
                dataflow_id=1, dataset_id=1, file_name="out.csv", dest=dest
            )

    assert dest.read_bytes() == content


def test_async_download_streams_response_to_dest(tmp_path: Path) -> None:
    dest = tmp_path / "out.csv"
    content = b"col1,col2\n1,2\n" * 1000

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/snapshot/downloadHistoricReleases/1").mock(
                return_value=httpx.Response(200, content=content)
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.dataset_snapshot.download_historic_releases_csv(
                    dataflow_id=1, dataset_id=1, file_name="out.csv", dest=dest
                )

    asyncio.run(run())
    assert dest.read_bytes() == content


def test_download_error_status_raises_and_skips_dest_write(tmp_path: Path) -> None:
    dest = tmp_path / "out.csv"

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/snapshot/downloadHistoricReleases/999").mock(
            return_value=httpx.Response(404, text="missing")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(NotFoundError) as exc_info:
                client.dataset_snapshot.download_historic_releases_csv(
                    dataflow_id=1, dataset_id=999, file_name="out.csv", dest=dest
                )

    assert exc_info.value.status_code == 404
    assert exc_info.value.response_body == "missing"
    assert not dest.exists()


def test_download_defaults_accept_to_any_and_allows_override(tmp_path: Path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(200, content=b"z"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.download("GET", "/x", dest=tmp_path / "a")
            assert route.calls.last.request.headers["Accept"] == "*/*"
            client.download("GET", "/x", dest=tmp_path / "b", headers={"Accept": "text/csv"})
            assert route.calls.last.request.headers["Accept"] == "text/csv"


def test_download_header_override_is_case_insensitive(tmp_path: Path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(200, content=b"z"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.download("GET", "/x", dest=tmp_path / "a", headers={"accept": "text/csv"})
        sent = route.calls.last.request.headers
        assert sent.get_list("accept") == ["text/csv"]
