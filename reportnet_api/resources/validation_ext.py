"""Hand-written Validation resource (run validation, read and export its results).

The Validation tag is absent from spec/api-docs.json ("Known spec-
snapshot gap") and every route here is `@ApiOperation(hidden = true)` in
`ValidationControllerImpl` (`validation-service`) / `JobControllerImpl`
(`orchestrator-service`). Paths are the ones the Reportnet UI calls. This file
is never touched by the generators.

Not covered: `PUT /validation/dataset/{id}` (the older direct start the job route
replaced) and the admin-only task routes. A "DL" (data-lake) variant of the
group listing was suggested by a third-party survey but exists in neither the
`develop` nor the `MasterDataLakes` branch of the Reportnet 3 backend repository, so it is not
implemented. All of this is mocked-test only: nothing has been run live.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._exceptions import NotFoundError
from ..jobs import JobError
from .dataflow_ext import _json_or_none

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient

_LEVELS = ("CORRECT", "WARNING", "ERROR", "INFO", "BLOCKER")
_ENTITIES = ("TABLE", "DATASET", "FIELD", "RECORD")


def _file_name(dataset_id: int) -> str:
    # ValidationServiceImpl#exportValidationFile composes exactly this name.
    return f"dataset-{dataset_id}-validations.csv"


def _check(values: list[str] | None, allowed: tuple[str, ...], what: str) -> list[str] | None:
    if values is None:
        return None
    bad = [v for v in values if v not in allowed]
    if bad:
        raise ValueError(f"{what} must be from {list(allowed)}, got {bad}")
    return list(values)


def _start_params(
    released: bool, dataflow_id: int | None, provider_id: int | None
) -> dict[str, str] | None:
    params = {"released": "true"} if released else {}
    if dataflow_id is not None:
        params["dataflowId"] = str(dataflow_id)
    if provider_id is not None:
        params["providerId"] = str(provider_id)
    return params or None


def _job_id_of_body(text: str) -> int | None:
    # `MasterOneVersion`'s JobControllerImpl#addValidationJob returns `Long jobId`;
    # `develop` and `MasterDataLakes` return void (an empty body).
    body = text.strip().strip('"')
    return int(body) if re.fullmatch(r"[0-9]+", body) else None


def _list_params(
    page_num: int,
    page_size: int,
    sort_by: str | None,
    asc: bool,
    level_errors: list[str] | None,
    type_entities: list[str] | None,
    table_filter: str | None,
    field_value_filter: str | None,
) -> dict[str, Any]:
    if page_num < 0 or page_size < 1:
        raise ValueError("page_num must be >= 0 and page_size >= 1")
    params: dict[str, Any] = {
        "pageNum": page_num,
        "pageSize": page_size,
        "headers": sort_by,
        "asc": str(asc).lower(),
        "levelErrorsFilter": _check(level_errors, _LEVELS, "level_errors"),
        "typeEntitiesFilter": _check(type_entities, _ENTITIES, "type_entities"),
        "tableFilter": table_filter,
        "fieldValueFilter": field_value_filter,
    }
    return {k: v for k, v in params.items() if v is not None}


class ValidationResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def start_validation(
        self,
        dataset_id: int,
        *,
        released: bool = False,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> int | None:
        """PUT /orchestrator/jobs/addValidationJob/{datasetId}: queue a validation.

        The route the Reportnet UI's "Validate" button calls. It only queues an
        Orchestrator job and returns the job's id (the backend's
        `MasterOneVersion` branch answers it as a bare number; live, 2026-11-06,
        `44570`), or None when the body is empty (older backends). Poll the id
        with `pollForJobStatus` (`easy.validate_and_wait()` does). Completion
        also shows as a `VALIDATION_FINISHED_EVENT` user notification
        (`GET /notification/findUserNotifications`). Read the results with
        `list_group_validations()` (or `_dl()`). This WRITES: it replaces the
        dataset's existing validation results and takes a dataset lock (a second
        start while one runs gets `423`). Roles: stewards, custodians, lead
        reporter, reporter write and similar (see `JobControllerImpl`), or ADMIN.
        `dataflow_id` and `provider_id` are optional; on `MasterOneVersion` they
        enable the route's ApiKey check (backend source, not tested live).
        `released` is for validating a dataset that is being released.
        """
        response = self._client.request(
            "PUT",
            f"/orchestrator/jobs/addValidationJob/{dataset_id}",
            params=_start_params(released, dataflow_id, provider_id),
        )
        return _job_id_of_body(response.text)

    def list_validations(
        self,
        dataset_id: int,
        *,
        page_num: int = 0,
        page_size: int = 20,
        sort_by: str | None = None,
        asc: bool = True,
        level_errors: list[str] | None = None,
        type_entities: list[str] | None = None,
        table_filter: str | None = None,
        field_value_filter: str | None = None,
    ) -> dict[str, Any] | None:
        """GET /validation/listValidations/{datasetId}: failed validations, one per failure.

        Returns the backend's `FailedValidationsDatasetVO`: `idDataset`,
        `idDatasetSchema`, `nameDataSetSchema`, `errors` (a list), `totalRecords`,
        `totalErrors` and `totalFilteredRecords`. Each error is one failure: `idValidation`, `idObject`, `idTableSchema`,
        `nameTableSchema`, `message`, `levelError`, `typeEntity`, `validationDate`,
        `nameFieldSchema`, `shortCode`.

        `page_num` is a 0-based page number; `page_size` defaults to 20 on the
        backend. `sort_by` is a column name (the backend maps `tableSchemaName`,
        `fieldSchemaName` and `entityType` to its own columns). `level_errors`
        takes `CORRECT`/`WARNING`/`ERROR`/`INFO`/`BLOCKER`, `type_entities`
        `TABLE`/`DATASET`/`FIELD`/`RECORD`. The backend swallows its own
        `EEAException` and answers an empty 200, so this can return `None`.
        Roles: any dataset role incl. observer/requester, custodians, stewards.
        For a data-lake dataflow (`bigData: true`) this answers empty even when the
        UI shows failures; there is no `DL` variant of this route (see
        `list_group_validations_dl()`).
        """
        params = _list_params(
            page_num,
            page_size,
            sort_by,
            asc,
            level_errors,
            type_entities,
            table_filter,
            field_value_filter,
        )
        response = self._client.request(
            "GET", f"/validation/listValidations/{dataset_id}", params=params
        )
        return _json_or_none(response)

    def list_group_validations(
        self,
        dataset_id: int,
        *,
        page_num: int = 0,
        page_size: int = 20,
        sort_by: str | None = None,
        asc: bool = True,
        level_errors: list[str] | None = None,
        type_entities: list[str] | None = None,
        table_filter: str | None = None,
        field_value_filter: str | None = None,
    ) -> dict[str, Any] | None:
        """GET /validation/listGroupValidations/{datasetId}: failed validations grouped by
        rule (what the UI shows).

        Returns the backend's `FailedValidationsDatasetVO`: `idDataset`,
        `idDatasetSchema`, `nameDataSetSchema`, `errors` (a list), `totalRecords`,
        `totalErrors` and `totalFilteredRecords`. Each error is one rule's failures grouped by code: `message`, `idRule`,
        `levelError`, `typeEntity`, `numberOfRecords`, `nameTableSchema`, `shortCode`,
        `nameFieldSchema` (what the UI's validation table shows).

        `page_num` is a 0-based page number; `page_size` defaults to 20 on the
        backend. `sort_by` is a column name (the backend maps `tableSchemaName`,
        `fieldSchemaName` and `entityType` to its own columns). `level_errors`
        takes `CORRECT`/`WARNING`/`ERROR`/`INFO`/`BLOCKER`, `type_entities`
        `TABLE`/`DATASET`/`FIELD`/`RECORD`. The backend swallows its own
        `EEAException` and answers an empty 200, so this can return `None`.
        Backend rule `checkAccessSuperUser('DATASET', id)`, not the role list of
        `list_validations`. For a data-lake dataflow (`bigData: true`) use
        `list_group_validations_dl()`: this one answers `errors: []` and
        `totalRecords: 0` there even when the UI shows failures.
        """
        params = _list_params(
            page_num,
            page_size,
            sort_by,
            asc,
            level_errors,
            type_entities,
            table_filter,
            field_value_filter,
        )
        response = self._client.request(
            "GET", f"/validation/listGroupValidations/{dataset_id}", params=params
        )
        return _json_or_none(response)

    def list_group_validations_dl(
        self,
        dataset_id: int,
        *,
        page_num: int = 0,
        page_size: int = 20,
        sort_by: str | None = None,
        asc: bool = True,
        level_errors: list[str] | None = None,
        type_entities: list[str] | None = None,
        table_filter: str | None = None,
        field_value_filter: str | None = None,
    ) -> dict[str, Any] | None:
        """GET /validation/listGroupValidationsDL/{datasetId}: grouped failures, data-lake datasets.

        For a dataflow whose `dataflow_datasets()` answer has `bigData: true`
        (data lake), validation results live in the data lake and
        `list_group_validations()` reads the empty old per-dataset database, so it
        answers `errors: []`, `totalRecords: 0`. This is the route the Reportnet UI
        calls for those datasets. Same arguments and answer shape as
        `list_group_validations()`. Live-tested on the sandbox (2026-10-27): it
        returned the same two rule groups and totals the UI shows. The backend source
        (`MasterDataLakes`) has no `DL` variant of `list_validations()` (one entry per
        failing record), so that one stays empty for data-lake datasets. The UI also
        sends a `shortCode` filter, not wrapped here.
        """
        params = _list_params(
            page_num,
            page_size,
            sort_by,
            asc,
            level_errors,
            type_entities,
            table_filter,
            field_value_filter,
        )
        response = self._client.request(
            "GET", f"/validation/listGroupValidationsDL/{dataset_id}", params=params
        )
        return _json_or_none(response)

    def start_validations_export(self, dataset_id: int) -> None:
        """POST /validation/export/{datasetId}: generate the validations CSV.

        Not a job: the backend writes `dataset-{id}-validations.csv` on the server
        and only notifies the Reportnet UI, so there is no id or status to poll.
        Fetch it with `download_validations_file()`, or use
        `export_validations_to_file()` which does both. Leaves a notification in the
        user's Reportnet UI.
        """
        self._client.request("POST", f"/validation/export/{dataset_id}")

    def download_validations_file(self, dataset_id: int, dest: str | os.PathLike[str]) -> bool:
        """GET /validation/downloadFile/{datasetId}: fetch the generated CSV to `dest`.

        Returns False (writing nothing) while the file does not exist yet (`404`),
        True once it was saved. The backend deletes the file after serving it, so a
        second call returns False again.
        """
        part = Path(f"{dest}.{uuid.uuid4().hex[:8]}.part")
        try:
            self._client.download(
                "GET",
                f"/validation/downloadFile/{dataset_id}",
                params={"fileName": _file_name(dataset_id)},
                dest=part,
            )
            if not part.exists() or part.stat().st_size == 0:
                return False
            part.replace(dest)
            return True
        except NotFoundError:
            return False
        finally:
            part.unlink(missing_ok=True)

    def export_validations_to_file(
        self,
        dataset_id: int,
        dest: str | os.PathLike[str],
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        """Generate the validations CSV and wait for it, saving it at `dest`.

        Calls `start_validations_export()` then polls `download_validations_file()`
        every `poll_interval` seconds; raises `JobError` after `timeout` seconds.
        Columns (from `ValidationServiceImpl`): entity, table, field, code, code
        name, code description, level error, message, number of records. A
        leftover file with the same name from an abandoned export could be served
        instead of a fresh one. The server path has no per-user part and the file
        is deleted when served, so two simultaneous exports of one dataset can
        take each other's file, and a dropped download loses it (export again).
        A failed export is not reported (the backend still answers 200), so it
        ends as a timeout.
        """
        self.start_validations_export(dataset_id)
        deadline = time.monotonic() + timeout
        while not self.download_validations_file(dataset_id, dest):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobError(
                    f"Validations file not ready within {timeout:g} seconds (the backend "
                    "answers 200 even when its export fails, so a failed export looks like this)"
                )
            time.sleep(min(poll_interval, remaining))


class AsyncValidationResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def start_validation(
        self,
        dataset_id: int,
        *,
        released: bool = False,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> int | None:
        """Async counterpart of ValidationResource.start_validation."""
        response = await self._client.request(
            "PUT",
            f"/orchestrator/jobs/addValidationJob/{dataset_id}",
            params=_start_params(released, dataflow_id, provider_id),
        )
        return _job_id_of_body(response.text)

    async def list_validations(
        self,
        dataset_id: int,
        *,
        page_num: int = 0,
        page_size: int = 20,
        sort_by: str | None = None,
        asc: bool = True,
        level_errors: list[str] | None = None,
        type_entities: list[str] | None = None,
        table_filter: str | None = None,
        field_value_filter: str | None = None,
    ) -> dict[str, Any] | None:
        """Async counterpart of ValidationResource.list_validations."""
        params = _list_params(
            page_num,
            page_size,
            sort_by,
            asc,
            level_errors,
            type_entities,
            table_filter,
            field_value_filter,
        )
        response = await self._client.request(
            "GET", f"/validation/listValidations/{dataset_id}", params=params
        )
        return _json_or_none(response)

    async def list_group_validations(
        self,
        dataset_id: int,
        *,
        page_num: int = 0,
        page_size: int = 20,
        sort_by: str | None = None,
        asc: bool = True,
        level_errors: list[str] | None = None,
        type_entities: list[str] | None = None,
        table_filter: str | None = None,
        field_value_filter: str | None = None,
    ) -> dict[str, Any] | None:
        """Async counterpart of ValidationResource.list_group_validations."""
        params = _list_params(
            page_num,
            page_size,
            sort_by,
            asc,
            level_errors,
            type_entities,
            table_filter,
            field_value_filter,
        )
        response = await self._client.request(
            "GET", f"/validation/listGroupValidations/{dataset_id}", params=params
        )
        return _json_or_none(response)

    async def list_group_validations_dl(
        self,
        dataset_id: int,
        *,
        page_num: int = 0,
        page_size: int = 20,
        sort_by: str | None = None,
        asc: bool = True,
        level_errors: list[str] | None = None,
        type_entities: list[str] | None = None,
        table_filter: str | None = None,
        field_value_filter: str | None = None,
    ) -> dict[str, Any] | None:
        """Async counterpart of ValidationResource.list_group_validations_dl."""
        params = _list_params(
            page_num,
            page_size,
            sort_by,
            asc,
            level_errors,
            type_entities,
            table_filter,
            field_value_filter,
        )
        response = await self._client.request(
            "GET", f"/validation/listGroupValidationsDL/{dataset_id}", params=params
        )
        return _json_or_none(response)

    async def start_validations_export(self, dataset_id: int) -> None:
        """Async counterpart of ValidationResource.start_validations_export."""
        await self._client.request("POST", f"/validation/export/{dataset_id}")

    async def download_validations_file(
        self, dataset_id: int, dest: str | os.PathLike[str]
    ) -> bool:
        """Async counterpart of ValidationResource.download_validations_file."""
        part = Path(f"{dest}.{uuid.uuid4().hex[:8]}.part")
        try:
            await self._client.download(
                "GET",
                f"/validation/downloadFile/{dataset_id}",
                params={"fileName": _file_name(dataset_id)},
                dest=part,
            )
            if not part.exists() or part.stat().st_size == 0:
                return False
            part.replace(dest)
            return True
        except NotFoundError:
            return False
        finally:
            part.unlink(missing_ok=True)

    async def export_validations_to_file(
        self,
        dataset_id: int,
        dest: str | os.PathLike[str],
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        """Async counterpart of ValidationResource.export_validations_to_file."""
        await self.start_validations_export(dataset_id)
        deadline = time.monotonic() + timeout
        while not await self.download_validations_file(dataset_id, dest):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobError(
                    f"Validations file not ready within {timeout:g} seconds (the backend "
                    "answers 200 even when its export fails, so a failed export looks like this)"
                )
            await asyncio.sleep(min(poll_interval, remaining))
