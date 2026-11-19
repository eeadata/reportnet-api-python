import httpx
import pytest
import respx

from reportnet_api import (
    AuthenticationError,
    ForbiddenError,
    LockedError,
    NotFoundError,
    ReportnetAPIError,
    ReportnetClient,
    ServerError,
    TooManyRequestsError,
    ValidationError,
)

BASE_URL = "https://api.reportnet.europa.eu"


def test_static_token_sets_bearer_header() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/1").mock(return_value=httpx.Response(200, json={"id": 1}))
        with ReportnetClient(base_url=BASE_URL, token="my-token") as client:
            response = client.request("GET", "/dataset/1")

    assert response.json() == {"id": 1}
    assert route.calls.last.request.headers["Authorization"] == "Bearer my-token"


def test_callable_token_is_invoked_per_request() -> None:
    calls = {"n": 0}

    def token_provider() -> str:
        calls["n"] += 1
        return f"token-{calls['n']}"

    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/dataset/1").mock(return_value=httpx.Response(200, json={}))
        with ReportnetClient(base_url=BASE_URL, token=token_provider) as client:
            client.request("GET", "/dataset/1")
            client.request("GET", "/dataset/1")

    assert route.calls[0].request.headers["Authorization"] == "Bearer token-1"
    assert route.calls[1].request.headers["Authorization"] == "Bearer token-2"


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, ForbiddenError),
        (404, NotFoundError),
        (422, ValidationError),
        (423, LockedError),
        (429, TooManyRequestsError),
        (500, ServerError),
        (503, ServerError),
        (418, ReportnetAPIError),
    ],
)
def test_error_status_codes_map_to_exceptions(
    status_code: int, expected_exception: type[ReportnetAPIError]
) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/1").mock(return_value=httpx.Response(status_code, text="boom"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(expected_exception) as exc_info:
                client.request("GET", "/dataset/1")

    error = exc_info.value
    assert error.status_code == status_code
    assert error.response_body == "boom"
    assert isinstance(error.request, httpx.Request)
    assert isinstance(error.response, httpx.Response)


def test_default_timeout_is_finite() -> None:
    with ReportnetClient(BASE_URL, token="t") as client:
        assert client._http.timeout == httpx.Timeout(60.0, connect=10.0)


def test_timeout_can_be_overridden_or_disabled() -> None:
    with ReportnetClient(BASE_URL, token="t", timeout=5) as client:
        assert client._http.timeout == httpx.Timeout(5)
    with ReportnetClient(BASE_URL, token="t", timeout=None) as client:
        assert client._http.timeout == httpx.Timeout(None)


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
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/1").mock(return_value=httpx.Response(status_code, text="nope"))
        with ReportnetClient(base_url=BASE_URL, token="t", token_scheme=scheme) as client:
            with pytest.raises(ReportnetAPIError) as exc_info:
                client.request("GET", "/dataset/1")

    error = exc_info.value
    message = str(error)
    assert message.startswith(f"GET {BASE_URL}/dataset/1 -> {status_code}")
    assert fragment in message
    assert error.status_code == status_code
    assert error.response_body == "nope"


def test_non_auth_errors_have_no_hint() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/1").mock(return_value=httpx.Response(404, text="x"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(NotFoundError) as exc_info:
                client.request("GET", "/dataset/1")
    assert "hint" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "fragment"),
    [(423, "holds a lock"), (429, "slow down")],
)
def test_locked_and_rate_limited_get_hints(status_code: int, fragment: str) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/1").mock(return_value=httpx.Response(status_code, text="x"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ReportnetAPIError) as exc_info:
                client.request("GET", "/dataset/1")
    assert f"-> {status_code}: x (hint:" in str(exc_info.value)
    assert fragment in str(exc_info.value)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Retry-After": "7"}, 7.0),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
        ({"Retry-After": "inf"}, None),
        ({"Retry-After": "nan"}, None),
        ({}, None),
    ],
)
def test_retry_after(headers: dict[str, str], expected: float | None) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/dataset/1").mock(return_value=httpx.Response(429, headers=headers))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(TooManyRequestsError) as exc_info:
                client.request("GET", "/dataset/1")
    assert exc_info.value.retry_after == expected


def _error(status_code: int, scheme: str = "Bearer", path: str = "/dataset/1", **kw):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(path).mock(return_value=httpx.Response(status_code, **kw))
        with ReportnetClient(base_url=BASE_URL, token="t", token_scheme=scheme) as client:
            with pytest.raises(ReportnetAPIError) as exc_info:
                client.request("GET", path)
    return exc_info.value


def test_message_includes_server_json_message_and_keeps_full_body() -> None:
    body = {"message": "Dataset 7 not found", "path": "/x", "trace": "secret@example.org"}
    error = _error(404, json=body)
    assert "-> 404: Dataset 7 not found" in str(error)
    assert "secret@example.org" not in str(error)
    assert "secret@example.org" in error.response_body


def test_message_truncates_long_reason_and_ignores_json_without_message() -> None:
    assert f"{'a' * 200}..." in str(_error(500, json={"message": "a" * 500}))
    error = _error(400, json={"error": "Bad Request"})
    assert str(error) == f"GET {BASE_URL}/dataset/1 -> 400"
    assert "Bad Request" in error.response_body


def test_message_falls_back_to_short_text_snippet() -> None:
    assert "-> 502: gateway down" in str(_error(502, text="  gateway\n down "))
    assert str(_error(404, text="")).endswith("-> 404")


def test_dead_apikey_body_with_two_json_objects_reads_first_message() -> None:
    # Live shape (2026-10-26): two JSON objects concatenated, no separator.
    body = (
        '{"status":500,"error":"Internal Server Error","message":"401 UNAUTHORIZED"}'
        '{"status":500,"error":"Internal Server Error","message":"No message available"}'
    )
    error = _error(500, "ApiKey", "/dataflow/v1/4242", text=body)
    assert str(error).endswith("-> 500: 401 UNAUTHORIZED")
    assert "regenerate" in error.explain()


def test_access_denied_500_explained_as_rejected_credential() -> None:
    error = _error(500, "ApiKey", "/dataflow/getDataflows", text='{"message":"Access is denied"}')
    text = error.explain()
    assert "rejected" in text and 'scheme="Bearer"' in text


def test_html_body_is_not_put_in_message() -> None:
    error = _error(502, text="<html><body>Bad gateway</body></html>")
    assert str(error).endswith("-> 502")
    assert "Bad gateway" in error.response_body


@pytest.mark.parametrize(
    ("status_code", "scheme", "path", "kwargs", "fragment"),
    [
        (500, "ApiKey", "/dataset/1", {"json": {"message": "401 UNAUTHORIZED"}}, "regenerate"),
        (
            500,
            "Bearer",
            "/dataflow/v1/999",
            {
                "json": {
                    "message": "status 500 reading DataFlowControllerZuul#accessReferenceEntity"
                }
            },
            "does not exist",
        ),
        (423, "Bearer", "/dataset/1", {"text": "x"}, "wait_for_job"),
        (403, "Bearer", "/dataset/v1/1/etlExport", {"text": "x"}, "gated separately"),
        (403, "ApiKey", "/dataschema/export", {"text": "x"}, "Reporter-level"),
        (403, "Bearer", "/dataset/1", {"text": "x"}, "required role"),
        (404, "Bearer", "/dataset/1", {"text": "x"}, "mixed up"),
        (500, "Bearer", "/dataset/1", {"text": "x"}, "server-side"),
    ],
)
def test_explain(status_code, scheme, path, kwargs, fragment) -> None:
    text = _error(status_code, scheme, path, **kwargs).explain()
    assert f"HTTP {status_code}" in text
    assert fragment in text
    assert len(text.splitlines()) >= 2
