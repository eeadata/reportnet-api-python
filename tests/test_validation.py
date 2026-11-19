"""Tests for the Validation resource (sync + async), mocked."""

import asyncio

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient
from reportnet_api.jobs import JobError

BASE_URL = "https://api.reportnet.europa.eu"
LISTING = {"idDataset": 7, "errors": [], "totalRecords": 0, "totalErrors": 0}


def test_start_validation_sends_released_only_when_true() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/orchestrator/jobs/addValidationJob/7").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(BASE_URL, "t") as c:
            c.validation.start_validation(7)
            assert "released" not in route.calls[-1].request.url.params
            c.validation.start_validation(7, released=True)
            assert route.calls[-1].request.url.params["released"] == "true"


def test_list_group_validations_params_and_validation() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/validation/listGroupValidations/7").mock(
            return_value=httpx.Response(200, json=LISTING)
        )
        with ReportnetClient(BASE_URL, "t") as c:
            out = c.validation.list_group_validations(
                7, page_num=1, level_errors=["ERROR", "BLOCKER"], sort_by="levelError", asc=False
            )
            assert out == LISTING
            q = route.calls[-1].request.url.params
            assert q["pageNum"] == "1" and q["pageSize"] == "20" and q["asc"] == "false"
            assert q.get_list("levelErrorsFilter") == ["ERROR", "BLOCKER"]
            assert q["headers"] == "levelError"
            with pytest.raises(ValueError, match="level_errors"):
                c.validation.list_group_validations(7, level_errors=["BAD"])
            with pytest.raises(ValueError, match="type_entities"):
                c.validation.list_validations(7, type_entities=["ROW"])


def test_list_group_validations_dl_uses_dl_route_and_same_params() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/validation/listGroupValidationsDL/7").mock(
            return_value=httpx.Response(200, json=LISTING)
        )
        with ReportnetClient(BASE_URL, "t") as c:
            assert c.validation.list_group_validations_dl(7, page_size=10) == LISTING
            q = route.calls[-1].request.url.params
            assert q["pageNum"] == "0" and q["pageSize"] == "10" and q["asc"] == "true"
            with pytest.raises(ValueError, match="level_errors"):
                c.validation.list_group_validations_dl(7, level_errors=["BAD"])

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/validation/listGroupValidationsDL/7").mock(
                return_value=httpx.Response(200, json=LISTING)
            )
            async with AsyncReportnetClient(BASE_URL, "t") as c:
                assert await c.validation.list_group_validations_dl(7) == LISTING

    asyncio.run(run())


def test_list_validations_empty_body_is_none() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/validation/listValidations/7").mock(return_value=httpx.Response(200))
        with ReportnetClient(BASE_URL, "t") as c:
            assert c.validation.list_validations(7) is None


def test_export_waits_for_file(tmp_path) -> None:
    dest = tmp_path / "v.csv"
    with respx.mock(base_url=BASE_URL) as mock:
        post = mock.post("/validation/export/7").mock(return_value=httpx.Response(200))
        dl = mock.get("/validation/downloadFile/7").mock(
            side_effect=[httpx.Response(404), httpx.Response(200, content=b"a,b\n1,2\n")]
        )
        with ReportnetClient(BASE_URL, "t") as c:
            c.validation.export_validations_to_file(7, dest, poll_interval=0.01)
        assert post.call_count == 1 and dl.call_count == 2
        assert dl.calls[-1].request.url.params["fileName"] == "dataset-7-validations.csv"
    assert dest.read_bytes() == b"a,b\n1,2\n"
    assert list(tmp_path.iterdir()) == [dest]  # no .part left behind


def test_export_times_out(tmp_path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/validation/export/7").mock(return_value=httpx.Response(200))
        mock.get("/validation/downloadFile/7").mock(return_value=httpx.Response(404))
        with ReportnetClient(BASE_URL, "t") as c:
            with pytest.raises(JobError, match="not ready"):
                c.validation.export_validations_to_file(
                    7, tmp_path / "v.csv", poll_interval=0.01, timeout=0.05
                )


def test_async_routes(tmp_path) -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.put("/orchestrator/jobs/addValidationJob/7").mock(return_value=httpx.Response(200))
            mock.get("/validation/listGroupValidations/7").mock(
                return_value=httpx.Response(200, json=LISTING)
            )
            mock.post("/validation/export/7").mock(return_value=httpx.Response(200))
            mock.get("/validation/downloadFile/7").mock(
                side_effect=[httpx.Response(404), httpx.Response(200, content=b"x\n")]
            )
            async with AsyncReportnetClient(BASE_URL, "t") as c:
                await c.validation.start_validation(7)
                assert await c.validation.list_group_validations(7) == LISTING
                await c.validation.export_validations_to_file(
                    7, tmp_path / "v.csv", poll_interval=0.01
                )
            assert (tmp_path / "v.csv").read_bytes() == b"x\n"

    asyncio.run(run())


def test_download_false_on_404_and_empty_body_and_errors_propagate(tmp_path) -> None:
    from reportnet_api import ForbiddenError

    dest = tmp_path / "v.csv"
    with respx.mock(base_url=BASE_URL) as mock:
        dl = mock.get("/validation/downloadFile/7")
        mock.post("/validation/export/7").mock(return_value=httpx.Response(200))
        with ReportnetClient(BASE_URL, "t") as c:
            dl.mock(return_value=httpx.Response(404))
            assert c.validation.download_validations_file(7, dest) is False
            dl.mock(return_value=httpx.Response(200, content=b""))
            assert c.validation.download_validations_file(7, dest) is False
            dl.mock(return_value=httpx.Response(403))
            with pytest.raises(ForbiddenError):
                c.validation.export_validations_to_file(7, dest, poll_interval=0.01)
    assert list(tmp_path.iterdir()) == []


def test_list_validations_query_and_paging_checks() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/validation/listValidations/7").mock(
            return_value=httpx.Response(200, json=LISTING)
        )
        with ReportnetClient(BASE_URL, "t") as c:
            c.validation.list_validations(
                7, type_entities=["TABLE"], table_filter="T", field_value_filter="x"
            )
            q = route.calls[-1].request.url.params
            assert q["typeEntitiesFilter"] == "TABLE" and q["tableFilter"] == "T"
            assert q["fieldValueFilter"] == "x" and "headers" not in q
            with pytest.raises(ValueError, match="page_size"):
                c.validation.list_validations(7, page_size=0)


def test_async_timeout_and_empty_body(tmp_path) -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/validation/export/7").mock(return_value=httpx.Response(200))
            mock.get("/validation/downloadFile/7").mock(return_value=httpx.Response(404))
            mock.get("/validation/listValidations/7").mock(return_value=httpx.Response(200))
            async with AsyncReportnetClient(BASE_URL, "t") as c:
                assert await c.validation.list_validations(7) is None
                with pytest.raises(JobError, match="not ready"):
                    await c.validation.export_validations_to_file(
                        7, tmp_path / "v.csv", poll_interval=0.01, timeout=0.05
                    )

    asyncio.run(run())
