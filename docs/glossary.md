# Glossary

Plain-language meanings of the words this client and Reportnet 3 use. Ids are always
integers; the most common mistake is passing a dataflow id where a dataset id belongs.

- **Dataflow**: the whole reporting obligation (one project). Has an id (`dataflow_id`),
  a name and a set of datasets. An ApiKey is created for one dataflow and works only there.
- **Dataset**: one set of tables inside a dataflow, with its own id (`dataset_id`). Not the
  same number as the dataflow id.
- **Kind**: which sort of dataset it is, as returned by `easy.list_datasets`: `design`,
  `reporting`, `data collection`, `eu`, `reference` or `test`. Some operations apply to
  certain kinds only.
- **Table schema / table**: a table's definition (name and fields) inside a dataset;
  `easy.list_tables` lists them and `read_table(..., table_name=...)` picks one.
- **Provider** (data provider): the reporting party, usually a country, that owns one
  reporting dataset (`provider_id`). `easy.list_providers` lists the known ones.
- **Representative**: a provider assigned to a dataflow, with its lead reporters.
  `easy.list_representatives` lists them with the country code and name; lead reporter
  emails only with `include_contacts=True`.
- **Lead reporter**: the person (by email) who reports for a provider.
- **Custodian / Steward / Reporter**: roles on a dataflow. A login (Bearer) token carries
  the user's roles; an ApiKey carries Reporter-level access only.
- **ApiKey / Bearer**: the two credential kinds; see the
  [reference index](reference/index.md#apikey-or-bearer). `easy.check_access` tells which
  you hold and whether it is alive.
- **Data lake dataflow** (`bigData`): a dataflow whose data is stored in the data lake.
  Some plain reads answer empty there; see `easy.is_data_lake` and the notes on
  `read_tables`.
- **Job**: a long server task (an import or an export) that you start and then poll. The
  waiting helpers hide this; `reportnet_api.jobs` and `Job.from_polling_url` give direct
  control. A job keeps running on the server if you stop waiting.
- **Handle**: `find_dataflow(...)` returns a `Dataflow` and `flow.dataset(...)` a `Dataset`
  that remember their ids, so you do not repeat them (`docs/reference/handles.md`).
- **Validation**: Reportnet's checks of the data against the schema's rules; `easy`
  has summary, error list and export helpers.

Look anything up by keyword with `reportnet_api.find("word")`, or print `easy.guide()`.
