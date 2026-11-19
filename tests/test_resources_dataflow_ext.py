"""Tests for the hand-written Dataflow resource."""

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetAPIError, ReportnetClient, ValidationError

BASE_URL = "https://api.reportnet.europa.eu"
PAGE = {"dataflows": [{"id": 1, "name": "x"}], "totalRecords": 1, "filteredRecords": 1}


@pytest.mark.parametrize(
    ("kind", "path"),
    [
        ("reporting", "/dataflow/getDataflows"),
        ("reference", "/dataflow/referenceDataflows"),
        ("business", "/dataflow/businessDataflows"),
        ("citizen_science", "/dataflow/citizenScienceDataflows"),
    ],
)
def test_dataflows_kinds(kind: str, path: str) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post(path).mock(return_value=httpx.Response(200, json=PAGE))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataflow.dataflows(
                kind,  # type: ignore[arg-type]
                filters={"name": "a"},
                asc=True,
                page_size=10,
                page_num=2,
            )
    assert result == PAGE
    request = route.calls.last.request
    assert request.url.params["asc"] == "true"
    assert request.url.params["pageSize"] == "10"
    assert request.url.params["pageNum"] == "2"
    assert "orderHeader" not in request.url.params
    assert request.content == b'{"name":"a"}'


def test_dataflows_bad_kind() -> None:
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match="kind must be one of"):
            client.dataflow.dataflows("nope")  # type: ignore[arg-type]


def test_dataflow_datasets() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataflow/v1/4242").mock(
            return_value=httpx.Response(200, json={"id": 4242, "designDatasets": []})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataflow.dataflow_datasets(4242, provider_id=5)
    assert result is not None
    assert result["id"] == 4242
    assert route.calls.last.request.url.params["providerId"] == "5"


def test_async_dataflows_and_datasets() -> None:
    async def run() -> tuple[dict[str, Any], dict[str, Any] | None]:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/dataflow/getDataflows").mock(return_value=httpx.Response(200, json=PAGE))
            mock.get("/dataflow/v1/7").mock(return_value=httpx.Response(200, json={"id": 7}))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                return (
                    await client.dataflow.dataflows(),
                    await client.dataflow.dataflow_datasets(7),
                )

    a, b = asyncio.run(run())
    assert a == PAGE
    assert b == {"id": 7}


def test_dataflows_paging_needs_both() -> None:
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match="given together"):
            client.dataflow.dataflows(page_size=10)
        with pytest.raises(ValueError, match="given together"):
            client.dataflow.dataflows(page_num=0)


def test_dataflow_datasets_empty_body_is_none() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/9").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.dataflow.dataflow_datasets(9) is None
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataflow/v1/9").mock(return_value=httpx.Response(200))

        async def run() -> object:
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                return await client.dataflow.dataflow_datasets(9)

        assert asyncio.run(run()) is None


def test_create_dataflow_returns_new_id() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataflow").mock(return_value=httpx.Response(200, text="13555"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            new_id = client.dataflow.create_dataflow(
                "RNT test", "desc", obligation_id=671, fields={"showPublicInfo": False}
            )

    assert new_id == 13555
    assert json.loads(route.calls.last.request.content) == {
        "name": "RNT test",
        "description": "desc",
        "type": "REPORTING",
        "releasable": True,
        "obligation": {"obligationId": 671},
        "showPublicInfo": False,
    }


def test_create_reference_dataflow_without_obligation() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/dataflow").mock(return_value=httpx.Response(200, text='"42"'))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.dataflow.create_dataflow("r", "d", dataflow_type="REFERENCE") == 42

    body = json.loads(route.calls.last.request.content)
    assert body["type"] == "REFERENCE"
    assert "obligation" not in body


def test_create_dataflow_error_raises() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataflow").mock(
            return_value=httpx.Response(400, text="Dataflow Obligation empty")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ValidationError):
                client.dataflow.create_dataflow("n", "d")


def test_delete_dataflow() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.delete("/dataflow/13555").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.dataflow.delete_dataflow(13555)

    assert route.called


def test_async_create_and_delete_dataflow() -> None:
    async def run() -> tuple[int, respx.Route]:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/dataflow").mock(return_value=httpx.Response(200, text="7"))
            deleting = mock.delete("/dataflow/7").mock(return_value=httpx.Response(200))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                new_id = await client.dataflow.create_dataflow("n", "d", obligation_id=1)
                await client.dataflow.delete_dataflow(new_id)
            return new_id, deleting

    new_id, deleting = asyncio.run(run())
    assert new_id == 7
    assert deleting.called


@pytest.mark.parametrize("key", ["name", "description", "type", "obligation"])
def test_create_dataflow_fields_cannot_override_arguments(key: str) -> None:
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match=key):
            client.dataflow.create_dataflow("n", "d", obligation_id=1, fields={key: "x"})


def test_create_dataflow_non_numeric_answer_raises_api_error() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataflow").mock(return_value=httpx.Response(200, text="<html>login</html>"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ReportnetAPIError) as exc_info:
                client.dataflow.create_dataflow("n", "d", obligation_id=1)

    assert exc_info.value.status_code == 200
    assert exc_info.value.response_body == "<html>login</html>"
