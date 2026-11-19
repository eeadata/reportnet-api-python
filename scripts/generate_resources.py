"""Generate reportnet_api/resources/<tag>.py from spec/api-docs.json paths.

Parses every operation in the swagger spec, groups them by tag, and emits
one sync + one async resource class per tag file. Each generated method:
typed params (path/query/body), typed return (from the `200` response
schema where a matching Pydantic model exists), and a docstring pulled
from the operation's `summary`/`description`.

Run via scripts/regen_resources.sh; do not hand-edit the output files in
reportnet_api/resources/ — see the README.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "spec" / "api-docs.json"
RESOURCES_DIR = REPO_ROOT / "reportnet_api" / "resources"

# Non-model schema names that exist in `definitions` but represent an
# opaque/binary payload rather than real structured data.
OPAQUE_REF_MODELS = {"StreamingResponseBody"}

# Method names (post operationId->snake_case) that are real file downloads,
# per SPEC.md §3.6. Not derived automatically: the swagger
# schema types for these are unreliable (e.g. "string"/"object"/no-schema)
# and don't reliably signal "this is a binary download" on their own, so
# this is a deliberate, explicit allowlist rather than a schema-based guess.
DOWNLOAD_METHOD_NAMES = {
    "download_historic_releases_csv",
    "etl_export_dataset",
    "etl_export_dataset_v2",
    # getAttachment declares produces: application/octet-stream and a
    # {"type": "string", "format": "byte"} schema — unambiguous binary.
    "get_attachment",
    # downloadImportedFile declares produces: */* with an opaque
    # {"type": "object"} schema, the same unreliable-schema pattern as the
    # other entries above; its name says "download" so treat it the same way.
    "download_imported_file",
}

# Query params that spec/api-docs.json declares optional (`required: false`)
# but the backend actually rejects when missing. Live-confirmed (production)
# for etl_export_dataset, etl_export_dataset_v2 and
# get_attachment: omitting dataflowId gets `400 Required Long parameter
# 'dataflowId' is not present`. The v3/v4/v5 job-based variants share the
# identical spec declaration and controller family but were NOT tested
# (they start server-side jobs). Regenerating from the
# spec can't fix this (the spec itself is wrong), hence an explicit override.
REQUIRED_PARAM_OVERRIDES: dict[str, set[str]] = {
    "etl_export_dataset": {"dataflowId"},
    "etl_export_dataset_v2": {"dataflowId"},
    "etl_export_dataset_with_job": {"dataflowId"},
    "etl_export_zip_csv": {"dataflowId"},
    "etl_export_zip_parquet": {"dataflowId"},
    "get_attachment": {"dataflowId"},
    # Backend source: required server-side.
    "etl_import_dataset": {"dataflowId"},
    "generate_import_presigned_url": {"dataflowId"},
    "historic_releases": {"datasetId"},
}

# Optional preparation-dataset code, present in the backend source (`33fe062`)
# but absent from the spec snapshot. Maps method name
# -> wire name; the controllers disagree (`code` vs `preparationCode`). Appended
# after the spec's own params, so no existing positional argument shifts.
PREPARATION_CODE_PARAMS: dict[str, str] = {
    "import_big_file_data": "code",
    "import_file_data": "code",
    "etl_export_dataset": "code",
    "etl_export_dataset_v2": "code",
    "etl_export_dataset_with_job": "code",
    "etl_export_zip_csv": "code",
    "etl_export_zip_parquet": "code",
    "etl_import_dataset_dl": "code",
    "generate_import_presigned_url": "code",
    "delete_dataset_data": "preparationCode",
    "delete_table_data": "preparationCode",
    "is_iceberg_table_created": "preparationCode",
    "get_iceberg_tables": "preparationCode",
}
_PREPARATION_CODE_NOTE = (
    "`preparation_code` (sent as `{wire}`; not in the swagger snapshot, read from the\n"
    "backend source) selects a preparation dataset instead of the regular one."
)

# Extra docstring text appended to specific methods where the spec's own
# description is silent on a behaviour the backend shows.
# `etl_export_dataset[_v2]`'s `offset`: the backend source on `develop`
# (RecordRepositoryImpl: offsetAux = limit*offset - limit) reads as
# a 1-based page number, but the deployed builds (production and the sandbox,
# live 2026-10-27) treat it as a plain 0-based ROW offset.
_ETL_PAGING_NOTE = (
    "Paging: live-tested (production and sandbox), `offset` is a 0-based ROW\n"
    "offset, not a page number: `offset=0` (or omitted) starts at the first\n"
    "row, then step by `limit` (`offset=limit`, `2*limit`, ...); an offset at\n"
    "or past the total returns no records. Sending `offset=1` skips the first\n"
    "row and overlaps the next page. (The backend source on `develop` reads as\n"
    "a 1-based page number, `limit * offset - limit`; the deployed builds do\n"
    "not follow it.) Keep the same `limit` on every call; `limit` defaults to\n"
    "10000 server-side. Do not use FME's 'new' paging mode on this backend."
)
# `replaceData` is declared in spec/api-docs.json
# for `etlImportDataset` and confirmed against the production-line backend
# (`@RequestParam replaceData`, default false). An earlier "no such param"
# finding came from a stale checkout.
_ETL_IMPORT_REPLACE_NOTE = (
    "Note: `replace_data` is a real backend parameter (default false): when\n"
    "true the existing dataset data is replaced by the import. Confirmed in\n"
    "the production-line backend source; not live-tested (destructive)."
)
# these return a download URL / job map, not file
# content, so they are plain request methods (not in DOWNLOAD_METHOD_NAMES).
_HISTORIC_EXPORT_NOTE = (
    "Returns the download URL string (not CSV content): the backend starts an\n"
    "async export and answers with\n"
    "`/snapshot/downloadHistoricReleases/{id}?dataflowId=..&fileName=..&processId=..`.\n"
    "Pass its `fileName`/`processId` to `download_historic_releases_csv`."
)
_JOB_EXPORT_NOTE = (
    "Async job-based export: returns job metadata, e.g. `{'pollingUrl': ...,\n"
    "'status': 'Preparing file'}`, never the exported data. Poll `pollingUrl`\n"
    "(Orchestrator, outside this client's spec coverage) until the job\n"
    "completes; this client has no polling helper."
)
_HISTORIC_DOWNLOAD_NOTE = (
    "Caution: if the export identified by `process_id` is still in progress\n"
    'or was canceled, the backend answers 200 with a plain-text "not ready"\n'
    "message instead of CSV, and that text is what lands in `dest`. Check the\n"
    "file content before trusting it."
)
DOCSTRING_NOTES: dict[str, str] = {
    "export_historic_releases_csv": _HISTORIC_EXPORT_NOTE,
    "download_historic_releases_csv": _HISTORIC_DOWNLOAD_NOTE,
    "etl_export_dataset_with_job": _JOB_EXPORT_NOTE,
    "etl_export_zip_csv": _JOB_EXPORT_NOTE,
    "etl_export_zip_parquet": _JOB_EXPORT_NOTE,
    "etl_import_dataset": _ETL_IMPORT_REPLACE_NOTE,
    "etl_export_dataset": _ETL_PAGING_NOTE,
    "etl_export_dataset_v2": _ETL_PAGING_NOTE,
}

# tag (as it appears in api-docs.json) -> (module stub, class stub)
TAG_TO_MODULE = {
    "Dataset Schema : Dataset Schema Manager": ("dataset_schema", "DatasetSchema"),
    "Datasets : Dataset Manager": ("datasets", "Datasets"),
    "Dataset Snapshot : Dataset Snapshot Manager": ("dataset_snapshot", "DatasetSnapshot"),
    "EU datasets : EU Dataset Manager": ("eu_datasets", "EuDatasets"),
    "release-receipt-controller-impl": ("release_receipts", "ReleaseReceipts"),
}

# Tags deliberately not generated. `test-dremio-controller-impl` is a test
# endpoint (`GET /dremio/run`) that 404s on production and has no controller
# in the audited backend.
EXCLUDED_TAGS = {"test-dremio-controller-impl"}

# Operations whose path contains this segment are not generated: the API
# gateway strips `/**/private/**` before routing, so they 404 unconditionally.
# Names are listed in docs/removed_private_endpoints.md.
EXCLUDED_PATH_SEGMENT = "/private/"

# Expected count of operations dropped by the filter above. A spec refresh
# that changes it prints a warning so the drift is reviewed, and
# docs/removed_private_endpoints.md updated.
EXPECTED_PRIVATE_OPERATIONS = 17

SWAGGER_TO_PY = {"string": "str", "integer": "int", "boolean": "bool", "number": "float"}

_OPERATION_ID_SUFFIX_RE = re.compile(r"Using(GET|POST|PUT|DELETE|PATCH)$")
_CAMEL_BOUNDARY_1_RE = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2_RE = re.compile(r"([a-z0-9])([A-Z])")


def to_snake_case(name: str) -> str:
    s1 = _CAMEL_BOUNDARY_1_RE.sub(r"\1_\2", name)
    s2 = _CAMEL_BOUNDARY_2_RE.sub(r"\1_\2", s1)
    return s2.lower()


def method_name_for(operation_id: str) -> str:
    return to_snake_case(_OPERATION_ID_SUFFIX_RE.sub("", operation_id))


def ref_model_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


@dataclass
class Param:
    wire_name: str
    py_name: str
    py_type: str
    required: bool
    location: str  # path | query | formData


@dataclass
class BodyParam:
    py_name: str
    py_type: str
    is_model: bool


@dataclass
class Operation:
    method: str
    path: str
    method_name: str
    summary: str
    description: str
    params: list[Param] = field(default_factory=list)
    body: BodyParam | None = None
    file_param: Param | None = None
    return_type: str = "None"
    return_kind: str = "none"  # none | model | model_list | json | text | raw | download
    return_model: str | None = None
    is_download: bool = False
    # Explicit `Accept` value, set only when the controller's `produces` is
    # neither JSON nor `*/*` (Spring 406s the client's JSON default otherwise).
    accept: str | None = None


def swagger_param_type(p: dict) -> str:
    if p.get("type") == "array":
        item_type = SWAGGER_TO_PY.get(p.get("items", {}).get("type"), "str")
        return f"list[{item_type}]"
    if p.get("type") == "file":
        return "str"
    return SWAGGER_TO_PY.get(p.get("type"), "str")


def accept_for(produces: list[str]) -> str | None:
    """`Accept` header to send for an operation's declared `produces`.

    None means the client's default (`application/json`) is already fine:
    either nothing is declared, JSON is accepted, or `*/*` matches anything.

    Otherwise the declared types come first, with a low-priority `*/*`
    fallback: live evidence conflicts on whether a bare
    `application/octet-stream` is accepted (it 406'd on `/dataschema/export`,
    reportedly not on `export_field_schemas`), while `*/*` always passes.
    """
    if not produces or "application/json" in produces or "*/*" in produces:
        return None
    return ", ".join([*produces, "*/*;q=0.1"])


def parse_operation(method: str, path: str, op: dict) -> Operation:
    method_name = method_name_for(op["operationId"])
    operation = Operation(
        method=method.upper(),
        path=path,
        method_name=method_name,
        summary=op.get("summary", ""),
        description=op.get("description", ""),
    )

    operation.accept = accept_for(op.get("produces", []))

    for p in op.get("parameters", []):
        location = p["in"]
        if location == "body":
            schema = p.get("schema", {})
            ref = schema.get("$ref")
            if ref:
                operation.body = BodyParam(
                    py_name=to_snake_case(p["name"]), py_type=ref_model_name(ref), is_model=True
                )
            else:
                py_type = SWAGGER_TO_PY.get(schema.get("type"), "str")
                operation.body = BodyParam(
                    py_name=to_snake_case(p["name"]), py_type=py_type, is_model=False
                )
            continue

        param = Param(
            wire_name=p["name"],
            py_name=to_snake_case(p["name"]),
            py_type=swagger_param_type(p),
            required=bool(p.get("required"))
            or location == "path"
            or p["name"] in REQUIRED_PARAM_OVERRIDES.get(method_name, ()),
            location=location,
        )
        if location == "formData" and p.get("type") == "file":
            operation.file_param = param
        else:
            operation.params.append(param)

    if method_name in PREPARATION_CODE_PARAMS:
        wire = PREPARATION_CODE_PARAMS[method_name]
        operation.params.append(
            Param(
                wire_name=wire,
                py_name="preparation_code",
                py_type="str",
                required=False,
                location="query",
            )
        )

    r200 = op.get("responses", {}).get("200")
    if r200 is None:
        operation.return_kind, operation.return_type = "none", "None"
    else:
        schema = r200.get("schema")
        if schema is None:
            operation.return_kind, operation.return_type = "none", "None"
        elif "$ref" in schema:
            model = ref_model_name(schema["$ref"])
            if model in OPAQUE_REF_MODELS:
                operation.return_kind, operation.return_type = "raw", "httpx.Response"
            else:
                operation.return_kind, operation.return_type = "model", f"generated.{model}"
                operation.return_model = model
        elif schema.get("type") == "array":
            items = schema.get("items", {})
            if "$ref" in items:
                model = ref_model_name(items["$ref"])
                operation.return_kind = "model_list"
                operation.return_type = f"list[generated.{model}]"
                operation.return_model = model
            else:
                item_type = SWAGGER_TO_PY.get(items.get("type"), "str")
                operation.return_kind, operation.return_type = "json", f"list[{item_type}]"
        elif schema.get("type") == "string":
            operation.return_kind, operation.return_type = "text", "str"
        elif schema.get("type") == "boolean":
            operation.return_kind, operation.return_type = "json", "bool"
        elif schema.get("type") == "integer":
            operation.return_kind, operation.return_type = "json", "int"
        elif schema.get("type") == "number":
            operation.return_kind, operation.return_type = "json", "float"
        else:
            operation.return_kind, operation.return_type = "json", "dict[str, Any]"

    if method_name in DOWNLOAD_METHOD_NAMES:
        operation.is_download = True
        operation.return_kind, operation.return_type = "download", "None"
        operation.return_model = None

    return operation


def load_operations() -> dict[str, list[Operation]]:
    spec = json.loads(SPEC_PATH.read_text())
    skipped = [
        f"{method.upper()} {path}"
        for path, methods in spec["paths"].items()
        if EXCLUDED_PATH_SEGMENT in path
        for method in methods
    ]
    if len(skipped) != EXPECTED_PRIVATE_OPERATIONS:
        print(
            f"warning: skipped {len(skipped)} {EXCLUDED_PATH_SEGMENT} operations, expected "
            f"{EXPECTED_PRIVATE_OPERATIONS}; review and update "
            "docs/removed_private_endpoints.md:\n  " + "\n  ".join(skipped),
            file=sys.stderr,
        )
    by_module: dict[str, list[Operation]] = {stub: [] for stub, _ in TAG_TO_MODULE.values()}
    for path, methods in spec["paths"].items():
        if EXCLUDED_PATH_SEGMENT in path:
            continue
        for method, op in methods.items():
            tag = op["tags"][0]
            if tag in EXCLUDED_TAGS:
                continue
            module_stub, _ = TAG_TO_MODULE[tag]
            by_module[module_stub].append(parse_operation(method, path, op))
    return by_module


def render_signature(op: Operation, *, is_async: bool) -> str:
    overridden = REQUIRED_PARAM_OVERRIDES.get(op.method_name, ())
    # Spec-optional params promoted to required are keyword-only: emitting them
    # in the (alphabetical) positional slot would silently shift existing
    # positional callers' arguments onto the wrong parameters.
    kw_only = [f"{p.py_name}: {p.py_type}" for p in op.params if p.wire_name in overridden]
    required = [
        f"{p.py_name}: {p.py_type}"
        for p in op.params
        if p.required and p.wire_name not in overridden
    ]
    if op.body is not None:
        py_type = f"generated.{op.body.py_type}" if op.body.is_model else op.body.py_type
        required.append(f"{op.body.py_name}: {py_type}")
    if op.file_param is not None:
        required.append(f"{op.file_param.py_name}: str | os.PathLike[str]")
    optional = [
        f"{p.py_name}: {p.py_type} | None = None"
        for p in op.params
        if not p.required and p.wire_name not in overridden
    ]
    if op.is_download:
        required.append("dest: str | os.PathLike[str]")

    args = ["self", *required, *optional, *(["*", *kw_only] if kw_only else [])]
    args_str = ",\n        ".join(args)
    prefix = "async def" if is_async else "def"
    return f"    {prefix} {op.method_name}(\n        {args_str},\n    ) -> {op.return_type}:"


def render_docstring(op: Operation) -> str:
    text = op.description.strip() or op.summary.strip() or op.method_name
    text = text.replace('"""', "'''")
    if op.method_name in DOCSTRING_NOTES:
        text = f"{text}\n\n{DOCSTRING_NOTES[op.method_name]}"
    if op.method_name in PREPARATION_CODE_PARAMS:
        # Match the description's own continuation indent, or ruff's docstring
        # dedent would shift the description's lines instead.
        rest = [ln for ln in text.split("\n")[1:] if ln.strip()]
        pad = " " * min((len(ln) - len(ln.lstrip()) for ln in rest), default=0)
        note = "\n".join(
            pad + ln
            for ln in _PREPARATION_CODE_NOTE.format(
                wire=PREPARATION_CODE_PARAMS[op.method_name]
            ).split("\n")
        )
        text = f"{text}\n\n{note}"
    return f'        """{text}"""'


def render_body(op: Operation, *, is_async: bool) -> str:
    lines = []
    query_items = [p for p in op.params if p.location == "query"]

    if query_items:
        pairs = ", ".join(f'"{p.wire_name}": {p.py_name}' for p in query_items)
        lines.append(f"        params = {{{pairs}}}")
        lines.append("        params = {k: v for k, v in params.items() if v is not None}")
    else:
        lines.append("        params = None")

    lines.append(f"        url = {op.path_fstring()}")

    await_kw = "await " if is_async else ""

    if op.is_download:
        lines.append(
            f'        {await_kw}self._client.download("{op.method}", url, params=params, dest=dest)'
        )
        return "\n".join(lines)

    call_kwargs = ["params=params"]
    header_items: list[str] = []
    if op.accept is not None:
        header_items.append(f'"Accept": "{op.accept}"')
    assign = "" if op.return_kind == "none" else "response = "

    def finish_kwargs() -> None:
        if header_items:
            call_kwargs.append("headers={" + ", ".join(header_items) + "}")

    if op.file_param is not None:
        finish_kwargs()
        lines.append(f"        with stream_upload_file('file', {op.file_param.py_name}) as files:")
        call_kwargs.append("files=files")
        lines.append(
            f"            {assign}{await_kw}self._client.request("
            f'"{op.method}", url, {", ".join(call_kwargs)})'
        )
    else:
        if op.body is not None:
            if op.body.is_model:
                call_kwargs.append(
                    f"json={op.body.py_name}.model_dump(mode='json', exclude_none=True)"
                )
            elif op.body.py_type == "str":
                # A raw `@RequestBody String` takes the body verbatim; `json=`
                # would wrap it in quotes.
                call_kwargs.append(f"content={op.body.py_name}")
                header_items.append('"Content-Type": "text/plain"')
            else:
                call_kwargs.append(f"json={op.body.py_name}")
        finish_kwargs()
        lines.append(
            f"        {assign}{await_kw}self._client.request("
            f'"{op.method}", url, {", ".join(call_kwargs)})'
        )

    if op.return_kind == "none":
        pass  # the method simply ends (no trailing `return None`)
    elif op.return_kind == "raw":
        lines.append("        return response")
    elif op.return_kind == "model":
        lines.append(f"        return generated.{op.return_model}.model_validate(response.json())")
    elif op.return_kind == "model_list":
        lines.append(
            f"        return [generated.{op.return_model}.model_validate(item) "
            "for item in response.json()]"
        )
    elif op.return_kind == "text":
        lines.append("        return response.text")
    else:
        lines.append(f"        return cast({op.return_type}, response.json())")

    return "\n".join(lines)


def _path_fstring(self: Operation) -> str:
    path_items = [p for p in self.params if p.location == "path"]
    if not path_items:
        return f'"{self.path}"'
    result = self.path
    for p in path_items:
        result = result.replace("{" + p.wire_name + "}", "{" + p.py_name + "}")
    return f'f"{result}"'


Operation.path_fstring = _path_fstring  # type: ignore[attr-defined]


def render_method(op: Operation, *, is_async: bool) -> str:
    return "\n".join(
        [
            render_signature(op, is_async=is_async),
            render_docstring(op),
            render_body(op, is_async=is_async),
        ]
    )


def render_module(module_stub: str, class_stub: str, ops: list[Operation]) -> str:
    sync_methods = "\n\n".join(render_method(op, is_async=False) for op in ops)
    async_methods = "\n\n".join(render_method(op, is_async=True) for op in ops)

    needs_any = any(op.return_type == "dict[str, Any]" for op in ops)
    needs_cast = any(op.return_kind == "json" for op in ops)
    needs_httpx = any(op.return_kind == "raw" for op in ops)
    needs_upload = any(op.file_param is not None for op in ops)
    needs_os = needs_upload or any(op.is_download for op in ops)

    typing_imports = (
        "TYPE_CHECKING" + (", Any" if needs_any else "") + (", cast" if needs_cast else "")
    )
    extra_imports = ("import os\n" if needs_os else "") + (
        "\nimport httpx\n" if needs_httpx else ""
    )
    core_import = "from .._core import stream_upload_file\n" if needs_upload else ""

    return f"""# Generated from spec/api-docs.json by scripts/generate_resources.py.
# Do not edit by hand.

from __future__ import annotations

{extra_imports}from typing import {typing_imports}

{core_import}from ..models import generated

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


class {class_stub}Resource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

{sync_methods}


class Async{class_stub}Resource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

{async_methods}
"""


def main() -> None:
    by_module = load_operations()
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    out_paths = []
    for module_stub, class_stub in TAG_TO_MODULE.values():
        ops = sorted(by_module[module_stub], key=lambda o: o.method_name)
        out_path = RESOURCES_DIR / f"{module_stub}.py"
        out_path.write_text(render_module(module_stub, class_stub, ops))
        out_paths.append(str(out_path))
        print(f"wrote {out_path} ({len(ops)} operations)", file=sys.stderr)

    import subprocess

    # Fixed argv, our own output files; `ruff` comes from the project environment (uv run).
    subprocess.run(["ruff", "check", "--fix", *out_paths], check=True)  # noqa: S603, S607
    subprocess.run(["ruff", "format", *out_paths], check=True)  # noqa: S603, S607


if __name__ == "__main__":
    main()
