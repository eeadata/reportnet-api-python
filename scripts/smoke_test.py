"""Manual smoke test against a real Reportnet 3 API instance.

Not part of the pytest suite (no live calls in CI) and not
run automatically anywhere. Use it to sanity-check a token/environment by
hand: does auth work, do a handful of read-only endpoints across different
resources return parseable data.

Usage:
    uv run python3 scripts/smoke_test.py --token "$REPORTNET_TOKEN" \\
        --dataset-id 123 [--dataflow-id 45] [--base-url https://...]

`--dataset-id` is required; `--dataflow-id` is optional and just skips a
couple of checks if omitted. Every check here is read-only — nothing here
imports, deletes, or modifies data.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reportnet_api import NotFoundError, ReportnetAPIError, ReportnetClient


@dataclass
class Check:
    name: str
    run: Callable[[], Any]
    requires: list[str]


def build_checks(client: ReportnetClient, dataset_id: int, dataflow_id: int | None) -> list[Check]:
    checks = [
        Check(
            "datasets.check_import_process",
            lambda: client.datasets.check_import_process(dataset_id=dataset_id),
            requires=["dataset_id"],
        ),
        Check(
            "dataset_schema.find_data_schema_by_dataset_id",
            lambda: client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=dataset_id),
            requires=["dataset_id"],
        ),
    ]
    if dataflow_id is not None:
        checks += [
            Check(
                "release_receipts.get_release_receipt_by_dataflow_id",
                lambda: client.release_receipts.get_release_receipt_by_dataflow_id(
                    dataflow_id=dataflow_id
                ),
                requires=["dataflow_id"],
            ),
            Check(
                "datasets.get_iceberg_tables",
                lambda: client.datasets.get_iceberg_tables(dataflow_id=dataflow_id),
                requires=["dataflow_id"],
            ),
            Check(
                "dataset_snapshot.historic_releases",
                lambda: client.dataset_snapshot.historic_releases(
                    dataflow_id=dataflow_id, dataset_id=dataset_id
                ),
                requires=["dataflow_id", "dataset_id"],
            ),
        ]
    return checks


def run_check(check: Check) -> tuple[str, str]:
    try:
        result = check.run()
    except NotFoundError as e:
        return "WARN", f"404 — endpoint reached but nothing found for this id ({e.response_body!r})"
    except ReportnetAPIError as e:
        return "FAIL", f"{e.status_code} {type(e).__name__} — {e.response_body!r}"
    except Exception as e:  # noqa: BLE001 - smoke test wants to report, not crash
        return "FAIL", f"unexpected {type(e).__name__}: {e}"
    else:
        return "PASS", repr(result)[:120]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://api.reportnet.europa.eu")
    parser.add_argument("--token", required=True, help="Bearer JWT or ApiKey key for the API")
    parser.add_argument(
        "--token-scheme",
        default="ApiKey",
        help="Authorization header scheme (default: ApiKey, for Reportnet's "
        "dataflow-scoped API keys; use Bearer for a JWT)",
    )
    parser.add_argument("--dataset-id", type=int, required=True)
    parser.add_argument("--dataflow-id", type=int, default=None)
    args = parser.parse_args()

    had_failure = False
    with ReportnetClient(
        base_url=args.base_url, token=args.token, token_scheme=args.token_scheme
    ) as client:
        checks = build_checks(client, args.dataset_id, args.dataflow_id)
        for check in checks:
            status, detail = run_check(check)
            had_failure = had_failure or status == "FAIL"
            print(f"[{status:4}] {check.name}: {detail}")

    return 1 if had_failure else 0


if __name__ == "__main__":
    sys.exit(main())
