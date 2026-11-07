# Using the library from FME

You can call the library from FME's Python (a PythonCaller, PythonCreator, a startup or
shutdown script) like any other Python package. **This page has not been run inside an FME
installation yet**: the code below is a sketch written from FME's documented Python API
and this library's tested behaviour. Please treat the first run as a test and report what
you find.

## Requirements

- **Python 3.11 or newer.** Safe Software documents FME 2025 as bundling Python 3.13 and
  allowing 3.9 to 3.13; FME 2024 supports up to 3.12. Check *Python Compatibility* in your
  workspace parameters (and Safe's "Python Compatibility" page for your release) and pick
  an interpreter of 3.11 or newer.
- **Dependencies:** `httpx` and `pydantic` (version 2). pandas is **optional**; the
  functions below do not need it. If another package in the same interpreter pins
  Pydantic 1, install into a separate environment and point the workspace at it.
- Install into the interpreter the workspace uses, for example
  `python -m pip install "reportnet-api @ git+https://github.com/eeadata/reportnet-api-python"`
  (or `pip install reportnet-api` once it is on PyPI).

## Keep the credential out of the workspace

Create a **published parameter of type "Password"** (for example `REPORTNET_API_KEY`) and
read it in Python with `fme.macroValues["REPORTNET_API_KEY"]`. Do not hard-code it in the
script. An ApiKey belongs to one dataflow and reads data; see [credentials](credentials.md).

## Read a table into features (sketch)

```python
import fme
import fmeobjects
from reportnet_api import easy

class FeatureProcessor(object):
    def __init__(self):
        self.rows = []

    def input(self, feature):
        pass  # the trigger feature is not used

    def close(self):
        client = easy.connect(fme.macroValues["REPORTNET_API_KEY"])
        try:
            rows = easy.read_records(
                client,
                int(fme.macroValues["DATASET_ID"]),
                int(fme.macroValues["DATAFLOW_ID"]),
                table_name=fme.macroValues["TABLE_NAME"],
            )
        finally:
            client.close()
        for row in rows:                      # every value is text, empty cells are ''
            out = fmeobjects.FMEFeature()
            for name, value in row.items():
                out.setAttribute(name, value)
            self.pyoutput(out)
```

`read_records` pages through the table for you and returns plain dictionaries, so no
pandas is needed. Cast the text values with FME's own transformers (for example
`AttributeManager` or `AttributeValueMapper`).

## Write data into Reportnet

Write the features to a CSV file with FME's writer, then upload it:

```python
easy.import_file(client, dataset_id, dataflow_id, "/path/TableName.csv")
```

The file name must be the table name, and the first line must name **every** field of the
table (the library checks this before uploading). Use a test dataset first. See
[`import_file`](reference/easy.md#import_file).

## Batch-friendly settings

- `easy.connect(key, retry=True)` retries transient network errors.
- Long exports run as server jobs; `easy.export_to_file(..., progress=True)` waits for
  them and prints status lines to the translation log.
- The `reportnet` command (`reportnet read DATASET DATAFLOW --out file.csv`) works from a
  SystemCaller without any Python code in the workspace.

## What we do not know yet

How FME's embedded Python handles package installation on your platform, and whether the
dependencies conflict with what is already installed, can only be found out in your
installation. Please tell us.
