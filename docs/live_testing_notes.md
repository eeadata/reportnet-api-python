# Live testing notes

> **Removed methods:** every method marked `/private/*` below (T06, P8-01)
> has since been removed from the client. They are listed in
> `docs/removed_private_endpoints.md`. The notes remain as history and can't
> be re-run against the current client.

> **About the labels:** headings and cross-references such as `T05`, `T06`, `P8-07` or
> "Phase 7/8" name the passes of the original live-testing log. They are only labels
> for the order the calls were made in; nothing else in this repository defines them.

Results of calling each read-only (`GET`) `reportnet_api` method against the
live production API (`https://api.reportnet.europa.eu`), using the scratch
dataflow `<scratch dataflow>` / dataset `<scratch dataset>` (`.env`'s `REPORTNET_DATAFLOW_ID`/
`REPORTNET_DATASET_ID`) and an `ApiKey` credential (Reporter-level access).
Findings that proved durable are repeated as live-tested notes in `docs/reference/`.

Each entry:

```
### <method_name>

- **Params used**: ...
- **Result**: <status> — <shape of what came back, or error>
- **Notes**: anything surprising, spec-vs-live mismatch, role requirement,
  or confirmation that it matched the spec/docstring exactly.
```

Status is one of: `confirmed` (matched spec, worked as documented),
`gotcha` (behaved differently from the spec/docstring — also repeated in
`docs/reference/`), `role-blocked` (403, credential lacks the required role — still
useful, confirms the role gate exists), `error` (unexpected failure, needs
follow-up).

## Credential requirement matrix

Quick-scan summary of what each of the 35 read-only (Phase 7/T05) methods
actually needs, as opposed to what the spec declares. `ApiKey` below always
means the scratch dataflow's Reporter-level key; `Bearer` means a JWT for a
user confirmed to hold `DATAFLOW_CUSTODIAN`/`DATAFLOW_STEWARD` on dataflow
`<scratch dataflow>` (T05's credential). Cells marked **not tested** genuinely weren't
tried with that credential — don't read them as "fails," just "unknown."
Link targets go to the full narrative entry below for the reasoning behind
each verdict. Mutating (`POST`/`PUT`/`DELETE`) endpoints are out of scope
for this table; they are covered in the Phase 8 section below.

| Method | ApiKey (Reporter) | Bearer (Custodian/Steward) | Notes |
|---|---|---|---|
| [`find_data_schema_by_dataset_id`](#find_data_schema_by_dataset_id) | ✅ works | not tested | — |
| [`get_table_schemas_ids`](#get_table_schemas_ids) | ✅ works | not tested | needs `dataflow_id` despite spec marking it optional |
| [`get_simple_schema`](#get_simple_schema) | ✅ works | not tested | needs `dataflow_id` despite spec marking it optional |
| [`get_table_schema_name`](#get_table_schema_name) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`get_table_schema_vo`](#get_table_schema_vo) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`get_field_schema`](#get_field_schema) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`get_field_name`](#get_field_name) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`export_field_schemas_from_dataset`](#export_field_schemas_from_dataset) | ✅ works | not tested | needs `Accept: */*`; returns binary ZIP despite `str` return type |
| [`export_field_schemas`](#export_field_schemas) | ✅ works | not tested | needs `Accept: */*` **and** `dataset_id`+`table_schema_id` together |
| [`export_dataflow_schemas_zip`](#export_dataflow_schemas_zip) | ❌ 403 | ✅ works | plain Custodian/Steward role gate, confirmed both ways |
| [`historic_releases`](#historic_releases) | ❌ 403 | ❌ still 403 | **not just a role gate** — suspected Design-dataset exclusion, see T07 |
| [`get_snapshot_by_dataset_id`](#get_snapshot_by_dataset_id) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`get_latest_historic_release_snapshot`](#get_latest_historic_release_snapshot) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`download_historic_releases_csv`](#download_historic_releases_csv) | ❌ 403 | ❌ still 403 | same suspected Design-dataset exclusion as `historic_releases`, see T07 |
| [`check_import_process`](#check_import_process) | ✅ works | not tested | — |
| [`datasets_updated_after_release`](#datasets_updated_after_release) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`find_tasks_by_process_id_and_status_in`](#find_tasks_by_process_id_and_status_in) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable; tested with a fake `process_id` |
| [`generate_import_presigned_url`](#generate_import_presigned_url) | ✅ works | not tested | side effect — allocates a real job/S3 path on every call |
| [`get_attachment`](#get_attachment) | ⚠️ inconclusive | not tested | needs `Accept: */*`; 500 past that, no real attachment data to test against |
| [`get_available_for_manual_editing_tables`](#get_available_for_manual_editing_tables) | ✅ works | not tested | — |
| [`get_iceberg_tables`](#get_iceberg_tables) | ✅ works | not tested | — |
| [`get_import_related_statistics`](#get_import_related_statistics) | ✅ works | not tested | — |
| [`get_record_geometry`](#get_record_geometry) | ⚠️ inconclusive | not tested | 500 — no real geometry-field data in scratch dataset |
| [`get_released_dataset_data_info`](#get_released_dataset_data_info) | ⚠️ inconclusive | not tested | 500 — no real provider registered on scratch dataflow |
| [`is_iceberg_table_created`](#is_iceberg_table_created) | ✅ works | not tested | — |
| [`list_imported_files`](#list_imported_files) | ❌ 403 | ✅ works | plain Custodian/Steward role gate, confirmed both ways |
| [`etl_export_dataset`](#etl_export_dataset) | ✅ works | not tested | synchronous |
| [`etl_export_dataset_v2`](#etl_export_dataset_v2) | ✅ works | not tested | synchronous |
| [`etl_export_dataset_with_job`](#etl_export_dataset_with_job) | ✅ 200, but... | not tested | async job-based — `dest=` captures a "job started" JSON, not real data |
| [`etl_export_zip_csv`](#etl_export_zip_csv) | ✅ 200, but... | not tested | same async-job gotcha as above |
| [`etl_export_zip_parquet`](#etl_export_zip_parquet) | ✅ 200, but... | not tested | same async-job gotcha as above |
| [`create_file_for_etl_export`](#create_file_for_etl_export) | ❌ 404, unreachable | ❌ 404, unreachable | `/private/*`, T06 confirmed permanently unreachable |
| [`download_imported_file`](#download_imported_file) | ❌ 403 | ✅ past role gate | Bearer reaches a specific 500 ("no import directory") instead of 403 — role satisfied, just no data |
| [`dremio.run`](#dremiorun) | ❌ 404, unexplained | not tested | not a `/private/*` path — possibly non-production-only, unconfirmed |
| [`get_release_receipt_by_dataflow_id`](#get_release_receipt_by_dataflow_id) | ✅ works | not tested | — |

---

## T06: `/private/*` unreachability — confirmed and explained

Phase 7/T05 observed all 9 `*/private/*`-routed methods 404ing with the
scratch dataflow's `ApiKey` credential and suspected (but didn't confirm)
that the path prefix isn't exposed through the gateway at all. T06 settles
this with two independent findings, both against the `develop` branch of
the Reportnet 3 backend source repository (GitHub) at commit `f7b5777` (2026-07-08):

1. **Gateway config confirms it's deliberate and total.** The API gateway
   (`api-gateway`, a Spring Cloud Zuul gateway) is configured via Consul KV
   (`configuration/consulKV.json`) with
   `config/apiGateway/zuul.ignoredPatterns` = `/**/private/**` (base64
   `LyoqL3ByaXZhdGUvKio=`, decodes to that literal glob). Zuul's
   `ignoredPatterns` strips any path matching the glob from routing
   entirely, before it reaches the auth layer — this is a single, global
   rule covering *every* service behind the gateway, not a per-endpoint or
   per-controller decision. This explains the 404 (route doesn't exist as
   far as the gateway is concerned) rather than a 401/403 (would mean the
   route exists but access was denied), and explains why credential class
   (`ApiKey` vs Bearer) made no difference in either Phase 7/T05 or T06's
   own Bearer retest below — the gateway drops the request before any
   credential is even inspected.
2. **The backend controller methods themselves no longer exist.** Reading
   the actual Java source for the 3 controllers behind these 9 operations
   — `DatasetSchemaControllerImpl.java`, `DatasetSnapshotControllerImpl.java`,
   `DatasetControllerImpl.java` (all in `dataset-service/src/main/java/
   the dataset service's `controller/` package/`) — none of the 9 method/path pairs declared
   in `spec/api-docs.json` (`getTableSchemName`, `getTableSchemaVo`,
   `getFieldSchemaVo`, `getFieldName`, `getSnapshotByDatasetId`,
   `latestReleaseSnapshot`, `datasetsUpdated`,
   `findTasksByProcessIdAndStatusIn`, `etlExport/createFile`) are present
   in current `develop`, by exact string or path. Each controller file was
   fetched in full and grepped directly (not GitHub's code search, which
   requires sign-in) — confirmed absent, not just missed by a shallow read.
   This means `spec/api-docs.json` is stale relative to the live backend
   for these 9 specifically: either the operations were removed/refactored
   away in the backend after the spec snapshot was taken, or they moved to
   a controller/module outside `dataset-service` that wasn't checked. Either
   way, the client-visible symptom is identical — permanently unreachable —
   so this doesn't change the verdict, only reinforces it with an
   independent cause.

Angle 1's retest (Bearer JWT, same elevated Custodian/Steward credential
from T05) is done: all 9 endpoints retried with fresh IDs pulled from a
successful `find_data_schema_by_dataset_id` call in the same run — every
one still 404s, identical body shape to the `ApiKey` pass. See each
method's own entry below for per-call detail; this section is the shared
finding referenced from all nine.

**Verdict**: all 9 endpoints are confirmed permanently unreachable through
this client against the public gateway, for two independent, reinforcing
reasons. Not a client bug, not a credential problem, not stale/wrong test
data. Decision (T06): documentation only — these 9 stay
generated as-is rather than being excluded from
`scripts/generate_resources.py`'s generation allowlist.

---

## dataset_schema.py

### find_data_schema_by_dataset_id

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: confirmed — returns `DataSetSchemaVO` with nested `tableSchemas`
  (one table, `TestTable`, `idTableSchema="<object id>"`) and
  each table's `recordSchema.fieldSchema` list (one field, `TestField`,
  `id="<object id>"`, type `TEXT`).
- **Notes**: matches the spec/docstring exactly. Used as the ID-discovery
  call for the rest of this phase's tests (`idDataSetSchema`,
  `idTableSchema`, field `id`).

### get_table_schemas_ids

- **Params used**: `dataset_id=<scratch dataset>` (first without `dataflow_id`, then
  with `dataflow_id=<scratch dataflow>`)
- **Result**: gotcha — without `dataflow_id`: `400 Bad Request: Required
  Long parameter 'dataflowId' is not present`. With `dataflow_id=<scratch dataflow>`:
  confirmed, returns `[TableSchemaIdNameVO(idTableSchema=..., nameTableSchema='TestTable')]`.
- **Notes**: same spec-vs-live mismatch already documented for
  `get_simple_schema` in `docs/reference/` — `dataflowId`/`datasetId`/`providerId`
  are all declared `required: false` for this endpoint family but the
  backend requires `dataflowId`. This confirms the earlier suspicion
  flagged as untested for this specific method.

### get_simple_schema

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>`
- **Result**: confirmed — returns `SimpleDatasetSchemaVO` with one table
  (`TestTable`) containing one field (`TestField`, type `TEXT`).
- **Notes**: re-confirms the already-documented `dataflow_id`-required
  gotcha from earlier this session; no new finding.

### get_table_schema_name

- **Params used**: `dataset_schema_id="<object id>",
  table_schema_id="<object id>"` (both freshly confirmed
  valid via `find_data_schema_by_dataset_id` above)
- **Result**: error — `404 Not Found` on
  `GET /dataschema/private/getTableSchemName`, even with valid IDs and
  retried with `Accept: */*`.
- **Notes**: see the shared note under `get_field_schema` below — all
  `/dataschema/private/*` routes 404 regardless of params.
- **T06 update**: retested with the Bearer credential — still `404`. See
  the T06 section below.

### get_table_schema_vo

- **Params used**: same as `get_table_schema_name` above.
- **Result**: error — `404 Not Found` on
  `GET /dataschema/private/getTableSchemaVo`, same conditions.
- **Notes**: see `get_field_schema` below.
- **T06 update**: retested with the Bearer credential — still `404`. See
  the T06 section below.

### get_field_schema

- **Params used**: `dataset_schema_id="<object id>",
  id_field_schema="<object id>"` (valid, from discovery).
- **Result**: error — `404 Not Found` on
  `GET /dataschema/private/getFieldSchemaVo`.
- **Notes**: **gotcha** — all three tested `/dataschema/private/*` routes
  (`getTableSchemName`, `getTableSchemaVo`, `getFieldSchemaVo`) 404
  consistently with fresh, valid IDs pulled from a successful
  `find_data_schema_by_dataset_id` call moments earlier — ruling out stale/
  wrong IDs as the cause. `get_field_name` (also under `/dataschema/
  private/`) 404s too, even with a syntactically-valid but fake
  `rule_reference_id` — same shape of failure regardless of whether the
  fake ID would plausibly 404 on its own. The consistent pattern across
  all four `/dataschema/private/*` endpoints suggests this path prefix
  isn't exposed through the public API gateway at all (`private` in the
  URL may be literal — these may be intended for internal service-to-
  service calls only), rather than any individual endpoint being broken.
 
- **T06 update**: retested with the Bearer credential — still `404`,
  identical body. See "T06: `/private/*` unreachability, confirmed and
  explained" below for the decisive finding (gateway config + controller
  source).

### get_field_name

- **Params used**: `dataset_schema_id="<object id>",
  rule_reference_id="<object id>"` (fake, no real rule
  reference existed to test with), `table_schema_id="<object id>"`
- **Result**: error — `404 Not Found` on `GET /dataschema/private/getFieldName`.
- **Notes**: consistent with the `/dataschema/private/*` pattern documented
  under `get_field_schema` above; not retested with a real rule reference
  ID since none exists in the scratch dataset, but the 404 shape matches
  the other three private routes exactly.
- **T06 update**: retested with the Bearer credential — still `404`. See
  the T06 section below.

### export_field_schemas_from_dataset

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: gotcha — `406` with the client's default `Accept:
  application/json` header. Retried with `Accept: */*` (same fix as the
  existing `/dataschema/export` 406 gotcha in `docs/reference/`): succeeds and
  returns a binary ZIP (`PK\x03\x04...` magic bytes, containing
  `TestTable.csv`).
- **Notes**: **gotcha, two parts.** (1) 406 without `Accept: */*` — the
  known gateway-negotiation gotcha isn't unique to `/dataschema/export`;
  it applies here too. (2) The method's return type is `str`
  (`response.text`) and it is **not** in `DOWNLOAD_METHOD_NAMES`, but the
  actual response body is a binary ZIP — decoding it as text is lossy/
  unsafe for real ZIP content (this scratch dataset's tiny CSV payload
  happened not to visibly corrupt when inspected, but that's not a safe
  general assumption). Candidate for the `dest=`-based download treatment;
  not changed in this pass since P7 is observation-only, but worth a
  follow-up task.

### export_field_schemas

- **Params used**: `dataset_schema_id="<object id>"`, tried
  with `dataset_id` only, `table_schema_id` only, neither, and both
  together (`dataset_id=<scratch dataset>, table_schema_id="<object id>"`).
- **Result**: gotcha — `406` with default `Accept` header (same fix:
  `Accept: */*`; `application/octet-stream` also works, re-tested in T08
  follow-up #6 — the 406 is Spring content negotiation against `produces`).
  Even after that fix: `400 Bad Request` with `table_schema_id` only or
  neither, and `500` (not 400) with `dataset_id` only (follow-up #6). Only succeeds
  (`200`, returns CSV text: `Field name,PK,Required,ReadOnly,Field
  description,...`) when **both** are supplied together.
- **Notes**: **gotcha.** Both `dataset_id` and `table_schema_id` are typed
  as independently optional (`| None = None`) in the method signature per
  the spec, but the backend actually requires both together — a stricter
  version of the same declared-optional/actually-required pattern as
  `get_simple_schema`'s `dataflow_id`. Unlike
  `export_field_schemas_from_dataset`, this one genuinely returns text
  (CSV), so no download-treatment concern here.

## dataset_schema_ext.py

### export_dataflow_schemas_zip

- **Params used**: `dataflow_id=<scratch dataflow>`
- **Result**: role-blocked — `403 Forbidden` (as expected — see this
  session's original diagnosis and the "Auth: API key vs Bearer role
  scope" section of `docs/reference/index.md`).
- **Notes**: confirms the documented Custodian/Steward requirement; the
  scratch dataflow's Reporter-level `ApiKey` credential can't satisfy it.
  No new finding — re-confirms the pre-Phase-7 diagnosis for the record.
- **T05 update (Bearer, elevated credential)**: confirmed — `200`, returns
  a real 2216-byte ZIP. Settles that the endpoint works exactly as
  documented once a credential actually holding Custodian/Steward on
  dataflow `<scratch dataflow>` is used — the earlier 403 was purely the `ApiKey`
  credential-class ceiling, nothing else.

## dataset_snapshot.py

### historic_releases

- **Params used**: none; `dataflow_id=<scratch dataflow>` only; `dataflow_id=<scratch dataflow>,
  dataset_id=<scratch dataset>`
- **Result**: gotcha, then role-blocked — no params: `400`. `dataflow_id`
  only: `400` (same error family as the other declared-optional/actually-
  required params in this codebase). Both `dataflow_id` and `dataset_id`:
  `403 Forbidden`.
- **Notes**: both params are typed independently optional but the backend
  needs both together before it will even evaluate the role check — same
  shape as `dataset_schema.export_field_schemas`'s `dataset_id`/
  `table_schema_id` pairing. The eventual `403` matches the docstring's
  declared `CUSTODIAN`/`STEWARD` requirement — the scratch dataflow's
  Reporter-level `ApiKey` credential doesn't hold either role, so this is
  role-blocked, not a bug. Confirms the role gate exists as documented.
- **T05 update (Bearer, elevated credential)**: still `403 Forbidden` —
  same generic `{"error":"Forbidden","message":"Forbidden"}` body, even
  though the *same* Bearer credential succeeded on
  `export_dataflow_schemas_zip` moments earlier in the same run (proving
  it does hold Custodian/Steward on dataflow `<scratch dataflow>`). **This means the
  original Phase 7 `role-blocked` verdict for this endpoint was wrong** —
  it isn't (purely) a role gate. `historic_releases`' own docstring lists
  allowed roles only for "Reporting dataset", "Data collection", and "EU
  dataset" — notably **not** "Design dataset". The scratch dataset `<scratch dataset>`
  (a bare schema with one table/field, no data) is very likely a Design
  dataset, which would mean this operation doesn't apply to it at all,
  regardless of role — not confirmed via a direct "get dataset type" call,
  but consistent with every other signal from this dataset (schema-only
  content, no import history, etc.). Needs a Reporting/Data collection/EU
  dataset to actually confirm the success path.
  correction to the Phase 7 note.

### get_snapshot_by_dataset_id

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: error — `404 Not Found` on `GET /snapshot/private/getSnapshotByDatasetId`.
- **Notes**: same `*/private/*` pattern as `dataset_schema`'s private
  routes (see that section) — generalizes the theory from `/dataschema/
  private/*` to `/snapshot/private/*` too, i.e. likely **any** `*/private/*`
  path in this API, not just the dataschema family.
- **T06 update**: retested with the Bearer credential — still `404`. See
  the T06 section below.

### get_latest_historic_release_snapshot

- **Params used**: `dataset_id=<scratch dataset>` alone, then with `dataflow_id=<scratch dataflow>` added.
- **Result**: error — `404 Not Found` on `GET /snapshot/private/latestReleaseSnapshot`, both times.
- **Notes**: same `*/private/*` pattern; see `get_snapshot_by_dataset_id` above.
- **T06 update**: retested with the Bearer credential — still `404`. See
  the T06 section below.

### download_historic_releases_csv

- **Params used**: `dataflow_id=<scratch dataflow>, dataset_id=<scratch dataset>, file_name="test.csv"`
  (guessed — no real historic-release file name was available to test with)
- **Result**: role-blocked — `403 Forbidden`.
- **Notes**: reaches the auth/role check before validating `file_name`
  (no `400`/`404` for the presumably-nonexistent file), so this is
  genuinely role-gated rather than input-validation failure — consistent
  with `historic_releases`' `CUSTODIAN`/`STEWARD` requirement even though
  this method's own docstring doesn't declare roles (spec gap, not
  retested with a real file name since the call never got past auth).
- **T05 update (Bearer, elevated credential)**: still `403 Forbidden`,
  same generic body as before. Same correction as `historic_releases`
  above — this Bearer credential proved it holds Custodian/Steward on
  dataflow `<scratch dataflow>` via the successful `export_dataflow_schemas_zip` call in
  the same run, so this isn't purely role-blocked either. Most likely
  shares `historic_releases`' dataset-type restriction (this endpoint is
  clearly related — same `/snapshot/*` family, same historic-release
  concept), not confirmed independently.

## datasets.py — general reads

### check_import_process

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: confirmed — `CheckLockVO(importInProgress=False, message='There is no import process in progress')`.
- **Notes**: matches spec/docstring exactly.

### datasets_updated_after_release

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: error — `404 Not Found` on `GET /dataset/private/datasetsUpdated`.
- **Notes**: `*/private/*` pattern, third resource family confirmed
  (dataschema, snapshot, now datasets).
- **T06 update**: retested with the Bearer credential — still `404`. See
  the T06 section below.

### find_tasks_by_process_id_and_status_in

- **Params used**: `process_id="fake-process-id"` (no real process ID was
  available — nothing in this scratch dataset has triggered an async
  job/process), `status=["IN_PROGRESS"]`
- **Result**: error — `404 Not Found` on `GET /dataset/private/findTasksByProcessIdAndStatusIn/...`.
- **Notes**: consistent with the `*/private/*` pattern, though not fully
  isolated from "fake process_id" as a cause since a real process ID was
  never available to retest with.
- **T06 update**: retested with the Bearer credential (still with the same
  fake `process_id`) — still `404`. See the T06 section below; the
  gateway-level explanation found there means the fake `process_id` was
  never isolated as *a* cause because it was never reachable enough to
  matter — the route is stripped before any parameter is evaluated.

### generate_import_presigned_url

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>, file_name="test.csv"`
- **Result**: confirmed — returns a real `JobPresignedUrlInfo` with a live
  S3 presigned PUT URL and a server-allocated `jobId` (`<job id>`).
- **Notes**: **caution, not a bug** — despite being a `GET`, this call is
  not fully side-effect-free: the backend allocates a real `jobId` and an
  S3 object path (`df-<dataflow>/dp-<provider>/ds-<dataset>/current/
  provider_import/<ts>_test.csv`) on every call, even though nothing was
  actually uploaded to the returned presigned URL in this test. Calling it
  repeatedly for exploratory/testing purposes will keep allocating job
  records server-side. Not harmful against the scratch dataflow, but worth
  knowing before calling this against a real dataflow just to "see what it
  returns."

### get_attachment

- **Params used**: `dataset_id=<scratch dataset>, field_id="<object id>"`
  (schema field ID — this scratch dataset has no actual data
  rows/attachments, so no real attachment existed to fetch),
  `dataflow_id=<scratch dataflow>`
- **Result**: gotcha, then error — `406` with the client's default
  `Accept: application/json`. Retried via a raw `client.download()` call
  with `Accept: */*`: gets past the 406 but then `500 Server Error`
  (plausible given `field_id` here is a `TEXT`-type schema field, not a
  real `ATTACHMENT`-type field with actual uploaded data — not retested
  against genuine attachment data since none exists in this dataset).
- **Notes**: **gotcha** — same `Accept: */*` gateway-negotiation issue as
  `dataschema_ext.export_dataflow_schemas_zip` and
  `dataset_schema.export_field_schemas*`, but this is the first case hit
  on an *already-migrated* `dest=`-based download method
  (`get_attachment` is in `DOWNLOAD_METHOD_NAMES`). `client.download()`
  builds headers the same way `client.request()` does (default `Accept:
  application/json`), and `get_attachment()`'s own signature doesn't
  expose a `headers=` override, so callers can't work around this
  themselves without reaching into `client.download()` directly.

### get_available_for_manual_editing_tables

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: confirmed — `[]` (no manually-editable tables in this scratch schema).
- **Notes**: matches spec/docstring; empty result is expected given the schema.

### get_iceberg_tables

- **Params used**: `dataflow_id=<scratch dataflow>, dataset_id=<scratch dataset>`
- **Result**: confirmed — `[]` (no Iceberg tables for this scratch dataset).
- **Notes**: matches spec/docstring.

### get_import_related_statistics

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: confirmed — `{'<object id>': {'lastImportDate': None, 'numberOfRecordsImported': None, 'fileExtension': None}}`.
- **Notes**: keyed by `table_schema_id`; matches spec/docstring shape.

### get_record_geometry

- **Params used**: `dataflow_id=<scratch dataflow>, dataset_id=<scratch dataset>,
  field_id="<object id>", id_table_schema="<object id>",
  record_id="<object id>"` (fake record ID — this scratch
  dataset has no actual data rows, let alone a geometry-type field)
- **Result**: error — `500 Server Error`.
- **Notes**: inconclusive — `field_id` used is a `TEXT`-type schema field,
  not a real geometry field with real record data, so the 500 is plausibly
  just "no such record/field combination" rather than a genuine server
  bug. Not retested with real geometry data since none exists in this
  scratch dataset. Needs follow-up with a dataset that actually has
  POINT/geometry-type field data before treating this as a confirmed bug.

### get_released_dataset_data_info

- **Params used**: `collection_dataset_id=<scratch dataset>, provider_code="XX"`
  (fake — no real provider is registered against this scratch dataflow),
  `table_schema_id="<object id>"`
- **Result**: error — `500 Server Error`.
- **Notes**: inconclusive, same shape as `get_record_geometry` above —
  likely "no such provider" rather than a genuine bug, given the fake
  `provider_code`. Needs a real provider-scoped dataset to confirm either way.

### is_iceberg_table_created

- **Params used**: `dataset_id=<scratch dataset>, table_schema_id="<object id>"`
- **Result**: confirmed — `False`.
- **Notes**: matches spec/docstring.

### list_imported_files

- **Params used**: `dataset_id=<scratch dataset>`
- **Result**: role-blocked — `403 Forbidden`.
- **Notes**: no roles declared in this method's docstring (spec gap), but
  the 403 shape matches every other role-gated call tested this phase —
  the scratch dataflow's Reporter-level `ApiKey` credential doesn't hold
  whatever role this needs.
- **T05 update (Bearer, elevated credential)**: confirmed — `200`, returns
  `[]` (empty, no files ever imported to this scratch dataset). This one
  really was a plain role gate — Custodian/Steward, matching the pattern
  of `export_dataflow_schemas_zip` rather than `historic_releases`. Empty
  result is expected, not a sign of a problem.

## datasets.py — export/download family

### etl_export_dataset

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>`
- **Result**: confirmed — `200`, no `Accept` override needed (unlike
  several other export/download endpoints this phase). Downloaded body is
  JSON: `{"tables":[{"records":[],"tableName":"TestTable","totalRecords":0}]}`.
- **Notes**: synchronous — returns actual (empty, since this scratch
  dataset has no data rows) table data directly in the response body, no
  job/polling involved. Matches the "v1 = plain sync export" reading in
  the method-naming rationale.

### etl_export_dataset_v2

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>`
- **Result**: confirmed — `200`, same shape as `etl_export_dataset`:
  `{"tables":[{"records":[],"tableName":"TestTable","totalRecords":0}]}`.
- **Notes**: same synchronous behavior as v1; content-wise indistinguishable
  in this scratch dataset (no data to show a v1-vs-v2 difference).

### etl_export_dataset_with_job

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>`
- **Result**: gotcha — `200`, but body is JSON, not the exported data:
  `{"pollingUrl":"/orchestrator/jobs/pollForJobStatus/236402?datasetId=<scratch dataset>&dataflowId=<scratch dataflow>","status":"Preparing file"}`.
- **Notes**: **gotcha** — confirms this is genuinely async/job-based (as
  the method-naming rationale already predicted from the operationId
  alone, now confirmed live). Because this method is wired to
  `client.download(..., dest=...)`, calling it as currently implemented
  writes this JSON "job started" response straight to `dest` — **not** the
  actual exported data. A caller needs to poll `pollingUrl` (an
  Orchestrator endpoint — outside this client's spec coverage,) until the job completes, then fetch the
  real output separately. This client has no method for that polling step.
  Worth a follow-up task; not fixed in this pass (P7 is observation-only).
 

### etl_export_zip_csv

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>`
- **Result**: gotcha — same shape as `etl_export_dataset_with_job`:
  `200` with `{"pollingUrl":"/orchestrator/jobs/pollForJobStatus/236403?...","status":"Preparing file"}`
  written to `dest`, not real ZIP bytes.
- **Notes**: same async/job-based gotcha as `etl_export_dataset_with_job`.

### etl_export_zip_parquet

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>`
- **Result**: gotcha — same shape again:
  `200` with `{"pollingUrl":"/orchestrator/jobs/pollForJobStatus/236404?...","status":"Preparing file"}`.
- **Notes**: same async/job-based gotcha; all three of `v3`/`v4`/`v5`
  behave identically at this "kick off the job" stage — they presumably
  differ only in what the eventual polled/downloaded artifact looks like
  (single JSON vs. CSV zip vs. Parquet zip), which this pass didn't reach.

### create_file_for_etl_export

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>, export_csv=True`
- **Result**: error — `404 Not Found` on
  `GET /dataset/private/etlExport/createFile/{dataset_id}`, with and
  without the `Accept: */*` retry.
- **Notes**: **settles the earlier "investigated and left as-is"
  ambiguity** — this route is under `/dataset/private/*`, matching the
  now-well-established pattern (confirmed across 8+ other `/private/*`
  routes this phase) of being unreachable through the public API gateway
  entirely. This doesn't resolve what the endpoint *would* return (the
  original binary-vs-void ambiguity), but it does mean the question is
  moot for this client: the route can't be reached at all, regardless of
  response type.
- **T06 update**: retested with the Bearer credential — still `404`. See
  the T06 section below.

### download_imported_file

- **Params used**: `dataflow_id=<scratch dataflow>, dataset_id=<scratch dataset>,
  file_name="test.csv"` (guessed — no real imported file existed to name)
- **Result**: role-blocked — `403 Forbidden`.
- **Notes**: reaches the auth/role check before validating `file_name`
  existence (no 400/404), consistent with the role-gated pattern seen
  elsewhere. Not retested with a real file name since none exists in this
  scratch dataset.
- **T05 update (Bearer, elevated credential)**: past the role gate this
  time — `500 Server Error`, body: `"No import directory found for
  datasetId <scratch dataset> under path /reportnet3-data/input/<scratch dataset>"`. Confirms
  this really was a plain Custodian/Steward role gate (like
  `list_imported_files`, not like `historic_releases`) — with the role
  satisfied, the failure becomes a clear, specific "nothing was ever
  imported here" server message rather than an opaque 403. Arguably a
  `404` would be more appropriate than `500` for "no such import
  directory," but that's the live API's behavior, not a client bug.

## dremio.py / release_receipts.py

### dremio.run

- **Params used**: none
- **Result**: error — `404 Not Found` on `GET /dremio/run`.
- **Notes**: not a `/private/*` path, so this is a different failure mode
  from the private-route pattern documented elsewhere in this file. The
  swagger tag for this endpoint (`test-dremio-controller-impl`) suggests
  it's a test/diagnostic hook — plausibly only wired up in non-production
  environments, or removed from production since the spec snapshot was
  taken. Not investigated further (would need access to a non-production
  Reportnet instance to confirm either theory) — flagged as `error`
  pending that.

### get_release_receipt_by_dataflow_id

- **Params used**: `dataflow_id=<scratch dataflow>`
- **Result**: confirmed — `200`, returns `ReleaseReceiptVO(dataflowId=None, id=None, note='')`.
- **Notes**: matches spec/docstring; the mostly-`None`/empty result is
  expected since no release has ever been made for this scratch dataflow,
  not a sign of a problem.

## Phase 8 — mutating endpoints

Same scratch dataflow `<scratch dataflow>` / dataset `<scratch dataset>`, Bearer JWT credential
(T05's Custodian/Steward token) unless noted otherwise. 
### P8-01: the 8 `/private/*` mutating methods

All 8 methods whose route contains `/private/` — identified during Phase 8
planning by cross-referencing operationIds against `spec/api-docs.json` —
called with real scratch IDs (`dataset_id=<scratch dataset>`, `dataflow_id=<scratch dataflow>`,
`table_schema_id="<object id>"`, the same TestTable schema ID
used throughout Phase 7) and a Bearer credential.

| Method | Path | Result |
| --- | --- | --- |
| `clear_old_locks` | `POST /dataset/private/clearOldLocks` | `404` |
| `create_empty_tables` | `POST /dataset/private/createEmptyTables` | `404` |
| `create_empty_tables_v2` | `POST /dataset/private/{tableSchemaId}/createEmptyTablesV2` | `404` |
| `delete_big_data_root_folder` | `DELETE /dataset/private/bigDataFolder/dataflow/{dataflowId}` | `404` |
| `delete_locks_to_delete_process` | `DELETE /dataset/private/deleteLocksToDeleteProcess/{datasetId}` | `404` |
| `import_big_file_data_private` | `POST /dataset/private/importFileData/{datasetId}` | `404` |
| `update_statistics` | `PUT /dataset/private/updateStatistics/{id}` | `404` |
| `roll_back_snapshot_record` | `PUT /snapshot/private/rollBackSnapshotRecord/{jobId}` | `404` |

- **Result**: confirmed — all 8 `404 Not Found`, identical error shape to
  the 9 read-only `/private/*` routes from T06
  (`{"status":404,"error":"Not Found","message":"No message available",...}`).
- **Notes**: extends T06's finding from `GET`-only to all three mutating
  verbs (`POST`/`PUT`/`DELETE`) — consistent with the root cause found
  there (Zuul's `zuul.ignoredPatterns=/**/private/**` strips any matching
  path before dispatch, regardless of verb). Combined with T06's 9, that's
  **17 confirmed-unreachable `/private/*` methods** across this client's
  full surface. `create_empty_tables_v2` initially returned a `500`
  ("URL was not normalized") on a first pass where `table_schema_id` was
  an empty string from an unset local `.env` var, producing a double
  slash (`/dataset/private//createEmptyTablesV2`) — not a finding about
  the endpoint, just a malformed test call; re-run with a real schema ID
  gave the same `404` as the other 7. Raw responses saved to
  a local capture (not included in this repository).

### P8-02: duplicate_field_value_exists

- **Params used**: `dataset_id=<scratch dataset>, table_schema_id="<object id>",
  field_vo=FieldVO(idFieldSchema="<object id>", value="p8_02_probe_value")`
  (same TestTable/TEXT-field IDs used throughout Phase 7/P8-01), called
  twice in a row with the identical value.
- **Result**: confirmed — `200`, `false` both times.
- **Notes**: `false` is expected — this scratch dataset has no data rows
  (per Phase 7), so no value can already exist to collide with. Despite
  the `POST` verb this behaves as a pure read-style check: two identical
  calls returned the identical answer with no observable side effect
  (schema/table state unchanged), consistent with a probe endpoint that
  looks up existing values via a `POST` body just because a `FieldVO`
  payload can't fit in query params, not because it mutates anything.
  Raw responses saved to
  a local capture (not included in this repository).

### P8-03: release_receipts.py full CRUD lifecycle

- **Params used**: `dataflow_id=<scratch dataflow>` throughout; `create_release_receipt`
  with `ReleaseReceiptVO(dataflowId=<scratch dataflow>, note="P8-03 test note")`;
  `update_release_receipt` with the same `id` returned by create and
  `note="P8-03 test note UPDATED"`.
- **Result**: confirmed, full round trip, no gotchas:
  1. `get` before: `{dataflowId: null, id: null, note: ''}` (baseline,
     matches Phase 7).
  2. `create`: `200`, returns `{dataflowId: <scratch dataflow>, id: 198, note: "P8-03
     test note"}` — a real server-assigned `id`.
  3. `get` after create: identical to the create response — confirms
     read-after-write consistency.
  4. `update` (same `id`, new note): `200`, returns the updated note.
  5. `get` after update: reflects the update.
  6. `delete`: `200`, no body.
  7. `get` after delete: back to the exact baseline from step 1
     (`dataflowId: null, id: null, note: ''`) — delete cleanly removes the
     record with no leftover state.
- **Notes**: first fully-confirmed mutating CRUD lifecycle in this client
  — every step matched spec/docstring exactly, and the dataflow was left
  in the same state it started in. No reference note needed (no
  spec-vs-live surprise). Raw responses saved to
  a local capture (not included in this repository).

### P8-04a: update_manually_editable_by_dataset_id

- **Params used**: `dataset_id=<scratch dataset>`, toggled `manually_editable=True`
  then `False`; bracketed each toggle with
  `datasets.get_available_for_manual_editing_tables(dataset_id=<scratch dataset>)` to
  observe a real side effect, not just a `200`.
- **Result**: confirmed — `set_true` → `200`/`None`; the follow-up `get`
  then returned `["idTableSchema='<object id>'
  nameTableSchema='TestTable'"]` (Phase 7 had this as `[]`); `set_false` →
  `200`/`None`; the follow-up `get` returned `[]` again.
- **Notes**: clean, fully reversible round trip with an observable,
  verifiable side effect in both directions. No gotcha. Raw responses
  saved to a local capture (not included in this repository).

### P8-04b: import_field_schemas

- **Params used**: got the real file format first via
  `export_field_schemas(dataset_schema_id="<object id>",
  dataset_id=<scratch dataset>, table_schema_id="<object id>")` (with
  the `Accept: */*` workaround) rather than guessing — returned:
  ```
  Field name,PK,Required,ReadOnly,Field description,Field type,Extra information
  TestField,,false,false,,TEXT,
  ```
  Then called `import_field_schemas` twice against the **same**
  `table_schema_id` (no new table): once with the field renamed to
  `TestFieldP804Renamed`, `replace=True`; once more with the original CSV
  (`TestField`), `replace=True`, to restore the name.
- **Result**: gotcha —
  1. Baseline: field `id="<object id>"`, `name="TestField"`.
  2. Import (renamed, `replace=True`): `200`. An immediate
     `find_data_schema_by_dataset_id` read straight after returned
     `fieldSchema: []` for `TestTable` — briefly no fields at all, not
     the renamed field.
  3. Import (original name, `replace=True`): `200`.
  4. A `find_data_schema_by_dataset_id` read after that (and a second one
     run ~30s later, in a fresh call) both show the field back with
     `name="TestField"` — but **`id="<object id>"`, a
     different ID than the original**. Stable across both reads, not a
     transient value.
- **Notes**: **gotcha, repeated in `docs/reference/`** — `import_field_schemas`
  with `replace=True` is a destroy-and-recreate operation, not an
  in-place field update: the field name and type came back identical to
  before, but the underlying `id` changed permanently, even though the
  net edit (rename then rename back) was a no-op from the caller's
  perspective. Any code or live-testing note anywhere in this repo that
  hardcodes the old field ID `<object id>` for dataset
  `<scratch dataset>`/table `<object id>` is now stale — the current
  id is `<object id>`. Separately, whether the intermediate
  `fieldSchema: []` read (step 2) reflects genuine async/eventual-
  consistency processing lag, or the renamed-field import silently not
  taking effect at all, is **not resolved** — confirming it either way
  would need another `import_field_schemas` call with a poll-and-wait
  before reverting, which weighs another permanent field-ID churn on the
  shared scratch schema against closing out an already-understood-enough
  finding. Left open rather than spending another live mutation on it
  without checking first. Raw responses saved to
  a local capture (not included in this repository).

### P8-05: populate_data_from_data_collection

- **Params used**: `dataflow_id=<scratch dataflow>`, `job_id` omitted.
- **Credential**: Bearer (T05's Custodian/Steward user on dataflow `<scratch dataflow>`,
  per the Phase 8 intro; raw response is under a local capture (not included in this repository)).
  Note the backend swallows `EEAException` and still returns `200`, so the
  `200` below is not evidence the call did anything (T08 audit, follow-up #9).
- **Result**: gotcha — `200`, `None`. Planning had predicted this would
  likely fail (role-block or a "not applicable to this dataset type" 400)
  given the working theory that dataset `<scratch dataset>` is a Design dataset with
  no real EU dataset/Data Collection relationship configured under
  dataflow `<scratch dataflow>`. It didn't fail.
- **Notes**: **gotcha, repeated in `docs/reference/`** — the call returns `200`/no
  body regardless of whether there's anything real to populate, and this
  client has no corresponding read endpoint to check what (if anything)
  actually happened as a result, nor any way to undo it. Can't
  distinguish "genuinely populated an EU dataset" from "silently
  enqueued/no-op'd a job that touched nothing" from the response alone —
  investigation dead-ends here without a way to inspect EU dataset state
  independently. Doesn't move the T07 dataset-type theory forward either
  way, since a clean 200 doesn't confirm or rule out dataset `<scratch dataset>`
  being a Design dataset. Raw response saved to
  a local capture (not included in this repository).

### P8-06: delete_snapshot and export_historic_releases_csv

- **Params used**: `delete_snapshot(id_dataset=<scratch dataset>, id_snapshot=999999999)`
  (fake — no snapshot-creation endpoint exists anywhere in this client's
  spec coverage, so no real snapshot ID is obtainable through it);
  `export_historic_releases_csv(dataflow_id=<scratch dataflow>, dataset_id=<scratch dataset>,
  dest=...)`.
- **Result**:
  - `delete_snapshot`: **not role-blocked** — `500 Internal Server Error`,
    `"No class <package>.dataset.persistence.metabase.domain.Snapshot entity
    with id 999999999 exists!"`. It reached real entity-lookup logic past
    auth/role/dataset-type checks; the 500 is just "no such snapshot",
    an artifact of the fake ID, not a role gate.
  - `export_historic_releases_csv`: `403 Forbidden` — same shape as its
    two siblings.
- **Notes**: **directly relevant to T07, updates the theory** —
  `delete_snapshot`'s docstring declares the identical dataset-type set as
  `historic_releases`/`download_historic_releases_csv`
  (Reporting dataset / Data collection / Test dataset / Reference dataset
  — no "Design dataset" in any of the three), yet it got *past* the
  role/type check for the same dataset (`<scratch dataset>`) and credential that
  403-blocks the other two. That rules out "this credential lacks some
  snapshot-related role for dataset `<scratch dataset>` in general" — if
  dataset-type gating were the uniform cause, `delete_snapshot` should
  have 403'd too, and it didn't.
  `export_historic_releases_csv` joining `historic_releases`/
  `download_historic_releases_csv` at `403` (now 3-for-3) while
  `delete_snapshot` clears the same gate narrows this to something
  specific to the **"historic releases" sub-feature** (all three blocked
  methods share that name), not a blanket "snapshot ops don't work on
  this dataset" story. A plausible refined read: "historic releases" is a
  formal release-to-collection concept that may genuinely not exist for a
  Design dataset (no data collection to have released *from*), while
  ad-hoc snapshot management (create/delete during schema design) is a
  separate feature that does apply to Design datasets — consistent with,
  but not independent proof of, `<scratch dataset>` being a Design dataset. Still no
  direct "get dataset type" confirmation available in this client. Raw
  responses saved to a local capture (not included in this repository).

### P8-07: import_file_data, import_big_file_data, etl_import_dataset, etl_import_dataset_dl

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>,
  table_schema_id="<object id>"` throughout.
  `import_file_data`/`import_big_file_data` each got a one-row CSV
  (`TestField` header, one data row) matching `TestTable`'s single field.
  `etl_import_dataset` got an `ETLDatasetVO` JSON body targeting
  `TestTable`/`TestField` directly (no file). `etl_import_dataset_dl` got
  a deliberately-fake `file_path_in_s3` (no real S3/data-lake path exists
  for this scratch dataflow).
- **Result**:
  - `import_file_data`: `200`/`None`. Confirmed *actually* landed — a
    follow-up `get_import_related_statistics` showed
    `numberOfRecordsImported: 1` (was `None` in Phase 7) and
    `list_imported_files` listed the uploaded `TestTable.csv`.
  - `import_big_file_data`: `200`, but returns
    `{"jobId": <job id>, "pollingUrl":
    "/orchestrator/jobs/pollForJobStatus/<job id>?..."}` — async/job-based,
    same shape as the `etl_export_*` v3/v4/v5 family. The uploaded
    `TestTable_v2.csv` appeared immediately in `list_imported_files`, but
    `numberOfRecordsImported` was still `1` (not `2`) at last check — the
    upload/save step completes synchronously but the actual data-merge
    happens in the async job, not yet observed to finish.
  - `etl_import_dataset`: `403 Forbidden`.
  - `etl_import_dataset_dl`: `403 Forbidden`.
- **Notes**: **gotcha, repeated in `docs/reference/`, two distinct findings**:
  1. **The whole ETL family is blocked for this Bearer credential.**
     Both ETL imports here `403`'d despite their docstrings listing
     `Design dataset: CUSTODIAN, STEWARD, ...` as an allowed role — the
     same role set that let plain `import_file_data`/`import_big_file_data`
     succeed moments earlier, same dataset, same credential. Chasing this
     down further (not part of this sub-task, but caught while verifying
     `import_file_data`'s result): `etl_export_dataset` and
     `etl_export_dataset_v2` — both confirmed working with a `200` and
     real JSON data under `ApiKey` in Phase 7 — now also `403` under this
     Bearer credential. So the pattern is credential-class-specific, not
     role-declaration-specific: `ApiKey` (Reporter-level) can use the ETL
     family; this Bearer JWT (Custodian/Steward) cannot, on this same
     dataset, even though the docstring's declared role table says
     Custodian/Steward should be enough. Most likely explanation: ETL
     access is gated by something outside the documented per-endpoint
     RBAC roles entirely (e.g. a separate "integration enabled" concept —
     `import_file_data`/`import_big_file_data` both take an
     `integration_id` param, suggesting ETL/FME access is its own
     subsystem), not simply a matter of holding a high enough role.
  2. **`check_import_process`'s lock appears stuck.** Right after
     `import_file_data`'s `200`, `check_import_process` returned
     `importInProgress=True`. Still `True` after ~6 minutes and a second
     import (`import_big_file_data`) triggered in between — even though
     the first import's completion was independently confirmed via
     `get_import_related_statistics` (`numberOfRecordsImported: 1`) well
     before the lock cleared. Either this lock reflects something with a
     much longer TTL than actual import completion, or it's a real
     backend bug; a caller polling `check_import_process` alone to know
     when it's safe to proceed would have looped past the point where the
     import was actually done and queryable. Not fully resolved — no
     observation continued long enough to see it clear. Raw responses
     saved to a local capture (not included in this repository).

### P8-08: update_geometry, update_geometry_v2

- **Params used**: `dataset_id=<scratch dataset>` only (neither method takes a body or
  query params). Bearer credential (T05's Custodian/Steward).
- **Result**: both `200`/`None`.
- **Notes**: inconclusive as to effect. The scratch schema has only a
  `TEXT`-type field (no `POINT`/geometry field), so there was nothing for
  the call to act on; a clean `200` doesn't show it did anything, and no
  read endpoint was checked afterwards. No role gate hit for Bearer. An
  earlier attempt with a stale token got `401` for both (token problem,
  not an endpoint finding). Raw responses saved to
  a local capture (not included in this repository).

### P8-09 (part 1): update_attachment, delete_attachment, get_attachment against the TEXT field

- **Params used**: `dataset_id=<scratch dataset>, dataflow_id=<scratch dataflow>,
  field_id="<object id>"` (current `TestField` id, re-fetched
  via `find_data_schema_by_dataset_id` after P8-04b's churn; type `TEXT`),
  `field_name="TestField", table_schema_name="TestTable"`, fake
  `record_id="<object id>"` (no real record ID available),
  file `p8_09_attach.txt`. `get_attachment` went through raw
  `client.download(..., headers={"Accept": "*/*"})` per the 406 workaround.
- **Result**: all three `500 Server Error`.
- **Notes**: inconclusive, as predicted: a `TEXT` field plus a fake record
  ID gives the backend nothing valid to act on, so the 500s don't
  distinguish "wrong field type" from "no such record". No role gate hit
  (not `403`). Part 2 (full upload -> get -> update -> delete against a
  genuine `ATTACHMENT`-type field) not run: P8-04 never added such a field,
  and adding one needs another `import_field_schemas(replace=True)`, which
  recreates fields (new IDs, per P8-04b). Raw responses in
  a local capture (not included in this repository).

### P8-10: convert_*_tables, create_empty_tables_v3, restore_prefilled_tables, create_public_files

- **Params used**: `dataflow_id=<scratch dataflow>, dataset_id=<scratch dataset>,
  table_schema_id(s)=TestTable "<object id>"`; Bearer
  credential. `create_public_files` got `dataflow_id=<scratch dataflow>` only.
- **Result**:
  - `convert_iceberg_to_parquet_tables`: `200`/`None`.
  - `convert_parquet_to_iceberg_tables`: `200`/`None`.
  - `create_empty_tables_v3`: `403 Forbidden`.
  - `restore_prefilled_tables`: `200`/`None`.
  - `create_public_files`: `403 Forbidden`.
- **Notes**: the two `convert_*` calls did NOT error informatively as
  expected, even though `is_iceberg_table_created` is `False`
  and `get_iceberg_tables` is `[]` both before and after. A clean `200`
  here shouldn't be read as a conversion happening (likely an async job
  or a no-op with nothing to convert; no job ID returned, not
  investigated). After the calls, `get_import_related_statistics` still
  showed `numberOfRecordsImported: 1` for TestTable, so
  `restore_prefilled_tables` did not visibly remove the P8-07 import
  (it restores *prefilled* data, which this table doesn't have; effect
  unconfirmed). The two `403`s are role/feature-gate blocks for this
  Bearer credential; not diagnosed further (`create_public_files` is
  dataflow-wide and likely Admin/Steward-only or needs a non-Design
  dataflow). Raw responses in a local capture (not included in this repository).

## T09 — dataflow listings (live, 2026-10-02, `ApiKey`)

`client.dataflow.dataflows(kind, page_size=5, page_num=0)` and
`dataflow_datasets(<scratch dataflow>)`, read-only, default `Accept: application/json`,
no request body:

- All four kinds return `200` (no 406, no body needed). `reporting` returned
  `totalRecords=39`/`filteredRecords=39` and 5 items for `pageSize=5`, so the
  paging params are honoured and `totalRecords` is the full count. `reference`,
  `business` and `citizen_science` returned 0 for this key.
- The `ApiKey` is **not** limited to its own dataflow for listing: it listed
  39 dataflows, consistent with a reading of the backend source that an
  ApiKey signs in as the key's owner. Listing does not imply access to each
  dataflow's contents.
- Item keys include `id`, `name`, `type`, `status`, `designDatasets`,
  `reportingDatasets`, `dataCollections`, `euDatasets`, `testDatasets`,
  `referenceDatasets`, `representatives`, `contributors`.
- `dataflow_datasets(<scratch dataflow>)` succeeded; 1 design dataset, other lists empty.
  (Supports T07's theory that the scratch dataflow only has a Design dataset.)

## P10-13 — error body shapes (live, 2026-10-26, read-only, `GET /dataflow/v1/{id}`)

Both `ApiKey` and a refreshed Bearer, scratch dataflow `<scratch dataflow>`:

- Real dataflow: `200`.
- Nonexistent id (`1`, `100`, `999999999`): `500`, body
  `{"status":500,"error":"Internal Server Error","message":"status 500 reading
  DataFlowControllerZuul#accessReferenceEntity(EntityClassEnum,Long)",...}`. Not an
  empty `200` and not a `404`; same for both credentials.
- Existing dataflow without access (`1986`): `403`, `message` "Forbidden".
- Garbage `ApiKey`: `500`, body is two JSON objects concatenated with no
  separator (`message` "401 UNAUTHORIZED", then "No message available"), so
  `json.loads` fails; read the first object only. A garbage key, not a real
  revoked one.
- Garbage Bearer: `401`, `message` "401 UNAUTHORIZED".
- The empty-`200` swallow described for `dataflow_datasets` was not reproduced on
  this route.

## P10-14 — credential shapes and dead-credential bodies (live, 2026-10-26, read-only)

- A refreshed ApiKey and a refreshed Bearer token are **both bare 36-character
  UUIDs**; neither is a JWT, so the shape cannot tell them apart. A Bearer token
  needs an explicit `scheme="Bearer"` (or the `"Bearer "` prefix). The JWT
  detection in `easy.connect` therefore does not recognise real Bearer tokens.
- `check_access` against `<scratch dataflow>`: ApiKey alive and reachable; Bearer
  (`scheme="Bearer"`) alive and reachable; dataflow `1` "not found" (500
  `accessReferenceEntity`); dataflow `1986` "no access" (403).
- A dead/garbage ApiKey on the listing route (`POST /dataflow/getDataflows`) is a
  `500` with two glued JSON objects, message "Access is denied" (not "401
  UNAUTHORIZED", which `GET /dataflow/v1/{id}` gives). A real Bearer token sent
  with the `ApiKey` scheme gets the identical answer, so the two causes cannot be
  told apart from the body.

## P10-08 / P10-03 — sandbox pass (2026-10-27)

Host `sandbox-api.reportnet.europa.eu` (also `test-api.reportnet.europa.eu`)
resolves and answers from inside the internal network (unauthenticated `GET
/dataflow/v1/<scratch dataflow>` -> 401 JSON). Dataflow `<sandbox dataflow>` has two Design datasets:
`<sandbox dataset>` (three empty tables) and `<sandbox dataset>` "Codelist" (one table `Boolean`, one
required primary-key TEXT field `Boolean`). Both the ApiKey and the Bearer reach
`list_datasets` and `check_access`.

- ETL export paging: `offset` is a 0-based row offset. Raw
  probes on the 4-row table `[true, '', false, true]`: no params -> all 4 rows;
  `limit=10&offset=1` -> rows 1-3; `limit=2` with `offset` 1/2/3 -> rows 1-2, 2-3,
  3; `limit=1` with `offset` 1..4 -> rows 1, 2, 3, none; `limit=2` with `offset`
  0/2/4 -> rows 0-1, 2-3, none. `totalRecords` was present and correct (4) on every
  unfiltered call. `read_tables` with the corrected loop: all rows, once each, at
  every page size tried (25 rows at 7/10/25/100).
- Import: `import_file` (Bearer, `replace=True`) of `Boolean.csv` worked, job
  FINISHED in ~21 s; `numberOfRecordsImported` = the number of rows in the file
  (4, then 25).
- Validation: see (reads work with the Bearer and 403 with the
  ApiKey; no failures produced; export file never appeared; no
  `datasetRunningStatus` in the Design dataset listing entry).
- The sandbox's dead/rejected-credential answers are the same as production's
  (500 `401 UNAUTHORIZED` / "Access is denied" for ApiKey, 401 for Bearer).

## P10-03 — data-lake (bigData) dataflows use `*DL` routes (live, 2026-10-27, sandbox)

Dataflow `<sandbox dataflow>` answers `bigData: true`. For its datasets (`<sandbox dataset>`, `<sandbox dataset>`):

- `GET /validation/listGroupValidations/{id}` -> `200`, `errors: []`,
  `totalErrors: 0`, `totalRecords: 0` (the empty old per-dataset database), even
  though the UI shows failures. Same for `listValidations`. Passing the UI's
  empty-string filters changes nothing.
- `GET /validation/listGroupValidationsDL/{id}?asc=0&shortCode=&fieldValueFilter=&
  headers=&levelErrorsFilter=&pageNum=0&pageSize=10&tableFilter=&typeEntitiesFilter=`
  (the URL the browser sent, supplied by the user) and the same call without the
  empty filters -> the real result. `<sandbox dataset>`: `{"shortCode":"FC4","typeEntity":
  "FIELD","levelError":"ERROR","numberOfRecords":"1","message":"The value must not
  be missing or empty"}`, `TU3` (TABLE, 2 records, "...unique within table"),
  `totalErrors 3`, `totalRecords 25`, `totalFilteredRecords 2`. `<sandbox dataset>`: `TB7` and
  `TB8` "Mandatory table has no records", `totalRecords 1`. `idRule` is `null`.
- The stored results survived a later `replace=True` import: the table then held 25
  distinct non-empty rows, yet the results still showed the earlier 4-row run's
  empty and duplicate key.
- Other `DL` routes in the UI config (`MasterDataLakes` branch):
  `/dataset/TableValueDatasetDL/{id}` (table data), `/dataset/{id}/exportDatasetFileDL`,
  `/dataset/exportFileDL`, `/dataset/{id}/downloadFileDL`. The validations export
  (`/validation/export/{id}` then `/validation/downloadFile/{id}`) has no `DL`
  variant in the UI config and gave no file on three tries for `<sandbox dataset>`.

## P10-19 — validation job endings (live, 2026-11-22, sandbox, Bearer)

`easy.validate_and_wait` on a data-lake dataset of `<sandbox dataflow>`, with the
validation job cancelled from a second thread through `PUT
/orchestrator/jobs/cancelJob/{jobId}?dataflowId=&datasetId=` (a route for dataflow
custodians, stewards and lead reporters; backend branch `MasterOneVersion`):

- The job is `QUEUED` for about the first 4 s, then `IN_PROGRESS`. A cancel at
  4.6 s answered `200` but did not stick: the job went on to `FINISHED` and
  `validate_and_wait` returned the normal result. Cancelling a queued job is not
  reliable.
- Cancel at about 22 s with `jobShouldFail=true`: the poll answered `FAILED` (no
  `info`) and `validate_and_wait` raised `JobError` with `status="FAILED"` at once.
- Cancel at about 22 s with `jobInfo=ERROR_VALIDATION_FAILURE`: `CANCELED_BY_ADMIN`
  with `info` "Validation failed due to system error. Please contact the Service
  Desk for support."; `JobError.status`/`.info` carried both.
- Both endings stayed as they were (re-polled minutes later). A new validation
  started 5 s after each cancel was accepted, so no lock was left behind.
- A refused start never becomes a job to poll: `addValidationJob` stores the job
  as `REFUSED`, sends the refused notification and answers `423`
  (`LockedError`), as seen on 2026-11-21.
- Not produced: a plain `CANCELED` (only the backend's hourly cleanup of stuck
  runs sets it) and `FINISHED` with an `info` note.
