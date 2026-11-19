"""Command line for schedulers, shell scripts and FME's system caller.

    reportnet check [--dataflow ID]
    reportnet dataflows
    reportnet datasets DATAFLOW_ID
    reportnet tables DATASET_ID
    reportnet read DATASET_ID DATAFLOW_ID [--table NAME] [--out FILE.csv]
    reportnet export DATASET_ID DATAFLOW_ID OUT.zip [--format csv|parquet]
    reportnet find WORDS...
    reportnet guide

The credential comes from `REPORTNET_API_KEY` (or `REPORTNET_TOKEN_SCHEME` and
`REPORTNET_BASE_URL`, see `easy.connect`), never from a command-line argument, so it
does not end up in shell history or process lists. `--demo` runs against built-in
fictional data instead. Every command here only reads or exports; there is deliberately
no command that writes or deletes data (use the Python API for that). Needs no pandas.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

import httpx

from . import easy
from ._exceptions import ReportnetAPIError
from .client import ReportnetClient
from .demo import demo_client
from .discover import find
from .jobs import JobError, ProgressPrinter

_DATASET_GROUPS = easy._DATASET_GROUPS
_UMASK = os.umask(0)
os.umask(_UMASK)  # read the process umask without changing it


def _writer(out: TextIO) -> Any:
    return csv.writer(out, lineterminator="\n")


def _table(rows: list[list[Any]], header: list[str], out: TextIO) -> None:
    w = _writer(out)
    w.writerow(header)
    w.writerows(rows)


def _dataflows(client: ReportnetClient, out: TextIO) -> None:
    rows: list[list[Any]] = []
    page = 0
    while True:
        result = client.dataflow.dataflows("reporting", page_size=200, page_num=page)
        batch = result.get("dataflows") or []
        rows.extend([[d.get("id"), d.get("name"), d.get("status")] for d in batch])
        total = result.get("filteredRecords") or result.get("totalRecords") or 0
        page += 1
        if not batch or len(rows) >= total:
            break
    _table(rows, ["id", "name", "status"], out)


def _datasets(client: ReportnetClient, dataflow_id: int, out: TextIO) -> None:
    flow = client.dataflow.dataflow_datasets(dataflow_id)
    if not flow:
        raise LookupError(f"Empty answer for dataflow {dataflow_id}: unknown id or no access")
    rows = [
        [ds.get("id"), ds.get("dataSetName"), kind, ds.get("dataProviderId") or ""]
        for group, kind in _DATASET_GROUPS.items()
        for ds in flow.get(group) or []
    ]
    _table(rows, ["dataset_id", "name", "kind", "provider_id"], out)


def _tables(client: ReportnetClient, dataset_id: int, out: TextIO) -> None:
    schema = client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=dataset_id)
    rows = [[t.idTableSchema, t.nameTableSchema] for t in schema.tableSchemas or []]
    _table(rows, ["table_id", "name"], out)


def _read(client: ReportnetClient, args: argparse.Namespace, out: TextIO) -> None:
    records = easy.read_records(client, args.dataset_id, args.dataflow_id, args.table)
    columns: list[str] = []
    for rec in records:
        columns.extend(c for c in rec if c not in columns)
    _table([[rec.get(c, "") for c in columns] for rec in records], columns, out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reportnet",
        description="Read-only command line for the Reportnet 3 API "
        "(credential from REPORTNET_API_KEY).",
    )
    p.add_argument("--demo", action="store_true", help="use built-in fictional data, no network")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="read-only check of the credential")
    c.add_argument("--dataflow", type=int, default=None)
    sub.add_parser("dataflows", help="list dataflows (CSV)")
    d = sub.add_parser("datasets", help="list a dataflow's datasets (CSV)")
    d.add_argument("dataflow_id", type=int)
    t = sub.add_parser("tables", help="list a dataset's tables (CSV)")
    t.add_argument("dataset_id", type=int)
    r = sub.add_parser("read", help="print or save one table as CSV")
    r.add_argument("dataset_id", type=int)
    r.add_argument("dataflow_id", type=int)
    r.add_argument("--table", default=None, help="table name (needed if the dataset has several)")
    r.add_argument("--out", default=None, help="write to this file instead of stdout")
    e = sub.add_parser("export", help="export a whole dataset to a ZIP of CSV/Parquet files")
    e.add_argument("dataset_id", type=int)
    e.add_argument("dataflow_id", type=int)
    e.add_argument("dest")
    e.add_argument("--format", choices=["csv", "parquet"], default="csv")
    f = sub.add_parser("find", help="search methods and helpers by keyword")
    f.add_argument("words", nargs="+")
    sub.add_parser("guide", help="print the cheat sheet")
    return p


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = out or sys.stdout
    try:
        if args.command == "find":
            print(find(" ".join(args.words)), file=out)
            return 0
        if args.command == "guide":
            print(easy.guide(show=False), file=out)
            return 0
        if args.demo:
            client = demo_client(quiet=True)
        else:
            try:
                client = easy.connect()
            except ValueError as err:
                print(
                    f"error: {err}\nSet REPORTNET_API_KEY (and REPORTNET_BASE_URL for another "
                    "host), or try --demo.",
                    file=sys.stderr,
                )
                return 2
        try:
            if args.command == "check":
                rows = easy.check_access(client, args.dataflow, show=False)
                for r in rows:
                    print(f"{r['check']}: {r['result']} ({r['detail']})", file=out)
                # Only the probed rows decide the exit code, not the static "expected" advice.
                probed = [
                    r
                    for r in rows
                    if r["check"] == "credential alive" or r["check"].startswith("dataflow ")
                ]
                if any(r["result"] not in {"yes", "reachable"} for r in probed):
                    return 1
            elif args.command == "dataflows":
                _dataflows(client, out)
            elif args.command == "datasets":
                _datasets(client, args.dataflow_id, out)
            elif args.command == "tables":
                _tables(client, args.dataset_id, out)
            elif args.command == "read":
                if args.out:
                    # Write next to the target and rename, so a failure leaves no empty file.
                    # abspath normalises '..' without touching the disk; Path.absolute() does not.
                    folder = os.path.dirname(os.path.abspath(args.out))  # noqa: PTH100, PTH120
                    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".part")
                    try:
                        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
                            _read(client, args, fh)
                        # mkstemp makes 0600; use the usual mode
                        Path(tmp).chmod(0o666 & ~_UMASK)
                        Path(tmp).replace(args.out)
                    except BaseException:
                        Path(tmp).unlink()
                        raise
                else:
                    _read(client, args, out)
            elif args.command == "export":
                printer = ProgressPrinter(sys.stderr)
                try:
                    path = easy.export_to_file(
                        client,
                        args.dataset_id,
                        args.dataflow_id,
                        args.dest,
                        file_format=args.format,
                        progress=printer,
                    )
                finally:
                    printer.close()  # end the status line before the path or an error
                print(path, file=out)
        finally:
            client.close()
    except ReportnetAPIError as err:
        print(f"{err}\n{err.explain()}", file=sys.stderr)
        return 1
    except (JobError, httpx.HTTPError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except OSError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    except (ValueError, LookupError, KeyError, RuntimeError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
