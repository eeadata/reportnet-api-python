from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from ._auth import TokenLike, TokenProvider
from ._core import (
    ACCEPT_ANY,
    DEFAULT_TIMEOUT,
    RequestCore,
    RetryPolicy,
    atomic_destination,
    ensure_same_origin,
    request_is_replayable,
    warn_if_insecure,
)
from .resources.dataflow_ext import AsyncDataflowResource
from .resources.dataset_schema_ext import AsyncDatasetSchemaResource
from .resources.dataset_snapshot import AsyncDatasetSnapshotResource
from .resources.datasets_ext import AsyncDatasetsResource
from .resources.eu_datasets import AsyncEuDatasetsResource
from .resources.reference_dataset_ext import AsyncReferenceDatasetResource
from .resources.release_receipts import AsyncReleaseReceiptsResource
from .resources.representative_ext import AsyncRepresentativeResource
from .resources.user_ext import AsyncUserResource
from .resources.validation_ext import AsyncValidationResource


class AsyncReportnetClient:
    """Async client for the EEA Reportnet 3 REST API."""

    def __init__(
        self,
        base_url: str,
        token: TokenLike,
        *,
        token_scheme: str = "Bearer",  # noqa: S107 - an auth scheme name, not a secret
        timeout: float | httpx.Timeout | None = DEFAULT_TIMEOUT,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._retry = retry
        self._core = RequestCore(TokenProvider(token, scheme=token_scheme))
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        warn_if_insecure(self._http.base_url)

        self.dataflow = AsyncDataflowResource(self)
        self.dataset_schema = AsyncDatasetSchemaResource(self)
        self.datasets = AsyncDatasetsResource(self)
        self.dataset_snapshot = AsyncDatasetSnapshotResource(self)
        self.eu_datasets = AsyncEuDatasetsResource(self)
        self.release_receipts = AsyncReleaseReceiptsResource(self)
        self.reference_dataset = AsyncReferenceDatasetResource(self)
        self.representative = AsyncRepresentativeResource(self)
        self.user = AsyncUserResource(self)
        self.validation = AsyncValidationResource(self)

    def __repr__(self) -> str:
        # Never include the token: only the base URL and the Authorization scheme.
        url, scheme = str(self._http.base_url), self._core.scheme
        return f"AsyncReportnetClient(base_url={url!r}, scheme={scheme!r})"

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        ensure_same_origin(self._http.base_url, self._http.build_request(method, path).url)
        headers = kwargs.pop("headers", None)
        # A file handle or one-shot stream is consumed by the first attempt.
        retry = self._retry if request_is_replayable(kwargs) else None
        attempt = 0
        while True:
            kwargs["headers"] = self._core.build_headers(headers)
            try:
                response = await self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                delay = retry.delay(attempt, method, error=exc) if retry else None
                if delay is None:
                    raise
            else:
                failed = not response.is_success
                delay = (
                    retry.delay(attempt, method, response=response) if retry and failed else None
                )
                if delay is None:
                    return self._core.handle_response(response)
            await asyncio.sleep(delay)
            attempt += 1

    async def download(
        self, method: str, path: str, *, dest: str | os.PathLike[str], **kwargs: Any
    ) -> None:
        """Stream a response body to `dest` without buffering it in memory."""
        ensure_same_origin(self._http.base_url, self._http.build_request(method, path).url)
        # Download endpoints declare `produces = octet-stream`; the JSON default
        # would 406, so default to */* (callers can still override `headers=`).
        kwargs["headers"] = self._core.build_headers(
            {**ACCEPT_ANY, **(kwargs.get("headers") or {})}
        )
        async with self._http.stream(method, path, **kwargs) as response:
            if not response.is_success:
                await response.aread()
                self._core.handle_response(response)
            with atomic_destination(dest) as part, part.open("wb") as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncReportnetClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
