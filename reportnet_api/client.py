from __future__ import annotations

import os
import time
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
from .resources.dataflow_ext import DataflowResource
from .resources.dataset_schema_ext import DatasetSchemaResource
from .resources.dataset_snapshot import DatasetSnapshotResource
from .resources.datasets_ext import DatasetsResource
from .resources.eu_datasets import EuDatasetsResource
from .resources.reference_dataset_ext import ReferenceDatasetResource
from .resources.release_receipts import ReleaseReceiptsResource
from .resources.representative_ext import RepresentativeResource
from .resources.user_ext import UserResource
from .resources.validation_ext import ValidationResource


class ReportnetClient:
    """Sync client for the EEA Reportnet 3 REST API."""

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
        self._http = httpx.Client(base_url=base_url, timeout=timeout)
        warn_if_insecure(self._http.base_url)

        self.dataflow = DataflowResource(self)
        self.dataset_schema = DatasetSchemaResource(self)
        self.datasets = DatasetsResource(self)
        self.dataset_snapshot = DatasetSnapshotResource(self)
        self.eu_datasets = EuDatasetsResource(self)
        self.release_receipts = ReleaseReceiptsResource(self)
        self.reference_dataset = ReferenceDatasetResource(self)
        self.representative = RepresentativeResource(self)
        self.user = UserResource(self)
        self.validation = ValidationResource(self)

    def __repr__(self) -> str:
        # Never include the token: only the base URL and the Authorization scheme.
        return (
            f"ReportnetClient(base_url={str(self._http.base_url)!r}, scheme={self._core.scheme!r})"
        )

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        ensure_same_origin(self._http.base_url, self._http.build_request(method, path).url)
        headers = kwargs.pop("headers", None)
        # A file handle or one-shot stream is consumed by the first attempt.
        retry = self._retry if request_is_replayable(kwargs) else None
        attempt = 0
        while True:
            kwargs["headers"] = self._core.build_headers(headers)
            try:
                response = self._http.request(method, path, **kwargs)
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
            time.sleep(delay)
            attempt += 1

    def download(
        self, method: str, path: str, *, dest: str | os.PathLike[str], **kwargs: Any
    ) -> None:
        """Stream a response body to `dest` without buffering it in memory."""
        ensure_same_origin(self._http.base_url, self._http.build_request(method, path).url)
        # Download endpoints declare `produces = octet-stream`; the JSON default
        # would 406, so default to */* (callers can still override `headers=`).
        kwargs["headers"] = self._core.build_headers(
            {**ACCEPT_ANY, **(kwargs.get("headers") or {})}
        )
        with self._http.stream(method, path, **kwargs) as response:
            if not response.is_success:
                response.read()
                self._core.handle_response(response)
            with atomic_destination(dest) as part, part.open("wb") as fh:
                for chunk in response.iter_bytes():
                    fh.write(chunk)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ReportnetClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
