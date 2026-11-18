<img src="assets/logo.svg" alt="reportnet-api for Python" width="360">

# Reportnet API Python client

A Python library for the [EEA Reportnet 3](https://reportnet.europa.eu/) REST API: typed,
sync and async, with notebook helpers that return pandas DataFrames.

> **Not an official EEA product.** An independent set of utilities for accessing the
> Reportnet 3 API, not developed or supported by the Reportnet team. For help with
> Reportnet itself, use the Reportnet helpdesk.

## Start here

- **Try it without a credential:** `from reportnet_api.easy import demo_client` gives a
  client that answers from built-in fictional data.
- **[Which credential do I need?](credentials.md)** ApiKey or Bearer, and what each can do.
- **[Function reference](reference/index.md):** every function, its arguments, the Reportnet
  rights it needs and live-tested caveats.
- **[Glossary](glossary.md):** dataflow, dataset, provider, job and the other terms.
- **[Using it from FME](fme.md).**
- **[Live testing notes](live_testing_notes.md):** what the real service did.
- [Source code, notebooks and issues](https://github.com/eeadata/reportnet-api-python)

## Install

```
pip install "reportnet-api[pandas]"
```

Python 3.11 or newer. Without pandas: `pip install reportnet-api`.

## Three ways to use it

| You are | Use |
|---|---|
| a programmer | `ReportnetClient` / `AsyncReportnetClient`, one namespace per Reportnet area |
| a scientist in a notebook | `reportnet_api.easy`: `connect_interactive()`, `read_table()`, ... |
| an FME user | `easy.read_records()` and `import_file()` from a PythonCaller, or the `reportnet` command |

Search everything by keyword with `reportnet_api.find("export")`.
