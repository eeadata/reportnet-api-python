# Changelog

All notable changes are listed here. The project follows [Semantic Versioning](https://semver.org/):
while the major version is `0`, a **minor** release (0.x.0) may change the API, and a patch
release (0.x.y) only fixes bugs. Breaking changes are called out below.

## 0.1.0 (unreleased)

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
