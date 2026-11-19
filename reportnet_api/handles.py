"""Handles for a dataflow and its datasets.

A `Dataflow` or `Dataset` carries the ids a notebook user would otherwise pass by
hand (dataflow id, dataset id, provider id, the data-lake flag) and resolves
datasets by id, country code or name. Handles are immutable snapshots; call
`Dataflow.refresh()` for a new one. They delegate to the `easy` functions and add
no endpoint.
"""

from __future__ import annotations

import numbers
import os
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import easy
from ._exceptions import AuthenticationError, ReportnetAPIError
from .client import ReportnetClient

if TYPE_CHECKING:
    import pandas as pd


_COUNTRY_CODE_LENGTH = 2  # ISO 3166-1 alpha-2, as Reportnet uses


def _int_or_none(value: Any) -> int | None:
    """Ints come back from DataFrames as floats with NaN for missing values."""
    try:
        return None if value is None or value != value else int(value)  # noqa: PLR0124 - NaN
    except (TypeError, ValueError):
        return None


def _as_id(key: object) -> int | None:
    """An integer key (numpy integers included; bool is not an id), else None."""
    # mypy thinks no bool is Integral; at runtime isinstance(True, numbers.Integral) is True.
    if isinstance(key, numbers.Integral) and not isinstance(key, bool):  # type: ignore[unreachable]
        return int(key)
    return None


def _describe(row: dict[str, Any], codes: dict[int, str] | None) -> str:
    pid = _int_or_none(row.get("provider_id"))
    code = f", {codes[pid]}" if codes and pid in codes else ""
    return f"{int(row['dataset_id'])} {row['name']} ({row['kind']}{code})"


class DataLakeError(RuntimeError):
    """A plain table read was refused: the dataset is in a data-lake dataflow."""


@dataclass(frozen=True, slots=True)
class Dataset:
    """One dataset: ids, kind and the country it belongs to (if any)."""

    id: int
    name: str
    kind: str
    provider_id: int | None
    country_code: str | None
    dataflow_id: int
    client: ReportnetClient = field(repr=False, compare=False)
    big_data: bool = False  # True when the dataflow is a data-lake one

    @property
    def tables(self) -> pd.DataFrame:
        """The dataset's tables as a DataFrame (`easy.list_tables`)."""
        return easy.list_tables(self.client, self.id)

    def _refuse_data_lake(self, allow: bool) -> None:
        if self.big_data and not allow:
            raise DataLakeError(
                f"Dataset {self.id} ({self.name}) is in a data-lake dataflow ({self.dataflow_id}): "
                "the plain table read answers 200 with 0 rows there even when data exists. "
                "Use .export(dest) for the data, or pass "
                "allow_data_lake=True to try the plain read anyway."
            )

    def read_all(self, *, allow_data_lake: bool = False, **kwargs: Any) -> dict[str, pd.DataFrame]:
        """All tables as ``{table_name: DataFrame}`` (`easy.read_tables`).

        The handle's `provider_id` is passed unless you give one. Other keyword
        arguments (`page_size`, `progress`, `table_schema_id`) go to `read_tables`;
        see it for the ETL credential caveats. Raises `DataLakeError` on a data-lake
        dataflow (`big_data`), where this route returns no rows: use `export()`, or
        `allow_data_lake=True` to try anyway.
        """
        self._refuse_data_lake(allow_data_lake)
        kwargs.setdefault("provider_id", self.provider_id)
        return easy.read_tables(self.client, self.id, self.dataflow_id, **kwargs)

    def read(
        self, table: str | None = None, *, allow_data_lake: bool = False, **kwargs: Any
    ) -> pd.DataFrame:
        """One table as a DataFrame (`easy.read_table`).

        Without `table` the dataset must hold exactly one table with data. Raises
        `DataLakeError` on a data-lake dataflow, as `read_all` does.
        """
        self._refuse_data_lake(allow_data_lake)
        kwargs.setdefault("provider_id", self.provider_id)
        return easy.read_table(self.client, self.id, self.dataflow_id, table, **kwargs)

    def validation_errors(self, **kwargs: Any) -> pd.DataFrame:
        """Failed validations, one row per failing rule (`easy.validation_errors`)."""
        return easy.validation_errors(self.client, self.id, self.dataflow_id, **kwargs)

    def validation_summary(self) -> pd.DataFrame:
        """Failures counted per table and level (`easy.validation_summary`)."""
        return easy.validation_summary(self.client, self.id, self.dataflow_id)

    def export(self, dest: str | os.PathLike[str], **kwargs: Any) -> Path:
        """Export the dataset as a ZIP of CSV or Parquet files at `dest` (`easy.export_to_file`).

        Starts an export job and leaves a job record behind. Keyword arguments
        (`file_format`, `table_schema_id`, `timeout`, `progress`) go to `export_to_file`.
        """
        return easy.export_to_file(self.client, self.id, self.dataflow_id, dest, **kwargs)

    def upload(self, path: str | os.PathLike[str], **kwargs: Any) -> dict[str, Any]:
        """Import a file into the dataset and wait for it (`easy.import_file`). WRITES.

        The file name must match a table name and the header must name every field
        (checked first). `replace=True` deletes the existing data first and needs
        `confirm=True`. The handle's `provider_id` is passed unless you give one.
        """
        kwargs.setdefault("provider_id", self.provider_id)
        return easy.import_file(self.client, self.id, self.dataflow_id, path, **kwargs)

    def validate(self, **kwargs: Any) -> pd.DataFrame:
        """Start a validation, wait for it, return the failures (`easy.validate_and_wait`). WRITES.

        Replaces the dataset's validation results and locks the dataset while it runs.
        """
        return easy.validate_and_wait(self.client, self.id, self.dataflow_id, **kwargs)

    def export_validations(self, dest: str | os.PathLike[str], **kwargs: Any) -> Path:
        """Save the validation failures as a CSV at `dest` (`easy.export_validations`).

        Close any open Reportnet page for this dataset first: the backend deletes
        the file once the web app downloads it.
        """
        return easy.export_validations(self.client, self.id, dest, **kwargs)


@dataclass(frozen=True, slots=True)
class Dataflow:
    """One dataflow. `big_data` is True for a data-lake dataflow."""

    id: int
    name: str
    status: str | None
    big_data: bool
    client: ReportnetClient = field(repr=False, compare=False)
    # Provider-code cache, filled on first lookup; None inside means unreadable.
    _cache: dict[str, Any] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )

    @property
    def datasets(self) -> pd.DataFrame:
        """The dataflow's datasets as a DataFrame (`easy.list_datasets`)."""
        return easy.list_datasets(self.client, self.id)

    def refresh(self) -> Dataflow:
        """A new handle read afresh from the server; this one is left unchanged."""
        return find_dataflow(self.client, self.id)

    def _codes(self) -> dict[int, str] | None:
        if "codes" not in self._cache:
            try:
                table = easy.list_providers(self.client)
                self._cache["codes"] = {
                    int(r["provider_id"]): str(r["code"]) for r in table.to_dict("records")
                }
            except ReportnetAPIError:  # 403, but a bad ApiKey also shows up as 401/500
                self._cache["codes"] = None
        codes: dict[int, str] | None = self._cache["codes"]
        return codes

    def dataset(self, key: int | str, *, kind: str | None = None) -> Dataset:
        """One dataset by id, country code or name; exactly one match or `LookupError`.

        A string is tried as a provider code (case-insensitive), then as a name:
        exact first, then substring. `kind` ("design", "reporting", "test", ...)
        narrows the candidates first.
        """
        rows: list[dict[str, Any]] = self.datasets.to_dict("records")
        if kind is not None:
            rows = [r for r in rows if r["kind"] == kind]
        wanted = _as_id(key)
        codes = self._codes()
        if wanted is not None:
            found = [r for r in rows if int(r["dataset_id"]) == wanted]
        else:
            k = str(key).strip().lower()
            if not k:
                raise ValueError("The dataset key is empty: give an id, a country code or a name")
            if codes is None and len(k) <= _COUNTRY_CODE_LENGTH:
                # Looks like a country code, which cannot be told from a name fragment.
                raise LookupError(
                    f"Cannot resolve {key!r} in dataflow {self.id}: provider codes could not "
                    "be read (no access to providers), so use the dataset id or its full name"
                )
            if codes and k in {c.lower() for c in codes.values()}:
                by_provider = {pid for pid, c in codes.items() if c.lower() == k}
                found = [r for r in rows if _int_or_none(r["provider_id"]) in by_provider]
                if not found:  # a real country with no dataset here: never fall back to names
                    listing = "; ".join(_describe(r, codes) for r in rows)
                    raise LookupError(
                        f"No dataset for provider {key!r} in dataflow {self.id}: {listing}"
                    )
            else:
                found = [r for r in rows if str(r["name"]).lower() == k]
                if not found:
                    found = [r for r in rows if k in str(r["name"]).lower()]
        if len(found) != 1:
            listing = "; ".join(_describe(r, codes) for r in (found or rows))
            note = (
                ""
                if codes is not None
                else " (provider codes could not be read: no access to providers)"
            )
            what = "Several datasets match" if found else "No dataset matches"
            raise LookupError(f"{what} {key!r} in dataflow {self.id}: {listing}{note}")
        row = found[0]
        pid = _int_or_none(row["provider_id"])
        return Dataset(
            id=int(row["dataset_id"]),
            name=str(row["name"]),
            kind=str(row["kind"]),
            provider_id=pid,
            country_code=codes.get(pid) if codes and pid is not None else None,
            dataflow_id=self.id,
            client=self.client,
            big_data=self.big_data,
        )


def read_many(datasets: Iterable[Dataset], table: str, **kwargs: Any) -> pd.DataFrame:
    """One table from several datasets, stacked, with `dataset` and `country` columns.

    Reads one dataset after another (no concurrency: concurrent ETL reads are not
    verified against the backend) with `Dataset.read_all`, so
    `kwargs` (`page_size`, `progress`, `allow_data_lake`) go there; a data-lake
    dataset raises `DataLakeError`. A dataset without that table, or
    with no rows in it, is skipped and named in a `RuntimeWarning`; no rows at all
    gives an empty frame. `country` is the dataset's country code, None if it has none.
    """
    import pandas as pd

    frames: list[pd.DataFrame] = []
    skipped: list[str] = []
    for ds in datasets:
        frame = ds.read_all(**kwargs).get(table)
        if frame is None or frame.empty:
            skipped.append(f"{ds.id} {ds.name}")
            continue
        frame = frame.copy()
        frame.insert(0, "country", ds.country_code)
        frame.insert(0, "dataset", ds.name)
        frames.append(frame)
    if skipped:
        warnings.warn(
            f"No rows of table {table!r} for: {'; '.join(skipped)}",
            RuntimeWarning,
            stacklevel=2,
        )
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def find_dataflow(client: ReportnetClient, query: int | str) -> Dataflow:
    """One dataflow by id or name text; exactly one match or `LookupError`.

    An int (or a string of digits) is an id: it is read from `list_dataflows()`
    when listed there, else accepted when `list_datasets()` can read it (the
    handle is then named after the id). Any other string matches names
    case-insensitively, exact first, then as a substring.
    The dataflow's `bigData` flag is read once, here.
    """
    if isinstance(query, str):
        text = query.strip()
        if not text:
            raise ValueError("The dataflow query is empty: give an id or part of a name")
        if text.isdigit():  # an id read from an env var or a command line
            query = int(text)
    rows: list[dict[str, Any]] = []
    try:
        rows = easy.list_dataflows(client).to_dict("records")
    except ReportnetAPIError:
        if _as_id(query) is None:
            raise  # a name search needs the listing; an id can still be checked below
    wanted = _as_id(query)
    if wanted is not None:
        query = wanted
        found = [r for r in rows if _int_or_none(r.get("id")) == query]
        if not found:
            try:
                easy.list_datasets(client, query)
            except AuthenticationError:
                raise  # an expired or bad credential is not "no such dataflow"
            except (LookupError, ReportnetAPIError) as err:
                raise LookupError(
                    f"Dataflow {query} is not listed and could not be read: {err}"
                ) from err
            found = [{"id": query, "name": str(query), "status": None}]
    else:
        k = str(query).strip().lower()
        found = [r for r in rows if str(r.get("name")).lower() == k]
        if not found:
            found = [r for r in rows if k in str(r.get("name")).lower()]
    if len(found) != 1:
        listing = "; ".join(f"{r.get('id')} {r.get('name')}" for r in (found or rows)[:20])
        what = "Several dataflows match" if found else "No dataflow matches"
        raise LookupError(f"{what} {query!r}: {listing}")
    row = found[0]
    flow_id = int(row["id"])
    status = row.get("status")
    return Dataflow(
        id=flow_id,
        name=str(row["name"]),
        status=None if status is None or status != status else str(status),  # noqa: PLR0124 - NaN
        big_data=easy.is_data_lake(client, flow_id),
        client=client,
    )
