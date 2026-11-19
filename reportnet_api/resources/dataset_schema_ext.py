"""Hand-written extension of the generated DatasetSchemaResource classes.

Adds endpoints that are hidden from Swagger via `@ApiOperation(hidden = true)`
in the live backend and therefore never appear in spec/api-docs.json — see
the "known spec-snapshot gap" (hidden endpoints). This file is never touched by
scripts/generate_resources.py since it lives outside dataset_schema.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
import time
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import httpx

from .._core import _NEVER_SENT_ERRORS, _TRANSIENT_ERRORS, ACCEPT_ANY, stream_upload_file
from .._exceptions import ReportnetAPIError, ServerError
from ..jobs import JobError
from .dataset_schema import AsyncDatasetSchemaResource as _GeneratedAsyncDatasetSchemaResource
from .dataset_schema import DatasetSchemaResource as _GeneratedDatasetSchemaResource

_IMPORT_PATH = "/dataschema/import"
_IMPORTED_PREFIX = "IMPORTED_"

# Indirection so tests can drive the clock without patching `time`/`asyncio`.
_monotonic = time.monotonic
_sleep = time.sleep
_async_sleep = asyncio.sleep

# Poll failures that don't stop the wait (the import keeps running server side):
# 5xx plus the transport errors the client's retry policy also treats as transient.
_POLL_RETRY_ERRORS = (ServerError, *_TRANSIENT_ERRORS)
# Export answers counted as "still changing" while waiting for an import to settle.
_EXPORT_RETRY_ERRORS = (*_POLL_RETRY_ERRORS, zipfile.BadZipFile)
_MAY_HAVE_STARTED = (
    "the import may have started and still be running on the server: check the "
    "dataflow's design datasets before retrying, or it is imported twice"
)


class SchemaImportError(JobError):
    """A schema import did not create its datasets or settle in time."""


def _check_zip_name(file: str | os.PathLike[str]) -> None:
    # ZipUtils#unZipImportSchema reads nothing unless the upload's file name
    # ends in .zip, and that failure only shows up in the async part.
    if not str(file).lower().endswith(".zip"):
        raise ValueError(f"the schema import file name must end in .zip, got {str(file)!r}")


def _source_shapes(file: str | os.PathLike[str]) -> dict[str, _Shape]:
    """The upload's schemas by name, with what each should end up holding."""
    _check_zip_name(file)
    shapes = _zip_shapes(Path(file), strict=True) or {}
    if not shapes:
        raise ValueError(f"{str(file)!r} holds no .schema file to import")
    return shapes


def _describe(error: BaseException) -> str:
    if isinstance(error, ReportnetAPIError):
        return f"{error.status_code} {str(error)[:200]}"
    return f"{type(error).__name__}: {str(error)[:200]}"


def _upload_failed(dataflow_id: int, error: Exception) -> Exception:
    """A sent upload that broke off may still have started the import."""
    if isinstance(error, _TRANSIENT_ERRORS) and not isinstance(error, _NEVER_SENT_ERRORS):
        message = f"schema upload to dataflow {dataflow_id} broke off ({_describe(error)}); "
        return SchemaImportError(message + _MAY_HAVE_STARTED)
    return error


def _design_ids(dataflow_id: int, dataflow: dict[str, Any] | None) -> set[int]:
    if dataflow is None:
        # The backend answers an empty 200 when it swallows its own error.
        raise SchemaImportError(f"dataflow {dataflow_id}: no dataflow details to start from")
    return {d["id"] for d in dataflow.get("designDatasets") or []}


def _zip_digest(path: Path) -> str:
    # Entry names and contents only: the export stamps entries with the current time.
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            digest.update(name.encode() + b"\0")
            with zf.open(name) as entry:
                for chunk in iter(lambda: entry.read(1 << 16), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class _Shape:
    """What a dataset schema's export files hold, as counts (the import's completion test).

    The backend writes each file as Jackson JSON (`ZipUtils#zipSchema`): `.schema` is the
    `DataSetSchema` (`tableSchemas[].recordSchema.fieldSchema[]`), `.qcrules` a
    `RulesSchema` (`rules[]`), the other three a plain list.
    """

    tables: tuple[tuple[str, int], ...]  # (table name, field count), sorted by name
    uniques: int
    rules: int
    integrity: int
    ext_integrations: int


def _json_count(raw: bytes | None, key: str | None = None) -> int:
    if raw is None:
        return 0
    data = json.loads(raw)
    if key is not None:
        data = (data or {}).get(key)
    return len(data or [])


def _zip_shapes(path: Path, *, strict: bool) -> dict[str, _Shape] | None:
    """Shape of every dataset schema in a schema ZIP, by dataset name (the file's base name).

    `strict` raises `ValueError` on content that is not the expected JSON (the upload);
    otherwise None is returned (an export caught half written counts as "not done").
    """
    try:
        with zipfile.ZipFile(path) as zf:
            files = {name: zf.read(name) for name in zf.namelist()}
        shapes: dict[str, _Shape] = {}
        for name, raw in files.items():
            if not name.lower().endswith(".schema"):
                continue
            base = name[: -len(".schema")]
            schema = json.loads(raw) or {}
            tables = tuple(
                sorted(
                    (
                        str(t.get("nameTableSchema")),
                        len((t.get("recordSchema") or {}).get("fieldSchema") or []),
                    )
                    for t in schema.get("tableSchemas") or []
                )
            )
            shapes[base] = _Shape(
                tables=tables,
                uniques=_json_count(files.get(f"{base}.unique")),
                rules=_json_count(files.get(f"{base}.qcrules"), "rules"),
                integrity=_json_count(files.get(f"{base}.integrity")),
                ext_integrations=_json_count(files.get(f"{base}.extintegrations")),
            )
    except (ValueError, AttributeError, TypeError, zipfile.BadZipFile) as error:
        if strict:
            raise ValueError(
                f"{str(path)!r} is not a readable schema export ZIP: {error}"
            ) from error
        return None
    return shapes


_IMPORTED_NAME = re.compile(rf"^{_IMPORTED_PREFIX}(.*?)(?: \(\d+\))?$", re.DOTALL)


def _source_name(imported_name: str) -> str:
    """`IMPORTED_<name>` or `IMPORTED_<name> (1)` -> `<name>`."""
    match = _IMPORTED_NAME.match(imported_name)
    return match.group(1) if match else imported_name


def _differences(want: _Shape, got: _Shape | None) -> list[str]:
    if got is None:
        return ["no files in the export"]
    out: list[str] = []
    got_tables = dict(got.tables)
    missing = [t for t, _ in want.tables if t not in got_tables]
    if len(got.tables) != len(want.tables) or missing:
        out.append(f"{len(got.tables)}/{len(want.tables)} tables")
    wrong = [t for t, n in want.tables if t in got_tables and got_tables[t] != n]
    if wrong:
        have = sum(got_tables[t] for t in wrong)
        need = sum(n for t, n in want.tables if t in wrong)
        out.append(f"{have}/{need} fields in {len(wrong)} table(s)")
    for label, a, b in (
        ("uniques", got.uniques, want.uniques),
        ("rules", got.rules, want.rules),
        ("integrity rules", got.integrity, want.integrity),
        ("external integrations", got.ext_integrations, want.ext_integrations),
    ):
        if a != b:
            out.append(f"{a}/{b} {label}")
    return out


class _ImportWait:
    """The wait's state; the resource methods only do the I/O and sleeping."""

    def __init__(
        self,
        dataflow_id: int,
        source: dict[str, _Shape],
        before: set[int],
        settle: float,
        timeout: float,
        quiet: float = 0.0,
    ) -> None:
        self.dataflow_id = dataflow_id
        self.source = source
        self.expected = len(source)
        self.before = before
        self.settle = settle
        self.quiet = quiet
        self.timeout = timeout
        self.deadline = _monotonic() + timeout
        self.new: list[dict[str, Any]] = []
        self._digest: str | None = None
        self._stable_since = 0.0
        self._pairs: list[tuple[dict[str, Any], _Shape]] | None = None
        self.last_error: Exception | None = None

    def _imported(self, dataflow: dict[str, Any] | None) -> list[dict[str, Any]]:
        # Only the import's own: new ids named IMPORTED_..., not datasets others add.
        new = [
            d
            for d in (dataflow or {}).get("designDatasets") or []
            if d.get("id") not in self.before
            and str(d.get("dataSetName", "")).startswith(_IMPORTED_PREFIX)
        ]
        return sorted(new, key=lambda d: d["id"])

    def _check_deadline(self, now: float, what: str) -> None:
        if now >= self.deadline:
            message = (
                f"schema import into dataflow {self.dataflow_id}: {what} after {self.timeout:g}s"
            )
            if self.last_error is not None:
                message += f" (last poll error: {_describe(self.last_error)})"
            raise SchemaImportError(message) from self.last_error

    def answered(self) -> None:
        self.last_error = None

    def retrying(self, error: Exception) -> None:
        self.last_error = error

    def interrupted(self, error: Exception) -> SchemaImportError:
        """A poll error that ends the wait (e.g. an expired login) while the import runs."""
        return SchemaImportError(
            f"waiting for the schema import into dataflow {self.dataflow_id} failed "
            f"({_describe(error)}); {_MAY_HAVE_STARTED}"
        )

    def datasets_seen(self, dataflow: dict[str, Any] | None) -> bool:
        """Step 1: True once all the import's datasets exist."""
        self.new = self._imported(dataflow) or self.new
        if len(self.new) >= self.expected:
            return True
        self._check_deadline(_monotonic(), f"{len(self.new)} of {self.expected} datasets created")
        return False

    def _pair(self) -> list[tuple[dict[str, Any], _Shape]]:
        """Each new dataset with the shape its source schema should end up with.

        By name first (`IMPORTED_<name>` <- `<name>`), then what is left in id order
        against what is left of the ZIP's schemas in file order.
        """
        if self._pairs is None:
            left = dict(self.source)
            pairs: list[tuple[dict[str, Any], _Shape]] = []
            rest: list[dict[str, Any]] = []
            for dataset in self.new:
                name = _source_name(str(dataset.get("dataSetName", "")))
                if name in left:
                    pairs.append((dataset, left.pop(name)))
                else:
                    rest.append(dataset)
            pairs.extend(zip(rest, left.values(), strict=False))
            self._pairs = pairs
        return self._pairs

    def mismatches(self, shapes: dict[str, _Shape] | None) -> list[str]:
        """What the export still lacks compared with the uploaded ZIP (empty: all there)."""
        if shapes is None:
            return ["export unreadable"]
        out: list[str] = []
        for dataset, want in self._pair():
            name = str(dataset.get("dataSetName", ""))
            out.extend(f"{name} has {d}" for d in _differences(want, shapes.get(name)))
        return out

    def export_seen(self, state: tuple[str, dict[str, _Shape] | None] | None) -> bool:
        """Step 2: True once the export matches the ZIP and then stopped changing.

        The match alone is not enough (the backend still runs its SQL rule check
        afterwards, which edits rules), so it must also hold for `quiet` seconds. An
        export that stays unchanged for `settle` seconds while it still lacks
        content means the import stalled or failed: that raises.
        """
        now = _monotonic()
        digest, shapes = state if state is not None else (None, None)
        if digest is None or digest != self._digest:
            self._digest, self._stable_since = digest, now
        missing = self.mismatches(shapes) if digest is not None else ["no export yet"]
        unchanged = now - self._stable_since
        if not missing and unchanged >= self.quiet:
            return True
        if missing and digest is not None and unchanged >= self.settle:
            raise SchemaImportError(
                f"schema import into dataflow {self.dataflow_id} seems stalled or failed: "
                f"the export has not changed for {unchanged:g}s and still lacks content "
                f"({'; '.join(missing[:6])})"
            )
        self._check_deadline(
            now,
            "export does not match the uploaded ZIP yet (" + "; ".join(missing[:6]) + ")"
            if missing
            else "export still changing",
        )
        return False

    def result(self, dataflow: dict[str, Any] | None) -> list[dict[str, Any]]:
        return self._imported(dataflow) or self.new


_T = TypeVar("_T")


def _poll(
    wait: _ImportWait, call: Callable[[], _T], retry: tuple[type[Exception], ...]
) -> _T | None:
    """`call()`, or None after an error worth polling again (kept for the timeout message)."""
    try:
        result = call()
    except retry as error:
        wait.retrying(error)
        return None
    except (ReportnetAPIError, httpx.HTTPError) as error:
        raise wait.interrupted(error) from error
    wait.answered()
    return result


async def _async_poll(
    wait: _ImportWait, call: Callable[[], Awaitable[_T]], retry: tuple[type[Exception], ...]
) -> _T | None:
    """Async counterpart of `_poll`."""
    try:
        result = await call()
    except retry as error:
        wait.retrying(error)
        return None
    except (ReportnetAPIError, httpx.HTTPError) as error:
        raise wait.interrupted(error) from error
    wait.answered()
    return result


_IMPORT_AND_WAIT_DOC = """Import a schema ZIP into a dataflow and wait until it looks done.

        Returns the design datasets the import created: the `designDatasets`
        entries of `dataflow_datasets()` that are new and named
        `IMPORTED_<name>`, sorted by id. Raises `ValueError` if the ZIP holds
        no `.schema` file, and `SchemaImportError` (a `JobError`) if the
        dataflow details can't be read first, if the import stalls, or after
        `timeout` seconds.

        The backend gives no completion signal through the API (its
        `IMPORT_DATASET_SCHEMA_COMPLETED_EVENT` / `_FAILED_EVENT` only reach
        the web app's websocket, and the import lock is only on an internal
        route), so this is a heuristic in two steps:

        1. until the dataflow has as many new `IMPORTED_` design datasets as
           the ZIP has `.schema` files (the import creates them first, ~4 s
           apart);
        2. until the dataflow's schema export (`export_dataflow_schemas_zip`)
           matches the uploaded ZIP and has stopped changing. The import fills
           the datasets one after another (tables ~2 s each, a dataset's
           schema document only after its last table), then the unique
           constraints, QC and integrity rules, external integrations and the
           SQL rule check, so a quiet export is not a finished one. For each
           new `IMPORTED_<name>` dataset (paired with `<name>` in the ZIP) the
           export must have the same tables, the same number of fields per
           table, and the same number of unique constraints, QC rules,
           integrity rules and external integrations (counts only: the SQL
           rule check disables and un-verifies rules that fail it, so their
           `enabled`/`verified` flags are not compared). Once it matches, it
           must also stay unchanged for two polls. A 5xx, a timeout or a broken
           ZIP from the export counts as "not done yet".

        If the export stays unchanged for `settle` seconds while it still lacks
        content, the import has stalled or failed and `SchemaImportError`
        says what is missing (for example "IMPORTED_X has 0/14 tables").

        A 5xx or a transient transport error (timeout, dropped connection)
        while polling does not end the wait: the import carries on server side,
        and a retry would import a second set. The timeout's `SchemaImportError`
        names the last such error and is chained to it. Any other error while
        waiting (e.g. `401` once a login token expires) raises a chained
        `SchemaImportError` saying the import may still be running: check the
        dataflow's design datasets before retrying. `timeout` counts from the
        end of the upload.

        Limits: the backend reports completion only on the web app's
        websocket, so this is still a heuristic. An item the import legitimately
        leaves out (a rule it cannot recreate, an integration it cannot
        create) shows up as a stall error naming the count, not as a silent
        success. An import that fails before creating datasets (invalid names
        in the ZIP, ...) ends in the timeout. `ValueError` if the ZIP holds no
        readable `.schema` file. Same roles as `import_dataflow_schemas_zip()`.
        Polls every `poll_interval` seconds.
        """


class DatasetSchemaResource(_GeneratedDatasetSchemaResource):
    def export_dataflow_schemas_zip(
        self, dataflow_id: int, *, dest: str | os.PathLike[str]
    ) -> None:
        """GET /dataschema/export?dataflowId=...

        Downloads the full dataflow schema export ZIP: one `.schema`/
        `.qcrules`/`.unique`/`.integrity`/`.extintegrations` file set per
        dataset schema in the dataflow, plus the global
        `datasetSchemaNames.names` and `datasetSchemaIds.ids` files.

        `DatasetSchemaControllerImpl#exportSchemas` (controller method
        mapped to this route) is annotated `@ApiOperation(hidden = true)`,
        so it never reaches spec/api-docs.json and can't come from the
        generator — this is a permanent hand-written addition, not a stopgap.
        Requires `DATAFLOW_CUSTODIAN` or `DATAFLOW_STEWARD` on the dataflow.

        The `Accept: */*` override is required: `RequestCore.build_headers()`'s
        default `Accept: application/json` gets rejected before auth is even
        checked — confirmed against the live production API, this specific
        route 406s behind what looks like a gateway/proxy layer in front of
        the actual controller. Oddly, `Accept: application/octet-stream`
        (matching the controller's declared `produces`) 406s too with an
        empty body, while `Accept: */*` passes through cleanly to the real
        auth/role check.
        """
        self._client.download(
            "GET",
            "/dataschema/export",
            params={"dataflowId": dataflow_id},
            headers=dict(ACCEPT_ANY),
            dest=dest,
        )

    def import_dataflow_schemas_zip(self, dataflow_id: int, file: str | os.PathLike[str]) -> None:
        """POST /dataschema/import?dataflowId=...: add the dataset schemas of an
        export ZIP (`export_dataflow_schemas_zip()`'s file set) to a dataflow.

        `DatasetSchemaControllerImpl#importSchemas` (hidden), multipart `file`.
        Requires `DATAFLOW_CUSTODIAN` or `DATAFLOW_STEWARD` on the dataflow, and
        the dataflow in `DESIGN` status (`403` "Invalid dataflow status"
        otherwise). The file name must end in `.zip` (checked here, raises
        `ValueError`): the backend ignores anything else.

        Asynchronous: answers 200 once the work is started. The import
        (`DataschemaServiceImpl#importSchemas`) adds one new design dataset
        per schema, named `IMPORTED_<name>` (`IMPORTED_<name> (1)`, ... when
        taken), never replaces existing ones, gives every schema, table,
        record and field a new id (remapping links, unique constraints,
        integrity checks, QC rules and external integrations to them), and
        then runs the SQL QC rule check. A second import into the same
        dataflow while one runs answers `423`. Use
        `import_dataflow_schemas_zip_and_wait()` to wait for it.

        Not retried: if the connection times out or drops after the upload was
        sent, this raises `SchemaImportError` (chained to the transport error),
        because the import may have started anyway; check the dataflow's design
        datasets before trying again.
        """
        _check_zip_name(file)
        try:
            with stream_upload_file("file", file) as files:
                self._client.request(
                    "POST", _IMPORT_PATH, params={"dataflowId": dataflow_id}, files=files
                )
        except httpx.HTTPError as error:
            raise _upload_failed(dataflow_id, error) from error

    def import_dataflow_schemas_zip_and_wait(
        self,
        dataflow_id: int,
        file: str | os.PathLike[str],
        *,
        poll_interval: float = 5.0,
        settle: float = 120.0,
        timeout: float = 900.0,
    ) -> list[dict[str, Any]]:
        source = _source_shapes(file)
        dataflow = self._client.dataflow
        before = _design_ids(dataflow_id, dataflow.dataflow_datasets(dataflow_id))
        self.import_dataflow_schemas_zip(dataflow_id, file)
        # Started after the upload: `timeout` bounds the waiting, not the upload.
        wait = _ImportWait(dataflow_id, source, before, settle, timeout, quiet=2 * poll_interval)

        def datasets() -> dict[str, Any] | None:
            return _poll(wait, lambda: dataflow.dataflow_datasets(dataflow_id), _POLL_RETRY_ERRORS)

        while True:
            _sleep(poll_interval)
            if wait.datasets_seen(datasets()):
                break
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "export.zip"

            def export_state() -> tuple[str, dict[str, _Shape] | None]:
                self.export_dataflow_schemas_zip(dataflow_id, dest=dest)
                return _zip_digest(dest), _zip_shapes(dest, strict=False)

            while not wait.export_seen(_poll(wait, export_state, _EXPORT_RETRY_ERRORS)):
                _sleep(poll_interval)
        return wait.result(datasets())

    import_dataflow_schemas_zip_and_wait.__doc__ = _IMPORT_AND_WAIT_DOC


class AsyncDatasetSchemaResource(_GeneratedAsyncDatasetSchemaResource):
    async def export_dataflow_schemas_zip(
        self, dataflow_id: int, *, dest: str | os.PathLike[str]
    ) -> None:
        """Async counterpart of DatasetSchemaResource.export_dataflow_schemas_zip."""
        await self._client.download(
            "GET",
            "/dataschema/export",
            params={"dataflowId": dataflow_id},
            headers=dict(ACCEPT_ANY),
            dest=dest,
        )

    async def import_dataflow_schemas_zip(
        self, dataflow_id: int, file: str | os.PathLike[str]
    ) -> None:
        """Async counterpart of DatasetSchemaResource.import_dataflow_schemas_zip."""
        _check_zip_name(file)
        try:
            with stream_upload_file("file", file) as files:
                await self._client.request(
                    "POST", _IMPORT_PATH, params={"dataflowId": dataflow_id}, files=files
                )
        except httpx.HTTPError as error:
            raise _upload_failed(dataflow_id, error) from error

    async def import_dataflow_schemas_zip_and_wait(
        self,
        dataflow_id: int,
        file: str | os.PathLike[str],
        *,
        poll_interval: float = 5.0,
        settle: float = 120.0,
        timeout: float = 900.0,
    ) -> list[dict[str, Any]]:
        source = _source_shapes(file)
        dataflow = self._client.dataflow
        before = _design_ids(dataflow_id, await dataflow.dataflow_datasets(dataflow_id))
        await self.import_dataflow_schemas_zip(dataflow_id, file)
        # Started after the upload: `timeout` bounds the waiting, not the upload.
        wait = _ImportWait(dataflow_id, source, before, settle, timeout, quiet=2 * poll_interval)

        async def datasets() -> dict[str, Any] | None:
            return await _async_poll(
                wait, lambda: dataflow.dataflow_datasets(dataflow_id), _POLL_RETRY_ERRORS
            )

        while True:
            await _async_sleep(poll_interval)
            if wait.datasets_seen(await datasets()):
                break
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "export.zip"

            async def export_state() -> tuple[str, dict[str, _Shape] | None]:
                await self.export_dataflow_schemas_zip(dataflow_id, dest=dest)
                return _zip_digest(dest), _zip_shapes(dest, strict=False)

            while not wait.export_seen(await _async_poll(wait, export_state, _EXPORT_RETRY_ERRORS)):
                await _async_sleep(poll_interval)
        return wait.result(await datasets())

    import_dataflow_schemas_zip_and_wait.__doc__ = _IMPORT_AND_WAIT_DOC
