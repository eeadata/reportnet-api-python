"""Small shared builders for tests."""

from typing import TypeVar

import httpx

from reportnet_api import ReportnetAPIError

E = TypeVar("E", bound=ReportnetAPIError)


def api_error(cls: type[E], status: int, body: str = "", message: str = "x") -> E:
    """An API error of type `cls` with a real (minimal) request and response attached."""
    request = httpx.Request("GET", "https://api.reportnet.europa.eu/test")
    response = httpx.Response(status, text=body, request=request)
    return cls(message, status_code=status, response_body=body, request=request, response=response)
