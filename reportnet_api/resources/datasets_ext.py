"""Hand-written extension of the generated DatasetsResource classes.

Adds endpoints hidden from Swagger via `@ApiOperation(hidden = true)` in the
live backend, so they never appear in spec/api-docs.json ("Known
spec-snapshot gap"), and helpers that wait for the async Orchestrator jobs
behind the `etl_export_*` v3/v4/v5 and `import_big_file_data` methods (polling
lives in `reportnet_api/jobs.py`). This file is never touched by
scripts/generate_resources.py since it lives outside datasets.py.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import uuid
import warnings
from pathlib import Path
from typing import Any

from .._exceptions import NotFoundError
from ..jobs import (
    JobError,
    Progress,
    async_wait_for_job,
    download_url_of,
    import_statistics_changed,
    progress_event,
    progress_scope,
    wait_for_job,
)
from .datasets import AsyncDatasetsResource as _GeneratedAsyncDatasetsResource
from .datasets import DatasetsResource as _GeneratedDatasetsResource

ExportJobError = JobError  # name from before the shared poller; same class

_EXPORT_TO_FILE_DOC = """{summary}

        `{starter}()` (`{route}`) only starts an async job. This polls its
        `pollingUrl` (`/orchestrator/jobs/pollForJobStatus/{{jobId}}`, answers
        `{{"status": ...}}`; `QUEUED` / `IN_PROGRESS` while it runs, see
        `reportnet_api.jobs`) every `poll_interval` seconds until `FINISHED`, then
        downloads the `downloadUrl` it returns
        (`/orchestrator/jobs/downloadEtlExportedFile/{{jobId}}`) to `dest`.
        Raises `JobError` (`ExportJobError`) on a failed/refused/cancelled job, on
        an `error` answer, or after `timeout` seconds. Same roles as `{starter}()`.
        `progress=True` shows one updating status line, a callable gets event dicts
        (see `reportnet_api.jobs.progress_event`).

        Written from the `MasterDataLakes` branch of the Reportnet 3 backend repository (the job
        and the orchestrator's poll/download routes); untested live.
        """

_WAIT_FOR_JOB_DOC = """Wait for an async job to finish and return its last status answer.

        Pass what `import_big_file_data()` (or any job-starting method) returned,
        or its `pollingUrl`. Polls every `poll_interval` seconds; raises `JobError`
        on a failed/refused/cancelled job or after `timeout` seconds. For an import,
        `FINISHED` is the job's own completion; `check_import_process()` is not a
        reliable signal (live-tested). `progress=True` shows one updating status
        line, a callable gets event dicts (`reportnet_api.jobs.progress_event`).
        Untested live.
        """

# After a big-file job reports FINISHED it is authoritative; statistics only get
# this long to show the change (they can lag, or stay equal for an empty/identical file).
_STATS_GRACE = 10.0

# Indirection so tests can drive import_file_and_wait's clock without patching `time`/`asyncio`.
_monotonic = time.monotonic
_sleep = time.sleep
_async_sleep = asyncio.sleep

_NO_JOB_MESSAGE = (
    "The file was uploaded but the answer carried no pollingUrl to wait on ({job!r}); "
    "the import may still complete, so check get_import_related_statistics() before retrying"
)

_IMPORT_AND_WAIT_DOC = """Upload a file into a dataset and wait until the import is visible.

        Reads `get_import_related_statistics()` as a baseline, uploads `file` with
        `import_big_file_data()` (`big_file=True`, the default; async job) or
        `import_file_data()` (`big_file=False`; returns nothing and merges in the
        background), then waits:

        - big file: polls the answer's `pollingUrl` until the job is `FINISHED`
          (`wait_for_job()`); if the answer has no `pollingUrl` this step is skipped.
          Once the job is `FINISHED` it is authoritative: statistics then get only a
          short grace period to show the change, after which the latest statistics
          are returned anyway (an empty or identical file may change nothing).
        - otherwise (small file, or no `pollingUrl`): polls
          `get_import_related_statistics()` until a table's
          `(lastImportDate, numberOfRecordsImported)` differs from the baseline
          (only `table_schema_id`'s table when given), else raises on timeout.
          Pass `confirm_statistics=False` to trust the job alone (big file only; a
          missing `pollingUrl` then raises, though the upload was already sent).

        `check_import_process()` is never used: its lock stayed set long after
        the data was in (live-tested). `list_imported_files()` is not used
        either: a file is listed before its data is merged. Returns the final
        statistics answer. Raises `JobError` on a failed/refused/cancelled job,
        or when `timeout` seconds pass while waiting (the upload may still complete
        afterwards; nothing is rolled back, so check before retrying). `timeout`
        bounds the waiting, not the baseline read or the upload itself, and
        `poll_interval` / `timeout` apply to both polling phases combined. Roles as
        for the underlying import method. `progress=True` shows one updating status
        line (a callable gets event dicts); its elapsed time counts from the start
        of the waiting.

        Limits of the statistics check: without `table_schema_id` any table's
        change counts, so a concurrent import into the same dataset can be
        mistaken for yours; and a `replace` that makes a table drop out of the
        statistics is not seen as a change.

        Verified live (2026-10-23, Bearer, scratch dataset): `import_big_file_data`
        returns a `pollingUrl` carrying `datasetId`/`dataflowId`, the job reached
        `FINISHED` in ~20s, and `lastImportDate` changed (the count stayed at 1:
        `numberOfRecordsImported` looks like the last import's rows, not a table
        total, so don't compare the count alone). The file name must match a table
        name or the job is `CANCELED`. The imported row was confirmed in the table
        via the v4 CSV export. An ApiKey import also worked (job
        FINISHED, statistics changed). NOT verified live: the `big_file=False`
        path with this helper.
        """

_EXPORT_DOCS = {
    "zip_csv": _EXPORT_TO_FILE_DOC.format(
        summary="Export a dataset as a ZIP of CSV files into `dest`, waiting for the job.",
        starter="etl_export_zip_csv",
        route="/dataset/v4/etlExport/{id}",
    ),
    "zip_parquet": _EXPORT_TO_FILE_DOC.format(
        summary="Export a dataset as a ZIP of Parquet files into `dest`, waiting for the job.",
        starter="etl_export_zip_parquet",
        route="/dataset/v5/etlExport/{id}",
    ),
    "with_job": _EXPORT_TO_FILE_DOC.format(
        summary="Export a dataset (v3 job variant) into `dest`, waiting for the job.",
        starter="etl_export_dataset_with_job",
        route="/dataset/v3/etlExport/{id}",
    ),
}

_DELETE_IMPORT_TABLE_DOC = """DELETE /dataset/{dataset_id}/deleteImportTable/{table_schema_id}

        Deletes all data in one table. Hidden legacy (unversioned) alias of
        `delete_table_data()` (`/dataset/v1/{id}/deleteTableData/{tableId}`):
        `DatasetControllerImpl#deleteImportTableLegacy` just calls
        `deleteTableData`. The Reportnet FME integration uses this route.
        Destructive and not undoable. Returns `None` (the controller is `void`).

        Role rules are the same as `delete_table_data()`; the hidden route
        also accepts an ApiKey (`dataflow_id`/`provider_id` feed that check).
        Untested live: the backend source audited is older than production.
        """


_FILE_EXPORT_NOTE = """

        Not job-based: the backend starts generating the file in the background
        and tells only the Reportnet UI (a user notification); there is no job
        id or polling URL. `fetch_export_file()` / the `*_to_file()` helpers
        therefore poll the download until a non-empty body arrives. A file left
        from an earlier export with the same name can be served instead of the
        new one (the normal download deletes the file, the `big_data` one does not).
        Read from `DatasetControllerImpl` / `FileTreatmentHelper` (`MasterDataLakes`
        branch; `develop` has no `big_data` variants). Live (2026-10-23, Bearer only: the
        routes reject an ApiKey with 403) production behaves like the `big_data`
        (`...DL`) routes, which is what the Reportnet UI calls; the plain routes
        accepted a request but never produced a file. Hence `big_data=True` is the
        default; for the dataset export use `zip csv` (plain `csv` produced no file).
        """


def _file_route(name: str, big_data: bool) -> str:
    return f"{name}DL" if big_data else name


def _table_export_request(
    dataset_id: int,
    mime_type: str,
    table_schema_id: str | None,
    level_error: list[str] | None,
    id_rules: str | None,
    field_value: str | None,
    big_data: bool,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    params: dict[str, Any] = {"datasetId": dataset_id, "mimeType": mime_type}
    if table_schema_id is not None:
        params["tableSchemaId"] = table_schema_id
    # The big-data route reads these without a null check, so always send them.
    body: dict[str, Any] = {
        "levelError": level_error or [],
        "idRules": id_rules or "",
        "fieldValue": field_value or "",
    }
    if big_data:
        body["qcCodes"] = ""  # a String in the backend's ExportFilterVO (MasterDataLakes)
    return "/dataset/" + _file_route("exportFile", big_data), params, body


def _check_extension(mime_type: str) -> None:
    """A table export is saved as `<table>.<mime_type>`, so it must be a bare extension."""
    if (
        not mime_type
        or mime_type != mime_type.strip()
        or " " in mime_type
        or mime_type.startswith(".")
    ):
        raise ValueError(
            f"mime_type must be a bare file extension such as 'csv' or 'xlsx', got {mime_type!r}"
        )


_STALE_WARNING = (
    "An export file named {name!r} already exists on the server and may be returned instead "
    "of the new export; compare the result with the dataset if the data changed."
)


def _dataset_file_name(dataset_name: str, mime_type: str) -> str:
    """File the dataset export writes: `<name>.zip` for `zip csv`/`zip xlsx`, else `<name>.<ext>`."""
    parts = mime_type.split()
    return (
        f"{dataset_name}.zip"
        if len(parts) > 1 and parts[0] == "zip"
        else f"{dataset_name}.{parts[-1]}"
    )


class DatasetsResource(_GeneratedDatasetsResource):
    def delete_import_table(
        self,
        dataset_id: int,
        table_schema_id: str,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> None:
        params = {"dataflowId": dataflow_id, "providerId": provider_id}
        params = {k: v for k, v in params.items() if v is not None}
        self._client.request(
            "DELETE", f"/dataset/{dataset_id}/deleteImportTable/{table_schema_id}", params=params
        )

    delete_import_table.__doc__ = _DELETE_IMPORT_TABLE_DOC

    def update_dataset_name(self, dataset_id: int, name: str) -> None:
        """PUT /datasetmetabase/updateDatasetName: rename a dataset (as the web
        app renames a design dataset, i.e. its schema).

        `DatasetMetabaseControllerImpl#updateDatasetName` (hidden). Requires
        `DATASCHEMA_STEWARD`, `DATASCHEMA_CUSTODIAN` or `DATASCHEMA_EDITOR_WRITE`
        on the dataset. The backend trims `name` and answers `400` unless it
        matches `[a-zA-Z0-9\\s()_-]+`, or for an unknown dataset. It does not
        check that the name is unique in the dataflow.
        """
        self._client.request(
            "PUT",
            "/datasetmetabase/updateDatasetName",
            params={"datasetId": dataset_id, "datasetName": name},
        )

    def wait_for_job(
        self,
        job: dict[str, Any] | str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        progress: Progress = None,
    ) -> dict[str, Any]:
        return wait_for_job(
            self._client, job, poll_interval=poll_interval, timeout=timeout, progress=progress
        )

    wait_for_job.__doc__ = _WAIT_FOR_JOB_DOC

    def import_file_and_wait(
        self,
        dataset_id: int,
        file: str | os.PathLike[str],
        *,
        dataflow_id: int | None = None,
        delimiter: str | None = None,
        integration_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        big_file: bool = True,
        confirm_statistics: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        progress: Progress = None,
    ) -> dict[str, Any]:
        before = self.get_import_related_statistics(dataset_id)
        options: dict[str, Any] = {
            "dataflow_id": dataflow_id,
            "delimiter": delimiter,
            "integration_id": integration_id,
            "provider_id": provider_id,
            "replace": replace,
            "table_schema_id": table_schema_id,
        }
        job_finished = False
        with progress_scope(progress) as report:
            job: Any = None  # only a big-file upload answers with a job to wait on
            if big_file:
                job = self.import_big_file_data(dataset_id, file, **options)
            else:
                self.import_file_data(dataset_id, file, **options)
            # `timeout` bounds the waiting, not the upload.
            started = _monotonic()
            deadline = started + timeout
            if isinstance(job, dict) and job.get("pollingUrl"):
                remaining = max(0.0, deadline - _monotonic())
                wait_for_job(
                    self._client,
                    job,
                    poll_interval=poll_interval,
                    timeout=remaining,
                    progress=report,
                )
                job_finished = True
                deadline = min(deadline, _monotonic() + _STATS_GRACE)
            elif big_file and not confirm_statistics:
                raise JobError(_NO_JOB_MESSAGE.format(job=job))
            while True:
                after = self.get_import_related_statistics(dataset_id)
                if (big_file and not confirm_statistics) or import_statistics_changed(
                    before, after, table_schema_id
                ):
                    return after
                if _monotonic() >= deadline:
                    if job_finished:
                        return after
                    raise JobError(f"Import not visible in statistics within {timeout:g} seconds")
                if report:
                    elapsed = _monotonic() - started
                    report(progress_event("confirm", elapsed=elapsed))
                _sleep(poll_interval)

    import_file_and_wait.__doc__ = _IMPORT_AND_WAIT_DOC

    def _finish_export(
        self,
        job: dict[str, Any],
        dest: str | os.PathLike[str],
        poll_interval: float,
        timeout: float,
        progress: Progress = None,
    ) -> None:
        answer = wait_for_job(
            self._client, job, poll_interval=poll_interval, timeout=timeout, progress=progress
        )
        self._client.download("GET", download_url_of(answer), dest=dest)

    def export_zip_csv_to_file(
        self,
        dataset_id: int,
        *,
        dataflow_id: int,
        dest: str | os.PathLike[str],
        table_schema_id: str | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        progress: Progress = None,
    ) -> None:
        job = self.etl_export_zip_csv(
            dataset_id, table_schema_id=table_schema_id, dataflow_id=dataflow_id
        )
        self._finish_export(job, dest, poll_interval, timeout, progress)

    export_zip_csv_to_file.__doc__ = _EXPORT_DOCS["zip_csv"]

    def export_zip_parquet_to_file(
        self,
        dataset_id: int,
        *,
        dataflow_id: int,
        dest: str | os.PathLike[str],
        table_schema_id: str | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        progress: Progress = None,
    ) -> None:
        job = self.etl_export_zip_parquet(
            dataset_id, table_schema_id=table_schema_id, dataflow_id=dataflow_id
        )
        self._finish_export(job, dest, poll_interval, timeout, progress)

    export_zip_parquet_to_file.__doc__ = _EXPORT_DOCS["zip_parquet"]

    def export_dataset_with_job_to_file(
        self,
        dataset_id: int,
        *,
        dataflow_id: int,
        dest: str | os.PathLike[str],
        table_schema_id: str | None = None,
        provider_id: int | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        progress: Progress = None,
    ) -> None:
        job = self.etl_export_dataset_with_job(
            dataset_id,
            table_schema_id=table_schema_id,
            provider_id=provider_id,
            dataflow_id=dataflow_id,
        )
        self._finish_export(job, dest, poll_interval, timeout, progress)

    export_dataset_with_job_to_file.__doc__ = _EXPORT_DOCS["with_job"]

    def start_table_export(
        self,
        dataset_id: int,
        *,
        mime_type: str = "csv",
        table_schema_id: str | None = None,
        level_error: list[str] | None = None,
        id_rules: str | None = None,
        field_value: str | None = None,
        big_data: bool = True,
    ) -> None:
        path, params, body = _table_export_request(
            dataset_id, mime_type, table_schema_id, level_error, id_rules, field_value, big_data
        )
        self._client.request("POST", path, params=params, json=body)

    def start_dataset_export(
        self, dataset_id: int, *, mime_type: str = "csv", big_data: bool = True
    ) -> None:
        self._client.request(
            "GET",
            f"/dataset/{dataset_id}/" + _file_route("exportDatasetFile", big_data),
            params={"mimeType": mime_type},
        )

    def fetch_export_file(
        self,
        dataset_id: int,
        file_name: str,
        *,
        dest: str | os.PathLike[str],
        big_data: bool = True,
    ) -> bool:
        part = Path(f"{dest}.{uuid.uuid4().hex[:8]}.part")
        try:
            self._client.download(
                "GET",
                f"/dataset/{dataset_id}/" + _file_route("downloadFile", big_data),
                params={"fileName": file_name},
                dest=part,
            )
            if not part.exists() or part.stat().st_size == 0:
                return False
            part.replace(dest)
            return True
        except NotFoundError:
            return False  # not generated yet
        finally:
            part.unlink(missing_ok=True)

    def _warn_if_stale(self, dataset_id: int, file_name: str, big_data: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe"
            if self.fetch_export_file(dataset_id, file_name, dest=probe, big_data=big_data):
                warnings.warn(_STALE_WARNING.format(name=file_name), RuntimeWarning, stacklevel=4)

    def _wait_for_export_file(
        self,
        dataset_id: int,
        file_name: str,
        dest: str | os.PathLike[str],
        big_data: bool,
        poll_interval: float,
        timeout: float,
        progress: Progress = None,
    ) -> None:
        started = time.monotonic()
        deadline = started + timeout
        with progress_scope(progress) as report:
            while not self.fetch_export_file(dataset_id, file_name, dest=dest, big_data=big_data):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise JobError(
                        f"Export file {file_name!r} not ready within {timeout:g} seconds"
                    )
                if report:
                    report(progress_event("file", elapsed=time.monotonic() - started))
                time.sleep(min(poll_interval, remaining))

    def export_table_to_file(
        self,
        dataset_id: int,
        *,
        table_name: str,
        table_schema_id: str,
        dest: str | os.PathLike[str],
        mime_type: str = "csv",
        level_error: list[str] | None = None,
        id_rules: str | None = None,
        field_value: str | None = None,
        big_data: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        progress: Progress = None,
    ) -> None:
        _check_extension(mime_type)
        file_name = f"{table_name}.{mime_type}"
        self._warn_if_stale(dataset_id, file_name, big_data)
        self.start_table_export(
            dataset_id,
            mime_type=mime_type,
            table_schema_id=table_schema_id,
            level_error=level_error,
            id_rules=id_rules,
            field_value=field_value,
            big_data=big_data,
        )
        self._wait_for_export_file(
            dataset_id, file_name, dest, big_data, poll_interval, timeout, progress
        )

    def export_dataset_to_file(
        self,
        dataset_id: int,
        *,
        dataset_name: str,
        dest: str | os.PathLike[str],
        mime_type: str = "csv",
        big_data: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        progress: Progress = None,
    ) -> None:
        file_name = _dataset_file_name(dataset_name, mime_type)
        self._warn_if_stale(dataset_id, file_name, big_data)
        self.start_dataset_export(dataset_id, mime_type=mime_type, big_data=big_data)
        self._wait_for_export_file(
            dataset_id,
            file_name,
            dest,
            big_data,
            poll_interval,
            timeout,
            progress,
        )


class AsyncDatasetsResource(_GeneratedAsyncDatasetsResource):
    async def delete_import_table(
        self,
        dataset_id: int,
        table_schema_id: str,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> None:
        params = {"dataflowId": dataflow_id, "providerId": provider_id}
        params = {k: v for k, v in params.items() if v is not None}
        await self._client.request(
            "DELETE", f"/dataset/{dataset_id}/deleteImportTable/{table_schema_id}", params=params
        )

    delete_import_table.__doc__ = _DELETE_IMPORT_TABLE_DOC

    async def update_dataset_name(self, dataset_id: int, name: str) -> None:
        """Async counterpart of DatasetsResource.update_dataset_name."""
        await self._client.request(
            "PUT",
            "/datasetmetabase/updateDatasetName",
            params={"datasetId": dataset_id, "datasetName": name},
        )

    async def wait_for_job(
        self, job: dict[str, Any] | str, *, poll_interval: float = 2.0, timeout: float = 300.0
    ) -> dict[str, Any]:
        return await async_wait_for_job(
            self._client, job, poll_interval=poll_interval, timeout=timeout
        )

    wait_for_job.__doc__ = _WAIT_FOR_JOB_DOC

    async def import_file_and_wait(
        self,
        dataset_id: int,
        file: str | os.PathLike[str],
        *,
        dataflow_id: int | None = None,
        delimiter: str | None = None,
        integration_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        big_file: bool = True,
        confirm_statistics: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        before = await self.get_import_related_statistics(dataset_id)
        options: dict[str, Any] = {
            "dataflow_id": dataflow_id,
            "delimiter": delimiter,
            "integration_id": integration_id,
            "provider_id": provider_id,
            "replace": replace,
            "table_schema_id": table_schema_id,
        }
        job_finished = False
        job: Any = None  # only a big-file upload answers with a job to wait on
        if big_file:
            job = await self.import_big_file_data(dataset_id, file, **options)
        else:
            await self.import_file_data(dataset_id, file, **options)
        # `timeout` bounds the waiting, not the upload.
        deadline = _monotonic() + timeout
        if isinstance(job, dict) and job.get("pollingUrl"):
            remaining = max(0.0, deadline - _monotonic())
            await async_wait_for_job(
                self._client, job, poll_interval=poll_interval, timeout=remaining
            )
            job_finished = True
            deadline = min(deadline, _monotonic() + _STATS_GRACE)
        elif big_file and not confirm_statistics:
            raise JobError(_NO_JOB_MESSAGE.format(job=job))
        while True:
            after = await self.get_import_related_statistics(dataset_id)
            if (big_file and not confirm_statistics) or import_statistics_changed(
                before, after, table_schema_id
            ):
                return after
            if _monotonic() >= deadline:
                if job_finished:
                    return after
                raise JobError(f"Import not visible in statistics within {timeout:g} seconds")
            await _async_sleep(poll_interval)

    import_file_and_wait.__doc__ = _IMPORT_AND_WAIT_DOC

    async def _finish_export(
        self,
        job: dict[str, Any],
        dest: str | os.PathLike[str],
        poll_interval: float,
        timeout: float,
    ) -> None:
        answer = await async_wait_for_job(
            self._client, job, poll_interval=poll_interval, timeout=timeout
        )
        await self._client.download("GET", download_url_of(answer), dest=dest)

    async def export_zip_csv_to_file(
        self,
        dataset_id: int,
        *,
        dataflow_id: int,
        dest: str | os.PathLike[str],
        table_schema_id: str | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        job = await self.etl_export_zip_csv(
            dataset_id, table_schema_id=table_schema_id, dataflow_id=dataflow_id
        )
        await self._finish_export(job, dest, poll_interval, timeout)

    export_zip_csv_to_file.__doc__ = _EXPORT_DOCS["zip_csv"]

    async def export_zip_parquet_to_file(
        self,
        dataset_id: int,
        *,
        dataflow_id: int,
        dest: str | os.PathLike[str],
        table_schema_id: str | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        job = await self.etl_export_zip_parquet(
            dataset_id, table_schema_id=table_schema_id, dataflow_id=dataflow_id
        )
        await self._finish_export(job, dest, poll_interval, timeout)

    export_zip_parquet_to_file.__doc__ = _EXPORT_DOCS["zip_parquet"]

    async def export_dataset_with_job_to_file(
        self,
        dataset_id: int,
        *,
        dataflow_id: int,
        dest: str | os.PathLike[str],
        table_schema_id: str | None = None,
        provider_id: int | None = None,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        job = await self.etl_export_dataset_with_job(
            dataset_id,
            table_schema_id=table_schema_id,
            provider_id=provider_id,
            dataflow_id=dataflow_id,
        )
        await self._finish_export(job, dest, poll_interval, timeout)

    export_dataset_with_job_to_file.__doc__ = _EXPORT_DOCS["with_job"]

    async def start_table_export(
        self,
        dataset_id: int,
        *,
        mime_type: str = "csv",
        table_schema_id: str | None = None,
        level_error: list[str] | None = None,
        id_rules: str | None = None,
        field_value: str | None = None,
        big_data: bool = True,
    ) -> None:
        path, params, body = _table_export_request(
            dataset_id, mime_type, table_schema_id, level_error, id_rules, field_value, big_data
        )
        await self._client.request("POST", path, params=params, json=body)

    async def start_dataset_export(
        self, dataset_id: int, *, mime_type: str = "csv", big_data: bool = True
    ) -> None:
        await self._client.request(
            "GET",
            f"/dataset/{dataset_id}/" + _file_route("exportDatasetFile", big_data),
            params={"mimeType": mime_type},
        )

    async def fetch_export_file(
        self,
        dataset_id: int,
        file_name: str,
        *,
        dest: str | os.PathLike[str],
        big_data: bool = True,
    ) -> bool:
        part = Path(f"{dest}.{uuid.uuid4().hex[:8]}.part")
        try:
            await self._client.download(
                "GET",
                f"/dataset/{dataset_id}/" + _file_route("downloadFile", big_data),
                params={"fileName": file_name},
                dest=part,
            )
            if not part.exists() or part.stat().st_size == 0:
                return False
            part.replace(dest)
            return True
        except NotFoundError:
            return False  # not generated yet
        finally:
            part.unlink(missing_ok=True)

    async def _warn_if_stale(self, dataset_id: int, file_name: str, big_data: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe"
            if await self.fetch_export_file(dataset_id, file_name, dest=probe, big_data=big_data):
                warnings.warn(_STALE_WARNING.format(name=file_name), RuntimeWarning, stacklevel=4)

    async def _wait_for_export_file(
        self,
        dataset_id: int,
        file_name: str,
        dest: str | os.PathLike[str],
        big_data: bool,
        poll_interval: float,
        timeout: float,
    ) -> None:
        deadline = time.monotonic() + timeout
        while not await self.fetch_export_file(dataset_id, file_name, dest=dest, big_data=big_data):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobError(f"Export file {file_name!r} not ready within {timeout:g} seconds")
            await asyncio.sleep(min(poll_interval, remaining))

    async def export_table_to_file(
        self,
        dataset_id: int,
        *,
        table_name: str,
        table_schema_id: str,
        dest: str | os.PathLike[str],
        mime_type: str = "csv",
        level_error: list[str] | None = None,
        id_rules: str | None = None,
        field_value: str | None = None,
        big_data: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        _check_extension(mime_type)
        file_name = f"{table_name}.{mime_type}"
        await self._warn_if_stale(dataset_id, file_name, big_data)
        await self.start_table_export(
            dataset_id,
            mime_type=mime_type,
            table_schema_id=table_schema_id,
            level_error=level_error,
            id_rules=id_rules,
            field_value=field_value,
            big_data=big_data,
        )
        await self._wait_for_export_file(
            dataset_id, file_name, dest, big_data, poll_interval, timeout
        )

    async def export_dataset_to_file(
        self,
        dataset_id: int,
        *,
        dataset_name: str,
        dest: str | os.PathLike[str],
        mime_type: str = "csv",
        big_data: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> None:
        file_name = _dataset_file_name(dataset_name, mime_type)
        await self._warn_if_stale(dataset_id, file_name, big_data)
        await self.start_dataset_export(dataset_id, mime_type=mime_type, big_data=big_data)
        await self._wait_for_export_file(
            dataset_id,
            file_name,
            dest,
            big_data,
            poll_interval,
            timeout,
        )


def _set_docs(docs: dict[str, str]) -> None:
    for name, doc in docs.items():
        getattr(DatasetsResource, name).__doc__ = doc
        getattr(AsyncDatasetsResource, name).__doc__ = doc


_set_docs(
    {
        "start_table_export": (
            """POST /dataset/exportFile (or `exportFileDL` with `big_data=True`): start exporting one table.

        `mime_type` is the file extension (`csv`, `xlsx`, ...); without
        `table_schema_id` the whole dataset is exported under the dataset's name.
        Optional filters (`ExportFilterVO`): `level_error` (names of the backend's
        `ErrorTypeEnum`), `id_rules`, `field_value`; `big_data=True` also sends an
        empty `qcCodes` string. Returns nothing; the file is
        named `<table name>.<mime_type>`."""
            + _FILE_EXPORT_NOTE
        ),
        "start_dataset_export": (
            """GET /dataset/{datasetId}/exportDatasetFile (or `exportDatasetFileDL`): start exporting the whole dataset.

        `mime_type` is `csv`, `xlsx`, ... or `zip csv` / `zip xlsx` (a space; the
        backend splits it). The file is `<dataset name>.zip` for the zip types,
        else `<dataset name>.<ext>`. Returns nothing."""
            + _FILE_EXPORT_NOTE
        ),
        "fetch_export_file": (
            """GET /dataset/{datasetId}/downloadFile (or `downloadFileDL`): download a generated export file.

        Saves to `dest` and returns True, or returns False without leaving a file
        when the backend answered with an empty body (file not generated yet or not
        found: the backend swallows that error)."""
            + _FILE_EXPORT_NOTE
        ),
        "export_table_to_file": (
            """Export one table to `dest`, waiting for the file: start the export, then poll the download.

        `table_name` is the table's name (the backend names the file after it);
        `table_schema_id` selects the table; `mime_type` must be a bare extension (`csv`, `xlsx`).
        Raises `JobError` after `timeout` seconds without a file."""
            + _FILE_EXPORT_NOTE
        ),
        "export_dataset_to_file": (
            """Export the whole dataset to `dest`, waiting for the file.

        `dataset_name` is the dataset's name (the backend names the file after it).
        Raises `JobError` after `timeout` seconds without a file."""
            + _FILE_EXPORT_NOTE
        ),
    }
)
