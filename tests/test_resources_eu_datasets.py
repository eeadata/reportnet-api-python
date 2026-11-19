"""Request-shape tests for reportnet_api/resources/eu_datasets.py (1 endpoint)."""

import httpx
import respx

from reportnet_api import ReportnetClient

BASE_URL = "https://api.reportnet.europa.eu"


def test_populate_data_from_data_collection() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/euDataset/v1/populateData/dataflow/5").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.eu_datasets.populate_data_from_data_collection(dataflow_id=5, job_id=9)

    request = route.calls.last.request
    assert request.method == "POST"
    assert request.url.path == "/euDataset/v1/populateData/dataflow/5"
    assert request.url.params["jobId"] == "9"


def test_populate_data_from_data_collection_without_job_id() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/euDataset/v1/populateData/dataflow/5").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.eu_datasets.populate_data_from_data_collection(dataflow_id=5)

    request = route.calls.last.request
    assert "jobId" not in request.url.params
