"""Interactive local dev tool for exercising reportnet_api against a real API.

Not part of the published package (see pyproject.toml's
[tool.hatch.build.targets.wheel] packages = ["reportnet_api"] - this
directory is never included in the wheel) and not installed by
`pip install reportnet-api` (streamlit lives in its own dependency group,
not [project.dependencies]).

Run:
    uv run --group ui streamlit run tools/streamlit_app.py

Generic by construction: it introspects each resource class's methods via
`inspect`/`typing.get_type_hints` rather than hardcoding a form per method,
so it stays in sync automatically as reportnet_api/resources/*.py changes.
"""

from __future__ import annotations

import inspect
import os
import tempfile
import types
import typing
from pathlib import Path

import streamlit as st
from pydantic import BaseModel
from streamlit.runtime.uploaded_file_manager import UploadedFile

from reportnet_api import ReportnetAPIError, ReportnetClient

RESOURCE_ATTRS = [
    "datasets",
    "dataset_schema",
    "dataset_snapshot",
    "eu_datasets",
    "release_receipts",
]

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "reportnet_ui_downloads"

# Parameter names that recur across many endpoints (a parameter
# scan) - if a method's parameter matches one of these by name, its widget is
# prefilled from the corresponding .env var. Anything more call-specific
# (delimiter, file_name, body-model params, ...) intentionally has no default.
COMMON_ID_ENV_VARS = {
    "dataset_id": "REPORTNET_DATASET_ID",
    "dataflow_id": "REPORTNET_DATAFLOW_ID",
    "provider_id": "REPORTNET_PROVIDER_ID",
    "table_schema_id": "REPORTNET_TABLE_SCHEMA_ID",
    "dataset_schema_id": "REPORTNET_DATASET_SCHEMA_ID",
    "job_id": "REPORTNET_JOB_ID",
    "field_id": "REPORTNET_FIELD_ID",
    "record_id": "REPORTNET_RECORD_ID",
    "integration_id": "REPORTNET_INTEGRATION_ID",
}


def unwrap_optional(hint: object) -> tuple[object, bool]:
    """Return (inner_type, is_optional) for a `T | None` hint, else (hint, False)."""
    if typing.get_origin(hint) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        is_optional = len(args) != len(typing.get_args(hint))
        if len(args) == 1:
            return args[0], is_optional
        return hint, is_optional
    return hint, False


def list_methods(resource: object) -> list[str]:
    return sorted(
        name
        for name, _ in inspect.getmembers(resource, predicate=inspect.ismethod)
        if not name.startswith("_")
    )


def render_param_widget(key_prefix: str, name: str, inner: object, required: bool) -> object:
    label = name if required else f"{name} (optional)"
    key = f"{key_prefix}.{name}"

    if name == "file":
        return st.file_uploader(label, key=key)
    if name == "dest":
        default = str(DOWNLOAD_DIR / f"{key_prefix}.out")
        return st.text_input(f"{label} — save to path", value=default, key=key)
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return st.text_area(f"{label} (JSON body for {inner.__name__})", value="{}", key=key)
    if typing.get_origin(inner) is list:
        return st.text_input(f"{label} (comma-separated)", key=key)
    default = os.environ.get(COMMON_ID_ENV_VARS.get(name, ""), "")
    return st.text_input(label, value=default, key=key)


def convert_param(name: str, raw: object, inner: object, required: bool) -> tuple[bool, object]:
    """Returns (include_in_kwargs, value)."""
    if name == "file":
        if raw is None:
            if required:
                raise ValueError("file is required")
            return False, None
        if not isinstance(raw, UploadedFile):
            raise TypeError(f"file: expected an uploaded file, got {type(raw).__name__}")
        tmp_path = Path(tempfile.gettempdir()) / raw.name
        tmp_path.write_bytes(raw.getvalue())
        return True, tmp_path

    if name == "dest":
        Path(str(raw)).parent.mkdir(parents=True, exist_ok=True)
        return True, raw

    text = str(raw or "").strip()
    if not text:
        if required:
            raise ValueError(f"{name} is required")
        return False, None

    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return True, inner.model_validate_json(text)
    if typing.get_origin(inner) is list:
        return True, [item.strip() for item in text.split(",") if item.strip()]
    if inner is bool:
        return True, text.lower() in ("1", "true", "yes", "y")
    if inner is int:
        return True, int(text)
    if inner is float:
        return True, float(text)
    return True, text


def render_result(result: object, dest_path: str | None) -> None:
    if dest_path is not None:
        st.success(f"Saved to {dest_path}")
        data = Path(dest_path).read_bytes()
        st.download_button("Download file", data=data, file_name=Path(dest_path).name)
        return
    if result is None:
        st.success("Call succeeded (no content)")
    elif isinstance(result, BaseModel):
        st.json(result.model_dump(mode="json"))
    elif isinstance(result, list) and result and isinstance(result[0], BaseModel):
        st.json([item.model_dump(mode="json") for item in result])
    elif isinstance(result, (dict, list)):
        st.json(result)
    else:
        st.write(result)


st.set_page_config(page_title="reportnet_api dev tester", page_icon="📡", layout="wide")
st.title("reportnet_api — local dev tester")
st.caption(
    "Calls the real client against a real API. Not part of the published package "
    "(see tools/streamlit_app.py docstring)."
)

with st.sidebar:
    st.header("Connection")
    base_url = st.text_input(
        "Base URL", value=os.environ.get("REPORTNET_BASE_URL") or "https://api.reportnet.europa.eu"
    )
    raw_token = st.text_input(
        "API key / token", value=os.environ.get("REPORTNET_API_KEY", ""), type="password"
    )
    # Scheme is inferred from the token itself rather than a separate field:
    # a "Bearer " prefix means a JWT (Bearer auth), anything else is treated
    # as a Reportnet dataflow-scoped API key (ApiKey auth).
    # ReportnetClient prepends the scheme itself, so the prefix is stripped
    # here to avoid ending up with "Authorization: Bearer Bearer <token>".
    if raw_token.lower().startswith("bearer "):
        token_scheme = "Bearer"  # noqa: S105 - an auth scheme name, not a secret
        token = raw_token[len("bearer ") :]
    else:
        token_scheme = "ApiKey"  # noqa: S105 - an auth scheme name, not a secret
        token = raw_token
    st.caption(f"Detected scheme: **{token_scheme}**")

if not token:
    st.info("Enter an API key/token in the sidebar to get started.")
    st.stop()

client = ReportnetClient(base_url=base_url, token=token, token_scheme=token_scheme)

col1, col2 = st.columns(2)
with col1:
    resource_name = st.selectbox("Resource", RESOURCE_ATTRS)
resource = getattr(client, resource_name)
with col2:
    method_name = st.selectbox("Method", list_methods(resource), key=f"method.{resource_name}")

method = getattr(resource, method_name)

# Surface any role/permission requirement documented on the method itself
# (e.g. dataset_schema_ext.py's "Requires `DATAFLOW_CUSTODIAN` or
# `DATAFLOW_STEWARD` on the dataflow.") so a 403 isn't a surprise before the
# call is even made. Read from the docstring rather than a hardcoded map so
# it stays in sync automatically as new "Requires ..." lines are added.
requires_line = next(
    (
        line.strip()
        for line in (method.__doc__ or "").splitlines()
        if line.strip().startswith("Requires ")
    ),
    None,
)
if requires_line:
    msg = requires_line
    if token_scheme == "ApiKey":  # noqa: S105 - a scheme name, not a secret
        msg += " Your detected scheme is ApiKey, which is Reporter-level and will not satisfy this."
    st.warning(msg)

st.divider()

hints = typing.get_type_hints(method)
signature = inspect.signature(method)
key_prefix = f"{resource_name}.{method_name}"

param_specs = []
for name, param in signature.parameters.items():
    hint = hints.get(name, str)
    inner, _ = unwrap_optional(hint)
    required = param.default is inspect.Parameter.empty
    param_specs.append((name, inner, required))

if not param_specs:
    st.caption("No parameters.")

widget_values = {}
for name, inner, required in param_specs:
    widget_values[name] = render_param_widget(key_prefix, name, inner, required)

# Methods named like a read are run directly; anything else may write or delete data
# on the dataflow, so the button stays disabled until the user confirms.
_READ_PREFIXES = ("get_", "list_", "find_", "check_", "is_", "has_", "export_", "download_")
may_write = not method_name.startswith(_READ_PREFIXES)
confirmed = True
if may_write:
    confirmed = st.checkbox(
        "I understand this call may write or delete data on the dataflow",
        key=f"confirm.{resource_name}.{method_name}",
    )

if st.button("Run", type="primary", disabled=not confirmed):
    kwargs: dict[str, object] = {}
    dest_value: str | None = None
    try:
        for name, inner, required in param_specs:
            include, value = convert_param(name, widget_values[name], inner, required)
            if include:
                kwargs[name] = value
                if name == "dest":
                    dest_value = str(value)
    except (ValueError, Exception) as exc:  # surface any parameter error inline
        st.error(f"Invalid parameters: {exc}")
    else:
        try:
            result = method(**kwargs)
        except ReportnetAPIError as exc:
            st.error(f"{exc.status_code} {type(exc).__name__} — {exc.response_body}")
        except Exception as exc:  # surface any call error inline
            st.exception(exc)
        else:
            render_result(result, dest_value)
