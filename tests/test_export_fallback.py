"""easy.export_to_file on a non-data-lake dataflow: the v3 fallback.

Newer backends (branch `MasterOneVersion`) fail the v4/v5 ZIP export jobs when
the dataflow is not a data lake; only the v3 job (a ZIP of ETL JSON) works there.
"""

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from reportnet_api import ReportnetClient, easy
from reportnet_api.jobs import JobError, _check

BASE_URL = "https://api.reportnet.europa.eu"
V4_POLL = "/orchestrator/jobs/pollForJobStatus/41"
V3_POLL = "/orchestrator/jobs/pollForJobStatus/43"
V3_DOWNLOAD = "/orchestrator/jobs/downloadEtlExportedFile/43"
# The backend's exact text, typographic quote and dash included.
REFUSED_INFO = (
    "ETL Export v4 isn’t compatible with non–big data dataflows. "  # noqa: RUF001
    "Please use a supported export version."
)
SCHEMA = {
    "tableSchemas": [
        {
            "idTableSchema": "t1",
            "nameTableSchema": "TestTable",
            "recordSchema": {
                "fieldSchema": [
                    {"name": "Id", "type": "NUMBER_INTEGER"},
                    {"name": "Text", "type": "TEXT"},
                    {"name": "Note", "type": "TEXTAREA"},
                ]
            },
        },
        {
            "idTableSchema": "t2",
            "nameTableSchema": "Empty",
            "recordSchema": {"fieldSchema": [{"name": "Code", "type": "TEXT"}]},
        },
    ]
}
ETL_JSON = {
    "tables": [
        {
            "totalRecords": 2,
            "tableName": "TestTable",
            "records": [
                {
                    "id_table_schema": "t1",
                    "id_record": "R1",
                    "countryCode": None,
                    "fields": [  # not in schema order on purpose
                        {"fieldName": "Text", "value": "a, b", "field_value_id": None},
                        {"fieldName": "Id", "value": "1", "field_value_id": None},
                        {"fieldName": "Note", "value": "two\nlines", "field_value_id": None},
                    ],
                },
                {
                    "id_table_schema": "t1",
                    "id_record": "R2",
                    "countryCode": None,
                    "fields": [{"fieldName": "Id", "value": "2", "field_value_id": None}],
                },
            ],
        },
        {"totalRecords": 0, "tableName": "Empty", "records": []},
    ]
}


def _zip_of(name: str, payload: dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, json.dumps(payload))
    return buf.getvalue()


def _mock_refused_v4(mock: respx.MockRouter, route: str, *, big_data: bool) -> None:
    mock.get(route).mock(
        return_value=httpx.Response(200, json={"pollingUrl": V4_POLL + "?datasetId=1"})
    )
    mock.get(V4_POLL).mock(
        return_value=httpx.Response(200, json={"status": "FAILED", "info": REFUSED_INFO})
    )
    mock.get("/dataflow/v1/2").mock(
        return_value=httpx.Response(200, json={"id": 2, "bigData": big_data})
    )


def test_job_error_carries_status_and_info() -> None:
    with pytest.raises(JobError) as caught:
        _check({"status": "FAILED", "info": "why"})
    assert (caught.value.status, caught.value.info) == ("FAILED", "why")
    assert JobError("plain").status is None


def test_non_lake_csv_export_falls_back_to_v3(tmp_path: Path) -> None:
    dest = tmp_path / "out.zip"
    with respx.mock(base_url=BASE_URL) as mock:
        _mock_refused_v4(mock, "/dataset/v4/etlExport/1", big_data=False)
        v3 = mock.get("/dataset/v3/etlExport/1").mock(
            return_value=httpx.Response(200, json={"pollingUrl": V3_POLL + "?datasetId=1"})
        )
        mock.get(V3_POLL).mock(
            return_value=httpx.Response(
                200, json={"status": "FINISHED", "downloadUrl": V3_DOWNLOAD + "?datasetId=1"}
            )
        )
        mock.get(V3_DOWNLOAD).mock(
            return_value=httpx.Response(200, content=_zip_of("43.json", ETL_JSON))
        )
        mock.get("/dataschema/v1/datasetId/1").mock(return_value=httpx.Response(200, json=SCHEMA))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert easy.export_to_file(client, 1, 2, dest, table_schema_id="t1") == dest

    assert v3.calls.last.request.url.params["tableSchemaId"] == "t1"
    assert v3.calls.last.request.url.params["dataflowId"] == "2"
    with zipfile.ZipFile(dest) as z:
        assert sorted(z.namelist()) == ["Empty.csv", "TestTable.csv"]
        rows = list(csv.reader(io.StringIO(z.read("TestTable.csv").decode("utf-8"), newline="")))
        empty = z.read("Empty.csv").decode("utf-8")
    assert rows == [["Id", "Text", "Note"], ["1", "a, b", "two\nlines"], ["2", "", ""]]
    assert empty.splitlines() == ["Code"]
    assert not list(tmp_path.glob("*.part"))


def test_lake_dataflow_failure_is_not_retried_with_v3(tmp_path: Path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        _mock_refused_v4(mock, "/dataset/v4/etlExport/1", big_data=True)
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(JobError, match="isn’t compatible"),  # noqa: RUF001 - backend text
        ):
            easy.export_to_file(client, 1, 2, tmp_path / "out.zip")
    assert not (tmp_path / "out.zip").exists()


def test_non_lake_parquet_export_explains(tmp_path: Path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        _mock_refused_v4(mock, "/dataset/v5/etlExport/1", big_data=False)
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(JobError, match="file_format='csv'"),
        ):
            easy.export_to_file(client, 1, 2, tmp_path / "out.zip", file_format="parquet")


def test_timeout_is_not_retried_with_v3(tmp_path: Path) -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.get("/dataset/v4/etlExport/1").mock(
            return_value=httpx.Response(200, json={"pollingUrl": V4_POLL + "?datasetId=1"})
        )
        mock.get(V4_POLL).mock(return_value=httpx.Response(200, json={"status": "IN_PROGRESS"}))
        lake = mock.get("/dataflow/v1/2").mock(return_value=httpx.Response(200, json={}))
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(JobError),
        ):
            easy.export_to_file(client, 1, 2, tmp_path / "out.zip", timeout=0)
    assert not lake.called
