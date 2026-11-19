"""Hand-written polling for async Orchestrator jobs (`pollForJobStatus`).

Several endpoints (`etl_export_dataset_with_job`, `etl_export_zip_csv`,
`etl_export_zip_parquet`, `import_big_file_data`) only start a job and answer
`{"pollingUrl": "/orchestrator/jobs/pollForJobStatus/{jobId}?datasetId=..."}`.
`wait_for_job()` / `async_wait_for_job()` poll that URL until the job ends.

Grounded in the Reportnet 3 backend source (read via the GitHub API, 2026-10):
- `JobControllerImpl#pollForJobStatus` (branch `MasterDataLakes`) answers HTTP
  200 with a map: `{"status": <JobStatusEnum value>}`, plus `"downloadUrl"`
  (`/orchestrator/jobs/downloadEtlExportedFile/{jobId}?datasetId=&dataflowId=
  [&providerId=]`) only when the job type is `FILE_EXPORT` and status is
  `FINISHED`. An unknown job or any exception is also a 200, with
  `{"error": "..."}` and no status. `datasetId` and `dataflowId` query params
  are required, which is why the `pollingUrl` is used verbatim.
- `JobStatusEnum` (re-read 2026-10-23 on both branches): `MasterDataLakes` has
  QUEUED, IN_PROGRESS, REFUSED, CANCELED, FAILED, FINISHED, CANCELED_BY_ADMIN;
  `develop` has QUEUED, IN_PROGRESS, ABORTED, CANCELLED, FAILED, FINISHED and
  no `pollForJobStatus` at all. Every value of either enum is handled on
  purpose: QUEUED/IN_PROGRESS keep waiting, FINISHED succeeds, the rest fail.
  A status outside both enums keeps waiting (forward-compatible) but warns.
- The poll route is guarded by `checkApiKey` over a long list of dataset/dataflow
  roles (stewards, custodians, reporters, observers) and takes an optional
  `providerId`; it is not custodian-only. A provider-scoped (reporter) ApiKey
  only passes the guard if `providerId` is on the poll URL, so pass
  `provider_id=` when starting the job (the API then embeds it in `pollingUrl`
  and `downloadUrl`). Backend-source reading only, not tested live.
Seen live (2026-10-23, `import_big_file_data`): a refused import answered
`{"status": "CANCELED", "info": "File name does not match any table name..."}`;
`info` is appended to the `JobError` message.
Not tested live otherwise.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from .async_client import AsyncReportnetClient
    from .client import ReportnetClient


class JobError(Exception):
    """An async job failed, was refused or cancelled, or did not finish in time.

    `status` and `info` are the job's final status and its `info` text when the
    job itself reported the failure (`FAILED`, `CANCELED`, ...), else None.
    """

    def __init__(self, message: str, *, status: str | None = None, info: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.info = info


# Every JobStatusEnum value of both backend branches (see module docstring).
JOB_RUNNING_STATUSES = frozenset({"QUEUED", "IN_PROGRESS"})
JOB_FINISHED_STATUS = "FINISHED"
JOB_FAILED_STATUSES = frozenset(
    {"FAILED", "REFUSED", "CANCELED", "CANCELED_BY_ADMIN", "ABORTED", "CANCELLED"}
)


def polling_url_of(job: dict[str, Any] | str) -> str:
    """The `pollingUrl` of a job-start answer (or the string itself)."""
    if isinstance(job, str):
        return job
    url = job.get("pollingUrl")
    if not url:
        raise JobError(f"Request did not start a job: {job}")
    return str(url)


def _check(answer: dict[str, Any]) -> bool:
    """True once FINISHED, False while it runs; raises JobError when it can't finish."""
    if answer.get("error"):
        raise JobError(str(answer["error"]))
    status = answer.get("status")
    if status == JOB_FINISHED_STATUS:
        return True
    if status in JOB_FAILED_STATUSES:
        info = answer.get("info")
        raise JobError(
            f"Job {status}: {info}" if info else f"Job {status}",
            status=str(status),
            info=str(info) if info else None,
        )
    if status not in JOB_RUNNING_STATUSES:
        warnings.warn(
            f"Unrecognised job status {status!r}; treating it as still running",
            RuntimeWarning,
            stacklevel=2,
        )
    return False


def _timeout_error(timeout: float) -> JobError:
    return JobError(f"Job did not finish within {timeout:g} seconds")


ProgressEvent = dict[str, Any]
# What the waiting helpers accept: off (None/False), the built-in line (True), or
# your own function that receives one event dict per step.
Progress = bool | Callable[[ProgressEvent], None] | None


def progress_event(
    kind: str,
    *,
    status: str | None = None,
    elapsed: float,
    job_id: str | None = None,
    page: int | None = None,
    rows: int | None = None,
) -> ProgressEvent:
    """The dict a progress callback receives.

    `kind` is ``"job"`` (one poll of an Orchestrator job; `status` is its
    status), ``"file"`` (waiting for an export file to appear), ``"confirm"``
    (import finished, checking the statistics) or ``"page"`` (`read_tables`
    fetched page `page`, `rows` rows so far). Keys not relevant to a kind are None.
    """
    return {
        "kind": kind,
        "status": status,
        "elapsed": elapsed,
        "job_id": job_id,
        "page": page,
        "rows": rows,
    }


def _describe(event: ProgressEvent) -> str:
    secs = f"{event['elapsed']:.0f}s"
    if event["kind"] == "page":
        rows = f", {event['rows']} rows so far" if event["rows"] is not None else ""
        return f"Read page {event['page']}{rows} ({secs})"
    if event["kind"] == "file":
        return f"Waiting for the export file ({secs})"
    if event["kind"] == "confirm":
        return f"Import finished, confirming statistics ({secs})"
    name = f"Job {event['job_id']}" if event["job_id"] else "Job"
    return f"{name}: {event['status']} ({secs})"


class ProgressPrinter:
    """The built-in `progress=True` display: one line, updated in place.

    On a terminal (and in Jupyter, where `\\r` redraws the output line) each
    event rewrites the same line. Anywhere else (a log file, CI, a pipe) a new
    line is printed only when the kind, status or page changes, so a 5-minute
    wait does not print 150 lines. Call `close()` to end a live line.
    """

    def __init__(self, stream: TextIO | None = None, *, live: bool | None = None) -> None:
        self._stream = stream
        self._live = live
        self._last_key: tuple[Any, ...] | None = None
        self._width = 0
        self._open = False

    def _is_live(self, stream: TextIO) -> bool:
        if self._live is not None:
            return self._live
        isatty = getattr(stream, "isatty", None)
        # ipykernel's stream says isatty() False but does honour `\\r`.
        return bool(isatty and isatty()) or "ipykernel" in sys.modules

    def __call__(self, event: ProgressEvent) -> None:
        stream = self._stream or sys.stdout
        text = _describe(event)
        if self._is_live(stream):
            self._width = max(self._width, len(text))
            stream.write(f"\r{text:<{self._width}}")
            self._open = True
        else:
            key = (event["kind"], event["status"], event["page"])
            if key == self._last_key:
                return
            self._last_key = key
            stream.write(text + "\n")
        stream.flush()

    def close(self) -> None:
        if self._open:
            (self._stream or sys.stdout).write("\n")
            self._open = False


@contextmanager
def progress_scope(progress: Progress) -> Iterator[Callable[[ProgressEvent], None] | None]:
    """Resolve a `progress` argument to a callback (or None) for the duration of a wait.

    `True` makes a `ProgressPrinter` and ends its line on exit; a callable is
    passed through untouched, so a helper can resolve once and hand the result to
    the helpers it calls.
    """
    if progress is True:
        printer = ProgressPrinter()
        try:
            yield printer
        finally:
            printer.close()
    elif callable(progress):
        yield progress
    else:
        yield None


def job_id_of(job: dict[str, Any] | str) -> str | None:
    """The job id of a job-start answer: its `jobId`, else parsed from the `pollingUrl`."""
    if isinstance(job, dict) and job.get("jobId") is not None:
        return str(job["jobId"])
    match = re.search(r"pollForJobStatus/([^/?#]+)", polling_url_of(job))
    return match.group(1) if match else None


def _interrupted(job_id: str | None) -> None:
    label = f"job {job_id}" if job_id else "the job"
    print(
        f"Interrupted: stopped waiting, but {label} keeps running on the server "
        "(this client cannot cancel it). Check on it later with Job.wait()/wait_for_job().",
        file=sys.stderr,
    )


def _wait(
    client: ReportnetClient,
    job: dict[str, Any] | str,
    poll_interval: float,
    timeout: float,
    progress: Progress,
    *,
    announce_interrupt: bool,
) -> dict[str, Any]:
    url = polling_url_of(job)
    job_id = job_id_of(job)
    started = time.monotonic()
    deadline = started + timeout
    with progress_scope(progress) as report:
        try:
            while True:
                answer: dict[str, Any] = client.request("GET", url).json()
                if report:
                    status = answer.get("status") or ("ERROR" if answer.get("error") else None)
                    elapsed = time.monotonic() - started
                    report(progress_event("job", status=status, elapsed=elapsed, job_id=job_id))
                if _check(answer):
                    return answer
                if time.monotonic() >= deadline:
                    raise _timeout_error(timeout)
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            if announce_interrupt or report:
                _interrupted(job_id)
            raise


def wait_for_job(
    client: ReportnetClient,
    job: dict[str, Any] | str,
    *,
    poll_interval: float = 2.0,
    timeout: float = 300.0,
    progress: Progress = None,
) -> dict[str, Any]:
    """Poll a job's `pollingUrl` until FINISHED and return the last answer.

    `job` is the dict a job-starting method returned (or its `pollingUrl`).
    Raises `JobError` on a failure status, an `error` answer, or after
    `timeout` seconds. `progress=True` shows one updating status line; a
    callable receives an event dict per poll (see `progress_event()`). With
    progress on, Ctrl-C prints the job id and that the job keeps running.
    """
    return _wait(client, job, poll_interval, timeout, progress, announce_interrupt=False)


class Job:
    """A started Orchestrator job you can check on later.

    Build one from what a job-starting method returned, do other work, then
    ask `.status` or call `.wait()`::

        job = Job.from_polling_url(client, client.datasets.etl_export_zip_csv(...))
        ...                          # other work
        answer = job.wait(progress=True)

    Nothing is polled until you ask. The job lives on the server; dropping the
    object does not stop it (and this client cannot cancel one).
    """

    def __init__(
        self,
        client: ReportnetClient,
        polling_url: str,
        *,
        job_id: str | None = None,
        kind: str | None = None,
    ) -> None:
        self._client = client
        self.polling_url = polling_url
        self.job_id = job_id if job_id is not None else job_id_of(polling_url)
        self.kind = kind
        self.last_status: str | None = None

    @classmethod
    def from_polling_url(
        cls, client: ReportnetClient, job: dict[str, Any] | str, *, kind: str | None = None
    ) -> Job:
        """From a job-start answer (its `pollingUrl`, `jobId` if present) or a bare URL."""
        return cls(client, polling_url_of(job), job_id=job_id_of(job), kind=kind)

    def poll(self) -> dict[str, Any]:
        """One poll: the full status answer. Read-only; remembers the status for the repr."""
        answer: dict[str, Any] = self._client.request("GET", self.polling_url).json()
        self.last_status = answer.get("status") or self.last_status
        return answer

    @property
    def status(self) -> str | None:
        """The job's status from one poll (e.g. ``"IN_PROGRESS"``), None if it names none."""
        status = self.poll().get("status")
        return str(status) if status is not None else None

    def wait(
        self, *, poll_interval: float = 2.0, timeout: float = 300.0, progress: Progress = None
    ) -> dict[str, Any]:
        """Like `wait_for_job()` for this job; Ctrl-C always reports the job id."""
        answer = _wait(
            self._client,
            self.polling_url,
            poll_interval,
            timeout,
            progress,
            announce_interrupt=True,
        )
        self.last_status = answer.get("status") or self.last_status
        return answer

    def __repr__(self) -> str:
        parts = [f"id={self.job_id}" if self.job_id else f"url={self.polling_url!r}"]
        if self.kind:
            parts.append(f"kind={self.kind}")
        parts.append(f"last_status={self.last_status}")
        return f"Job({', '.join(parts)})"


async def async_wait_for_job(
    client: AsyncReportnetClient,
    job: dict[str, Any] | str,
    *,
    poll_interval: float = 2.0,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Async twin of `wait_for_job()`."""
    url = polling_url_of(job)
    deadline = time.monotonic() + timeout
    while True:
        answer: dict[str, Any] = (await client.request("GET", url)).json()
        if _check(answer):
            return answer
        if time.monotonic() >= deadline:
            raise _timeout_error(timeout)
        await asyncio.sleep(poll_interval)


def download_url_of(answer: dict[str, Any]) -> str:
    """The `downloadUrl` of a finished export job."""
    url = answer.get("downloadUrl")
    if not url:
        raise JobError("Job finished without a download URL")
    return str(url)


def import_statistics_changed(
    before: dict[str, Any], after: dict[str, Any], table_schema_id: str | None = None
) -> bool:
    """True if `get_import_related_statistics()` shows a new import since `before`.

    The answer maps table schema id -> `{"lastImportDate", "numberOfRecordsImported",
    "fileExtension"}`. An import counts as visible once a table's
    `(lastImportDate, numberOfRecordsImported)` pair differs from the baseline (or
    the table is new); comparing the pair, not the count alone, also catches a
    re-import that leaves the count unchanged. With `table_schema_id` only that
    table is checked, otherwise any table.
    """
    keys = [table_schema_id] if table_schema_id else list(after)
    for key in keys:
        now = after.get(key)
        if not isinstance(now, dict):
            continue
        was = before.get(key)
        was = was if isinstance(was, dict) else {}
        pair = ("lastImportDate", "numberOfRecordsImported")
        if tuple(now.get(k) for k in pair) != tuple(was.get(k) for k in pair):
            return True
    return False
