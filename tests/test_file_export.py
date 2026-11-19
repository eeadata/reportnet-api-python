"""Tests for the notification-driven table/dataset export routes and easy.export_table."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient, easy
from reportnet_api.jobs import JobError
from reportnet_api.resources.datasets_ext import _dataset_file_name

BASE_URL = "https://api.reportnet.europa.eu"
DL = "/dataset/1/downloadFileDL"


def test_start_table_export_sends_params_and_filter_body() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/exportFile").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.start_table_export(
                1, mime_type="xlsx", table_schema_id="abc", level_error=["ERROR"], big_data=False
            )
    request = route.calls.last.request
    assert dict(request.url.params) == {
        "datasetId": "1",
        "mimeType": "xlsx",
        "tableSchemaId": "abc",
    }
    assert json.loads(request.content) == {"levelError": ["ERROR"], "idRules": "", "fieldValue": ""}


def test_big_data_variants_use_dl_routes_and_qc_codes(tmp_path: Path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        table = mock.post("/dataset/exportFileDL").mock(return_value=httpx.Response(200))
        dataset = mock.get("/dataset/1/exportDatasetFileDL").mock(return_value=httpx.Response(200))
        dl = mock.get("/dataset/1/downloadFileDL").mock(
            return_value=httpx.Response(200, content=b"x")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.start_table_export(1, big_data=True)
            client.datasets.start_dataset_export(1, mime_type="zip csv", big_data=True)
            assert client.datasets.fetch_export_file(
                1, "T.csv", dest=tmp_path / "x.csv", big_data=True
            )
    assert json.loads(table.calls.last.request.content)["qcCodes"] == ""
    assert dataset.calls.last.request.url.params["mimeType"] == "zip csv"
    assert dl.called


def test_fetch_returns_false_for_empty_body_and_leaves_no_file(tmp_path: Path) -> None:
    dest = tmp_path / "t.csv"
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(DL).mock(return_value=httpx.Response(200, content=b""))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.datasets.fetch_export_file(1, "T.csv", dest=dest) is False
    assert list(tmp_path.iterdir()) == []


def test_fetch_saves_and_returns_true(tmp_path: Path) -> None:
    dest = tmp_path / "t.csv"
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get(DL).mock(return_value=httpx.Response(200, content=b"a,b\n1,2\n"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.datasets.fetch_export_file(1, "T.csv", dest=dest) is True
    assert dest.read_bytes() == b"a,b\n1,2\n"
    assert route.calls.last.request.url.params["fileName"] == "T.csv"
    assert [p.name for p in tmp_path.iterdir()] == ["t.csv"]  # no .part left


def test_export_table_to_file_polls_until_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("reportnet_api.resources.datasets_ext.time.sleep", lambda s: None)
    dest = tmp_path / "t.csv"
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataset/exportFileDL").mock(return_value=httpx.Response(200))
        down = mock.get(DL).mock(
            side_effect=[
                httpx.Response(200),  # stale-file probe before the export starts
                httpx.Response(200),
                httpx.Response(200),
                httpx.Response(200, content=b"ok"),
            ]
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.export_table_to_file(
                1, table_name="TestTable", dest=dest, table_schema_id="x"
            )
    assert down.call_count == 4
    assert down.calls.last.request.url.params["fileName"] == "TestTable.csv"
    assert dest.read_bytes() == b"ok"


def test_export_times_out_with_job_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("reportnet_api.resources.datasets_ext.time.sleep", lambda s: None)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataset/exportFileDL").mock(return_value=httpx.Response(200))
        mock.get(DL).mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError, match="not ready"):
                client.datasets.export_table_to_file(
                    1, table_name="T", table_schema_id="x", dest=tmp_path / "t.csv", timeout=0
                )


def test_dataset_file_names() -> None:
    assert _dataset_file_name("Test", "csv") == "Test.csv"
    assert _dataset_file_name("Test", "zip csv") == "Test.zip"
    assert _dataset_file_name("Test", "zip xlsx") == "Test.zip"
    assert _dataset_file_name("Test", "xlsx") == "Test.xlsx"


def test_async_export_table_and_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("reportnet_api.resources.datasets_ext.asyncio.sleep", no_sleep)

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/dataset/exportFileDL").mock(return_value=httpx.Response(200))
            mock.get("/dataset/1/exportDatasetFileDL").mock(return_value=httpx.Response(200))
            empty, ok = httpx.Response(200), httpx.Response(200, content=b"ok")
            mock.get(DL).mock(side_effect=[empty, empty, ok, empty, ok])
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.datasets.export_table_to_file(
                    1, table_name="T", dest=tmp_path / "t.csv", table_schema_id="x"
                )
                await client.datasets.export_dataset_to_file(
                    1, dataset_name="Test", dest=tmp_path / "d.csv"
                )

    asyncio.run(run())
    assert (tmp_path / "t.csv").read_bytes() == b"ok"
    assert (tmp_path / "d.csv").read_bytes() == b"ok"


def test_easy_export_table_resolves_name_and_rejects_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("pandas")
    monkeypatch.setattr("reportnet_api.resources.datasets_ext.time.sleep", lambda s: None)
    schema = {
        "tableSchemas": [{"idTableSchema": "abc", "nameTableSchema": "TestTable"}],
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataschema/v1/datasetId/1").mock(return_value=httpx.Response(200, json=schema))
        export = mock.post("/dataset/exportFileDL").mock(return_value=httpx.Response(200))
        mock.get(DL).mock(side_effect=[httpx.Response(200), httpx.Response(200, content=b"x")])
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            out = easy.export_table(client, 1, "TestTable", tmp_path / "t.csv")
            with pytest.raises(ValueError, match="No table named 'Nope'"):
                easy.export_table(client, 1, "Nope", tmp_path / "n.csv")
    assert out == tmp_path / "t.csv"
    assert export.calls.last.request.url.params["tableSchemaId"] == "abc"


def test_existing_server_file_triggers_stale_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("reportnet_api.resources.datasets_ext.time.sleep", lambda s: None)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataset/exportFileDL").mock(return_value=httpx.Response(200))
        mock.get(DL).mock(return_value=httpx.Response(200, content=b"old"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.warns(RuntimeWarning, match="already exists on the server"):
                client.datasets.export_table_to_file(
                    1, table_name="T", table_schema_id="x", dest=tmp_path / "t.csv"
                )
    assert (tmp_path / "t.csv").read_bytes() == b"old"


def test_404_while_polling_means_not_ready_and_leaves_no_file(tmp_path: Path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(DL).mock(return_value=httpx.Response(404))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.datasets.fetch_export_file(1, "T.csv", dest=tmp_path / "t.csv") is False
    assert list(tmp_path.iterdir()) == []


def test_other_errors_while_polling_propagate(tmp_path: Path) -> None:
    from reportnet_api import ServerError

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(DL).mock(return_value=httpx.Response(500))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ServerError):
                client.datasets.fetch_export_file(1, "T.csv", dest=tmp_path / "t.csv")
    assert list(tmp_path.iterdir()) == []


def test_sleep_is_clamped_to_remaining_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("reportnet_api.resources.datasets_ext.time.sleep", sleeps.append)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataset/exportFileDL").mock(return_value=httpx.Response(200))
        mock.get(DL).mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError):
                client.datasets.export_table_to_file(
                    1,
                    table_name="T",
                    table_schema_id="x",
                    dest=tmp_path / "t.csv",
                    poll_interval=50,
                    timeout=1,
                )
    assert sleeps and all(0 < x <= 1 for x in sleeps)


@pytest.mark.parametrize("bad", ["", ".csv", "zip csv", " csv"])
def test_table_export_rejects_non_extension_mime(tmp_path: Path, bad: str) -> None:
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match="bare file extension"):
            client.datasets.export_table_to_file(
                1, table_name="T", table_schema_id="x", dest=tmp_path / "t", mime_type=bad
            )


def test_table_schema_id_is_required(tmp_path: Path) -> None:
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(TypeError):
            client.datasets.export_table_to_file(  # type: ignore[call-arg]
                1, table_name="T", dest=tmp_path / "t"
            )


def test_easy_export_table_validates_format_and_duplicate_names(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    schema = {
        "tableSchemas": [
            {"idTableSchema": "a", "nameTableSchema": "Dup"},
            {"idTableSchema": "b", "nameTableSchema": "Dup"},
        ]
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataschema/v1/datasetId/1").mock(return_value=httpx.Response(200, json=schema))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ValueError, match="bare extension"):
                easy.export_table(client, 1, "Dup", tmp_path / "x", file_format=".csv")
            with pytest.raises(ValueError, match="2 tables named"):
                easy.export_table(client, 1, "Dup", tmp_path / "x")
