"""Request-shape tests for reportnet_api/resources/release_receipts.py (4 endpoints)."""

import httpx
import respx

from reportnet_api import ReportnetClient
from reportnet_api.models import generated

BASE_URL = "https://api.reportnet.europa.eu"


def test_create_release_receipt() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/release-receipts").mock(
            return_value=httpx.Response(200, json={"id": 1, "dataflowId": 3, "note": "hi"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.release_receipts.create_release_receipt(
                generated.ReleaseReceiptVO(dataflowId=3, note="hi")
            )

    request = route.calls.last.request
    assert request.method == "POST"
    assert request.url.path == "/release-receipts"
    assert request.content == b'{"dataflowId":3,"note":"hi"}'
    assert result.id == 1


def test_delete_release_receipt_by_dataflow_id() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.delete("/release-receipts/dataflow/3").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.release_receipts.delete_release_receipt_by_dataflow_id(dataflow_id=3)

    request = route.calls.last.request
    assert request.method == "DELETE"
    assert request.url.path == "/release-receipts/dataflow/3"
    assert result is None


def test_get_release_receipt_by_dataflow_id() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/release-receipts/dataflow/3").mock(
            return_value=httpx.Response(200, json={"id": 1, "dataflowId": 3})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.release_receipts.get_release_receipt_by_dataflow_id(dataflow_id=3)

    request = route.calls.last.request
    assert request.method == "GET"
    assert request.url.path == "/release-receipts/dataflow/3"
    assert result.id == 1


def test_update_release_receipt() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/release-receipts").mock(
            return_value=httpx.Response(200, json={"id": 1, "dataflowId": 3, "note": "updated"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.release_receipts.update_release_receipt(
                generated.ReleaseReceiptVO(id=1, dataflowId=3, note="updated")
            )

    request = route.calls.last.request
    assert request.method == "PUT"
    assert request.url.path == "/release-receipts"
    assert result.note == "updated"
