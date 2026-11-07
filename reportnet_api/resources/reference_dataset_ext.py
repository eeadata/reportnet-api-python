"""Hand-written Reference-dataset resource (lock / unlock a reference dataset).

`ReferenceDatasetControllerImpl` (`dataset-service`) is `@ApiIgnore` and its
`PUT /referenceDataset/{datasetId}` is `@ApiOperation(hidden = true)`, so it is
absent from spec/api-docs.json ("Known spec-snapshot gap"). The
controller and `ReferenceDatasetServiceImpl#updateUpdatableReferenceDataset`
are identical on the `develop` and `MasterDataLakes` branches of
the Reportnet 3 backend repository. The controller's other routes are `/private/*` (stripped by
the gateway) or read-only lookups and are not covered. This file is never
touched by the generators. Mocked-test only: nothing has been run live.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


def _bool_param(updatable: bool) -> str:
    # Strict: bool("false") is True, which would silently unlock instead of lock.
    if not isinstance(updatable, bool):
        raise TypeError(f"updatable must be a bool, got {type(updatable).__name__}")
    return "true" if updatable else "false"


class ReferenceDatasetResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def set_updatable(self, dataset_id: int, updatable: bool) -> None:
        """Lock or unlock a reference dataset (`PUT /referenceDataset/{datasetId}`).

        The backend sets the reference dataset's `updatable` flag. Setting it to
        False ("lock") also generates the reference dataset's files
        (`FileTreatmentHelper#createReferenceDatasetFiles`), so it is more than a
        flag flip; True ("unlock") only saves the flag. Answers an empty 200.
        `404` is returned both when the dataset is not a reference dataset and
        for any I/O failure while generating the files (the controller maps
        `EEAException`/`IOException` to the same 404). Roles (`@PreAuthorize`):
        dataset/dataschema/reference-dataset custodian, steward, steward support,
        observer or reference lead reporter on the dataset, or a data custodian/
        steward with access to the reference entity; not documented for ApiKey.
        This WRITES. A PUT is never retried after the request was sent (see
        `RetryPolicy`), so a lock is not re-run by a retry.

        Raises `TypeError` if `updatable` is not a real `bool`.
        """
        self._client.request(
            "PUT",
            f"/referenceDataset/{dataset_id}",
            params={"updatable": _bool_param(updatable)},
        )


class AsyncReferenceDatasetResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def set_updatable(self, dataset_id: int, updatable: bool) -> None:
        """Async counterpart of `ReferenceDatasetResource.set_updatable`.

        Lock or unlock a reference dataset (`PUT /referenceDataset/{datasetId}`).
        This WRITES, and `updatable=False` ("lock") also makes the backend
        generate the reference dataset's files. Answers an empty 200; `404` for a
        non-reference dataset or a file-generation failure. Raises `TypeError` if
        `updatable` is not a real `bool`.
        """
        await self._client.request(
            "PUT",
            f"/referenceDataset/{dataset_id}",
            params={"updatable": _bool_param(updatable)},
        )
