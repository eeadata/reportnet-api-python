"""A demo client that answers from built-in, fictional data (no network, no credential).

`demo_client()` returns a normal `ReportnetClient` whose transport is replaced by a tiny
in-process fake of the few Reportnet routes the notebook helpers use, so training
sessions and first-time users can try `list_dataflows`, `list_datasets`, `list_tables`,
`list_providers`, `find_dataflow` and `read_table` immediately.

Everything it returns is invented ("DEMO DATA"); only these read routes exist, and
anything else answers 501 (not implemented) with a message saying so. It is not a model
of Reportnet's behaviour, only of the response shapes the helpers read.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .client import ReportnetClient

DEMO_BASE_URL = "https://demo.invalid"
DEMO_DATAFLOW_ID = 1
DEMO_DATASET_IDS = {"design": 101, "AT": 102, "BE": 103}

_PROVIDERS = [
    {"id": 2, "code": "AT", "label": "Austria", "groupId": 1},
    {"id": 3, "code": "BE", "label": "Belgium", "groupId": 1},
]
_FIELDS = [
    ("Id", "NUMBER_INTEGER"),
    ("Station", "TEXT"),
    ("Latitude", "NUMBER_DECIMAL"),
    ("Commissioned", "DATE"),
]
_ROWS = {
    102: [
        ("1", "Vienna Centre", "48.2082", "2019-04-01"),
        ("2", "Graz South", "47.0707", "2021-09-15"),
        ("3", "Linz Harbour", "", "2022-01-20"),
    ],
    103: [
        ("1", "Brussels Ring", "50.8503", "2018-06-30"),
        ("2", "Ghent Canal", "51.0543", ""),
    ],
}
_CODES = {102: "AT", 103: "BE"}


def _json(data: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    method = request.method

    if method == "POST" and path == "/dataflow/getDataflows":
        flow = {
            "id": DEMO_DATAFLOW_ID,
            "name": "Demo dataflow: air quality stations (DEMO DATA)",
            "status": "OPEN",
            "description": "Invented data for trying the library without a credential.",
        }
        return _json({"dataflows": [flow], "totalRecords": 1, "filteredRecords": 1})

    if method == "GET" and (m := re.fullmatch(r"/dataflow/v1/(\d+)", path)):
        if int(m.group(1)) != DEMO_DATAFLOW_ID:
            return _json({"message": "Demo mode only knows dataflow 1"}, 404)
        return _json(
            {
                "id": DEMO_DATAFLOW_ID,
                "bigData": False,
                "designDatasets": [{"id": DEMO_DATASET_IDS["design"], "dataSetName": "Design"}],
                "reportingDatasets": [
                    {"id": DEMO_DATASET_IDS["AT"], "dataSetName": "Austria", "dataProviderId": 2},
                    {"id": DEMO_DATASET_IDS["BE"], "dataSetName": "Belgium", "dataProviderId": 3},
                ],
            }
        )

    if method == "GET" and path == "/representative/dataProvider/countryGroups":
        return _json([{"id": 1, "label": "Member countries"}])
    if method == "GET" and path == "/representative/dataProvider/1":
        return _json(_PROVIDERS)

    if method == "GET" and (m := re.fullmatch(r"/dataschema/v1/datasetId/(\d+)", path)):
        if int(m.group(1)) not in DEMO_DATASET_IDS.values():
            return _json({"message": "Demo mode only knows datasets 101, 102 and 103"}, 404)
        return _json(
            {
                "idDataSetSchema": "demo-schema",
                "tableSchemas": [
                    {
                        "idTableSchema": "demo-table-stations",
                        "nameTableSchema": "Stations",
                        "recordSchema": {
                            "idRecordSchema": "demo-record",
                            "fieldSchema": [
                                {"id": f"demo-field-{i}", "name": name, "type": ftype}
                                for i, (name, ftype) in enumerate(_FIELDS)
                            ],
                        },
                    }
                ],
            }
        )

    if method == "GET" and (m := re.fullmatch(r"/dataset/v1/(\d+)/etlExport", path)):
        rows = _ROWS.get(int(m.group(1)), [])
        offset = int(request.url.params.get("offset", 0))
        limit = int(request.url.params.get("limit", 10000))
        records = [
            {
                "id_record": f"demo-{m.group(1)}-{row[0]}",
                "countryCode": _CODES[int(m.group(1))],
                "fields": [
                    {"fieldName": name, "value": value}
                    for (name, _), value in zip(_FIELDS, row, strict=True)
                ],
            }
            for row in rows[offset : offset + limit]
        ]
        table = {"tableName": "Stations", "totalRecords": len(rows), "records": records}
        return httpx.Response(
            200,
            content=json.dumps({"tables": [table]}).encode(),
            headers={"content-type": "application/json"},
        )

    # 501 rather than 404, so the error does not read as "wrong id".
    return _json(
        {"message": f"Demo mode has no {method} {path}: it only fakes the read helpers"}, 501
    )


def demo_client(*, quiet: bool = False) -> ReportnetClient:
    """A `ReportnetClient` backed by built-in fictional data; see the module docstring.

    Try ``easy.list_dataflows(c)``, ``easy.list_datasets(c, 1)``, ``easy.list_tables(c, 102)``
    and ``easy.read_table(c, 102, 1)``. Prints a one-line notice unless `quiet=True`.
    """
    if not quiet:
        print("DEMO MODE: fictional data, no network, no credential (dataflow 1).")
    client = ReportnetClient(DEMO_BASE_URL, "demo")
    client._http = httpx.Client(base_url=DEMO_BASE_URL, transport=httpx.MockTransport(_handler))
    return client
