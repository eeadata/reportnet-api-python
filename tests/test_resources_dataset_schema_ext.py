"""Tests for the hand-written dataset_schema_ext additions (hidden export/import endpoints)."""

import asyncio
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from reportnet_api import (
    AsyncReportnetClient,
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    ReportnetClient,
    ServerError,
)
from reportnet_api.jobs import JobError
from reportnet_api.resources import dataset_schema_ext
from reportnet_api.resources.dataset_schema_ext import SchemaImportError

BASE_URL = "https://api.reportnet.europa.eu"


def test_export_dataflow_schemas_zip(tmp_path: Path) -> None:
    dest = tmp_path / "dataflow_export_1619.zip"
    content = b"PK\x03\x04fake-zip-bytes"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataschema/export").mock(
            return_value=httpx.Response(200, content=content)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.dataset_schema.export_dataflow_schemas_zip(dataflow_id=4321, dest=dest)

    request = route.calls.last.request
    assert request.url.path == "/dataschema/export"
    assert request.url.params["dataflowId"] == "4321"
    assert request.headers["Accept"] == "*/*"
    assert dest.read_bytes() == content


def test_async_export_dataflow_schemas_zip(tmp_path: Path) -> None:
    dest = tmp_path / "dataflow_export_1619.zip"
    content = b"PK\x03\x04fake-zip-bytes"

    async def run() -> respx.Route:
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get("/dataschema/export").mock(
                return_value=httpx.Response(200, content=content)
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.dataset_schema.export_dataflow_schemas_zip(dataflow_id=4321, dest=dest)
            return route

    route = asyncio.run(run())
    request = route.calls.last.request
    assert request.url.params["dataflowId"] == "4321"
    assert request.headers["Accept"] == "*/*"
    assert dest.read_bytes() == content


def test_export_dataflow_schemas_zip_error_status_raises_and_skips_dest_write(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "out.zip"

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataschema/export").mock(return_value=httpx.Response(404, text="not found"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(NotFoundError) as exc_info:
                client.dataset_schema.export_dataflow_schemas_zip(dataflow_id=999, dest=dest)

    assert exc_info.value.status_code == 404
    assert not dest.exists()


def _schema_json(description: str = "", *, tables: int = 1, fields: int = 2) -> str:
    return json.dumps(
        {
            "description": description,
            "tableSchemas": [
                {
                    "nameTableSchema": f"T{i}",
                    "recordSchema": {"fieldSchema": [{"name": f"f{j}"} for j in range(fields)]},
                }
                for i in range(tables)
            ],
        }
    )


def _schema_files(
    zf: zipfile.ZipFile, name: str, description: str = "", *, complete: bool = True, rules: int = 1
) -> None:
    """One dataset schema's files: 1 table with 2 fields, `rules` rules, 1 unique."""
    zf.writestr(f"{name}.schema", _schema_json(description, tables=1 if complete else 0))
    zf.writestr(f"{name}.qcrules", json.dumps({"rules": [{}] * (rules if complete else 0)}))
    zf.writestr(f"{name}.unique", json.dumps([{}] * (1 if complete else 0)))


def _schema_zip(path: Path, names: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name in names:
            _schema_files(zf, name)
        zf.writestr("datasetSchemaNames.names", "{}")
    return path


def _export_bytes(
    content: str = "",
    names: tuple[str, ...] = ("IMPORTED_d9",),
    *,
    complete: bool = True,
    rules: int = 1,
) -> bytes:
    """A dataflow export holding `names`; `content` makes two exports differ."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            _schema_files(zf, name, content, complete=complete, rules=rules)
    return buf.getvalue()


def _designs(*ids: int, names: dict[int, str] | None = None) -> httpx.Response:
    """Dataflow details; ids >= 9 are named like the import's own datasets."""
    names = names or {}
    datasets = [
        {"id": i, "dataSetName": names.get(i, f"IMPORTED_d{i}" if i >= 9 else f"d{i}")} for i in ids
    ]
    return httpx.Response(200, json={"id": 5, "designDatasets": datasets})


def test_import_dataflow_schemas_zip(tmp_path: Path) -> None:
    upload = _schema_zip(tmp_path / "Schemas.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.dataset_schema.import_dataflow_schemas_zip(5, upload)

    request = route.calls.last.request
    assert request.url.params["dataflowId"] == "5"
    assert request.headers["Content-Type"].startswith("multipart/form-data")
    assert b'name="file"; filename="Schemas.zip"' in request.content


def test_import_dataflow_schemas_zip_needs_zip_name(tmp_path: Path) -> None:
    upload = _schema_zip(tmp_path / "Schemas.bin", ["A"])
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match=r"\.zip"):
            client.dataset_schema.import_dataflow_schemas_zip(5, upload)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Fake clock: the module's sleeps advance it instead of waiting."""
    now = [0.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    async def async_sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(dataset_schema_ext, "_monotonic", lambda: now[0])
    monkeypatch.setattr(dataset_schema_ext, "_sleep", sleep)
    monkeypatch.setattr(dataset_schema_ext, "_async_sleep", async_sleep)
    return now


def _wait(client: ReportnetClient, upload: Path, **kwargs: float) -> list[dict]:
    return client.dataset_schema.import_dataflow_schemas_zip_and_wait(
        5, upload, **{"poll_interval": 5, **kwargs}
    )


def test_import_and_wait_waits_for_datasets_then_stable_export(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A", "B"])
    two = ("IMPORTED_d10", "IMPORTED_d11")

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(
            side_effect=[_designs(1), _designs(1, 10), _designs(1, 10, 11), _designs(1, 11, 10)]
        )
        importing = mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        export = mock.get("/dataschema/export").mock(
            side_effect=[
                httpx.Response(200, content=_export_bytes("1", two)),
                httpx.Response(500, text="half-built"),
                httpx.Response(200, content=_export_bytes("2", two)),
                httpx.Response(200, content=_export_bytes("2", two)),
                httpx.Response(200, content=_export_bytes("2", two)),
            ]
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new = _wait(client, upload, settle=10)

    assert [d["id"] for d in new] == [10, 11]
    assert importing.call_count == 1
    # Changed, 5xx, changed, then the same twice over 10 s of settling.
    assert export.call_count == 5


def test_import_and_wait_needs_a_schema_in_the_zip(tmp_path: Path) -> None:
    upload = _schema_zip(tmp_path / "s.zip", [])
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match="no .schema"):
            _wait(client, upload)


def test_import_and_wait_refuses_missing_dataflow_details(tmp_path: Path) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.get("/dataflow/v1/5").mock(return_value=httpx.Response(200, content=b""))
        importing = mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="no dataflow details"):
                _wait(client, upload)

    assert not importing.called


def test_import_and_wait_counts_only_its_own_datasets(tmp_path: Path, clock: list[float]) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])
    others = {3: "Added by someone else", 4: "IMPORTED_d4"}

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(
            side_effect=[
                _designs(1, 4, names=others),
                _designs(1, 3, 4, names=others),
                httpx.Response(200, content=b""),  # swallowed error mid-wait
                _designs(1, 3, 4, 12, names=others),
                _designs(1, 3, 4, 12, names=others),
            ]
        )
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        mock.get("/dataschema/export").mock(
            return_value=httpx.Response(200, content=_export_bytes("x", ("IMPORTED_d12",)))
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new = _wait(client, upload, settle=5)

    assert [d["id"] for d in new] == [12]


def test_import_and_wait_treats_timeouts_and_broken_zips_as_changing(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9), _designs(9)])
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        export = mock.get("/dataschema/export").mock(
            side_effect=[
                httpx.Response(200, content=_export_bytes("x")),
                httpx.ReadTimeout("slow"),
                httpx.Response(200, content=_export_bytes("x")),
                httpx.Response(200, content=b"PK\x03\x04truncated"),
                httpx.Response(200, content=_export_bytes("x")),
                httpx.Response(200, content=_export_bytes("x")),
                httpx.Response(200, content=_export_bytes("x")),
            ]
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new = _wait(client, upload, settle=5)

    assert [d["id"] for d in new] == [9]
    # Neither the timeout nor the broken ZIP counted as "unchanged": the match must
    # then hold over two polls (10 s) after the last change.
    assert export.call_count == 7


def test_import_and_wait_times_out_without_datasets(tmp_path: Path, clock: list[float]) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(return_value=_designs(1))
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="0 of 1 datasets"):
                _wait(client, upload, timeout=20)


def test_import_and_wait_times_out_while_export_changes(tmp_path: Path, clock: list[float]) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])
    exports = iter(range(1000))

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9)])
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        mock.get("/dataschema/export").mock(
            side_effect=lambda request: httpx.Response(
                200, content=_export_bytes(str(next(exports)))
            )
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="still changing"):
                _wait(client, upload, settle=10, timeout=60)


def test_schema_import_error_is_a_job_error() -> None:
    assert issubclass(SchemaImportError, JobError)


def test_import_and_wait_propagates_auth_errors(tmp_path: Path, clock: list[float]) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(return_value=_designs())
        mock.post("/dataschema/import").mock(return_value=httpx.Response(403, text="no"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ForbiddenError):
                _wait(client, upload)


def test_async_import_and_wait(tmp_path: Path, clock: list[float]) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    async def run() -> tuple[list[dict], respx.Route]:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataflow/v1/5").mock(
                side_effect=[_designs(1), _designs(1), _designs(1, 9), _designs(1, 9)]
            )
            importing = mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
            mock.get("/dataschema/export").mock(
                return_value=httpx.Response(200, content=_export_bytes("x"))
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                new = await client.dataset_schema.import_dataflow_schemas_zip_and_wait(
                    5, upload, poll_interval=5, settle=5
                )
            return new, importing

    new, importing = asyncio.run(run())
    assert [d["id"] for d in new] == [9]
    assert importing.calls.last.request.url.params["dataflowId"] == "5"


def test_import_and_wait_timeout_starts_after_the_upload(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    def slow_upload(request: httpx.Request) -> httpx.Response:
        clock[0] += 1000  # longer than the whole timeout
        return httpx.Response(200)

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(
            side_effect=[_designs(), _designs(), _designs(9), _designs(9)]
        )
        mock.post("/dataschema/import").mock(side_effect=slow_upload)
        mock.get("/dataschema/export").mock(
            return_value=httpx.Response(200, content=_export_bytes("x"))
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new = _wait(client, upload, settle=5, timeout=60)

    assert [d["id"] for d in new] == [9]


def test_import_and_wait_keeps_polling_through_transient_errors(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(
            side_effect=[
                _designs(),
                httpx.ReadTimeout("slow"),
                httpx.Response(503, text="busy"),
                httpx.ConnectError("reset"),
                _designs(9),
                httpx.Response(502, text="gateway"),  # final refetch: keep what was seen
            ]
        )
        importing = mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        mock.get("/dataschema/export").mock(
            return_value=httpx.Response(200, content=_export_bytes("x"))
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new = _wait(client, upload, settle=5)

    assert [d["id"] for d in new] == [9]
    assert importing.call_count == 1


def test_import_and_wait_before_snapshot_stays_strict(tmp_path: Path) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.get("/dataflow/v1/5").mock(return_value=httpx.Response(503, text="busy"))
        importing = mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ServerError):
                _wait(client, upload)

    assert not importing.called


def test_async_import_and_wait_keeps_polling_through_transient_errors(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    async def run() -> list[dict]:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataflow/v1/5").mock(
                side_effect=[
                    _designs(),
                    httpx.ReadTimeout("slow"),
                    httpx.Response(500, text="oops"),
                    _designs(9),
                    _designs(9),
                ]
            )
            mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
            mock.get("/dataschema/export").mock(
                return_value=httpx.Response(200, content=_export_bytes("x"))
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                return await client.dataset_schema.import_dataflow_schemas_zip_and_wait(
                    5, upload, poll_interval=5, settle=5
                )

    assert [d["id"] for d in asyncio.run(run())] == [9]


def test_import_and_wait_timeout_names_the_last_poll_error(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(
            side_effect=[_designs()] + [httpx.Response(500, text="db down")] * 10
        )
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="last poll error: 500") as exc_info:
                _wait(client, upload, timeout=20)

    assert isinstance(exc_info.value.__cause__, ServerError)


@pytest.mark.parametrize("status", [401, 403])
def test_import_and_wait_auth_error_says_import_may_still_run(
    tmp_path: Path, clock: list[float], status: int
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(
            side_effect=[_designs(), httpx.Response(status, text="expired")]
        )
        importing = mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="may have started") as exc_info:
                _wait(client, upload)

    assert isinstance(exc_info.value.__cause__, (AuthenticationError, ForbiddenError))
    assert str(status) in str(exc_info.value)
    assert importing.call_count == 1


def test_import_and_wait_permanent_transport_error_is_not_retried(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9)])
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        export = mock.get("/dataschema/export").mock(
            side_effect=httpx.UnsupportedProtocol("bad scheme")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="may have started") as exc_info:
                _wait(client, upload)

    assert isinstance(exc_info.value.__cause__, httpx.UnsupportedProtocol)
    assert export.call_count == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("dropped")])
def test_upload_broken_off_after_sending_may_have_started(tmp_path: Path, error: Exception) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        importing = mock.post("/dataschema/import").mock(side_effect=error)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="may have started") as exc_info:
                client.dataset_schema.import_dataflow_schemas_zip(5, upload)

    assert exc_info.value.__cause__ is error
    assert importing.call_count == 1  # never retried


def test_upload_never_sent_raises_the_transport_error(tmp_path: Path) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataschema/import").mock(side_effect=httpx.ConnectError("refused"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(httpx.ConnectError):
                client.dataset_schema.import_dataflow_schemas_zip(5, upload)


def test_async_upload_broken_off_may_have_started(tmp_path: Path) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/dataschema/import").mock(side_effect=httpx.ReadTimeout("slow"))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.dataset_schema.import_dataflow_schemas_zip(5, upload)

    with pytest.raises(SchemaImportError, match="may have started"):
        asyncio.run(run())


def test_async_import_and_wait_auth_error_says_import_may_still_run(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataflow/v1/5").mock(
                side_effect=[_designs(), httpx.Response(401, text="expired")]
            )
            mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.dataset_schema.import_dataflow_schemas_zip_and_wait(5, upload)

    with pytest.raises(SchemaImportError, match="may have started") as exc_info:
        asyncio.run(run())
    assert isinstance(exc_info.value.__cause__, AuthenticationError)


def test_import_and_wait_keeps_waiting_while_an_unchanged_export_is_incomplete(
    tmp_path: Path, clock: list[float]
) -> None:
    # The import's silent middle: the export does not change for a while but the
    # dataset still has no tables. That must not end the wait.
    upload = _schema_zip(tmp_path / "s.zip", ["A"])
    half = httpx.Response(200, content=_export_bytes("h", complete=False))
    full = httpx.Response(200, content=_export_bytes("f"))

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9), _designs(9)])
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        export = mock.get("/dataschema/export").mock(side_effect=[half] * 4 + [full] * 3)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new = _wait(client, upload, settle=60)

    assert [d["id"] for d in new] == [9]
    assert export.call_count == 7  # 4 incomplete, then complete and quiet for two polls


def test_import_and_wait_raises_when_the_export_stalls_incomplete(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9)])
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        mock.get("/dataschema/export").mock(
            return_value=httpx.Response(200, content=_export_bytes("h", complete=False))
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match="stalled or failed") as exc_info:
                _wait(client, upload, settle=20, timeout=600)

    assert "IMPORTED_d9 has 0/1 tables" in str(exc_info.value)
    assert "0/1 rules" in str(exc_info.value)


def test_import_and_wait_counts_qc_rules(tmp_path: Path, clock: list[float]) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])  # 1 rule

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9)])
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        mock.get("/dataschema/export").mock(
            return_value=httpx.Response(200, content=_export_bytes("r", rules=0))
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match=r"0/1 rules") as exc_info:
                _wait(client, upload, settle=20, timeout=600)

    assert "tables" not in str(exc_info.value)  # tables, fields and uniques did match


def test_import_and_wait_timeout_names_what_is_missing(tmp_path: Path, clock: list[float]) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])
    exports = iter(range(1000))

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9)])
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        mock.get("/dataschema/export").mock(
            side_effect=lambda request: httpx.Response(
                200, content=_export_bytes(str(next(exports)), complete=False)
            )
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(SchemaImportError, match=r"does not match.*0/1 tables"):
                _wait(client, upload, settle=100, timeout=60)


def test_async_import_and_wait_raises_when_the_export_stalls_incomplete(
    tmp_path: Path, clock: list[float]
) -> None:
    upload = _schema_zip(tmp_path / "s.zip", ["A"])

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataflow/v1/5").mock(side_effect=[_designs(), _designs(9)])
            mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
            mock.get("/dataschema/export").mock(
                return_value=httpx.Response(200, content=_export_bytes("h", complete=False))
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await client.dataset_schema.import_dataflow_schemas_zip_and_wait(
                    5, upload, poll_interval=5, settle=20
                )

    with pytest.raises(SchemaImportError, match="0/1 tables"):
        asyncio.run(run())


def test_import_and_wait_pairs_renamed_datasets_with_their_source(
    tmp_path: Path, clock: list[float]
) -> None:
    # `IMPORTED_A (1)`: the name was taken, so the backend adds a counter.
    upload = _schema_zip(tmp_path / "s.zip", ["A"])
    renamed = {9: "IMPORTED_A (1)"}

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/5").mock(
            side_effect=[_designs(), _designs(9, names=renamed), _designs(9, names=renamed)]
        )
        mock.post("/dataschema/import").mock(return_value=httpx.Response(200))
        mock.get("/dataschema/export").mock(
            return_value=httpx.Response(200, content=_export_bytes("x", ("IMPORTED_A (1)",)))
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new = _wait(client, upload, settle=20)

    assert [d["id"] for d in new] == [9]


def test_import_wait_pairs_by_name_not_by_order() -> None:
    small = dataset_schema_ext._Shape((("T", 1),), 0, 0, 0, 0)
    big = dataset_schema_ext._Shape((("T", 1), ("U", 3)), 2, 5, 1, 1)
    wait = dataset_schema_ext._ImportWait(5, {"A": small, "B": big}, set(), 60, 600)
    wait.new = [
        {"id": 9, "dataSetName": "IMPORTED_B"},
        {"id": 10, "dataSetName": "IMPORTED_A"},
    ]

    assert wait.mismatches({"IMPORTED_B": big, "IMPORTED_A": small}) == []
    swapped = wait.mismatches({"IMPORTED_B": small, "IMPORTED_A": big})
    assert any(m.startswith("IMPORTED_B has 1/2 tables") for m in swapped)
    assert wait.mismatches({"IMPORTED_B": big}) == ["IMPORTED_A has no files in the export"]
    assert wait.mismatches(None) == ["export unreadable"]


def test_import_and_wait_rejects_an_unreadable_upload(tmp_path: Path) -> None:
    upload = tmp_path / "s.zip"
    with zipfile.ZipFile(upload, "w") as zf:
        zf.writestr("A.schema", "not json")
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match="not a readable schema export"):
            client.dataset_schema.import_dataflow_schemas_zip_and_wait(5, upload)
