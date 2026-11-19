# Generated from spec/api-docs.json by scripts/generate_resources.py.
# Do not edit by hand.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


class EuDatasetsResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def populate_data_from_data_collection(
        self,
        dataflow_id: int,
        job_id: int | None = None,
    ) -> None:
        """Allowed roles: CUSTODIAN, STEWARD"""
        params = {"jobId": job_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/euDataset/v1/populateData/dataflow/{dataflow_id}"
        self._client.request("POST", url, params=params)


class AsyncEuDatasetsResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def populate_data_from_data_collection(
        self,
        dataflow_id: int,
        job_id: int | None = None,
    ) -> None:
        """Allowed roles: CUSTODIAN, STEWARD"""
        params = {"jobId": job_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/euDataset/v1/populateData/dataflow/{dataflow_id}"
        await self._client.request("POST", url, params=params)
