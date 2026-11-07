"""Tests for the opt-in RetryPolicy (sync + async clients)."""

import asyncio
from datetime import UTC

import httpx
import pytest
import respx

from reportnet_api import (
    AsyncReportnetClient,
    LockedError,
    ReportnetAPIError,
    ReportnetClient,
    RetryPolicy,
    ServerError,
    TooManyRequestsError,
)

BASE_URL = "https://api.reportnet.europa.eu"
POLICY = RetryPolicy(retries=3, backoff=0.5, max_delay=4.0)


@pytest.fixture
def sleeps(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr("reportnet_api.client.time.sleep", calls.append)

    async def fake_async_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr("reportnet_api.async_client.asyncio.sleep", fake_async_sleep)
    return calls


def _client(policy: RetryPolicy | None = POLICY) -> ReportnetClient:
    return ReportnetClient(base_url=BASE_URL, token="t", retry=policy)


def test_no_policy_means_no_retry(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(503))
        with _client(None) as client, pytest.raises(ServerError):
            client.request("GET", "/x")
    assert route.call_count == 1
    assert sleeps == []


def test_get_503_is_retried_with_backoff_then_succeeds(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(
            side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200, json={})]
        )
        with _client() as client:
            assert client.request("GET", "/x").status_code == 200
    assert route.call_count == 3
    assert sleeps == [0.5, 1.0]


def test_retries_exhausted_raises_last_error(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(503))
        with _client() as client, pytest.raises(ServerError):
            client.request("GET", "/x")
    assert route.call_count == 4  # first try + 3 retries
    assert sleeps == [0.5, 1.0, 2.0]


def test_backoff_is_capped(sleeps) -> None:
    policy = RetryPolicy(retries=4, backoff=1.0, max_delay=3.0)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/x").mock(return_value=httpx.Response(503))
        with _client(policy) as client, pytest.raises(ServerError):
            client.request("GET", "/x")
    assert sleeps == [1.0, 2.0, 3.0, 3.0]


def test_retry_after_replaces_backoff_and_is_capped(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/x").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "2"}),
                httpx.Response(429, headers={"Retry-After": "600"}),
                httpx.Response(200),
            ]
        )
        with _client() as client:
            client.request("GET", "/x")
    assert sleeps == [2.0, 4.0]


def test_429_still_raises_typed_error_when_exhausted(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/x").mock(return_value=httpx.Response(429, headers={"Retry-After": "1"}))
        with _client(RetryPolicy(retries=1)) as client:
            with pytest.raises(TooManyRequestsError) as exc_info:
                client.request("GET", "/x")
    assert exc_info.value.retry_after == 1.0


@pytest.mark.parametrize("status", [500, 423, 404, 403])
def test_other_statuses_are_never_retried(sleeps, status: int) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(status))
        with _client() as client, pytest.raises(ReportnetAPIError):
            client.request("GET", "/x")
    assert route.call_count == 1
    assert sleeps == []


def test_status_retry_is_get_only(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/x").mock(return_value=httpx.Response(503))
        with _client() as client, pytest.raises(ServerError):
            client.request("POST", "/x", json={})
    assert route.call_count == 1


def test_connect_error_is_retried_for_any_method(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/x").mock(side_effect=[httpx.ConnectError("down"), httpx.Response(200)])
        with _client() as client:
            assert client.request("POST", "/x", json={}).status_code == 200
    assert route.call_count == 2


def test_read_timeout_is_retried_for_get_but_not_post(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        get = mock.get("/x").mock(side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200)])
        post = mock.post("/x").mock(side_effect=httpx.ReadTimeout("slow"))
        with _client() as client:
            assert client.request("GET", "/x").status_code == 200
            with pytest.raises(httpx.ReadTimeout):
                client.request("POST", "/x", json={})
    assert get.call_count == 2
    assert post.call_count == 1


def test_file_uploads_are_not_retried(sleeps, tmp_path) -> None:
    f = tmp_path / "a.csv"
    f.write_text("x\n1\n")
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(503))
        with _client() as client, f.open("rb") as fh, pytest.raises(ServerError):
            client.request("GET", "/x", files={"file": ("a.csv", fh)})
    assert route.call_count == 1


def test_lock_423_is_not_retried(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(423))
        with _client() as client, pytest.raises(LockedError):
            client.request("GET", "/x")
    assert route.call_count == 1


def test_async_retry_and_no_retry_for_post(sleeps) -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            get = mock.get("/x").mock(side_effect=[httpx.Response(504), httpx.Response(200)])
            post = mock.post("/x").mock(return_value=httpx.Response(503))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t", retry=POLICY) as client:
                assert (await client.request("GET", "/x")).status_code == 200
                with pytest.raises(ServerError):
                    await client.request("POST", "/x", json={})
            assert get.call_count == 2
            assert post.call_count == 1

    asyncio.run(run())
    assert sleeps == [0.5]


def test_retry_after_nan_and_garbage_fall_back_to_backoff(sleeps) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/x").mock(
            side_effect=[
                httpx.Response(503, headers={"Retry-After": "nan"}),
                httpx.Response(503, headers={"Retry-After": "soon"}),
                httpx.Response(200),
            ]
        )
        with _client() as client:
            client.request("GET", "/x")
    assert sleeps == [0.5, 1.0]


def test_retry_after_http_date_is_honoured_and_capped(sleeps) -> None:
    from datetime import datetime, timedelta
    from email.utils import format_datetime

    soon = format_datetime(datetime.now(UTC) + timedelta(seconds=2), usegmt=True)
    past = format_datetime(datetime.now(UTC) - timedelta(seconds=60), usegmt=True)
    far = format_datetime(datetime.now(UTC) + timedelta(hours=1), usegmt=True)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/x").mock(
            side_effect=[
                httpx.Response(503, headers={"Retry-After": soon}),
                httpx.Response(503, headers={"Retry-After": past}),
                httpx.Response(503, headers={"Retry-After": far}),
                httpx.Response(200),
            ]
        )
        with _client() as client:
            client.request("GET", "/x")
    assert 0.5 < sleeps[0] <= 2.0
    assert sleeps[1:] == [0.0, 4.0]


@pytest.mark.parametrize(
    "error",
    [
        httpx.UnsupportedProtocol("no scheme"),
        httpx.LocalProtocolError("bad"),
        httpx.ProxyError("p"),
    ],
)
def test_permanent_transport_errors_are_not_retried(error: httpx.TransportError) -> None:
    assert POLICY.delay(0, "GET", error=error) is None


@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("t"), httpx.ReadError("r"), httpx.RemoteProtocolError("p")]
)
def test_transient_transport_errors_retry_only_for_get(error: httpx.TransportError) -> None:
    assert POLICY.delay(0, "GET", error=error) == 0.5
    assert POLICY.delay(0, "POST", error=error) is None


def test_pool_timeout_is_retried_for_any_method() -> None:
    assert POLICY.delay(0, "POST", error=httpx.PoolTimeout("busy")) == 0.5


def test_streamed_bodies_are_not_retried(sleeps) -> None:
    def chunks():
        yield b"abc"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/x").mock(return_value=httpx.Response(503))
        with _client() as client, pytest.raises(ServerError):
            client.request("GET", "/x", content=chunks())
    assert route.call_count == 1


@pytest.mark.parametrize(
    "kwargs", [{"retries": -1}, {"backoff": -1.0}, {"max_delay": -0.1}, {"backoff": float("nan")}]
)
def test_policy_validates_fields(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(**kwargs)
