"""Refuse live runs against dataflows that are not on the user's sandbox allowlist.

The list is `REPORTNET_ALLOWED_DATAFLOW_IDS` (comma-separated, from the environment or
the git-ignored `.env`). Usage: `uv run python scripts/live_guard.py <dataflow_id>`, or
`from live_guard import check; check(<dataflow_id>)`. Exit code 1 / SystemExit when not allowed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _env_file_value(name: str) -> str | None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.is_file():
        return None
    for line in env.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            return value.strip().strip("'\"")
    return None


def allowed_ids() -> set[int]:
    raw = os.environ.get("REPORTNET_ALLOWED_DATAFLOW_IDS") or _env_file_value(
        "REPORTNET_ALLOWED_DATAFLOW_IDS"
    )
    return {int(p) for p in (raw or "").replace(" ", "").split(",") if p}


def check(dataflow_id: int) -> None:
    allowed = allowed_ids()
    if not allowed:
        raise SystemExit("REPORTNET_ALLOWED_DATAFLOW_IDS is empty: refusing live run")
    if int(dataflow_id) not in allowed:
        raise SystemExit(
            f"Dataflow {dataflow_id} is not on the sandbox allowlist {sorted(allowed)}"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:  # noqa: PLR2004 - program name plus at least one id
        raise SystemExit("usage: live_guard.py <dataflow_id> [...]")
    for arg in sys.argv[1:]:
        check(int(arg))
    print("ok")
