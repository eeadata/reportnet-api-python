"""Request-shape tests for reportnet_api/resources/dataset_snapshot.py (7 endpoints).

`download_historic_releases_csv` (streaming download) is already covered by
tests/test_upload_download.py (sync, async, and error-path); not repeated here.
"""

import httpx
import respx

from reportnet_api import ReportnetClient

BASE_URL = "https://api.reportnet.europa.eu"


def test_delete_snapshot() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.delete("/snapshot/v1/7/dataset/1/delete").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.dataset_snapshot.delete_snapshot(id_dataset=1, id_snapshot=7)

    request = route.calls.last.request
    assert request.method == "DELETE"
    assert request.url.path == "/snapshot/v1/7/dataset/1/delete"


def test_export_historic_releases_csv() -> None:
    url = "/snapshot/downloadHistoricReleases/1?dataflowId=2&fileName=f.csv&processId=p"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/snapshot/exportHistoricReleases/1").mock(
            return_value=httpx.Response(200, text=url)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_snapshot.export_historic_releases_csv(
                dataflow_id=2, dataset_id=1
            )

    request = route.calls.last.request
    assert request.method == "POST"
    assert request.url.path == "/snapshot/exportHistoricReleases/1"
    assert request.url.params["dataflowId"] == "2"
    assert result == url


def test_historic_releases() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/snapshot/v1/historicReleases").mock(
            return_value=httpx.Response(200, json=[{"id": 3, "datasetId": 1}])
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.dataset_snapshot.historic_releases(dataflow_id=2, dataset_id=1)

    request = route.calls.last.request
    assert request.url.params["dataflowId"] == "2"
    assert request.url.params["datasetId"] == "1"
    assert result[0].id == 3
