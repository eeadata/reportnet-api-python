# SPEC.md — reportnet-api-python (original design notes)

> **Historical document.** This is the design written before the library was built. Parts
> of it are out of date (for example it rules out a command line and lists names that
> changed). The code, the [README](README.md) and `docs/reference/` describe what the library
> does today.

## 1. Purpose

A Python client library for the EEA Reportnet 3 REST API (`api.reportnet.europa.eu`),
generated from the project's Swagger 2.0 spec (`api-docs.json`, 62 endpoints / 49
model definitions across 6 tags). The library wraps raw HTTP calls with a typed,
ergonomic, resource-namespaced client for both sync and async usage.

Source spec snapshot: `spec/api-docs.json` (Swagger 2.0, host `api.reportnet.europa.eu`,
JWT bearer auth via `Authorization` header).

## 2. Scope

In scope:
- Full coverage of all 62 endpoints across the 6 tags:
  - Dataset Schema (11 endpoints)
  - Datasets (42 endpoints)
  - Dataset Snapshot (7 endpoints)
  - EU Datasets (1 endpoint)
  - Release Receipts (4 endpoints)
- Pydantic v2 models for all 49 swagger definitions.
- Sync and async clients sharing one HTTP core.
- File upload/download support (attachments, CSV/Parquet export, importFileData).

Out of scope (v1):
- No login/token-acquisition flow — the caller supplies a valid JWT or a callable
  that returns one.
- No CLI.
- No response caching.

## 3. Architecture

### 3.1 Package layout

```
reportnet_api/
├── __init__.py
├── _core.py              # shared request-building/transport logic
├── _auth.py               # token / token-provider handling
├── _exceptions.py         # exception hierarchy
├── client.py               # ReportnetClient (sync)
├── async_client.py          # AsyncReportnetClient
├── models/                  # Pydantic models, generated from swagger definitions
│   ├── __init__.py
│   └── generated.py
└── resources/                # one module per swagger tag
    ├── __init__.py
    ├── dataset_schema.py
    ├── datasets.py
    ├── dataset_snapshot.py
    ├── eu_datasets.py
    └── release_receipts.py
```

Usage shape:

```python
from reportnet_api import ReportnetClient

client = ReportnetClient(base_url="https://api.reportnet.europa.eu", token="...")
schema = client.dataset_schema.find_data_schema_by_dataset_id(dataset_id=...)
client.datasets.import_file_data(dataset_id=123, file="path/to/file.csv", ...)
```

Async mirrors this 1:1 with `await`:

```python
from reportnet_api import AsyncReportnetClient

client = AsyncReportnetClient(base_url="...", token="...")
schema = await client.dataset_schema.find_data_schema_by_dataset_id(...)
```

### 3.2 Transport core

- Built on `httpx`. One shared module (`_core.py`) builds requests (URL, params,
  headers, body) from method-level metadata; `client.py` and `async_client.py`
  are thin wrappers calling `httpx.Client` / `httpx.AsyncClient` respectively.
- No endpoint's request-building logic should be written twice for sync/async.

### 3.3 Auth

- `ReportnetClient(token="...")` accepts either a static string or a zero-arg
  callable (`token_provider`) so callers can plug in their own refresh logic.
- Every request attaches `Authorization: <scheme> <token>`, where `<scheme>`
  defaults to `Bearer` but is overridable via `token_scheme=` — Reportnet's
  dataflow-scoped API keys use `Authorization: ApiKey <key>` instead of a JWT
  bearer token, so the scheme isn't fixed.
- No login endpoint is implemented — none exists in the swagger spec.

### 3.4 Models

- All 49 definitions in `api-docs.json#/definitions` are converted to Pydantic v2
  models via `datamodel-code-generator`, output to `models/generated.py`.
- Regeneration is a scripted, repeatable step (see `scripts/`), not a one-time
  hand-edit — if the spec changes, models regenerate cleanly.
- Hand-written model subclasses/helpers (if needed for ergonomics) live outside
  `generated.py` so regeneration never clobbers them.

### 3.5 Method generation

- A custom generator script (`scripts/generate_resources.py`) parses
  `api-docs.json` and emits one method per operation into the appropriate
  `resources/<tag>.py` file, grouped by swagger `tags`.
- Each generated method: typed params (from path/query/body parameters), typed
  return (from the `200` response schema where available), and a docstring
  pulled from the operation's `summary`/`description`.
- Endpoints with duplicate versions (`etlExport` v1/v2/v3, `importFileData` v1/v2/v3
  under `/dataset/{version}/...`) are all exposed as separate methods
  (e.g. `export_etl_v1`, `export_etl_v2`, `export_etl_v3`); older versions are
  marked `Deprecated: use export_etl_v3 instead.` in the docstring, not removed.
- Manual review pass after generation focuses on: naming consistency, docstring
  quality, and correctness of file-upload/download endpoints (these need special
  handling the generic generator won't get right automatically).

### 3.6 File upload/download

- Interface is path-based streaming, not in-memory bytes:
  - Upload: `client.datasets.import_file_data(dataset_id=..., file="local/path.csv", ...)`
  - Download: `client.snapshot.download_historic_releases(dataset_id=..., dest="local/out.csv")`
- Implemented via `httpx`'s streaming request/response support so large files
  aren't fully buffered in memory.

### 3.7 Errors

Custom exception hierarchy, mapped from HTTP status codes:

```
ReportnetAPIError (base)
├── AuthenticationError      # 401
├── ForbiddenError           # 403
├── NotFoundError            # 404
├── ValidationError          # 400 / 422 if applicable
└── ServerError              # 5xx
```

All exceptions carry `status_code`, `response_body`, and the originating
`httpx.Request`/`httpx.Response` for debugging. Unmapped status codes raise the
base `ReportnetAPIError`.

## 4. Tooling

- **Packaging**: `uv` + `hatchling`, `pyproject.toml`-only (no `setup.py`).
- **Lint/format**: `ruff`.
- **Type checking**: `mypy` (strict on `reportnet_api/`, relaxed on generated
  code if needed).
- **Testing**: `pytest` + `respx` (or `pytest-httpx`) for mocked HTTP — no live
  calls to the real API in CI.
- **CI**: GitHub Actions workflow running ruff → mypy → pytest on every push/PR.

## 5. Non-goals / open questions for later

- Rate limiting / retry policy: not decided yet, revisit once real usage patterns
  are known (Datasets tag alone has 42 endpoints, likely a mix of read-heavy and
  write-heavy calls).
- Pagination helpers (`limit`/`offset` appear on `etlExport` endpoints only) —
  v1 will expose `limit`/`offset` as plain params; auto-pagination iterators are
  a possible v2 addition.
- PyPI publishing — not scoped for v1; local/`uv add` from git is sufficient
  initially.
