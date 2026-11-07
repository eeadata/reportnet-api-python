# Generated from spec/api-docs.json by scripts/generate_resources.py.
# Do not edit by hand.

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ..models import generated

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


class DatasetSnapshotResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def delete_snapshot(
        self,
        id_dataset: int,
        id_snapshot: int,
    ) -> None:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, REPORTER WRITE

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD"""
        params = None
        url = f"/snapshot/v1/{id_snapshot}/dataset/{id_dataset}/delete"
        self._client.request("DELETE", url, params=params)
        return None

    def download_historic_releases_csv(
        self,
        dataflow_id: int,
        dataset_id: int,
        file_name: str,
        dest: str | os.PathLike[str],
        process_id: str | None = None,
    ) -> None:
        """downloadHistoricReleasesCSV

        Caution: if the export identified by `process_id` is still in progress
        or was canceled, the backend answers 200 with a plain-text "not ready"
        message instead of CSV, and that text is what lands in `dest`. Check the
        file content before trusting it."""
        params = {"dataflowId": dataflow_id, "fileName": file_name, "processId": process_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/snapshot/downloadHistoricReleases/{dataset_id}"
        self._client.download("GET", url, params=params, dest=dest)
        return None

    def export_historic_releases_csv(
        self,
        dataflow_id: int,
        dataset_id: int,
    ) -> str:
        """exportHistoricReleasesCSV

        Returns the download URL string (not CSV content): the backend starts an
        async export and answers with
        `/snapshot/downloadHistoricReleases/{id}?dataflowId=..&fileName=..&processId=..`.
        Pass its `fileName`/`processId` to `download_historic_releases_csv`."""
        params = {"dataflowId": dataflow_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/snapshot/exportHistoricReleases/{dataset_id}"
        response = self._client.request("POST", url, params=params)
        return response.text

    def historic_releases(
        self,
        dataflow_id: int | None = None,
        *,
        dataset_id: int,
    ) -> list[generated.ReleaseVO]:
        """Allowed roles:

        Reporting dataset: CUSTODIAN, STEWARD

        Data collection: CUSTODIAN, STEWARD

        EU dataset: CUSTODIAN, STEWARD"""
        params = {"dataflowId": dataflow_id, "datasetId": dataset_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = "/snapshot/v1/historicReleases"
        response = self._client.request("GET", url, params=params)
        return [generated.ReleaseVO.model_validate(item) for item in response.json()]


class AsyncDatasetSnapshotResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def delete_snapshot(
        self,
        id_dataset: int,
        id_snapshot: int,
    ) -> None:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, REPORTER WRITE

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD"""
        params = None
        url = f"/snapshot/v1/{id_snapshot}/dataset/{id_dataset}/delete"
        await self._client.request("DELETE", url, params=params)
        return None

    async def download_historic_releases_csv(
        self,
        dataflow_id: int,
        dataset_id: int,
        file_name: str,
        dest: str | os.PathLike[str],
        process_id: str | None = None,
    ) -> None:
        """downloadHistoricReleasesCSV

        Caution: if the export identified by `process_id` is still in progress
        or was canceled, the backend answers 200 with a plain-text "not ready"
        message instead of CSV, and that text is what lands in `dest`. Check the
        file content before trusting it."""
        params = {"dataflowId": dataflow_id, "fileName": file_name, "processId": process_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/snapshot/downloadHistoricReleases/{dataset_id}"
        await self._client.download("GET", url, params=params, dest=dest)
        return None

    async def export_historic_releases_csv(
        self,
        dataflow_id: int,
        dataset_id: int,
    ) -> str:
        """exportHistoricReleasesCSV

        Returns the download URL string (not CSV content): the backend starts an
        async export and answers with
        `/snapshot/downloadHistoricReleases/{id}?dataflowId=..&fileName=..&processId=..`.
        Pass its `fileName`/`processId` to `download_historic_releases_csv`."""
        params = {"dataflowId": dataflow_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/snapshot/exportHistoricReleases/{dataset_id}"
        response = await self._client.request("POST", url, params=params)
        return response.text

    async def historic_releases(
        self,
        dataflow_id: int | None = None,
        *,
        dataset_id: int,
    ) -> list[generated.ReleaseVO]:
        """Allowed roles:

        Reporting dataset: CUSTODIAN, STEWARD

        Data collection: CUSTODIAN, STEWARD

        EU dataset: CUSTODIAN, STEWARD"""
        params = {"dataflowId": dataflow_id, "datasetId": dataset_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = "/snapshot/v1/historicReleases"
        response = await self._client.request("GET", url, params=params)
        return [generated.ReleaseVO.model_validate(item) for item in response.json()]
