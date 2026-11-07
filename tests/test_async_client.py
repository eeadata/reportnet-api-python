import asyncio

import httpx
import pytest
import respx

from reportnet_api import (
    AsyncReportnetClient,
    LockedError,
    NotFoundError,
    ReportnetAPIError,
    TooManyRequestsError,
)

BASE_URL = "https://api.reportnet.europa.eu"


def test_static_token_sets_bearer_header() -> None:
    async def run() -> tuple[httpx.Response, respx.Route]:
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get("/dataset/1").mock(return_value=httpx.Response(200, json={"id": 1}))
            async with AsyncReportnetClient(base_url=BASE_URL, token="my-token") as client:
                response = await client.request("GET", "/dataset/1")
            return response, route

    response, route = asyncio.run(run())
    assert response.json() == {"id": 1}
    assert route.calls.last.request.headers["Authorization"] == "Bearer my-token"


def test_404_raises_not_found_error() -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataset/999").mock(return_value=httpx.Response(404, text="missing"))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                with pytest.raises(NotFoundError) as exc_info:
                    await client.request("GET", "/dataset/999")
        assert exc_info.value.status_code == 404
        assert exc_info.value.response_body == "missing"

    asyncio.run(run())


def test_default_timeout_is_finite() -> None:
    async def run() -> None:
        async with AsyncReportnetClient(BASE_URL, token="t") as client:
            assert client._http.timeout == httpx.Timeout(60.0, connect=10.0)
        async with AsyncReportnetClient(BASE_URL, token="t", timeout=None) as client:
            assert client._http.timeout == httpx.Timeout(None)

    asyncio.run(run())


@pytest.mark.parametrize(
    ("status_code", "scheme", "fragment"),
    [
        (401, "Bearer", "may have expired"),
        (401, "ApiKey", "ApiKey is correct"),
        (403, "Bearer", "required role"),
        (403, "ApiKey", "Reporter-level only"),
    ],
)
def test_auth_errors_get_scheme_specific_hint(status_code: int, scheme: str, fragment: str) -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataset/1").mock(return_value=httpx.Response(status_code, text="nope"))
            async with AsyncReportnetClient(
                base_url=BASE_URL, token="t", token_scheme=scheme
            ) as client:
                with pytest.raises(ReportnetAPIError) as exc_info:
                    await client.request("GET", "/dataset/1")
        error = exc_info.value
        assert str(error).startswith(f"GET {BASE_URL}/dataset/1 -> {status_code}")
        assert fragment in str(error)
        assert error.status_code == status_code
        assert error.response_body == "nope"

    asyncio.run(run())


@pytest.mark.parametrize(
    ("status_code", "exc_cls"), [(423, LockedError), (429, TooManyRequestsError)]
)
def test_async_locked_and_rate_limited(status_code: int, exc_cls: type[ReportnetAPIError]) -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/dataset/1").mock(
                return_value=httpx.Response(status_code, headers={"Retry-After": "3"})
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                with pytest.raises(exc_cls) as exc_info:
                    await client.request("GET", "/dataset/1")
        assert "(hint:" in str(exc_info.value)
        if isinstance(exc_info.value, TooManyRequestsError):
            assert exc_info.value.retry_after == 3.0

    asyncio.run(run())
