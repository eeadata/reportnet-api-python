# Changelog

All notable changes are listed here. The project follows [Semantic Versioning](https://semver.org/):
while the major version is `0`, a **minor** release (0.x.0) may change the API, and a patch
release (0.x.y) only fixes bugs. Breaking changes are called out below.

## Unreleased

- New `easy.list_representatives(client, dataflow_id)`: the countries assigned to a
  dataflow as a table, with the country code and name joined from the provider
  listing (one lookup per provider group). Lead reporter email addresses are left out
  unless `include_contacts=True`. Also in `easy.guide()` and the glossary.

## 0.1.4 (2026-11-21)

- `datasets.import_big_file_data` docstring: on the current backend a data-lake import
  answers a job map like any other import (checked live on the sandbox); the empty-body
  `{}` case is for older backends.
- `read_tables` (and `read_table`, `read_records`, `read_all_records`): when the export
  has no rows at all, the dataflow's `bigData` flag is looked up. A data-lake dataflow
  gets a definite warning pointing to `export_to_file()`; a dataflow that answers
  `bigData: false` gets no warning, since its tables really are empty. If the lookup
  fails or its answer does not say, the old "may be a data lake" warning stays.
- `validate_and_wait` (and `Dataset.validate`) now polls the validation job: the
  current backend answers `validation.start_validation` with the job's id, which
  that method now returns (`None` on backends that answer an empty body). A job that
  ends FAILED, REFUSED or CANCELED raises `JobError` with the job's status and
  `info` right away, instead of waiting for the timeout; a finished job with a note
  warns with it and stores it in the result's `attrs["validation_note"]`. Without a
  job id, or when polling is refused, it waits for the user notification as before,
  and now also stops on a refused, canceled or failed notification. New keyword
  `provider_id` (the handle passes its own); `start_validation` also takes
  `dataflow_id` and `provider_id`. Checked live on the sandbox (normal run, and a
  second start while one runs, which gets `LockedError`).

## 0.1.3 (2026-11-19)

- Downloads (`client.download()` and everything built on it, such as `export_to_file`)
  write to a temporary file next to `dest` and replace `dest` only when complete: a
  failed download no longer leaves a partial file in place of the previous one.
- `export_to_file`'s fallback on non-data-lake dataflows now stays within the one
  `timeout` and no longer overwrites a file named `<dest>.part`.
- `TooManyRequestsError.retry_after` returns `None` (not `inf`/`nan`) for such
  `Retry-After` values.
- Development: strict mypy over the whole project, a wider ruff rule set, warnings as
  errors in tests (which also no longer reach the network), pre-commit hooks.

## 0.1.2 (2026-11-19)

- `easy.export_to_file` (and `Dataset.export`) work again on dataflows that are not a
  data lake. Newer Reportnet versions refuse the CSV and Parquet ZIP exports there; CSV
  now falls back to the older JSON export and writes the same ZIP of per-table CSVs.
  Parquet on such a dataflow raises a `JobError` that says so.
- `JobError` has `status` and `info` attributes when the job itself reported the failure.

## 0.1.1 (2026-11-18)

- Docstring fixes only (no behaviour change): `easy.export_validations` and the
  `handles` module docstring had leftover fragments and wrong indentation.

## 0.1.0 (2026-11-18)

First public version.

- Sync and async clients for the Reportnet 3 REST API, generated resource methods plus
  hand-written ones for endpoints missing from the API's Swagger description.
- `reportnet_api.easy`: notebook helpers (pandas DataFrames or plain records), typed
  columns, safer uploads (`check_import_file`, `import_dataframe`, `confirm=True` for
  `replace=True`), validation helpers, progress and job waiting.
- Dataflow and dataset handles, `find()` search, `easy.guide()` cheat sheet.
- `demo_client()` for trying the helpers without a credential; a read-only `reportnet`
  command line.
- The credential is only sent to the configured host, and a plain-`http` base URL warns.
- `read_records`/`read_all_records` for plain dicts without pandas (FME, scripts).
- Python 3.11 or newer.
