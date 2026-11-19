<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/eeadata/reportnet-api-python/main/docs/assets/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/eeadata/reportnet-api-python/main/docs/assets/logo.svg" alt="reportnet-api for Python" width="420">
  </picture>
</p>

# reportnet-api-python

Python library for the [EEA Reportnet 3](https://reportnet.europa.eu/)
REST API. Typed, resource-namespaced, sync and async, built on `httpx` and
Pydantic v2. The function reference is in `docs/reference/`.

> **Not an official EEA product.** An independent set of utilities for accessing the
> Reportnet 3 API, not developed or supported by the Reportnet team. For help with
> Reportnet itself, use the Reportnet helpdesk.

[![CI](https://github.com/eeadata/reportnet-api-python/actions/workflows/ci.yml/badge.svg)](https://github.com/eeadata/reportnet-api-python/actions/workflows/ci.yml)
[![Open the demo in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/eeadata/reportnet-api-python/blob/main/examples/try_it_demo.ipynb)

**Who it is for:** programmers (the typed clients), scientists in notebooks
(`reportnet_api.easy`, pandas), and FME users (plain Python, see
[docs/fme.md](https://github.com/eeadata/reportnet-api-python/blob/main/docs/fme.md)). **No credential yet?** `easy.demo_client()` answers from
fictional built-in data; start with the
[demo notebook](https://github.com/eeadata/reportnet-api-python/blob/main/examples/try_it_demo.ipynb). **Not sure which credential you need?**
[docs/credentials.md](https://github.com/eeadata/reportnet-api-python/blob/main/docs/credentials.md).

## Install

```
pip install reportnet-api            # or: uv add reportnet-api
pip install "reportnet-api[pandas]"  # with the pandas notebook helpers
```

Python 3.11 or newer. The latest unreleased code: `pip install git+https://github.com/eeadata/reportnet-api-python`.

## Notebooks and non-developers

`reportnet_api.easy` wraps the client for notebook use: credentials from
`REPORTNET_API_KEY`, and listings/tables returned as pandas DataFrames.

```python
%pip install "reportnet-api[pandas]"

from reportnet_api.easy import connect, list_dataflows, list_datasets, read_table
client = connect()                      # or connect("<api key>"); a Bearer token: connect(tok, scheme="Bearer")
list_dataflows(client)
read_table(client, dataset_id=123, dataflow_id=1, table_name="MyTable")
```

`connect_interactive()` asks for the key with a hidden prompt, `connect(token_provider=fn,
retry=True)` takes a refreshing token and retries transient errors (recipe in its
docstring), and `check_access(client, dataflow_id)` makes a few read-only calls to show
the credential kind, whether it is alive and whether the dataflow is reachable.

The waiting helpers (`import_file`, `export_to_file`, `export_table`, `read_tables`,
`wait_for_job`) take `progress=True` to show one updating status line (status, elapsed
seconds, page number), or `progress=fn` to receive an event dict per step; it is off by
default, and on a log or pipe it prints a line only when the status changes. A started
job can be kept as `Job.from_polling_url(client, answer)` (from `reportnet_api.jobs`): its
`.status` polls once and `.wait(progress=True)` waits. Ctrl-C while waiting stops only the
waiting and prints the job id; the job keeps running on the server and cannot be cancelled
from here.

Not sure which function you need? `reportnet_api.find("export")` searches every
method and helper by keyword, and `easy.guide()` prints a one-page cheat sheet.
Terms (dataflow, dataset, provider, job, ...) are in [docs/glossary.md](https://github.com/eeadata/reportnet-api-python/blob/main/docs/glossary.md).

Notebooks: [quickstart](https://github.com/eeadata/reportnet-api-python/blob/main/examples/quickstart.ipynb),
[export and upload](https://github.com/eeadata/reportnet-api-python/blob/main/examples/export_and_upload.ipynb),
[validation](https://github.com/eeadata/reportnet-api-python/blob/main/examples/validation.ipynb). `read_table` uses the
synchronous ETL export, whose access is credential-dependent (see `docs/live_testing_notes.md`).

## Command line

`pip install` also adds a read-only `reportnet` command for schedulers and FME's system
caller: `reportnet dataflows`, `reportnet datasets <dataflow>`, `reportnet read <dataset>
<dataflow> --out table.csv`, `reportnet export <dataset> <dataflow> out.zip`,
`reportnet find <words>`. The credential comes from `REPORTNET_API_KEY`, never from an
argument; `--demo` uses fictional data. There is deliberately no command that writes or
deletes data. Without pandas, use `easy.read_records()` (plain dicts) instead of
`read_table()`.

## Reference

Per-function reference (arguments, required ReportNet rights, live-tested caveats):
[docs/reference/index.md](https://github.com/eeadata/reportnet-api-python/blob/main/docs/reference/index.md), also built as a searchable site by
`mkdocs` (see `mkdocs.yml`). Changes are listed in [CHANGELOG.md](https://github.com/eeadata/reportnet-api-python/blob/main/CHANGELOG.md).

## Auth

There's no login/token-acquisition flow — the caller supplies a valid credential:
a Bearer JWT or a dataflow-scoped ApiKey, either as a static string or as a zero-arg
callable for custom refresh logic:

```python
client = ReportnetClient(base_url="https://api.reportnet.europa.eu", token="<jwt>")

# or, for a token that can refresh itself:
client = ReportnetClient(base_url="https://api.reportnet.europa.eu", token=my_token_provider)
```

Every request attaches `Authorization: <scheme> <token>`. The scheme defaults to
`Bearer`; pass `token_scheme="ApiKey"` for an API key (`easy.connect` detects which
one you gave it). The credential is only ever sent to the host of `base_url`: a
request or job URL pointing at another origin raises `ValueError` instead of being sent.

## Calls that write or delete

Many methods change data: imports, deletes, `import_field_schemas`, validations, and
the generated `POST`/`PUT`/`DELETE` methods. Point the client at a dataflow you own.
`easy.import_file(..., replace=True)` deletes existing data first (it emptied the
dataset's other tables too when live-tested) and therefore needs `confirm=True`;
`easy.import_file` also checks a `.csv`'s name and header against the dataset schema
before uploading. The generated delete methods have no such guard. Reportnet answers can
contain personal data (for example lead reporters' emails): handle them accordingly.

## Quickstart — sync

```python
from reportnet_api import ReportnetClient

with ReportnetClient(base_url="https://api.reportnet.europa.eu", token="<jwt>") as client:
    schema = client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=123)
    client.datasets.import_file_data(dataset_id=123, file="local/path.csv")  # WRITES data
```

## Quickstart — async

```python
import asyncio
from reportnet_api import AsyncReportnetClient

async def main() -> None:
    async with AsyncReportnetClient(
        base_url="https://api.reportnet.europa.eu", token="<jwt>"
    ) as client:
        schema = await client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=123)
        await client.datasets.import_file_data(dataset_id=123, file="local/path.csv")  # WRITES data

asyncio.run(main())
```

## File upload/download

Upload and download are path-based and streaming, not in-memory bytes:

```python
client.datasets.import_file_data(dataset_id=123, file="local/path.csv")  # WRITES data
client.dataset_snapshot.download_historic_releases_csv(
    dataflow_id=1, dataset_id=123, file_name="releases.csv", dest="local/out.csv",
)

# Full dataflow schema export ZIP (.schema/.qcrules/.unique/.integrity/
# .extintegrations per dataset, plus datasetSchemaNames.names/
# datasetSchemaIds.ids) — same format the Reportnet UI's schema export
# produces. Requires DATAFLOW_CUSTODIAN or DATAFLOW_STEWARD on the dataflow.
client.dataset_schema.export_dataflow_schemas_zip(
    dataflow_id=4321, dest="local/dataflow_4321_schemas.zip",
)
```

## Errors

HTTP errors raise a typed exception (`AuthenticationError`, `ForbiddenError`,
`NotFoundError`, `ValidationError`, `LockedError` (423: another operation holds
a lock), `TooManyRequestsError` (429, with a `retry_after` property),
`ServerError`, or the base `ReportnetAPIError` for unmapped status codes).
Every exception carries
`status_code`, `response_body`, and the originating `request`/`response`:

```python
from reportnet_api import NotFoundError

try:
    client.datasets.check_import_process(dataset_id=999)
except NotFoundError as e:
    print(e.status_code, e.response_body)
    print(e)            # includes the server's JSON `message` (first 200 chars)
    print(e.explain())  # plain-language cause and what to try
```

`str(e)` ends with the server's `message` when the body is JSON (or a short
text snippet otherwise); the full body stays on `response_body`. `explain()`
adds a likely cause for patterns seen live (revoked ApiKey surfacing as a 500,
423 import lock, ETL 403 for Bearer, ApiKey on a Custodian-only route). In
`easy`, `list_datasets` raises `LookupError` on an empty 200 (the backend's
answer for an unknown dataflow or no access) instead of returning no rows.

## Retries (opt-in)

By default nothing is retried. Pass a `RetryPolicy` to either client to retry
transient failures with exponential backoff:

```python
from reportnet_api import ReportnetClient, RetryPolicy

client = ReportnetClient(base_url=..., token=..., retry=RetryPolicy(retries=3))
```

It retries 429/502/503/504 for GET requests only (honouring `Retry-After`, as
seconds or an HTTP date, capped by `max_delay`), connection failures and pool
timeouts for any method (the request was never sent), and other transient
transport errors for GET only. It never retries 500 (those were deterministic in
live testing), 423 (wait for the other job, e.g. with `wait_for_job`),
permanent errors such as a malformed `base_url`, or requests whose body can't be
replayed (file uploads, streamed bodies). Downloads (`download()`) aren't retried.

## Third-party material

`spec/api-docs.json` is a snapshot of the Reportnet 3 API's own Swagger description, used
to generate the models and method stubs. Its metadata declares "Apache 2.0" (and
`urn:tos`), which are Springfox's defaults rather than a statement about this repository;
the code here is MIT-licensed (see `LICENSE`).

## Development

```
uv sync --all-groups   # install deps + dev tools
uv run ruff check . && uv run ruff format --check .
uv run mypy            # strict, whole project
uv run pytest
```

Resources (`reportnet_api/resources/*.py`) and models
(`reportnet_api/models/generated.py`) are generated, not hand-written — see
[CONTRIBUTING.md](https://github.com/eeadata/reportnet-api-python/blob/main/CONTRIBUTING.md) before touching either, and [SECURITY.md](https://github.com/eeadata/reportnet-api-python/blob/main/SECURITY.md)
to report a security problem.

## Testing against a live API

`uv run pytest` (above) covers everything with mocked HTTP — no network
calls, safe to run anytime. To check a real token/environment actually
works end to end, use `scripts/smoke_test.py`:

```
uv run python3 scripts/smoke_test.py --token "<your-jwt>" \
    --dataset-id <real_id> [--dataflow-id <real_id>]
```

It runs a handful of read-only calls across every resource
(`check_import_process`, `find_data_schema_by_dataset_id`,
plus 3 more if `--dataflow-id` is given) and
prints one line per check:

- `PASS` — call succeeded, response parsed into the expected model
- `WARN` — got a 404 (endpoint reached, but nothing matches that id —
  check `--dataset-id`/`--dataflow-id`)
- `FAIL` — a real problem: auth/validation/server error, or an unexpected
  exception (e.g. a response the client mis-parses)

It's read-only by design (nothing here writes, uploads, or deletes) and
isn't run in CI — it's a manual tool for sanity-checking a deployment.

A few things worth knowing before poking the real API:

- Start with `GET`-only calls before anything that writes or deletes data.
- For upload (`import_file_data`, etc.) or download endpoints, test
  against a dataset you don't mind touching — uploads genuinely write
  data.
- `get_attachment` and `download_imported_file` take a `dest=` and stream
  to it like the other download endpoints.
- `/private/*` operations in the spec are not exposed (the gateway 404s
  them); see `docs/removed_private_endpoints.md`.

For interactively exploring any of the 48 generated endpoints against a real API
instead of writing one-off scripts, there's a local-only Streamlit UI —
`tools/streamlit_app.py`. It introspects the resource classes at runtime
(no per-method hardcoding) to build a resource/method picker with an
auto-generated parameter form. It is **not** part of the published package
(the wheel only ever contains `reportnet_api/`, per
`[tool.hatch.build.targets.wheel]` in `pyproject.toml`) and `streamlit`
lives in its own `uv` dependency group, not `[project.dependencies]`, so
`pip install reportnet-api` never pulls it in:

```
uv run --group ui streamlit run tools/streamlit_app.py
```
