# Removed `/private/*` endpoints

These 17 operations are in `spec/api-docs.json` but are **not generated** into
the client. Every one of them 404s on production (`api.reportnet.europa.eu`),
with both `ApiKey` and Bearer credentials. Two independent causes
(see `docs/live_testing_notes.md`, sections T06 and P8-01):

1. The API gateway (Zuul) is configured with `zuul.ignoredPatterns=/**/private/**`,
   which strips any such path before routing or auth.
2. For 9 of them, the Java controller methods no longer exist in the backend
   (the Reportnet 3 backend source, `dataset-service`), so the spec is stale.

The filter is `EXCLUDED_PATH_SEGMENT` in `scripts/generate_resources.py`.
To restore them, remove that filter and run `scripts/regen_resources.sh`.

| Resource | Method name | HTTP | Path |
|---|---|---|---|
| `datasets` | `clear_old_locks` | POST | `/dataset/private/clearOldLocks` |
| `datasets` | `create_empty_tables` | POST | `/dataset/private/createEmptyTables` |
| `datasets` | `create_empty_tables_v2` | POST | `/dataset/private/{tableSchemaId}/createEmptyTablesV2` |
| `datasets` | `create_file_for_etl_export` | GET | `/dataset/private/etlExport/createFile/{datasetId}` |
| `datasets` | `datasets_updated_after_release` | GET | `/dataset/private/datasetsUpdated` |
| `datasets` | `delete_big_data_root_folder` | DELETE | `/dataset/private/bigDataFolder/dataflow/{dataflowId}` |
| `datasets` | `delete_locks_to_delete_process` | DELETE | `/dataset/private/deleteLocksToDeleteProcess/{datasetId}` |
| `datasets` | `find_tasks_by_process_id_and_status_in` | GET | `/dataset/private/findTasksByProcessIdAndStatusIn/{processId}` |
| `datasets` | `import_big_file_data_private` | POST | `/dataset/private/importFileData/{datasetId}` |
| `datasets` | `update_statistics` | PUT | `/dataset/private/updateStatistics/{id}` |
| `dataset_schema` | `get_field_name` | GET | `/dataschema/private/getFieldName` |
| `dataset_schema` | `get_field_schema` | GET | `/dataschema/private/getFieldSchemaVo` |
| `dataset_schema` | `get_table_schema_name` | GET | `/dataschema/private/getTableSchemName` |
| `dataset_schema` | `get_table_schema_vo` | GET | `/dataschema/private/getTableSchemaVo` |
| `dataset_snapshot` | `get_latest_historic_release_snapshot` | GET | `/snapshot/private/latestReleaseSnapshot` |
| `dataset_snapshot` | `get_snapshot_by_dataset_id` | GET | `/snapshot/private/getSnapshotByDatasetId` |
| `dataset_snapshot` | `roll_back_snapshot_record` | PUT | `/snapshot/private/rollBackSnapshotRecord/{jobId}` |

## A `/private/*` route outside the spec: `isBigDataflow`

`GET /dataflow/private/v1/{dataflowId}/isBigDataflow` (returns a boolean) is not
in `spec/api-docs.json` (the Dataflow tag isn't in our snapshot), so it was
never generated. Checked 2026-10-23 (P10-05):

- Backend: `DataflowControllerImpl` has the method on the `MasterDataLakes`
  branch (line ~650) and not on `develop`.
- Live, read-only, dataflow `<scratch dataflow>`: `404` for both a Bearer and an ApiKey
  credential, body `{"status":404,"error":"Not Found","message":"No message
  available"}` — the same shape as the 17 above, consistent with the gateway's
  `zuul.ignoredPatterns` rule stripping `/**/private/**` before routing.

So it is unreachable through the public gateway and no client method exists
for it. Treat any `/private/` path the same way.
