"""Save a dated copy of a dataset's tables every night (a template, not a library module).

Schedule it with cron, Windows Task Scheduler or an FME schedule. The credential comes
from the REPORTNET_API_KEY environment variable; edit the three ids below. Reads only.

    REPORTNET_API_KEY=... python nightly_export.py
"""

from datetime import date
from pathlib import Path

from reportnet_api import easy

DATASET_ID = 0  # <- a dataset id (not the dataflow id)
DATAFLOW_ID = 0  # <- its dataflow id
OUT_DIR = Path("exports")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    client = easy.connect(retry=True)  # retries transient network errors
    try:
        dest = OUT_DIR / f"dataset_{DATASET_ID}_{date.today():%Y-%m-%d}.zip"
        print(easy.export_to_file(client, DATASET_ID, DATAFLOW_ID, dest, progress=True))
    finally:
        client.close()


if __name__ == "__main__":
    main()
