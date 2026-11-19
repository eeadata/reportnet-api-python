"""Tests for the hand-written ReferenceDataset resource (sync + async)."""

import asyncio

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, NotFoundError, ReportnetClient

BASE_URL = "https://api.reportnet.europa.eu"


def test_set_updatable_sends_lowercase_bool() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/referenceDataset/7").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as c:
            c.reference_dataset.set_updatable(7, False)
            assert route.calls.last.request.url.params["updatable"] == "false"
            c.reference_dataset.set_updatable(7, True)
            assert route.calls.last.request.url.params["updatable"] == "true"


def test_set_updatable_404() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.put("/referenceDataset/7").mock(return_value=httpx.Response(404, text="nope"))
        with ReportnetClient(base_url=BASE_URL, token="t") as c, pytest.raises(NotFoundError):
            c.reference_dataset.set_updatable(7, False)


def test_set_updatable_method_path_and_auth() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.put("/referenceDataset/7").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as c:
            c.reference_dataset.set_updatable(7, True)
        request = route.calls.last.request
        assert request.method == "PUT"
        assert request.url.path == "/referenceDataset/7"
        assert request.headers["Authorization"] == "Bearer t"


@pytest.mark.parametrize("bad", ["false", "true", 0, 1, None])
def test_set_updatable_rejects_non_bool(bad: object) -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        route = mock.put("/referenceDataset/7").mock(return_value=httpx.Response(200))
        with ReportnetClient(base_url=BASE_URL, token="t") as c, pytest.raises(TypeError):
            c.reference_dataset.set_updatable(7, bad)  # type: ignore[arg-type]
        assert not route.called


def test_async_set_updatable() -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.put("/referenceDataset/9").mock(return_value=httpx.Response(200))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as c:
                await c.reference_dataset.set_updatable(9, True)
                assert request_param(route) == "true"
                await c.reference_dataset.set_updatable(9, False)
                assert request_param(route) == "false"
            assert route.calls.last.request.method == "PUT"

    asyncio.run(run())


def request_param(route: respx.Route) -> str:
    return route.calls.last.request.url.params["updatable"]


def test_async_set_updatable_404_and_non_bool() -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.put("/referenceDataset/9").mock(return_value=httpx.Response(404, text="nope"))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as c:
                with pytest.raises(NotFoundError):
                    await c.reference_dataset.set_updatable(9, False)
                with pytest.raises(TypeError):
                    await c.reference_dataset.set_updatable(9, "false")  # type: ignore[arg-type]

    asyncio.run(run())
