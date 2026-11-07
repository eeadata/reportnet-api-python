# Which credential do I need?

Reportnet accepts two kinds of credential. Pick by what you want to do, not by which
sounds more powerful: they are **not** interchangeable.

| You want to... | ApiKey | Bearer token |
|---|---|---|
| List dataflows and datasets, read schemas | works | works |
| Read a table into pandas (`read_table`) | works | **403** for a Custodian/Steward user |
| Export a whole dataset to a ZIP (`export_to_file`) | works | **403** for a Custodian/Steward user |
| Upload a file (`import_file`) | works | works |
| Export the dataflow's schemas as a ZIP, list imported files | **403** (needs Custodian/Steward) | works for a Custodian/Steward user |

(Observed on the live service for the cases above; a case that is not in this table has
not been checked. The table is also built into `easy.check_access()`.)

In short: **to read data, use an ApiKey; for dataflow-management calls that need a
Custodian or Steward role, use a login (Bearer) token.**

## ApiKey

- Created in the Reportnet web app: open your dataflow, choose *Settings*, then
  *Generate new API key*.
- It belongs to **one dataflow** and carries **Reporter-level** access. It gets a 403 on
  any other dataflow.
- It stays valid until you revoke or regenerate it.

## Bearer token

- It is the token of a logged-in user and carries that user's roles on each dataflow.
- It expires after a short time (minutes in our testing), so a long job may need a fresh
  one: `connect(token_provider=your_function)` calls your function whenever it needs a
  token.
- This library does **not** log you in or fetch a token for you. Get one the way your
  organisation's Reportnet access allows (ask the Reportnet helpdesk if unsure).

## Keeping the credential safe

- Never type it into a notebook cell or commit it. `connect_interactive()` asks for it
  with a hidden prompt; or set the `REPORTNET_API_KEY` environment variable and call
  `connect()`.
- A `.env` file is fine on your own machine as long as it is in `.gitignore`.
- A client's `repr` never shows the token, but anything you print yourself might.
- The credential is only sent to the host of the base URL you configured.

## Is my credential alive?

```python
from reportnet_api.easy import connect_interactive, check_access

client = connect_interactive()
check_access(client)          # read-only; add a dataflow id to test access to it
```

## Common errors

| What you see | Likely cause | What to try |
|---|---|---|
| `AuthenticationError` (401) | credential missing, expired or revoked | get a fresh one |
| `ServerError` (500) mentioning `401 UNAUTHORIZED` | a **dead or revoked ApiKey** looks like this | run `check_access(client)`; regenerate the key |
| `ForbiddenError` (403) | wrong kind of credential for the call (see the table), or no access to that dataflow | use the other kind; check the dataflow id |
| `NotFoundError` (404) or empty results | wrong id, often a dataflow id used as a dataset id | `list_datasets(client, dataflow_id)` shows both |
| `LockedError` (423) | another import or validation holds the dataset | wait for it, then retry |

Every error has `.explain()`, which prints the likely cause in plain words.
