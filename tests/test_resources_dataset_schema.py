"""Request-shape tests for reportnet_api/resources/dataset_schema.py (11 endpoints)."""

from pathlib import Path

import httpx
import respx

from reportnet_api import ReportnetClient

BASE_URL = "https://api.reportnet.europa.eu"


def test_export_field_schemas() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataschema/v1/s1/exportFieldSchemas").mock(
            return_value=httpx.Response(200, text="csv,data")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_schema.export_field_schemas(
                dataset_schema_id="s1", dataset_id=1, table_schema_id="t1"
            )

    request = route.calls.last.request
    assert request.url.path == "/dataschema/v1/s1/exportFieldSchemas"
    assert request.url.params["datasetId"] == "1"
    assert request.url.params["tableSchemaId"] == "t1"
    assert request.headers["accept"] == "application/octet-stream, */*;q=0.1"
    assert result == "csv,data"


def test_export_field_schemas_from_dataset() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataschema/v1/dataset/1/exportFieldSchemas").mock(
            return_value=httpx.Response(200, text="csv,data")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_schema.export_field_schemas_from_dataset(dataset_id=1)

    request = route.calls.last.request
    assert request.url.path == "/dataschema/v1/dataset/1/exportFieldSchemas"
    assert request.headers["accept"] == "application/octet-stream, */*;q=0.1"
    assert result == "csv,data"


def test_find_data_schema_by_dataset_id() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataschema/v1/datasetId/1").mock(
            return_value=httpx.Response(200, json={"idDataSetSchema": "sch1"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=1)

    request = route.calls.last.request
    assert request.url.path == "/dataschema/v1/datasetId/1"
    assert result.idDataSetSchema == "sch1"


def test_get_simple_schema() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataschema/v1/getSimpleSchema/dataset/1").mock(
            return_value=httpx.Response(200, json={"datasetName": "ds1"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_schema.get_simple_schema(
                dataset_id=1, dataflow_id=2, provider_id=3
            )

    request = route.calls.last.request
    assert request.url.path == "/dataschema/v1/getSimpleSchema/dataset/1"
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["providerId"] == "3"
    assert result.datasetName == "ds1"


def test_get_table_schemas_ids() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataschema/v1/getTableSchemasIds/1").mock(
            return_value=httpx.Response(200, json=[{"idTableSchema": "t1"}])
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_schema.get_table_schemas_ids(
                dataset_id=1, dataflow_id=2, provider_id=3
            )

    request = route.calls.last.request
    assert request.url.path == "/dataschema/v1/getTableSchemasIds/1"
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["providerId"] == "3"
    assert result[0].idTableSchema == "t1"


def test_import_field_schemas(tmp_path: Path) -> None:
    src = tmp_path / "schema.xml"
    src.write_text("<schema/>")

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataschema/v1/s1/importFieldSchemas").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_schema.import_field_schemas(
                dataset_schema_id="s1", file=src, dataset_id=1, replace=True, table_schema_id="t1"
            )

    request = route.calls.last.request
    assert request.url.path == "/dataschema/v1/s1/importFieldSchemas"
    assert request.url.params["datasetId"] == "1"
    assert request.url.params["replace"] == "true"
    assert request.url.params["tableSchemaId"] == "t1"
    assert b"<schema/>" in request.content
    assert b'filename="schema.xml"' in request.content
    assert result is None


def test_update_manually_editable_by_dataset_id() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/dataschema/updateManuallyEditable/1").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_schema.update_manually_editable_by_dataset_id(
                dataset_id=1, manually_editable=True
            )

    request = route.calls.last.request
    assert request.method == "PUT"
    assert request.url.path == "/dataschema/updateManuallyEditable/1"
    assert request.url.params["manuallyEditable"] == "true"
    assert result is None
