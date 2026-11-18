"""Tests for the hand-written datasets_ext addition (hidden deleteImportTable)."""

import asyncio
from pathlib import Path

import httpx
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient

BASE_URL = "https://api.reportnet.europa.eu"
PATH = "/dataset/7/deleteImportTable/abc123"


def test_delete_import_table() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.delete(PATH).mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.delete_import_table(7, "abc123", dataflow_id=1)

    assert result is None
    request = route.calls.last.request
    assert request.url.params["dataflowId"] == "1"
    assert "providerId" not in request.url.params


def test_async_delete_import_table() -> None:
    async def run() -> respx.Route:
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(PATH).mock(return_value=httpx.Response(200))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                assert await client.datasets.delete_import_table(7, "abc123") is None
            return route

    assert asyncio.run(run()).called


def test_update_dataset_name() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/datasetmetabase/updateDatasetName").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.datasets.update_dataset_name(44266, "Codelist (2)") is None

    params = route.calls.last.request.url.params
    assert params["datasetId"] == "44266"
    assert params["datasetName"] == "Codelist (2)"


def test_async_update_dataset_name() -> None:
    async def run() -> respx.Route:
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.put("/datasetmetabase/updateDatasetName").mock(
                return_value=httpx.Response(200)
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.datasets.update_dataset_name(1, "Reporting data")
            return route

    assert asyncio.run(run()).calls.last.request.url.params["datasetName"] == "Reporting data"


def test_export_zip_csv_to_file_polls_then_downloads(tmp_path) -> None:
    import pytest

    from reportnet_api.resources.datasets_ext import ExportJobError

    poll = "/orchestrator/jobs/pollForJobStatus/9"
    dest = tmp_path / "out.zip"
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/v4/etlExport/1").mock(
            return_value=httpx.Response(
                200,
                json={"pollingUrl": poll + "?datasetId=1&dataflowId=2", "status": "Preparing file"},
            )
        )
        mock.get(poll).mock(
            side_effect=[
                httpx.Response(200, json={"status": "IN_PROGRESS"}),
                httpx.Response(
                    200,
                    json={
                        "status": "FINISHED",
                        "downloadUrl": (
                            "/orchestrator/jobs/downloadEtlExportedFile/9?datasetId=1&dataflowId=2"
                        ),
                    },
                ),
            ]
        )
        mock.get("/orchestrator/jobs/downloadEtlExportedFile/9").mock(
            return_value=httpx.Response(200, content=b"PK-zip")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.export_zip_csv_to_file(1, dataflow_id=2, dest=dest, poll_interval=0)
        assert dest.read_bytes() == b"PK-zip"

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/v4/etlExport/1").mock(
            return_value=httpx.Response(200, json={"pollingUrl": poll})
        )
        mock.get(poll).mock(return_value=httpx.Response(200, json={"status": "FAILED"}))
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(ExportJobError, match="FAILED"),
        ):
            client.datasets.export_zip_csv_to_file(1, dataflow_id=2, dest=dest, poll_interval=0)


def test_export_zip_csv_to_file_times_out(tmp_path) -> None:
    import pytest

    from reportnet_api.resources.datasets_ext import ExportJobError

    poll = "/orchestrator/jobs/pollForJobStatus/9"
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/v4/etlExport/1").mock(
            return_value=httpx.Response(200, json={"pollingUrl": poll})
        )
        mock.get(poll).mock(return_value=httpx.Response(200, json={"status": "QUEUED"}))
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(ExportJobError, match="did not finish"),
        ):
            client.datasets.export_zip_csv_to_file(
                1, dataflow_id=2, dest=tmp_path / "x.zip", poll_interval=0, timeout=0
            )


def test_async_export_zip_csv_to_file(tmp_path) -> None:
    poll = "/orchestrator/jobs/pollForJobStatus/9"
    dest = tmp_path / "out.zip"

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataset/v4/etlExport/1").mock(
                return_value=httpx.Response(200, json={"pollingUrl": poll})
            )
            mock.get(poll).mock(
                return_value=httpx.Response(
                    200, json={"status": "FINISHED", "downloadUrl": "/dl/9"}
                )
            )
            mock.get("/dl/9").mock(return_value=httpx.Response(200, content=b"PK"))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.datasets.export_zip_csv_to_file(
                    1, dataflow_id=2, dest=dest, poll_interval=0
                )

    asyncio.run(run())
    assert dest.read_bytes() == b"PK"


IMPORT_PATH = "/dataset/v2/importFileData/7"


def test_import_big_file_data_empty_body_returns_empty_dict(tmp_path: Path) -> None:
    f = tmp_path / "a.csv"
    f.write_text("a|b\n1|2\n")
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post(IMPORT_PATH).mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_big_file_data(
                7, f, dataflow_id=1, delimiter="|", preparation_code="c"
            )

    assert result == {}
    params = route.calls.last.request.url.params
    assert params["dataflowId"] == "1"
    assert params["delimiter"] == "|"
    assert params["code"] == "c"


def test_import_big_file_data_json_body_still_returned(tmp_path: Path) -> None:
    f = tmp_path / "a.csv"
    f.write_text("a\n1\n")
    body = {"jobId": 5, "pollingUrl": "/x"}
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post(IMPORT_PATH).mock(return_value=httpx.Response(200, json=body))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.datasets.import_big_file_data(7, f) == body


def test_import_big_file_data_forwards_timeout(tmp_path: Path) -> None:
    f = tmp_path / "a.csv"
    f.write_text("a\n1\n")
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post(IMPORT_PATH).mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.import_big_file_data(7, f, timeout=900.0)
    assert route.calls.last.request.extensions["timeout"]["read"] == 900.0


def test_import_big_file_data_default_timeout_kept(tmp_path: Path) -> None:
    f = tmp_path / "a.csv"
    f.write_text("a\n1\n")
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post(IMPORT_PATH).mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.import_big_file_data(7, f)
    assert route.calls.last.request.extensions["timeout"]["read"] == 60.0


def test_async_import_big_file_data_empty_body_and_timeout(tmp_path: Path) -> None:
    f = tmp_path / "a.csv"
    f.write_text("a\n1\n")

    async def run() -> tuple[dict[str, object], respx.Route]:
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(IMPORT_PATH).mock(return_value=httpx.Response(200))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                result = await client.datasets.import_big_file_data(7, f, timeout=900.0)
            return result, route

    result, route = asyncio.run(run())
    assert result == {}
    assert route.calls.last.request.extensions["timeout"]["read"] == 900.0
