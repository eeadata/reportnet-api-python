"""Hand-kept live-tested notes shown in docs/reference/ (see generate_docs.py).

Keyed by method/function name; use "<page>.<name>" (e.g. "jobs.wait_for_job") to
target one page when the same name appears on several. Each entry is a list of
`(note, source)` pairs. Every fact here must already be written down in
docs/live_testing_notes.md; keep each
note to 1-2 sentences and keep "unverified" wherever the source says so. The
/private/* methods are not on the client and are deliberately not listed.
"""

from __future__ import annotations

Caveat = tuple[str, str]

_LIVE = "live testing notes"
_NOTES = "docs/live_testing_notes.md"

_ACCEPT_406 = (
    "The default `Accept: application/json` gets a 406 from this route (Spring content "
    "negotiation against the controller's `produces`); `Accept: */*` gets through. "
    "The generated method now sends a matching `Accept` itself (mocked tests only, not "
    "re-tested live).",
    _LIVE,
)
_ETL_GATE = (
    "The ETL family is gated separately from the documented roles: a Bearer Custodian/Steward "
    "credential got 403 on the scratch dataset even though the docstring lists those roles, "
    "while an ApiKey worked for the exports. Do not assume a Bearer role level predicts ETL "
    "access; unverified per credential.",
    _LIVE,
)
_JOB_VARIANT = (
    "Async job variant: returns job metadata (`pollingUrl`), never the data. Use the matching "
    "`*_to_file` helper or `jobs.wait_for_job` to wait for it.",
    _LIVE,
)
CAVEATS: dict[str, list[Caveat]] = {
    # --- dataset_schema
    "get_simple_schema": [
        (
            "`dataflow_id` is typed optional (as in the spec) but the backend requires it: "
            "without it the call fails with 400 `Required Long parameter 'dataflowId' is not "
            "present`.",
            _LIVE,
        )
    ],
    "get_table_schemas_ids": [
        (
            "`dataflow_id` is typed optional (as in the spec) but the backend requires it: "
            "omitting it gets the same 400 as `get_simple_schema`.",
            _LIVE,
        )
    ],
    "export_field_schemas": [
        _ACCEPT_406,
        (
            "`dataset_id` and `table_schema_id` are both typed optional, but the backend needs "
            "both together (one alone gives 400 or 500); with both it returns CSV text.",
            _LIVE,
        ),
    ],
    "export_field_schemas_from_dataset": [
        _ACCEPT_406,
        (
            "Typed to return `str`, but the real body is a binary ZIP containing a per-table "
            "CSV, so decoding it as text is lossy. Not yet migrated to the `dest=` download "
            "treatment.",
            _LIVE,
        ),
    ],
    "import_field_schemas": [
        (
            "With `replace=True` fields are destroyed and recreated even for a no-op change, so "
            "field ids change; re-fetch ids via `find_data_schema_by_dataset_id` afterwards. A "
            "read right after a renaming import came back with no fields (lag vs failure "
            "unresolved).",
            _LIVE,
        )
    ],
    "export_dataflow_schemas_zip": [
        (
            "Hidden endpoint (absent from the spec), hand-written. Needs `DATAFLOW_CUSTODIAN` or "
            "`DATAFLOW_STEWARD`: an ApiKey (Reporter-level) gets 403, a Bearer JWT of such a "
            "user returns the ZIP. Sends `Accept: */*`.",
            _LIVE,
        )
    ],
    # --- datasets
    "check_import_process": [
        (
            "The lock is unreliable as a 'safe to proceed' signal: it stayed "
            "`importInProgress=True` for 6+ minutes after an import whose completion was "
            "confirmed elsewhere. Prefer `get_import_related_statistics()` or "
            "`import_file_and_wait()`. It also said `importInProgress=False` while an import "
            "job was running, so it is unreliable in both directions.",
            _LIVE,
        )
    ],
    "import_big_file_data": [
        (
            "Job-based: returns `{jobId, pollingUrl}` and the import is not done yet; wait with "
            "`wait_for_job` or use `import_file_and_wait`. The uploaded file name must match a "
            "table name (e.g. `TestTable.csv`), otherwise the job is `CANCELED` with an `info` "
            "explaining it.",
            _LIVE,
        ),
        (
            "A second import to the same dataset while one is running gets `423` "
            "(`LockedError`); its body message says 'unknown error' but the cause is another "
            "job still QUEUED or IN_PROGRESS for the dataset (the RN3 UI says so). Wait for "
            "the first job before starting the next.",
            _LIVE,
        ),
    ],
    "import_file_data": [
        (
            "Returns immediately with `None`; the import was confirmed to complete in the "
            "background. Check completion via `get_import_related_statistics()`, not "
            "`check_import_process()`.",
            _LIVE,
        )
    ],
    "import_file_and_wait": [
        (
            "Live-checked with both Bearer and ApiKey (job FINISHED in ~20-25s). Not verified "
            "live: the `big_file=False` path and `replace=True`; on the small-file path an "
            "import that changes neither statistics value reads as a timeout.",
            "",
        )
    ],
    "get_import_related_statistics": [
        (
            "`numberOfRecordsImported` looks like the rows of the last import, not a table "
            "total (it stayed 1 after a second one-row import); `lastImportDate` does change "
            "per import.",
            _LIVE,
        )
    ],
    "list_imported_files": [
        (
            "Needs Custodian/Steward: an ApiKey got 403, a Bearer Custodian/Steward credential "
            "returned `[]` on the scratch dataset.",
            _NOTES,
        )
    ],
    "download_imported_file": [
        (
            "ApiKey got 403; a Bearer Custodian/Steward credential passed the role gate and "
            "got a 500 'no import directory' on the scratch dataset (no data to download).",
            _LIVE,
        )
    ],
    "generate_import_presigned_url": [
        (
            "A GET that is not side-effect-free: every call allocates a server-side `jobId` "
            "and S3 object path, even if the URL is never used.",
            _LIVE,
        )
    ],
    "get_attachment": [
        _ACCEPT_406,
        (
            "Past the 406, the live test ended in a 500 (no real attachment data on the "
            "scratch dataset), so the success path is inconclusive.",
            _NOTES,
        ),
    ],
    "etl_export_dataset": [
        _ETL_GATE,
        (
            "Synchronous export (worked live with an ApiKey). `offset` is a 0-based "
            "row offset, not a page number (live-tested on production and the sandbox, "
            "2026-10-27: step by `limit` from 0).",
            _LIVE,
        ),
    ],
    "etl_export_dataset_v2": [
        _ETL_GATE,
        (
            "Synchronous export (worked live with an ApiKey). `offset` is a 0-based "
            "row offset, not a page number (live-tested on production and the sandbox, "
            "2026-10-27: step by `limit` from 0).",
            _LIVE,
        ),
    ],
    "etl_import_dataset": [_ETL_GATE],
    "etl_import_dataset_dl": [_ETL_GATE],
    "etl_export_dataset_with_job": [
        _JOB_VARIANT,
        (
            "Only the job start was tested live; the finished job's download was not.",
            "",
        ),
    ],
    "etl_export_zip_csv": [
        _JOB_VARIANT,
        (
            "The v4 CSV export ran end to end with an ApiKey (~75s, valid ZIP); a Bearer "
            "Custodian/Steward credential got 403.",
            "",
        ),
    ],
    "etl_export_zip_parquet": [
        _JOB_VARIANT,
        (
            "The v5 Parquet export ran end to end with an ApiKey (~31s, valid ZIP).",
            "",
        ),
    ],
    "export_zip_csv_to_file": [("Live-checked end to end with an ApiKey (Bearer got 403).", "")],
    "export_zip_parquet_to_file": [("Live-checked end to end with an ApiKey.", "")],
    "export_dataset_with_job_to_file": [
        ("Only the job start (v3) was tested live; the full flow is unverified.", "")
    ],
    "delete_import_table": [
        (
            "Hidden legacy alias of `delete_table_data`. Mocked tests only; not tested live "
            "because it is destructive.",
            _LIVE,
        )
    ],
    "delete_dataset_data": [
        (
            "Irreversible; deliberately not run against production. Not verified live.",
            _LIVE,
        )
    ],
    # --- dataset_snapshot / eu_datasets
    "historic_releases": [
        (
            "Got 403 even with a Bearer Custodian/Steward credential on the scratch dataset, "
            "so it is not just a role gate. That dataset is confirmed to be a Design dataset; "
            "the suspected (unconfirmed) cause is that historic releases do not apply to them.",
            _LIVE,
        )
    ],
    "download_historic_releases_csv": [
        (
            "Same 403 as `historic_releases` with an elevated credential on a Design dataset "
            "(suspected exclusion, unconfirmed). A not-ready export answers 200 with plain "
            "text, which lands in `dest`; check the file.",
            _LIVE,
        )
    ],
    "export_historic_releases_csv": [
        (
            "Also 403 with the elevated credential on the scratch (Design) dataset (same "
            "suspected exclusion, unconfirmed). Returns a URL string, not CSV.",
            _LIVE,
        )
    ],
    "delete_snapshot": [
        (
            "Passed the role/type check on the scratch dataset (reached a 500 'no such snapshot "
            "entity'), unlike the historic-releases methods.",
            _LIVE,
        )
    ],
    "populate_data_from_data_collection": [
        (
            "A clean 200 with no body is not proof that anything meaningful (or safe) happened: "
            "there is no read endpoint to check, and on a dataflow with a real Data Collection it "
            "would plausibly move real data into an EU dataset, with no undo through this client.",
            _LIVE,
        )
    ],
    # --- table/dataset export (notification-driven)
    "start_table_export": [
        (
            "Needs a Bearer token (an ApiKey gets 403). Live: with the default `big_data=True` "
            "(the `exportFileDL` route the Reportnet UI calls) the export worked; the plain route "
            "was accepted but never produced a file. Filters and non-csv formats are unverified.",
            "",
        )
    ],
    "start_dataset_export": [
        (
            "Live: `zip csv` worked with `big_data=True` (file `<dataset name>.zip`); plain `csv` "
            "produced no file within 40s. Bearer only.",
            "",
        )
    ],
    "fetch_export_file": [
        (
            "An unknown or not-yet-generated file gives an empty 200, so this returns False; the "
            "`DL` download does not delete the file, so a stale one can be served.",
            "",
        )
    ],
    "export_table_to_file": [
        (
            "Live-checked with a Bearer token on the scratch dataset: a CSV with all rows in 0.6s "
            "(`big_data=True`). Short-lived Bearer tokens can expire during a long poll.",
            "",
        )
    ],
    "export_dataset_to_file": [
        (
            "Live-checked with `mime_type='zip csv'` (ZIP with one CSV per table); plain `csv` did "
            "not work.",
            "",
        )
    ],
    # --- reference dataset
    "set_updatable": [
        (
            "Mocked tests only; not run live (it writes, and `updatable=false` generates files).",
            "",
        )
    ],
    # --- representative
    "representatives": [
        (
            "Live-checked (ApiKey and Bearer) on a dataflow with no representatives (empty "
            "list) and with Bearer on a sandbox dataflow with one: the item shape matches the "
            "list above, and `leadReporters` items are `{id, email, representativeId, invalid}` "
            "(email addresses: personal data). `easy.list_representatives` adds the country.",
            "",
        )
    ],
    "data_providers": [
        (
            "Live-checked: group 1 returned 33 member countries with `id` (the `providerId`), "
            "`code` and `label`.",
            "",
        )
    ],
    "data_provider_groups": [
        (
            "Live-checked: two groups, 1 'Member countries' and 2 'All countries'.",
            "",
        )
    ],
    "data_provider": [("Live-checked with ApiKey and Bearer.", "")],
    **{
        name: [
            (
                "Mocked tests only; not run live. Written from the `develop` source; needs a "
                "custodian's, steward's or steward support's login token (no ApiKey branch).",
                _LIVE,
            )
        ]
        for name in (
            "export_lead_reporters_file",
            "import_lead_reporters_file",
            "create_representative",
            "create_lead_reporter",
            "validate_lead_reporters",
        )
    },
    # --- easy / jobs
    "easy.connect": [
        (
            "A dead or revoked ApiKey shows up as a 500 '401 UNAUTHORIZED' on any call; check "
            "with `list_datasets`. An ApiKey only works for its own dataflow (403 elsewhere).",
            "",
        )
    ],
    "easy.read_table": [
        (
            "Uses the synchronous ETL export, whose access is credential-dependent.",
            _LIVE,
        )
    ],
    "easy.read_tables": [
        (
            "Uses the synchronous ETL export, whose access is credential-dependent.",
            _LIVE,
        ),
        (
            "On a data-lake dataflow (`bigData: true`) the export answers 200 with 0 rows "
            "although rows exist; an all-empty result looks up `bigData` and warns only "
            "for a lake (or when the lookup fails); use `export_to_file()` there.",
            "",
        ),
    ],
    "easy.export_to_file": [
        (
            "Live-checked with an ApiKey for CSV and Parquet; a Bearer Custodian/Steward "
            "credential got 403 on the v4 export.",
            "",
        )
    ],
    "easy.export_table": [
        (
            "Live-checked with a Bearer token (CSV, 0.6s); an ApiKey gets 403. Leaves a "
            "notification in the user's Reportnet UI.",
            "",
        )
    ],
    "easy.import_file": [
        (
            "The file name must match a table name. Live-checked with Bearer and ApiKey.",
            "",
        )
    ],
    "jobs.wait_for_job": [
        (
            "Mocked tests, plus live runs of the v4/v5 exports and `import_big_file_data` jobs; "
            "whether v3 `downloadUrl` behaves like v4's is unverified. The `develop` backend has "
            "no `pollForJobStatus` (only the `MasterDataLakes` branch was read).",
            "; jobs.py module docstring",
        )
    ],
    "wait_for_job": [
        (
            "Waits for an Orchestrator job (e.g. from `import_big_file_data` or the "
            "`etl_export` v3/v4/v5 starters) to reach FINISHED; raises `JobError` otherwise.",
            "",
        )
    ],
}
