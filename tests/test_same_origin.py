import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient

BASE = "https://api.example.invalid"
OTHER = [
    "https://evil.example/steal",
    "http://api.example.invalid/x",
    "https://api.example.invalid:8443/x",
]


@pytest.mark.parametrize("url", OTHER)
@respx.mock
def test_sync_request_and_download_refuse_other_origin(url: str, tmp_path: Path) -> None:
    route = respx.route().respond(200, json={})
    with ReportnetClient(BASE, "SECRET") as c:
        with pytest.raises(ValueError, match="Refusing to send the credential"):
            c.request("GET", url)
        with pytest.raises(ValueError, match="Refusing to send the credential"):
            c.download("GET", url, dest=tmp_path / "f")
    assert route.call_count == 0


@pytest.mark.parametrize("url", OTHER)
@respx.mock
def test_async_request_and_download_refuse_other_origin(url: str, tmp_path: Path) -> None:
    route = respx.route().respond(200, json={})

    async def run() -> None:
        async with AsyncReportnetClient(BASE, "SECRET") as c:
            with pytest.raises(ValueError, match="Refusing to send the credential"):
                await c.request("GET", url)
            with pytest.raises(ValueError, match="Refusing to send the credential"):
                await c.download("GET", url, dest=tmp_path / "f")

    asyncio.run(run())
    assert route.call_count == 0


@respx.mock
def test_protocol_relative_url_stays_on_the_configured_host() -> None:
    # httpx reads `//host/x` as a path on the base host, so nothing leaves it.
    route = respx.route(host="api.example.invalid").respond(200, json={})
    with ReportnetClient(BASE, "SECRET") as c:
        c.request("GET", "//evil.example/steal")
    assert route.call_count == 1


@respx.mock
def test_same_origin_paths_and_absolute_urls_still_work() -> None:
    route = respx.get(f"{BASE}/orchestrator/jobs/pollForJobStatus/1").respond(200, json={"ok": 1})
    with ReportnetClient(BASE, "SECRET") as c:
        assert c.request("GET", "/orchestrator/jobs/pollForJobStatus/1").json() == {"ok": 1}
        absolute = f"{BASE}/orchestrator/jobs/pollForJobStatus/1"
        assert c.request("GET", absolute).json() == {"ok": 1}
    assert route.call_count == 2
    assert all(call.request.headers["authorization"].endswith("SECRET") for call in route.calls)


def test_polling_url_on_other_host_is_not_followed() -> None:
    from reportnet_api.jobs import wait_for_job

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"status": "FINISHED"})

    c = ReportnetClient(BASE, "SECRET")
    c._http = httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="Refusing"):
        wait_for_job(c, {"pollingUrl": "https://evil.example/poll"}, timeout=5)
    assert seen == []


def test_message_names_scheme_and_port_when_only_they_differ() -> None:
    with ReportnetClient(BASE, "SECRET") as c:
        with pytest.raises(
            ValueError, match=r"to http://api\.example\.invalid:.*\(https://api\.example\.invalid\)"
        ):
            c.request("GET", "http://api.example.invalid/x")


def test_plain_http_base_url_warns_but_localhost_does_not(recwarn: pytest.WarningsRecorder) -> None:
    with pytest.warns(UserWarning, match="plain http"):
        ReportnetClient("http://api.example.invalid", "SECRET").close()
    ReportnetClient("http://127.0.0.1:8080", "SECRET").close()
    assert not [w for w in recwarn if "plain http" in str(w.message)]


def test_insecure_warning_points_at_the_callers_line_through_easy_connect() -> None:
    from reportnet_api import easy

    with pytest.warns(UserWarning, match="plain http") as caught:
        easy.connect("k", base_url="http://api.example.invalid").close()
    assert caught[0].filename == __file__


@pytest.mark.parametrize("url", ["http://127.0.0.2:8000", "http://app.localhost", "http://[::1]:9"])
def test_any_loopback_address_counts_as_local(url: str, recwarn: pytest.WarningsRecorder) -> None:
    ReportnetClient(url, "SECRET").close()
    assert not [w for w in recwarn if "plain http" in str(w.message)]


def test_ipv6_origin_is_bracketed() -> None:
    with ReportnetClient("https://[::1]:9443", "SECRET") as c:
        with pytest.raises(ValueError, match=r"\(https://\[::1\]:9443\)"):
            c.request("GET", "https://evil.example/x")
