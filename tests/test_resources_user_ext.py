"""Tests for the hand-written User resource."""

import asyncio

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient
from reportnet_api._exceptions import AuthenticationError

BASE_URL = "https://api.reportnet.europa.eu"
TOKEN_VO = {
    "accessToken": "new-uuid",
    "refreshToken": "new-refresh-jwt",
    "accessTokenExpiration": 1790000000,
    "preferredUsername": "someone",
}


def test_refresh_token() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/user/refreshToken").mock(
            return_value=httpx.Response(200, json=TOKEN_VO)
        )
        with ReportnetClient(base_url=BASE_URL, token="old-uuid") as client:
            result = client.user.refresh_token("old-refresh-jwt")
    assert result == TOKEN_VO
    request = route.calls.last.request
    assert request.url.params["refreshToken"] == "old-refresh-jwt"
    assert request.content == b""


def test_refresh_token_error() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/user/refreshToken").mock(return_value=httpx.Response(401, text="expired"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(AuthenticationError):
                client.user.refresh_token("stale")


def test_async_refresh_token() -> None:
    async def run() -> dict:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/user/refreshToken").mock(return_value=httpx.Response(200, json=TOKEN_VO))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                return await client.user.refresh_token("r")

    assert asyncio.run(run()) == TOKEN_VO
