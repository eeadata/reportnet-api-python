from __future__ import annotations

import ipaddress
import math
import os
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, BinaryIO

import httpx

from ._auth import TokenProvider
from ._exceptions import error_for_response

# httpx treats an explicit `timeout=None` as "no timeout at all", so the clients
# need a real default. `read` is per-chunk, not per-response, so streamed
# exports/downloads aren't cut off as long as data keeps arriving; it's also
# the wait for the first byte, which some server-side exports take a while for.
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Transport errors worth repeating; permanent ones (UnsupportedProtocol,
# LocalProtocolError, ProxyError, ...) are deliberately not listed.
_TRANSIENT_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
# Raised before anything was sent, so repeating can't duplicate a write.
_NEVER_SENT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)

# Accept header for routes that produce octet-stream (downloads, file answers):
# the default `application/json` gets 406 there. Copy it (`dict(ACCEPT_ANY)`)
# before changing it.
ACCEPT_ANY: Mapping[str, str] = MappingProxyType({"Accept": "*/*"})


def caller_stacklevel() -> int:
    """The `stacklevel` that points a warning at the first frame outside this package."""
    # os.path on purpose: Path.resolve() follows symlinks, co_filename does not.
    package_dir = os.path.dirname(os.path.abspath(__file__)) + os.sep  # noqa: PTH100, PTH120
    level, frame = 1, sys._getframe(1)
    while frame is not None and os.path.abspath(  # noqa: PTH100 - same reason
        frame.f_code.co_filename
    ).startswith(package_dir):
        level += 1
        frame = frame.f_back  # type: ignore[assignment]
    return level


def _is_local(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def ensure_same_origin(base_url: httpx.URL, target: httpx.URL) -> None:
    """Refuse to send the credential to a host other than the configured one.

    A `path` may come from a server answer (a job's `pollingUrl`), so an absolute or
    protocol-relative URL on another origin must never receive the token.
    """

    def origin(url: httpx.URL) -> str:
        host = f"[{url.host}]" if ":" in url.host else url.host
        port = f":{url.port}" if url.port else ""
        return f"{url.scheme}://{host}{port}"

    if origin(target) != origin(base_url):
        raise ValueError(
            f"Refusing to send the credential to {origin(target)}: it is not the configured "
            f"base URL's origin ({origin(base_url)})"
        )


def warn_if_insecure(base_url: httpx.URL) -> None:
    """Warn when the credential would travel unencrypted (plain http to a non-local host)."""
    if base_url.scheme == "http" and not _is_local(base_url.host):
        import warnings

        warnings.warn(
            f"base_url {str(base_url)!r} uses plain http: the credential would be sent "
            "unencrypted. Use https.",
            UserWarning,
            stacklevel=caller_stacklevel(),
        )


def request_is_replayable(kwargs: dict[str, Any]) -> bool:
    """False if the request body can't be sent twice (file handle or one-shot stream)."""
    if "files" in kwargs:
        return False
    content, data = kwargs.get("content"), kwargs.get("data")
    return (content is None or isinstance(content, (bytes, str))) and (
        data is None or isinstance(data, dict)
    )


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """`Retry-After` as seconds (number or HTTP-date), or None if absent or unusable."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - datetime.now(UTC)).total_seconds()
    return seconds if math.isfinite(seconds) else None


@dataclass(frozen=True)
class RetryPolicy:
    """Opt-in retries for transient failures; pass as `retry=` to a client.

    Without a policy the clients never retry. What is retried, and why:

    - Status codes in `statuses` (429/502/503/504 by default), for GET/HEAD/OPTIONS only.
    - Connection failures and pool timeouts, where the request was never sent,
      for any method.
    - Other transient transport errors (timeouts, dropped connections), for
      GET/HEAD/OPTIONS only: the server may already have acted on a write.

    Never retried: 500 (every 500 seen live was deterministic, e.g. "Access is
    denied"), 423 (wait for the other job instead, e.g. `wait_for_job`),
    permanent errors such as a malformed `base_url`, and requests whose body
    can't be replayed (file uploads, streamed bodies). Waits grow as
    `backoff * 2**attempt` up to `max_delay`; a `Retry-After` (seconds or
    HTTP-date) replaces that (also capped).
    """

    retries: int = 3
    backoff: float = 0.5
    max_delay: float = 30.0
    statuses: frozenset[int] = frozenset({429, 502, 503, 504})

    def __post_init__(self) -> None:
        if self.retries < 0:
            raise ValueError(f"retries must be >= 0, got {self.retries}")
        for name in ("backoff", "max_delay"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite number >= 0, got {value}")

    def delay(
        self,
        attempt: int,
        method: str,
        *,
        response: httpx.Response | None = None,
        error: httpx.TransportError | None = None,
    ) -> float | None:
        """Seconds to wait before retry number `attempt + 1`, or None to give up."""
        if attempt >= self.retries:
            return None
        idempotent = method.upper() in _IDEMPOTENT_METHODS
        if error is not None:
            if not isinstance(error, _TRANSIENT_ERRORS):
                return None
            if not (isinstance(error, _NEVER_SENT_ERRORS) or idempotent):
                return None
        elif response is None or response.status_code not in self.statuses or not idempotent:
            return None
        wait: float = min(self.backoff * 2**attempt, self.max_delay)
        if response is not None:
            asked = _retry_after_seconds(response)
            if asked is not None:
                wait = min(max(asked, 0.0), self.max_delay)
        return wait


class RequestCore:
    """Request/response plumbing shared by ReportnetClient and AsyncReportnetClient.

    Builds auth headers and maps HTTP error responses to `ReportnetAPIError`
    subclasses, so this logic is never duplicated between the sync and async
    transports.
    """

    def __init__(self, auth: TokenProvider) -> None:
        self._auth = auth

    @property
    def scheme(self) -> str:
        return self._auth.scheme

    def build_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        merged = {"Accept": "application/json"}
        merged.update(self._auth.auth_header())
        for name, value in (headers or {}).items():
            # HTTP header names are case-insensitive: drop any default that
            # the caller's key would otherwise duplicate (e.g. "accept").
            for existing in [k for k in merged if k.lower() == name.lower()]:
                del merged[existing]
            merged[name] = value
        return merged

    def handle_response(self, response: httpx.Response) -> httpx.Response:
        error = error_for_response(response)
        if error is not None:
            raise error
        return response


@contextmanager
def stream_upload_file(
    field_name: str, file: str | os.PathLike[str]
) -> Iterator[dict[str, tuple[str, BinaryIO]]]:
    """Open `file` for a path-based streaming multipart upload.

    httpx reads from the file handle lazily while sending the request, so
    the file is never fully buffered in memory.
    """
    path = Path(file)
    with path.open("rb") as fh:
        yield {field_name: (path.name, fh)}
