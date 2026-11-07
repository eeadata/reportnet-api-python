"""Request-shape tests for reportnet_api/resources/datasets.py (40 endpoints).

`import_file_data` (upload) and `download_historic_releases_csv`-style
streaming are covered in tests/test_upload_download.py; the `datasets`
upload endpoints below still get their own request-shape assertions since
each hits a distinct URL/param set.
"""

from pathlib import Path

import httpx
import pytest
import respx

from reportnet_api import ReportnetClient
from reportnet_api.models import generated

BASE_URL = "https://api.reportnet.europa.eu"


def test_check_import_process() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/checkImportProcess/42").mock(
            return_value=httpx.Response(200, json={"importInProgress": True})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.check_import_process(dataset_id=42)

    request = route.calls.last.request
    assert request.url.path == "/dataset/checkImportProcess/42"
    assert result.importInProgress is True


def test_convert_iceberg_to_parquet_tables() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/convertIcebergToParquetTables/1").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.convert_iceberg_to_parquet_tables(
                dataflow_id=2, dataset_id=1, provider_id=3, table_schema_ids=["a", "b"]
            )

    request = route.calls.last.request
    assert request.url.path == "/dataset/convertIcebergToParquetTables/1"
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["providerId"] == "3"
    assert request.url.params.get_list("tableSchemaIds") == ["a", "b"]
    assert result is None


def test_convert_parquet_to_iceberg_tables() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/convertParquetToIcebergTables/1").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.convert_parquet_to_iceberg_tables(dataflow_id=2, dataset_id=1)

    request = route.calls.last.request
    assert request.url.path == "/dataset/convertParquetToIcebergTables/1"
    assert request.url.params["dataflowId"] == "2"
    assert result is None


def test_create_empty_tables_v3() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/1/createEmptyTablesV3").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.create_empty_tables_v3(dataset_id=1, table_schema_id="t1")

    request = route.calls.last.request
    assert request.url.path == "/dataset/1/createEmptyTablesV3"
    assert request.url.params["tableSchemaId"] == "t1"
    assert result is None


def test_create_public_files() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/createPublicFiles").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.create_public_files(dataflow_id=2, provider_id=3)

    request = route.calls.last.request
    assert request.url.path == "/dataset/createPublicFiles"
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["providerId"] == "3"
    assert result is None


def test_delete_attachment() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.delete("/dataset/v1/1/field/f1/attachment").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.delete_attachment(dataset_id=1, field_id="f1", record_id="r1")

    request = route.calls.last.request
    assert request.method == "DELETE"
    assert request.url.path == "/dataset/v1/1/field/f1/attachment"
    assert request.url.params["recordId"] == "r1"
    assert result is None


def test_delete_dataset_data() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.delete("/dataset/v1/1/deleteDatasetData").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.delete_dataset_data(dataset_id=1, delete_prefilled_tables=True)

    request = route.calls.last.request
    assert request.url.path == "/dataset/v1/1/deleteDatasetData"
    assert request.url.params["deletePrefilledTables"] == "true"
    assert result == {"ok": True}


def test_delete_table_data() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.delete("/dataset/v1/1/deleteTableData/t1").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.delete_table_data(dataset_id=1, table_schema_id="t1")

    request = route.calls.last.request
    assert request.url.path == "/dataset/v1/1/deleteTableData/t1"
    assert result == {"ok": True}


def test_download_imported_file(tmp_path: Path) -> None:
    dest = tmp_path / "imported.csv"
    content = b"a,b\n1,2\n"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/download-imported-file").mock(
            return_value=httpx.Response(200, content=content)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.download_imported_file(
                dataflow_id=2, dataset_id=1, file_name="f.csv", dest=dest
            )

    request = route.calls.last.request
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["datasetId"] == "1"
    assert request.url.params["fileName"] == "f.csv"
    assert dest.read_bytes() == content
    assert result is None


def test_duplicate_field_value_exists() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/duplicateFieldValueExists/1").mock(
            return_value=httpx.Response(200, json=True)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.duplicate_field_value_exists(
                dataset_id=1, table_schema_id="t1", field_vo=generated.FieldVO(id="f1")
            )

    request = route.calls.last.request
    assert request.url.path == "/dataset/duplicateFieldValueExists/1"
    assert request.url.params["tableSchemaId"] == "t1"
    assert result is True


def test_etl_export_dataset(tmp_path: Path) -> None:
    dest = tmp_path / "out.zip"
    content = b"data"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/v1/1/etlExport").mock(
            return_value=httpx.Response(200, content=content)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.etl_export_dataset(dataset_id=1, dest=dest, dataflow_id=2)

    request = route.calls.last.request
    assert request.url.path == "/dataset/v1/1/etlExport"
    assert request.url.params["dataflowId"] == "2"
    assert dest.read_bytes() == content
    assert result is None


def test_etl_export_dataset_v2(tmp_path: Path) -> None:
    dest = tmp_path / "out.zip"
    content = b"data"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/v2/etlExport/1").mock(
            return_value=httpx.Response(200, content=content)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.etl_export_dataset_v2(dataset_id=1, dest=dest, dataflow_id=2)

    request = route.calls.last.request
    assert request.url.path == "/dataset/v2/etlExport/1"
    assert dest.read_bytes() == content
    assert result is None


def test_etl_export_dataset_with_job() -> None:
    job = {"pollingUrl": "/orchestrator/jobs/pollForJobStatus/1", "status": "Preparing file"}

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/v3/etlExport/1").mock(return_value=httpx.Response(200, json=job))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.etl_export_dataset_with_job(dataset_id=1, dataflow_id=2)

    request = route.calls.last.request
    assert request.url.path == "/dataset/v3/etlExport/1"
    assert result == job


def test_etl_export_zip_csv() -> None:
    job = {"pollingUrl": "/orchestrator/jobs/pollForJobStatus/1", "status": "Preparing file"}

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/v4/etlExport/1").mock(return_value=httpx.Response(200, json=job))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.etl_export_zip_csv(dataset_id=1, dataflow_id=2)

    request = route.calls.last.request
    assert request.url.path == "/dataset/v4/etlExport/1"
    assert result == job


def test_etl_export_zip_parquet() -> None:
    job = {"pollingUrl": "/orchestrator/jobs/pollForJobStatus/1", "status": "Preparing file"}

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/v5/etlExport/1").mock(return_value=httpx.Response(200, json=job))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.etl_export_zip_parquet(dataset_id=1, dataflow_id=2)

    request = route.calls.last.request
    assert request.url.path == "/dataset/v5/etlExport/1"
    assert result == job


def test_etl_import_dataset() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/v1/1/etlImport").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.etl_import_dataset(
                dataset_id=1,
                dataflow_id=2,
                etl_dataset_vo=generated.ETLDatasetVO(),
                replace_data=True,
            )

    request = route.calls.last.request
    assert request.url.path == "/dataset/v1/1/etlImport"
    assert request.url.params["replaceData"] == "true"
    assert result == {"status": "ok"}


def test_etl_import_dataset_dl() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/1/etlImportDL").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.etl_import_dataset_dl(
                dataflow_id=2, dataset_id=1, delimiter=",", file_path_in_s3="s3://bucket/f.csv"
            )

    request = route.calls.last.request
    assert request.url.path == "/dataset/1/etlImportDL"
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["delimiter"] == ","
    assert request.content == b"s3://bucket/f.csv"
    assert request.headers["content-type"] == "text/plain"
    assert result == {"status": "ok"}


def test_generate_import_presigned_url() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/1/generateImportPresignedUrl").mock(
            return_value=httpx.Response(200, json={"jobId": 5})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.generate_import_presigned_url(
                dataset_id=1, dataflow_id=2, file_name="f.csv", etl_import=False
            )

    request = route.calls.last.request
    assert request.url.path == "/dataset/1/generateImportPresignedUrl"
    assert request.url.params["fileName"] == "f.csv"
    assert request.url.params["etlImport"] == "false"
    assert result.jobId == 5


def test_get_attachment(tmp_path: Path) -> None:
    dest = tmp_path / "attachment.bin"
    content = b"attachment-bytes"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/v1/1/field/f1/attachment").mock(
            return_value=httpx.Response(200, content=content)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.get_attachment(
                dataset_id=1, field_id="f1", dest=dest, dataflow_id=2, record_id="r1"
            )

    request = route.calls.last.request
    assert request.url.path == "/dataset/v1/1/field/f1/attachment"
    assert request.url.params["recordId"] == "r1"
    assert dest.read_bytes() == content
    assert result is None


def test_get_available_for_manual_editing_tables() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/getAvailableForManualEditingTables/1").mock(
            return_value=httpx.Response(200, json=[{"idTableSchema": "t1"}])
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.get_available_for_manual_editing_tables(dataset_id=1)

    request = route.calls.last.request
    assert request.url.path == "/dataset/getAvailableForManualEditingTables/1"
    assert result[0].idTableSchema == "t1"


def test_get_iceberg_tables() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/getIcebergTables").mock(
            return_value=httpx.Response(200, json=[{"id": 1}])
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.get_iceberg_tables(dataflow_id=2, dataset_id=1)

    request = route.calls.last.request
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["datasetId"] == "1"
    assert result[0].id == 1


def test_get_import_related_statistics() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/getImportRelatedStatistics/1").mock(
            return_value=httpx.Response(200, json={"stat": 1})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.get_import_related_statistics(dataset_id=1)

    request = route.calls.last.request
    assert request.url.path == "/dataset/getImportRelatedStatistics/1"
    assert result == {"stat": 1}


def test_get_record_geometry() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/v1/1/record/r1/geometry").mock(
            return_value=httpx.Response(200, text="POINT(0 0)")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.get_record_geometry(
                dataflow_id=2, dataset_id=1, field_id="f1", id_table_schema="t1", record_id="r1"
            )

    request = route.calls.last.request
    assert request.url.path == "/dataset/v1/1/record/r1/geometry"
    assert request.url.params["fieldId"] == "f1"
    assert request.url.params["idTableSchema"] == "t1"
    assert result == "POINT(0 0)"


def test_get_released_dataset_data_info() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/getReleasedDatasetDataInfo").mock(
            return_value=httpx.Response(200, json={"hasReleased": True})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.get_released_dataset_data_info(
                collection_dataset_id=1, provider_code="p1", table_schema_id="t1"
            )

    request = route.calls.last.request
    assert request.url.params["collectionDatasetId"] == "1"
    assert request.url.params["providerCode"] == "p1"
    assert result.hasReleased is True


def test_import_big_file_data(tmp_path: Path) -> None:
    src = tmp_path / "big.csv"
    src.write_text("a,b\n1,2\n")

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/v2/importFileData/1").mock(
            return_value=httpx.Response(200, json={"jobId": 1})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_big_file_data(dataset_id=1, file=src, delimiter=",")

    request = route.calls.last.request
    assert request.url.path == "/dataset/v2/importFileData/1"
    assert request.url.params["delimiter"] == ","
    assert b'filename="big.csv"' in request.content
    assert result == {"jobId": 1}


def test_is_iceberg_table_created() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/isIcebergTableCreated/1/t1").mock(
            return_value=httpx.Response(200, json=True)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.is_iceberg_table_created(dataset_id=1, table_schema_id="t1")

    request = route.calls.last.request
    assert request.url.path == "/dataset/isIcebergTableCreated/1/t1"
    assert result is True


def test_list_imported_files() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/list-imported-files").mock(
            return_value=httpx.Response(200, json=[{"fileName": "f.csv"}])
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.list_imported_files(dataset_id=1)

    request = route.calls.last.request
    assert request.url.params["datasetId"] == "1"
    assert result[0].fileName == "f.csv"


def test_restore_prefilled_tables() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataset/restorePrefilledTables/1").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.restore_prefilled_tables(dataset_id=1, table_schema_id="t1")

    request = route.calls.last.request
    assert request.url.path == "/dataset/restorePrefilledTables/1"
    assert request.url.params["tableSchemaId"] == "t1"
    assert result is None


def test_update_attachment(tmp_path: Path) -> None:
    src = tmp_path / "attach.pdf"
    src.write_bytes(b"%PDF-1.4")

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/dataset/v1/1/field/f1/attachment").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.update_attachment(
                dataset_id=1, field_id="f1", file=src, record_id="r1"
            )

    request = route.calls.last.request
    assert request.method == "PUT"
    assert request.url.path == "/dataset/v1/1/field/f1/attachment"
    assert request.url.params["recordId"] == "r1"
    assert b'filename="attach.pdf"' in request.content
    assert result is None


def test_update_geometry() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/dataset/1/updateGeometry").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.update_geometry(dataset_id=1)

    request = route.calls.last.request
    assert request.url.path == "/dataset/1/updateGeometry"
    assert result is None


def test_update_geometry_v2() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/dataset/v2/1/updateGeometry").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.update_geometry_v2(dataset_id=1)

    request = route.calls.last.request
    assert request.url.path == "/dataset/v2/1/updateGeometry"
    assert result is None


def test_dataflow_id_is_required_keyword_only(tmp_path: Path) -> None:
    # Spec says optional, backend 400s without it (live-confirmed); positional
    # use must fail loudly rather than shift args onto the wrong parameters.
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(TypeError):
            client.datasets.etl_export_dataset(1, tmp_path / "x")  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            client.datasets.get_attachment(1, "f1", tmp_path / "x")  # type: ignore[call-arg]


def test_preparation_code_wire_names() -> None:
    """T08 follow-up #16: the backend uses `code` on some routes, `preparationCode` on others."""
    with respx.mock(base_url=BASE_URL) as mock:
        dl = mock.post("/dataset/1/etlImportDL").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        delete = mock.delete("/dataset/v1/1/deleteTableData/t1").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        plain = mock.get("/dataset/getIcebergTables").mock(
            return_value=httpx.Response(200, json=[])
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.datasets.etl_import_dataset_dl(
                dataflow_id=2,
                dataset_id=1,
                delimiter=",",
                file_path_in_s3="p",
                preparation_code="A1",
            )
            client.datasets.delete_table_data(
                dataset_id=1, table_schema_id="t1", preparation_code="B2"
            )
            client.datasets.get_iceberg_tables(dataflow_id=2)

    assert dl.calls.last.request.url.params["code"] == "A1"
    assert "preparationCode" not in dl.calls.last.request.url.params
    assert delete.calls.last.request.url.params["preparationCode"] == "B2"
    assert "preparationCode" not in plain.calls.last.request.url.params
