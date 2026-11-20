"""Hand-written convenience layer for notebooks and non-developers.

Thin wrappers over `ReportnetClient` that hide API plumbing: credentials from
the environment, flat listings, and tables as pandas DataFrames. The full
client stays available for anything not covered here. pandas is optional
(`pip install "reportnet-api[pandas]"`); it is only imported when a function
returning a DataFrame is called.
"""

from __future__ import annotations

import csv
import getpass
import io
import json
import numbers
import operator
import os
import re
import tempfile
import time
import warnings
import zipfile
from collections.abc import Callable, Iterable
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlencode

import httpx

from ._core import RetryPolicy, atomic_destination, caller_stacklevel
from ._exceptions import (
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    ReportnetAPIError,
    ServerError,
    _is_rejected_credential_500,
)
from .client import ReportnetClient
from .demo import demo_client as _demo_client
from .jobs import JobError, Progress, progress_event, progress_scope, wait_for_job
from .resources.dataflow_ext import DataflowKind

if TYPE_CHECKING:
    import pandas as pd

    from .handles import Dataflow, Dataset

DEFAULT_BASE_URL = "https://api.reportnet.europa.eu"

_DATASET_GROUPS = {
    "designDatasets": "design",
    "reportingDatasets": "reporting",
    "dataCollections": "data collection",
    "euDatasets": "eu",
    "referenceDatasets": "reference",
    "testDatasets": "test",
}


# Three non-empty base64url parts: header.payload.signature.
_JWT_SHAPE = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_SCHEMES = {"apikey": "ApiKey", "bearer": "Bearer"}


def connect(
    token: str | None = None,
    *,
    base_url: str | None = None,
    scheme: str | None = None,
    token_provider: Callable[[], str] | None = None,
    retry: RetryPolicy | bool | None = None,
) -> ReportnetClient:
    """Build a client from arguments or environment variables.

    `token` falls back to `REPORTNET_API_KEY`, `base_url` to `REPORTNET_BASE_URL`
    and then production. The scheme is chosen from the value: a ``"Bearer "``
    prefix or a JWT-shaped value (three dot-separated base64url parts) is sent
    as Bearer; anything else is a dataflow API key (``ApiKey`` scheme). Live,
    both an ApiKey and a Bearer token are bare UUIDs and look alike, so for a
    Bearer token pass `scheme="Bearer"` (or the ``"Bearer "`` prefix); sent as
    an ApiKey it fails with a 500 "Access is denied". Which one you have
    matters: API keys carry Reporter-level access only. Set `REPORTNET_TOKEN_SCHEME`
    (``ApiKey`` or ``Bearer``) to fix the scheme once, e.g. next to a Bearer token
    in `REPORTNET_API_KEY`; precedence is `scheme=`, a ``"Bearer "`` prefix, that
    variable, then the guess from the value. The chosen scheme shows in the
    client's repr; the secret never does.

    `token_provider` is a zero-arg callable returning the current token, called
    before every request (instead of `token`; the scheme defaults to Bearer).
    `retry=True` retries transient failures with a default `RetryPolicy`; pass
    your own policy for other settings.

    A Bearer token expires after a few minutes. If you have your own way to get fresh
    tokens, pass it as `token_provider`; `client.user.refresh_token()` renews a login
    when you hold the refresh token issued with it. This library does not log in.
    """
    if scheme is not None:
        if scheme.lower() not in _SCHEMES:
            raise ValueError(f"scheme must be 'ApiKey' or 'Bearer', got {scheme!r}.")
        scheme = _SCHEMES[scheme.lower()]
    env_scheme = os.environ.get("REPORTNET_TOKEN_SCHEME", "").strip()
    if env_scheme and env_scheme.lower() not in _SCHEMES:
        raise ValueError(
            f"REPORTNET_TOKEN_SCHEME must be 'ApiKey' or 'Bearer', got {env_scheme!r}."
        )
    if token_provider is not None:
        if token:
            raise ValueError("Pass either token or token_provider, not both.")
        credential: str | Callable[[], str] = token_provider
        scheme = scheme or _SCHEMES.get(env_scheme.lower()) or "Bearer"
    else:
        token = (token or os.environ.get("REPORTNET_API_KEY") or "").strip()
        if not token:
            raise ValueError(
                "No credential: pass token=... or set the REPORTNET_API_KEY environment variable."
            )
        guessed = _SCHEMES.get(env_scheme.lower()) or "ApiKey"
        if token.lower().startswith("bearer "):
            guessed = "Bearer"
            token = token[len("bearer ") :].strip()
        elif _JWT_SHAPE.fullmatch(token) and not env_scheme:
            guessed = "Bearer"
        credential = token
        scheme = scheme or guessed
    policy = RetryPolicy() if retry is True else (retry or None)
    url = base_url or os.environ.get("REPORTNET_BASE_URL") or DEFAULT_BASE_URL
    return ReportnetClient(base_url=url, token=credential, token_scheme=scheme, retry=policy)


def demo_client(*, quiet: bool = False) -> ReportnetClient:
    """A client that answers from built-in fictional data: no network, no credential.

    For training and first tries (`list_dataflows(c)`, `list_datasets(c, 1)`,
    `read_table(c, 102, 1)`, `find_dataflow(c, "demo")`); see `reportnet_api.demo`.
    Prints a one-line notice unless `quiet=True`.
    """
    return _demo_client(quiet=quiet)


def connect_interactive(
    *,
    base_url: str | None = None,
    scheme: str | None = None,
    retry: RetryPolicy | bool | None = None,
    prompt: str = "Reportnet API key or token (input hidden): ",
) -> ReportnetClient:
    """Like `connect()`, but asks for the credential with a hidden prompt.

    Use it in a notebook so the key is typed, not pasted into a cell that gets
    saved with the notebook. Same `scheme`/`retry` options as `connect()`.
    """
    return connect(getpass.getpass(prompt), base_url=base_url, scheme=scheme, retry=retry)


def _pandas() -> Any:
    try:
        import pandas
    except ImportError:
        raise ImportError(
            "pandas is required for DataFrame output: install it with `pip install pandas` "
            "(or use read_records() for plain dicts)"
        ) from None
    return pandas


def _require_id(value: object, name: str, hint: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer id, got {value!r}. {hint}")
    return value


def _hinted(err: ReportnetAPIError, hint: str) -> ReportnetAPIError:
    """Same exception type and attributes, with a plain-language hint appended."""
    return type(err)(
        f"{err} - {hint}",
        status_code=err.status_code,
        response_body=err.response_body,
        request=err.request,
        response=err.response,
    )


_DATAFLOW_HINT = "Pick an id from the list_dataflows() table."
_DATASET_HINT = "Use a dataset_id from list_datasets(), not the dataflow id."
_FORBIDDEN_HINT = "Also check that you did not mix up dataflow and dataset ids."


def list_dataflows(
    client: ReportnetClient, kind: DataflowKind = "reporting", *, page_size: int = 200
) -> pd.DataFrame:
    """All dataflows visible to the credential, one row each (id, name, status, ...)."""
    pd = _pandas()
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        result = client.dataflow.dataflows(kind, page_size=page_size, page_num=page)
        batch = result.get("dataflows") or []
        rows.extend(batch)
        total = result.get("filteredRecords") or result.get("totalRecords") or 0
        page += 1
        if not batch or len(rows) >= total:
            break
    return pd.DataFrame(rows)


def find_dataflow(client: ReportnetClient, query: int | str) -> Dataflow:
    """One dataflow handle by id or name text (see `handles.find_dataflow`).

    The handle resolves datasets by id, country code or name:
    `find_dataflow(c, "air quality").dataset("AT")`. Raises `LookupError` listing
    the candidates when nothing or more than one matches.
    """
    from .handles import find_dataflow as _find

    return _find(client, query)


def read_many(datasets: Iterable[Dataset], table: str, **kwargs: Any) -> pd.DataFrame:
    """One table from several dataset handles, stacked (see `handles.read_many`).

    Adds `dataset` and `country` columns; sequential; datasets without rows for the
    table are skipped with a `RuntimeWarning`. Needs ETL access, like `read_tables()`.
    """
    from .handles import read_many as _read_many

    return _read_many(datasets, table, **kwargs)


def list_datasets(
    client: ReportnetClient, dataflow_id: int, *, provider_id: int | None = None
) -> pd.DataFrame:
    """Datasets of a dataflow as a flat table: dataset_id, name, kind, provider_id.

    An unknown dataflow id answers HTTP 500 (`ServerError`, see `explain()`) and
    no access answers 403 (live-tested). `LookupError` is a guard for an empty
    200 body, which the notes say the backend can send when it swallows an
    error; not reproduced on this route.
    """
    pd = _pandas()
    _require_id(dataflow_id, "dataflow_id", _DATAFLOW_HINT)
    try:
        flow = client.dataflow.dataflow_datasets(dataflow_id, provider_id=provider_id)
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    if not flow:
        # The backend answers 200 with an empty body when it swallows an error.
        raise LookupError(
            f"Empty answer for dataflow {dataflow_id}: the id is unknown or this credential "
            "has no access to it (the server does not say which). "
            f"{_DATAFLOW_HINT} Reporters also need provider_id."
        )
    rows = []
    for group, kind in _DATASET_GROUPS.items():
        for ds in flow.get(group) or []:
            rows.append(
                {
                    "dataset_id": ds.get("id"),
                    "name": ds.get("dataSetName"),
                    "kind": kind,
                    "provider_id": ds.get("dataProviderId"),
                }
            )
    return pd.DataFrame(rows, columns=["dataset_id", "name", "kind", "provider_id"])


def is_data_lake(client: ReportnetClient, dataflow_id: int) -> bool:
    """True when the dataflow is a data-lake one (`bigData: true` in its dataset listing).

    Data-lake dataflows keep validation results and table data in the lake, so the
    old per-dataset routes answer an empty `200` there.
    """
    _require_id(dataflow_id, "dataflow_id", _DATAFLOW_HINT)
    try:
        flow = client.dataflow.dataflow_datasets(dataflow_id)
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    return bool((flow or {}).get("bigData"))


def _big_data_flag(
    client: ReportnetClient, dataflow_id: int, provider_id: int | None
) -> bool | None:
    """The dataflow's `bigData` flag, or None when the answer does not say.

    Advisory only (it picks a warning), so it never raises: a refused or failed
    call, an empty 200 (the route swallows its own errors) or a body without a
    boolean `bigData` all give None.
    """
    try:
        flow = client.dataflow.dataflow_datasets(dataflow_id, provider_id=provider_id)
    except (ReportnetAPIError, httpx.HTTPError, ValueError):
        return None
    flag = flow.get("bigData") if isinstance(flow, dict) else None
    return flag if isinstance(flag, bool) else None


_ERROR_COLUMNS = [
    "short_code",
    "level",
    "entity",
    "table",
    "field",
    "message",
    "records",
    "rule_id",
]


def validation_errors(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    *,
    level_errors: list[str] | None = None,
    type_entities: list[str] | None = None,
    page_size: int = 100,
    data_lake: bool | None = None,
) -> pd.DataFrame:
    """Failed validations of a dataset, one row per failing rule (what the UI shows).

    Columns: short_code, level, entity, table, field, message, records (number of
    failing records), rule_id. Picks the data-lake route (`list_group_validations_dl`)
    when the dataflow has `bigData: true`, else `list_group_validations`; the old
    route answers an empty list on a lake dataset even when the UI shows failures.
    Pass `data_lake=True`/`False` when the caller already knows (it skips the
    `bigData` lookup, whose empty answer would read as not a lake); `None` detects it.
    An empty frame means no failures, or a validation that has not run yet: this
    does not start one. Needs a credential that may read validations (an ApiKey
    got 403 on the sandbox).
    """
    pd = _pandas()
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    lake = is_data_lake(client, dataflow_id) if data_lake is None else data_lake
    fetch = (
        client.validation.list_group_validations_dl
        if lake
        else client.validation.list_group_validations
    )
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        try:
            result = fetch(
                dataset_id,
                page_num=page,
                page_size=page_size,
                level_errors=level_errors,
                type_entities=type_entities,
            )
        except ForbiddenError as err:
            raise _hinted(err, _FORBIDDEN_HINT) from err
        batch = (result or {}).get("errors") or []
        for e in batch:
            rows.append(
                {
                    "short_code": e.get("shortCode"),
                    "level": e.get("levelError"),
                    "entity": e.get("typeEntity"),
                    "table": e.get("nameTableSchema"),
                    "field": e.get("nameFieldSchema"),
                    "message": e.get("message"),
                    "records": e.get("numberOfRecords"),
                    "rule_id": e.get("idRule"),
                }
            )
        total = (
            (result or {}).get("totalFilteredRecords") or (result or {}).get("totalRecords") or 0
        )
        page += 1
        if not batch or len(rows) >= total or page >= _MAX_PAGES:
            break
    return pd.DataFrame(rows, columns=_ERROR_COLUMNS)


def validation_summary(client: ReportnetClient, dataset_id: int, dataflow_id: int) -> pd.DataFrame:
    """Failures counted per table and level: table, level, rules, records.

    `rules` is the number of failing rules, `records` the sum of their failing
    record counts (one record can fail several rules, so it is not a distinct
    count). Built on `validation_errors()`, so it has the same lake handling and
    does not start a validation. Empty frame: no failures, or none run yet.
    """
    pd = _pandas()
    errors = validation_errors(client, dataset_id, dataflow_id)
    cols = ["table", "level", "rules", "records"]
    if errors.empty:
        return pd.DataFrame(columns=cols)
    grouped = (
        errors.fillna({"table": "", "level": ""})
        .groupby(["table", "level"], as_index=False)
        .agg(rules=("short_code", "size"), records=("records", "sum"))
    )
    return grouped[cols]


# Notification event types that end a validation run without results. The
# backend's `MasterDataLakes` and `MasterOneVersion` branches persist these as user
# notifications (`EventType`, `persist=true`); `develop` has none.
_VALIDATION_FAILURE_EVENTS = {
    "VALIDATION_REFUSED_EVENT": "REFUSED",
    "VALIDATE_AS_PROVIDER_REFUSED_EVENT": "REFUSED",
    "VALIDATION_CANCELED_EVENT": "CANCELED",
}


def _validation_failure_status(event_type: str) -> str | None:
    """The job status a failure notification stands for, or None if it is not one."""
    if event_type in _VALIDATION_FAILURE_EVENTS:
        return _VALIDATION_FAILURE_EVENTS[event_type]
    if event_type.startswith("VALIDATION_FAILED_") and event_type.endswith("_EVENT"):
        return "FAILED"  # e.g. VALIDATION_FAILED_SYSTEM_ERROR_EVENT
    return None


def _newest_validation_event(
    client: ReportnetClient, dataset_id: int, finished_event: str
) -> tuple[int, str, dict[str, Any]]:
    """Newest `finished_event` or failure notification for the dataset: (ms, type, content).

    Reads `GET /notification/findUserNotifications` (hidden route; the list the
    Reportnet UI shows, newest first, for the calling user only). `(0, "", {})` when
    there is none.
    """
    answer = client.request(
        "GET", "/notification/findUserNotifications", params={"pageNum": 0, "pageSize": 50}
    ).json()
    newest: tuple[int, str, dict[str, Any]] = (0, "", {})
    for note in (answer or {}).get("userNotifications") or []:
        content = note.get("content") or {}
        kind = str(note.get("eventType") or "")
        if content.get("datasetId") != dataset_id:
            continue
        if kind != finished_event and _validation_failure_status(kind) is None:
            continue
        ms = int(note.get("insertDate") or 0)
        if ms > newest[0]:
            newest = (ms, kind, content)
    return newest


def _wait_validation_job(
    client: ReportnetClient,
    job_id: int,
    dataset_id: int,
    dataflow_id: int,
    provider_id: int | None,
    *,
    deadline: float,
    timeout: float,
    poll_interval: float,
) -> dict[str, Any] | None:
    """Poll the validation job until it ends; None when the poll route is refused."""
    params: dict[str, int] = {"datasetId": dataset_id, "dataflowId": dataflow_id}
    if provider_id is not None:
        params["providerId"] = provider_id
    url = f"/orchestrator/jobs/pollForJobStatus/{job_id}?{urlencode(params)}"
    try:
        return wait_for_job(
            client,
            url,
            poll_interval=poll_interval,
            timeout=max(0.0, deadline - time.monotonic()),
        )
    except (AuthenticationError, ForbiddenError, NotFoundError):
        # `MasterDataLakes` guards this route with an ApiKey check only.
        return None
    except ServerError as err:
        if _is_rejected_credential_500(err.response_body):
            return None  # a refused credential, answered as 500 (see `explain`)
        raise
    except JobError as err:
        if err.status is None and "did not finish" in str(err):
            raise JobError(
                f"Validation job {job_id} for dataset {dataset_id} did not finish within "
                f"{timeout:g} seconds (it may still be running on the server)"
            ) from err
        raise


def validate_and_wait(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    *,
    released: bool = False,
    provider_id: int | None = None,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
    data_lake: bool | None = None,
) -> pd.DataFrame:
    """Start a validation, wait until it finishes, return `validation_errors()`.

    `data_lake` is passed to `validation_errors()` (None: detect from `bigData`).
    `provider_id` goes to the start and the poll; a provider-scoped (reporter)
    ApiKey needs it there.

    WRITES: replaces the dataset's validation results and takes a dataset lock (a
    second start while one runs gets `LockedError`, 423). Runs took about 35-100 s
    on the sandbox.

    How the end is detected: the current backend answers the start with the
    validation job's id, so the job is polled (`pollForJobStatus`, as for imports
    and exports). A job that ends FAILED, REFUSED or CANCELED raises `JobError`
    with the job's `status` and `info`; a FINISHED job with an `info` text (for
    example "There are canceled validation tasks", so the results may be partial)
    warns with it and puts it in the result's `attrs["validation_note"]`. Read from the
    backend source (`MasterOneVersion` branch); the job polling is not yet tested
    live for validations.

    Without a job id (older backends), or when the poll route is refused, the
    signal is the user notification the backend creates when a run ends
    (`VALIDATION_FINISHED_EVENT`, or `VALIDATION_RELEASE_FINISHED_EVENT` with
    `released=True`), read from `/notification/findUserNotifications` (live, the
    sandbox). A newer refused, canceled or `VALIDATION_FAILED_*` notification
    raises `JobError` instead. Only the calling user's notifications are visible,
    and their times are server-side, so a newer one than any seen before the start
    counts; a run started by someone else at the same moment could be mistaken
    for this one.

    Raises `JobError` after `timeout` seconds: some backend failures leave the job
    running and create no notification.
    """
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    event = "VALIDATION_RELEASE_FINISHED_EVENT" if released else "VALIDATION_FINISHED_EVENT"
    baseline = _newest_validation_event(client, dataset_id, event)[0]
    try:
        job_id = client.validation.start_validation(
            dataset_id, released=released, dataflow_id=dataflow_id, provider_id=provider_id
        )
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    deadline = time.monotonic() + timeout
    if job_id is not None:
        answer = _wait_validation_job(
            client,
            job_id,
            dataset_id,
            dataflow_id,
            provider_id,
            deadline=deadline,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        if answer is not None:
            errors = validation_errors(client, dataset_id, dataflow_id, data_lake=data_lake)
            if answer.get("info"):
                errors.attrs["validation_note"] = str(answer["info"])
                warnings.warn(
                    f"Validation job {job_id} finished with a note: {answer['info']}",
                    RuntimeWarning,
                    stacklevel=caller_stacklevel(),
                )
            return errors
    while True:
        ms, kind, content = _newest_validation_event(client, dataset_id, event)
        if ms > baseline:
            status = _validation_failure_status(kind)
            if status is None:
                break
            error = content.get("error")
            raise JobError(
                f"Validation of dataset {dataset_id} ended with {kind}"
                + (f": {error}" if error else ""),
                status=status,
                info=str(error) if error else None,
            )
        if time.monotonic() >= deadline:
            raise JobError(
                f"No {event} notification for dataset {dataset_id} within {timeout:g} "
                "seconds (the validation may still be running, or it failed without "
                "leaving a notification)"
            )
        time.sleep(poll_interval)
    return validation_errors(client, dataset_id, dataflow_id, data_lake=data_lake)


def export_validations(
    client: ReportnetClient,
    dataset_id: int,
    dest: str | os.PathLike[str],
    *,
    timeout: float = 300.0,
    poll_interval: float = 2.0,
) -> Path:
    """Save a dataset's validation failures as a CSV at `dest` and return the path.

    Generates the export and waits for it (`validation.export_validations_to_file`).
    Columns: Entity, Table, Field, Code, QC Name, QC Description, Severity Level,
    Message, Number of records. Works on data-lake datasets (live-tested on the
    sandbox). Close any open Reportnet page for the same dataset first: the backend
    deletes the file when it is served, so the web app, which downloads it on the
    notification, can take it before this does and the wait ends in a `JobError`
    timeout. Leaves a notification in the user's Reportnet UI.
    """
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    path = Path(dest)
    try:
        client.validation.export_validations_to_file(
            dataset_id, path, timeout=timeout, poll_interval=poll_interval
        )
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    return path


def list_providers(client: ReportnetClient, group_id: int = 1) -> pd.DataFrame:
    """Data providers of a group as a table: provider_id, code, label, group_id.

    A provider is a reporting country; `provider_id` is the `providerId` other
    calls take and `code` its country code. Group `1` is the member
    countries; `client.representative.data_provider_groups()` lists the groups.
    """
    pd = _pandas()
    _require_id(group_id, "group_id", "Group 1 is the member countries.")
    try:
        providers = client.representative.data_providers(group_id) or []
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    rows = [
        {
            "provider_id": p.get("id"),
            "code": p.get("code"),
            "label": p.get("label"),
            "group_id": p.get("groupId"),
        }
        for p in providers
    ]
    return pd.DataFrame(rows, columns=["provider_id", "code", "label", "group_id"])


def list_tables(client: ReportnetClient, dataset_id: int) -> pd.DataFrame:
    """Tables defined in a dataset's schema: table_id and name."""
    pd = _pandas()
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    try:
        schema = client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=dataset_id)
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    rows = [
        {"table_id": t.idTableSchema, "name": t.nameTableSchema} for t in schema.tableSchemas or []
    ]
    return pd.DataFrame(rows, columns=["table_id", "name"])


def _records_to_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rec in records:
        row: dict[str, Any] = {}
        if rec.get("countryCode") is not None:
            row["country_code"] = rec["countryCode"]
        fields = rec.get("fields")
        if isinstance(fields, list):  # [{"fieldName": ..., "value": ...}, ...]
            for f in fields:
                row[f.get("fieldName")] = f.get("value")
        elif isinstance(fields, dict):
            row.update(fields)
        else:  # unknown shape: keep everything rather than silently dropping it
            row.update({k: v for k, v in rec.items() if k != "countryCode"})
        rows.append(row)
    return rows


_MAX_PAGES = 10_000  # backstop against a backend that keeps returning full pages


def _schema_table_names(client: ReportnetClient, dataset_id: int) -> set[str] | None:
    try:
        return {
            t.nameTableSchema
            for t in client.dataset_schema.find_data_schema_by_dataset_id(
                dataset_id=dataset_id
            ).tableSchemas
            or []
            if t.nameTableSchema
        }
    except ReportnetAPIError:
        return None  # best-effort cross-check only


def _schema_field_types(client: ReportnetClient, dataset_id: int) -> dict[str, dict[str, str]]:
    """``{table name: {field name: backend DataType}}`` from the dataset schema."""
    schema = client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=dataset_id)
    out: dict[str, dict[str, str]] = {}
    for t in schema.tableSchemas or []:
        fields = t.recordSchema.fieldSchema if t.recordSchema else None
        out[t.nameTableSchema or ""] = {
            f.name: str(getattr(f.type, "value", f.type)) for f in fields or [] if f.name
        }
    return out


_BOOL_TEXT = {"true": True, "false": False}


def _convert_column(series: pd.Series, field_type: str) -> pd.Series:
    """Convert one text column by its schema type; raises ValueError if any value
    does not fit. Empty text becomes NA."""
    pd = _pandas()
    text = series.astype("string").str.strip()
    text = text.mask(text == "")
    if field_type == "NUMBER_INTEGER":
        num = pd.to_numeric(text, errors="raise")
        if (num.dropna() % 1 != 0).any():
            raise ValueError("non-integer value in an integer field")
        return num.astype("Int64")
    if field_type == "NUMBER_DECIMAL":
        return pd.to_numeric(text, errors="raise").astype("Float64")
    if field_type == "DATE":
        return pd.to_datetime(text, format="%Y-%m-%d", errors="raise")
    if field_type == "DATETIME":
        return pd.to_datetime(text, format="ISO8601", errors="raise", utc=True)
    if field_type == "BOOLEAN":
        low = text.str.lower()
        if not low.dropna().isin(_BOOL_TEXT).all():
            raise ValueError("value is not true/false")
        return low.map(_BOOL_TEXT).astype("boolean")
    return series  # text-like, geometry and codelist types stay as exported


def apply_schema_dtypes(
    tables: dict[str, pd.DataFrame], field_types: dict[str, dict[str, str]]
) -> dict[str, pd.DataFrame]:
    """Convert columns to the types the dataset schema declares.

    Handles NUMBER_INTEGER (`Int64`), NUMBER_DECIMAL (`Float64`), DATE, DATETIME (UTC)
    and BOOLEAN (`true`/`false`, any case); every other type stays text. A column
    whose values do not all fit keeps its original text and a `RuntimeWarning` names
    it, so a wrong guess never silently changes data. Returns new frames.
    """
    out = {}
    for name, frame in tables.items():
        df = frame.copy()
        types = field_types.get(name, {})
        for col in df.columns:
            ftype = types.get(col)
            if ftype is None:
                continue
            try:
                df[col] = _convert_column(df[col], ftype)
            except (ValueError, TypeError) as err:
                warnings.warn(
                    f"Table {name!r}, column {col!r} ({ftype}): left as text, {err}",
                    RuntimeWarning,
                    stacklevel=3,
                )
        out[name] = df
    return out


def _collect_tables(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    *,
    table_schema_id: str | None,
    provider_id: int | None,
    page_size: int,
    progress: Progress,
) -> dict[str, list[dict[str, Any]]]:
    """Page through the ETL export; ``{table name: rows}`` as plain dicts (no pandas)."""
    try:
        size = operator.index(page_size)  # accepts numpy integers, rejects 2.5 and "10"
    except TypeError:
        size = 0
    if isinstance(page_size, bool) or size < 1:
        raise ValueError(f"page_size must be a positive integer, got {page_size!r}")
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    _require_id(dataflow_id, "dataflow_id", _DATAFLOW_HINT)
    collected: dict[str, list[dict[str, Any]]] = {}
    seen: dict[str, set[str]] = {}
    totals: dict[str, int] = {}
    duplicates: dict[str, int] = {}
    page = 1  # counts requests, for progress and the page cap
    offset = 0  # 0-based row offset: the backend's `offset` is not a page number
    started = time.monotonic()
    with progress_scope(progress) as report, tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "export.json"
        while True:
            try:
                client.datasets.etl_export_dataset(
                    dataset_id,
                    dest,
                    limit=page_size,
                    offset=offset,
                    provider_id=provider_id,
                    table_schema_id=table_schema_id,
                    dataflow_id=dataflow_id,
                )
            except ForbiddenError as err:
                raise _hinted(err, _FORBIDDEN_HINT) from err
            payload = json.loads(dest.read_text(encoding="utf-8") or "{}")
            more = False
            for t in payload.get("tables") or []:
                name = t.get("tableName") or "table"
                rows = collected.setdefault(name, [])
                ids = seen.setdefault(name, set())
                recs = t.get("records") or []
                fresh = []
                for rec in recs:
                    rid = rec.get("id_record")
                    if rid is not None:
                        if rid in ids:
                            duplicates[name] = duplicates.get(name, 0) + 1
                            continue
                        ids.add(rid)
                    fresh.append(rec)
                rows.extend(_records_to_rows(fresh))
                if not fresh:
                    continue  # nothing new on this page: do not ask for more
                # The backend only sends `totalRecords` when a filter such as
                # `tableSchemaId` is set (per its develop source; live it was
                # present without one); without it, a full page is the only sign
                # that more may follow.
                if "totalRecords" in t:
                    totals[name] = int(t["totalRecords"] or 0)
                    more = more or len(rows) < totals[name]
                else:
                    more = more or len(recs) >= page_size
            if report:
                rows_so_far = sum(len(r) for r in collected.values())
                elapsed = time.monotonic() - started
                report(progress_event("page", elapsed=elapsed, page=page, rows=rows_so_far))
            if not more:
                break
            if page >= _MAX_PAGES:
                warnings.warn(
                    f"read_tables stopped after {_MAX_PAGES} pages; the data is incomplete",
                    RuntimeWarning,
                    stacklevel=caller_stacklevel(),
                )
                break
            page += 1
            offset += page_size
    for name, n in duplicates.items():
        warnings.warn(
            f"Table {name!r}: the backend returned {n} duplicate record(s) across pages; "
            "they were dropped",
            RuntimeWarning,
            stacklevel=caller_stacklevel(),
        )
    for name, total in totals.items():
        if len(collected[name]) != total:
            warnings.warn(
                f"Table {name!r}: got {len(collected[name])} rows but the backend reports "
                f"totalRecords={total}; the result may be incomplete",
                RuntimeWarning,
                stacklevel=caller_stacklevel(),
            )
    if not any(collected.values()):
        # Only looked up here: a lake answers 200 with 0 rows (live-tested), so an
        # empty result is the one case where `bigData` changes what it means.
        lake = _big_data_flag(client, dataflow_id, provider_id)
        if lake:
            warnings.warn(
                f"The ETL export answered with no rows: dataflow {dataflow_id} is a "
                "data-lake dataflow (`bigData: true`), where this route never returns "
                "rows (live-tested); read it with `easy.export_to_file()` instead",
                RuntimeWarning,
                stacklevel=caller_stacklevel(),
            )
        elif lake is None:
            warnings.warn(
                "The ETL export answered with no rows. If the dataset is not empty, it may be "
                "in a data-lake dataflow (`bigData: true`), where this route answers 200 with "
                "0 rows (live-tested); read it with `easy.export_to_file()` instead",
                RuntimeWarning,
                stacklevel=caller_stacklevel(),
            )
    if table_schema_id is None:
        expected = _schema_table_names(client, dataset_id)
        missing = sorted(expected - collected.keys()) if expected else []
        if missing:
            warnings.warn(
                f"Tables {missing} are in the dataset schema but missing from the export",
                RuntimeWarning,
                stacklevel=caller_stacklevel(),
            )
    return collected


def read_tables(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    *,
    table_schema_id: str | None = None,
    provider_id: int | None = None,
    page_size: int = 10000,
    dtypes: Literal["schema"] | None = None,
    progress: Progress = None,
) -> dict[str, pd.DataFrame]:
    """Download a dataset's data as ``{table_name: DataFrame}``.

    Pages through the synchronous ETL export until every row has been fetched.
    Note: ETL access is credential-dependent (an API key works; some Bearer
    users get 403) - see the README.

    The backend's `offset` is a 0-based row offset (live-tested on production
    and the sandbox), so pages are fetched at offsets 0,
    `page_size`, 2 * `page_size`, ... Multi-table datasets are not verified. As a
    guard, rows are de-duplicated by the backend's `id_record`, paging stops when
    a page brings nothing new, and a `RuntimeWarning` is raised for duplicates, a
    row count that differs from `totalRecords`, or tables of the schema missing
    from the answer.

    Data-lake caveat: for a dataflow with `bigData: true` this route answers `200`
    with 0 rows even when data exists (live-tested). When a result has no rows at
    all, the dataflow's `bigData` flag is looked up (one extra call): a lake gets a
    `RuntimeWarning` pointing to `export_to_file()` (job export), a dataflow that
    answers `bigData: false` gets none (the tables are empty), and if the lookup
    fails or does not say, the warning says the dataset may be in a lake.

    Values arrive from the backend as text, empty cells as `''`. With
    `dtypes="schema"` columns are converted using the field types in the dataset
    schema (see `apply_schema_dtypes`: integers, decimals, dates, datetimes and
    booleans; everything else stays text; a column that does not fit stays text with
    a warning). Live-checked on the sandbox for integer, decimal, date and datetime
    text; boolean text is unverified. The default (`None`) keeps all columns as text.

    `progress=True` shows one updating line with the page number and rows so far;
    a callable receives an event dict per page (`reportnet_api.jobs.progress_event`).
    """
    pd = _pandas()
    if dtypes not in (None, "schema"):
        raise ValueError('dtypes must be None or "schema"')
    collected = _collect_tables(
        client,
        dataset_id,
        dataflow_id,
        table_schema_id=table_schema_id,
        provider_id=provider_id,
        page_size=page_size,
        progress=progress,
    )
    frames = {name: pd.DataFrame(rows) for name, rows in collected.items()}
    if dtypes == "schema":
        try:
            field_types = _schema_field_types(client, dataset_id)
        except ReportnetAPIError as err:
            warnings.warn(
                f"dtypes='schema': could not read the dataset schema ({err}); columns left as text",
                RuntimeWarning,
                stacklevel=caller_stacklevel(),
            )
            return frames
        frames = apply_schema_dtypes(frames, field_types)
    return frames


def read_records(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    table_name: str | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """One table as a list of dicts, without pandas (for FME and plain scripts).

    Same paging, de-duplication and warnings as `read_tables`; each row is a dict
    ``{field name: text}`` (plus `country_code` when the backend sends one) and empty
    cells are `''`. With no `table_name`, the dataset must contain exactly one table with
    data. Keyword arguments (`table_schema_id`, `provider_id`, `page_size`, `progress`)
    are those of `read_tables`.
    """
    tables = read_all_records(client, dataset_id, dataflow_id, **kwargs)
    if table_name is not None:
        try:
            return tables[table_name]
        except KeyError:
            raise KeyError(f"No table {table_name!r}; available: {sorted(tables)}") from None
    if len(tables) != 1:
        filled = {name: rows for name, rows in tables.items() if len(rows)}
        if len(filled) == 1:
            return next(iter(filled.values()))
        if not filled:
            raise ValueError(
                f"All {len(tables)} tables are empty: {sorted(tables)}; "
                "pass table_name=... to get one anyway"
            )
        raise ValueError(
            f"Dataset has {len(filled)} tables with data {sorted(filled)}; pass table_name=..."
        )
    return next(iter(tables.values()))


def read_all_records(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    *,
    table_schema_id: str | None = None,
    provider_id: int | None = None,
    page_size: int = 10000,
    progress: Progress = None,
) -> dict[str, list[dict[str, Any]]]:
    """Every table as ``{table name: list of row dicts}``, without pandas (see `read_records`)."""
    return _collect_tables(
        client,
        dataset_id,
        dataflow_id,
        table_schema_id=table_schema_id,
        provider_id=provider_id,
        page_size=page_size,
        progress=progress,
    )


def read_table(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    table_name: str | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """One table of a dataset as a DataFrame.

    With no `table_name`, the dataset must contain exactly one table with data.
    Extra keyword arguments go to `read_tables`, e.g. `dtypes="schema"` for typed columns.
    """
    tables = read_tables(client, dataset_id, dataflow_id, **kwargs)
    if table_name is not None:
        try:
            return tables[table_name]
        except KeyError:
            raise KeyError(f"No table {table_name!r}; available: {sorted(tables)}") from None
    if len(tables) != 1:
        filled = {name: rows for name, rows in tables.items() if len(rows)}
        if len(filled) == 1:
            return next(iter(filled.values()))
        if not filled:
            raise ValueError(
                f"All {len(tables)} tables are empty: {sorted(tables)}; "
                "pass table_name=... to get one anyway"
            )
        raise ValueError(
            f"Dataset has {len(filled)} tables with data {sorted(filled)}; pass table_name=..."
        )
    return next(iter(tables.values()))


def export_to_file(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    dest: str | os.PathLike[str],
    *,
    file_format: Literal["csv", "parquet"] = "csv",
    table_schema_id: str | None = None,
    timeout: float = 300.0,
    progress: Progress = None,
) -> Path:
    """Export a dataset as a ZIP of CSV (or Parquet) files at `dest`.

    Starts the async export job, waits for it to finish, then downloads the
    ZIP. Raises `reportnet_api.jobs.JobError` if the job fails or `timeout`
    seconds pass. Same ETL-access caveat as `read_tables()`. `progress=True` shows
    one updating status line; a callable gets event dicts (see `wait_for_job()`).

    Newer Reportnet versions refuse the CSV and Parquet ZIP exports for a dataflow
    that is not a data lake (live on the sandbox, 2026-11-18). For CSV this then
    falls back to the older JSON export and writes the ZIP itself: one
    ``<table>.csv`` per table, comma-separated UTF-8, fields in schema order (then
    `country_code` when the records carry one), no record id column. That export is
    read into memory whole. `timeout` covers both jobs together.
    Parquet has no such fallback; the `JobError` says so.
    """
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    _require_id(dataflow_id, "dataflow_id", _DATAFLOW_HINT)
    if file_format not in ("csv", "parquet"):
        raise ValueError(f"file_format must be 'csv' or 'parquet', got {file_format!r}")
    export = (
        client.datasets.export_zip_csv_to_file
        if file_format == "csv"
        else client.datasets.export_zip_parquet_to_file
    )
    started = time.monotonic()
    try:
        try:
            export(
                dataset_id,
                dataflow_id=dataflow_id,
                dest=dest,
                table_schema_id=table_schema_id,
                timeout=timeout,
                progress=progress,
            )
        except JobError as err:
            if err.status != "FAILED" or is_data_lake(client, dataflow_id):
                raise
            if file_format == "parquet":
                raise JobError(
                    f"{err} Parquet export needs a data-lake dataflow here; use "
                    "file_format='csv' (converted from the JSON export) or read_tables().",
                    status=err.status,
                    info=err.info,
                ) from err
            left = max(0.0, timeout - (time.monotonic() - started))  # one budget for both jobs
            _export_csv_zip_from_json(
                client, dataset_id, dataflow_id, Path(dest), table_schema_id, left, progress
            )
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    return Path(dest)


def _export_csv_zip_from_json(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    dest: Path,
    table_schema_id: str | None,
    timeout: float,
    progress: Progress,
) -> None:
    """The v3 job export (a ZIP holding one ETL JSON file), rewritten as a ZIP of CSVs."""
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "etl.zip"
        client.datasets.export_dataset_with_job_to_file(
            dataset_id,
            dataflow_id=dataflow_id,
            dest=raw,
            table_schema_id=table_schema_id,
            timeout=timeout,
            progress=progress,
        )
        with zipfile.ZipFile(raw) as z:
            names = [n for n in z.namelist() if n.endswith(".json")]
            if len(names) != 1:
                raise JobError(f"Expected one JSON file in the export, got {z.namelist()}")
            payload = json.loads(z.read(names[0]))
    try:
        field_order = _schema_field_types(client, dataset_id)
    except ReportnetAPIError:
        field_order = {}  # columns then follow the records
    with atomic_destination(dest) as part, zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as out:
        for table in payload.get("tables") or []:
            name = str(table.get("tableName") or "table")
            rows = _records_to_rows(table.get("records") or [])
            columns = list(field_order.get(name, {}))
            for row in rows:
                columns += [k for k in row if k not in columns]
            buf = io.StringIO()
            writer = csv.writer(buf, lineterminator="\n")
            writer.writerow(columns)
            for row in rows:
                writer.writerow(["" if row.get(c) is None else row[c] for c in columns])
            out.writestr(f"{name}.csv", buf.getvalue().encode("utf-8"))


def export_table(
    client: ReportnetClient,
    dataset_id: int,
    table: str,
    dest: str | os.PathLike[str],
    *,
    file_format: str = "csv",
    big_data: bool = True,
    timeout: float = 300.0,
    progress: Progress = None,
) -> Path:
    """Export one table (by name) to `dest` as csv/xlsx/..., waiting for the file.

    Unlike `export_to_file()` this is not a job: the backend generates the file
    in the background and only notifies the Reportnet UI, so the helper polls the
    download until the file appears. Raises `reportnet_api.jobs.JobError` after
    `timeout` seconds. It leaves a notification in the user's Reportnet UI.
    Needs a Bearer token (an ApiKey gets 403). `big_data=True` (default) uses the
    routes the Reportnet UI calls; the plain ones never produced a file live.
    Check `dest` afterwards: a leftover file with the same name on the server
    could be served instead. `progress=True` shows a "waiting for the file" line
    with the elapsed seconds; a callable gets event dicts.
    """
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    if not file_format or " " in file_format or file_format.startswith("."):
        raise ValueError(f"file_format must be a bare extension like 'csv', got {file_format!r}")
    tables = list_tables(client, dataset_id)
    match = tables[tables["name"] == table]
    if match.empty:
        raise ValueError(f"No table named {table!r}; the dataset has {sorted(tables['name'])}")
    if len(match) > 1:
        raise ValueError(f"The dataset has {len(match)} tables named {table!r}; can't pick one")
    try:
        client.datasets.export_table_to_file(
            dataset_id,
            table_name=table,
            table_schema_id=str(match.iloc[0]["table_id"]),
            dest=dest,
            mime_type=file_format,
            big_data=big_data,
            timeout=timeout,
            progress=progress,
        )
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    return Path(dest)


def import_file(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    path: str | os.PathLike[str],
    *,
    table_schema_id: str | None = None,
    replace: bool = False,
    confirm: bool = False,
    check: bool = True,
    provider_id: int | None = None,
    delimiter: str | None = None,
    timeout: float = 300.0,
    progress: Progress = None,
) -> dict[str, Any]:
    """Upload a CSV (or other import file) into a dataset and wait until it is in.

    Before uploading a `.csv`, the file is checked against the dataset schema
    (`check_import_file`): the name must be a table name and the header must name
    every field of that table, else `ValueError` lists the problems and nothing is
    sent (`check=False` skips this; so does an unreadable schema).
    `replace=True` deletes data, so it also needs `confirm=True`.

    The file name must match a table name in the dataset (``TestTable.csv`` for
    table ``TestTable``); otherwise Reportnet cancels the job ("File name does not
    match any table name") and nothing is imported.

    `delimiter` is the file's field separator; leave it None for the dataset's own
    setting. A multi-column file whose separator differs from the dataset's is
    cancelled ("headers ... do not match"): live on the sandbox the delimiter is `|`.
    `replace=True` emptied the dataset's *other* tables too (live, 2026-11-07,
    the sandbox: a one-table file left the second table empty), so re-import the tables
    you want to keep afterwards.

    Uploads with the async big-file import, waits for its job, and then
    confirms through the dataset's import statistics. Returns those statistics
    (``{table_id: {"numberOfRecordsImported": ..., ...}}``). This WRITES to the
    dataset; `replace=True` also deletes the existing data first. Raises
    `reportnet_api.jobs.JobError` if the job fails or `timeout` seconds pass
    (the upload may still finish later). `progress=True` shows one updating status
    line; a callable gets event dicts. Ctrl-C while waiting only stops the waiting:
    the import keeps running on the server and cannot be cancelled from here.
    """
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    _require_id(dataflow_id, "dataflow_id", _DATAFLOW_HINT)
    if not Path(path).is_file():
        raise FileNotFoundError(f"No such file: {path}")
    if replace and not confirm:
        raise ValueError(
            "replace=True deletes the dataset's existing data first (live: also the other "
            "tables'); pass confirm=True to go ahead"
        )
    if check:
        problems = check_import_file(client, dataset_id, path, delimiter=delimiter)
        if problems:
            raise ValueError("The file would be rejected by Reportnet:\n- " + "\n- ".join(problems))
    try:
        return client.datasets.import_file_and_wait(
            dataset_id,
            path,
            dataflow_id=dataflow_id,
            provider_id=provider_id,
            table_schema_id=table_schema_id,
            replace=True if replace else None,  # omit rather than send replace=false
            delimiter=delimiter,
            timeout=timeout,
            progress=progress,
        )
    except ForbiddenError as err:
        raise _hinted(err, _FORBIDDEN_HINT) from err
    except JobError as err:
        if "do not contain any records" in str(err) or "headers" in str(err):
            raise JobError(f"{err} {_HEADERS_HINT}") from err
        raise


_HEADERS_HINT = (
    "(The web app reports this as wrong headers: the first line must name every field "
    "of the table, separated by the dataset's delimiter; see check_import_file().)"
)
_DELIMITERS = (",", "|", ";", "\t")


def _schema_fields(client: ReportnetClient, dataset_id: int) -> dict[str, list[tuple[str, str]]]:
    """``{table name: [(field name, DataType), ...]}`` in schema order."""
    schema = client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=dataset_id)
    out: dict[str, list[tuple[str, str]]] = {}
    for t in schema.tableSchemas or []:
        fields = t.recordSchema.fieldSchema if t.recordSchema else None
        out[t.nameTableSchema or ""] = [
            (f.name, str(getattr(f.type, "value", f.type))) for f in fields or [] if f.name
        ]
    return out


def check_import_file(
    client: ReportnetClient,
    dataset_id: int,
    path: str | os.PathLike[str],
    *,
    delimiter: str | None = None,
) -> list[str]:
    """Read-only pre-check of an import file; returns the problems found (empty = ok).

    Only `.csv` files are checked (a ZIP or workbook is left to Reportnet). The name
    must match a table of the dataset (ignoring case: whether the backend is
    case-sensitive is unverified) and the first line must name exactly that table's
    fields, split by `delimiter` (or by any of `,` `|` `;` tab when None, since the
    dataset's own delimiter cannot be read). Live: a header with only some of the
    fields was cancelled (the sandbox). If the schema cannot be read, returns [].
    """
    path = Path(path)
    if path.suffix.lower() != ".csv":
        return []
    try:
        tables = _schema_fields(client, dataset_id)
    except ReportnetAPIError:
        return []
    by_lower = {name.lower(): name for name in tables}
    table = by_lower.get(path.stem.lower())
    if table is None:
        return [f"File name {path.name!r} matches no table; tables: {sorted(tables)}"]
    wanted = [name for name, _ in tables[table]]
    with path.open("rb") as fh:  # only the first line matters; the rest may be any encoding
        raw = fh.readline()
    first = raw.decode("utf-8-sig", errors="replace").rstrip("\r\n")
    best: tuple[set[str], set[str]] | None = None
    for d in (delimiter,) if delimiter else _DELIMITERS:
        cols = [c.strip().strip('"').strip() for c in first.split(d)]
        missing, extra = set(wanted) - set(cols), set(cols) - set(wanted)
        if not missing and not extra:
            return []
        if best is None or len(missing) + len(extra) < len(best[0]) + len(best[1]):
            best = (missing, extra)
    if best is None:  # unreachable: the loop runs at least once
        raise RuntimeError("no delimiter was tried")
    missing, extra = best
    parts = []
    if missing:
        parts.append(f"missing {sorted(missing)}")
    if extra:
        parts.append(f"unknown {sorted(extra)}")
    where = f"delimiter {delimiter!r}" if delimiter else "any of , | ; tab"
    return [
        f"Header of {path.name!r} does not match table {table!r} ({where}): " + ", ".join(parts)
    ]


def _format_cell(value: Any, field_type: str) -> str:
    """Text for one cell in the form the backend exports (see `read_tables`)."""
    pd = _pandas()
    if value is None or value is pd.NA:
        return ""
    is_real = isinstance(value, numbers.Real) and not isinstance(value, numbers.Integral | bool)
    if is_real and value != value:  # noqa: PLR0124 - NaN, also numpy's and Decimal's
        return ""
    if value is pd.NaT:
        return ""
    if field_type == "DATE" and hasattr(value, "strftime"):
        return str(value.strftime("%Y-%m-%d"))
    if field_type == "DATETIME" and hasattr(value, "strftime"):
        ts = pd.Timestamp(value)
        ts = ts.tz_convert("UTC") if ts.tzinfo else ts
        return str(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
    if field_type == "BOOLEAN" and isinstance(value, bool):
        return "true" if value else "false"
    if is_real:  # python and numpy floats: plain digits, never 1e-07 or 1e+16
        if value in (float("inf"), float("-inf")):
            raise ValueError(f"{value} cannot be stored in a {field_type} field")
        text = format(Decimal(str(value)), "f")  # str() is the shortest exact form
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text
    return str(value)


def import_dataframe(
    client: ReportnetClient,
    dataset_id: int,
    dataflow_id: int,
    table_name: str,
    df: pd.DataFrame,
    *,
    delimiter: str = ",",
    **kwargs: Any,
) -> dict[str, Any]:
    """Import a DataFrame into one table of a dataset (`import_file` underneath). WRITES.

    Writes a temporary `<table_name>.csv` with a header for EVERY field of the table
    in schema order (fields missing from `df` are left empty; columns that are not
    fields raise `ValueError`), values formatted by field type (dates `YYYY-MM-DD`,
    datetimes UTC ISO, NA empty), and uploads it with `delimiter`. A value containing
    the delimiter or a line break raises `ValueError` (how the backend reads quotes is
    unverified). Other keyword arguments (`replace`, `confirm`, `provider_id`,
    `progress`, ...) go to `import_file`; `replace=True` needs `confirm=True`.

    The delimiter is always sent with the upload, so it overrides the dataset's own
    setting. Live-tested once, on a sandbox dataset: a typed read, then
    `import_dataframe(..., delimiter="|", replace=True, confirm=True)` and a second read
    gave identical data. Other field types and datasets are not verified.
    """
    _pandas()
    _require_id(dataset_id, "dataset_id", _DATASET_HINT)
    _require_id(dataflow_id, "dataflow_id", _DATAFLOW_HINT)
    tables = _schema_fields(client, dataset_id)
    if table_name not in tables:
        raise KeyError(f"No table {table_name!r}; available: {sorted(tables)}")
    fields = tables[table_name]
    duplicated = sorted({str(c) for c in df.columns if list(df.columns).count(c) > 1})
    if duplicated:
        raise ValueError(f"Duplicate column names {duplicated}: each field can appear only once")
    unknown = [c for c in df.columns if c not in {n for n, _ in fields}]
    if unknown:
        raise ValueError(
            f"Columns {unknown} are not fields of {table_name!r}: {[n for n, _ in fields]}"
        )
    rows = {
        name: [_format_cell(v, ftype) for v in df[name]] if name in df.columns else [""] * len(df)
        for name, ftype in fields
    }
    for name, cells in rows.items():
        bad = next((c for c in cells if delimiter in c or "\n" in c or "\r" in c), None)
        if bad is not None:
            raise ValueError(
                f"Column {name!r} has a value with the delimiter or a line break: {bad!r}"
            )
    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp) / f"{table_name}.csv"
        lines = [delimiter.join(rows)] + [
            delimiter.join(cells) for cells in zip(*rows.values(), strict=True)
        ]
        file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return import_file(client, dataset_id, dataflow_id, file, delimiter=delimiter, **kwargs)


# What each credential class is *expected* to manage, per feature family, as
# recorded in docs/live_testing_notes.md ("Credential requirement matrix",
# sections) and the live-testing notes. Static text, not
# probed: check_access() prints it labelled "expected". Update it with those notes.
_EXPECTED_ACCESS: tuple[tuple[str, str, str], ...] = (
    # (feature family, ApiKey, Bearer)
    (
        "listing dataflows/datasets, schema reads",
        "worked live",
        "worked live (dataflow read, refreshed Bearer)",
    ),
    (
        "table read / sync ETL export (read_table)",
        "worked live",
        "403 live for a Custodian/Steward user (ETL is gated separately)",
    ),
    (
        "job exports (export_to_file, v4/v5)",
        "worked live",
        "403 live on v4 for a Custodian/Steward user",
    ),
    ("file import (import_file)", "worked live", "worked live"),
    (
        "schema ZIP export, list imported files",
        "403 live (needs Custodian/Steward)",
        "worked live for a Custodian/Steward user",
    ),
    (
        "historic releases",
        "403 live on a Design dataset",
        "403 live on a Design dataset (cause unconfirmed)",
    ),
)


def _probe_failure(err: ReportnetAPIError) -> tuple[str, str]:
    """(verdict, detail) for a failed probe; the detail is explain()'s second line."""
    lines = err.explain().splitlines()
    return err.__class__.__name__, lines[1] if len(lines) > 1 else lines[0]


def check_access(
    client: ReportnetClient, dataflow_id: int | None = None, *, show: bool = True
) -> list[dict[str, str]]:
    """Read-only self-check of a credential: which kind, alive, dataflow reachable.

    Makes one call (list dataflows, page size 1) and, with `dataflow_id`, one
    more (the dataflow's datasets). Nothing is written. Returns rows with
    ``check``, ``result`` and ``detail`` and prints them as a table unless
    `show=False`. The credential itself is never printed.

    The ``expected`` rows are static advice for the credential's scheme taken
    from the live-testing notes; they were not probed by this call.
    """
    scheme = client._core.scheme
    rows: list[dict[str, str]] = [
        {
            "check": "credential",
            "result": scheme,
            "detail": f"sent as `Authorization: {scheme} ...`",
        }
    ]
    alive = False
    try:
        client.dataflow.dataflows("reporting", page_size=1, page_num=0)
        alive = True
        rows.append({"check": "credential alive", "result": "yes", "detail": "list dataflows ok"})
    except ReportnetAPIError as err:
        verdict, detail = _probe_failure(err)
        if err.status_code == HTTPStatus.UNAUTHORIZED or (
            err.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            and _is_rejected_credential_500(err.response_body)
        ):
            verdict = "no (rejected)"
            detail = "expired, revoked, or sent with the wrong scheme"
            if scheme == "ApiKey":
                detail += " (a Bearer token needs scheme='Bearer')"
        rows.append({"check": "credential alive", "result": verdict, "detail": detail})
    except httpx.TransportError as err:
        rows.append(
            {"check": "credential alive", "result": "unknown", "detail": f"network error: {err}"}
        )
    if dataflow_id is not None:
        _require_id(dataflow_id, "dataflow_id", _DATAFLOW_HINT)
        check = f"dataflow {dataflow_id}"
        if not alive:
            rows.append({"check": check, "result": "skipped", "detail": "credential not usable"})
        else:
            try:
                flow = client.dataflow.dataflow_datasets(dataflow_id)
            except ReportnetAPIError as err:
                if err.status_code == HTTPStatus.FORBIDDEN:
                    verdict, detail = "no access", "the server refuses this credential (403)"
                elif "accessReferenceEntity" in err.response_body:
                    verdict, detail = "not found", "unknown id, or not visible (reported as 500)"
                else:
                    verdict, detail = _probe_failure(err)
                rows.append({"check": check, "result": verdict, "detail": detail})
            except httpx.TransportError as err:
                rows.append(
                    {"check": check, "result": "unknown", "detail": f"network error: {err}"}
                )
            else:
                count = sum(len((flow or {}).get(group) or []) for group in _DATASET_GROUPS)
                rows.append(
                    {"check": check, "result": "reachable", "detail": f"{count} dataset(s) listed"}
                    if flow
                    else {
                        "check": check,
                        "result": "unclear",
                        "detail": "empty 200 answer (unknown id or no access)",
                    }
                )
    column = 2 if scheme == "Bearer" else 1 if scheme == "ApiKey" else None
    for entry in _EXPECTED_ACCESS:
        advice = entry[column] if column else "no advice for this scheme"
        rows.append(
            {"check": f"expected: {entry[0]}", "result": advice, "detail": "not probed now"}
        )
    if show:
        width = max(len(r["check"]) for r in rows)
        for r in rows:
            print(f"{r['check']:<{width}}  {r['result']}  ({r['detail']})")
    return rows


_GUIDE = """\
Reportnet cheat sheet (full reference: docs/reference/index.md; terms: docs/glossary.md)

1. Connect       client = connect_interactive()      # hidden prompt; or connect()
                 check_access(client)                # read-only: credential kind, alive?
2. Find ids      list_dataflows(client)              # dataflow ids and names
                 list_datasets(client, dataflow_id)  # dataset ids (NOT the dataflow id)
                 flow = find_dataflow(client, id_or_name); flow.dataset(id_or_country)
3. Read          list_tables(client, dataset_id); read_table(client, dataset_id, dataflow_id)
                 read_tables(...) for all tables; read_many(datasets, table) to stack
4. Validation    validation_summary / validation_errors; validate_and_wait (WRITES)
                 export_validations(client, dataset_id, dest)
5. Export        export_table(...) one table to csv/xlsx; export_to_file(...) whole dataset
6. Upload        import_file(client, dataset_id, dataflow_id, path)   (WRITES)
7. Wrong?        a ReportnetAPIError has .explain(); an ApiKey can only reach its own
                 dataflow with Reporter rights, the ETL reads/exports need an ApiKey.
8. Search        reportnet_api.find("export")        # any method or helper by keyword
"""


def guide(*, show: bool = True) -> str:
    """Print a one-page cheat sheet of the helpers in the order a notebook uses them.

    Returns the text; prints it unless `show=False`. Search every method and helper
    by keyword with `reportnet_api.find(text)`.
    """
    if show:
        print(_GUIDE)
    return _GUIDE
