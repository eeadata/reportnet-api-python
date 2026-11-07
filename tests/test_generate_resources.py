"""Unit tests for scripts/generate_resources.py helpers."""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_resources.py"
_SPEC = importlib.util.spec_from_file_location("generate_resources", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
gen = importlib.util.module_from_spec(_SPEC)
sys.modules["generate_resources"] = gen  # dataclasses resolve annotations via sys.modules
_SPEC.loader.exec_module(gen)


@pytest.mark.parametrize(
    ("produces", "expected"),
    [
        ([], None),
        (["*/*"], None),
        (["application/json"], None),
        (["application/json", "application/xml"], None),
        (["application/octet-stream"], "application/octet-stream, */*;q=0.1"),
        (["text/csv", "application/zip"], "text/csv, application/zip, */*;q=0.1"),
    ],
)
def test_accept_for(produces: list[str], expected: str | None) -> None:
    assert gen.accept_for(produces) == expected


def _op(produces: list[str]) -> dict:
    return {
        "operationId": "fooUsingGET",
        "tags": ["Datasets : Dataset Manager"],
        "produces": produces,
        "responses": {"200": {"schema": {"type": "string"}}},
    }


def test_octet_stream_operation_emits_accept_header() -> None:
    op = gen.parse_operation("get", "/foo", _op(["application/octet-stream"]))
    body = gen.render_body(op, is_async=False)
    assert 'headers={"Accept": "application/octet-stream, */*;q=0.1"}' in body


def test_wildcard_operation_emits_no_headers() -> None:
    op = gen.parse_operation("get", "/foo", _op(["*/*"]))
    assert "headers=" not in gen.render_body(op, is_async=False)


def test_private_paths_are_not_generated() -> None:
    ops = gen.load_operations()
    urls = [op.path for group in ops.values() for op in group]
    assert urls
    assert not [u for u in urls if "/private/" in u]


def test_private_operation_count_matches_expected(capsys: pytest.CaptureFixture[str]) -> None:
    gen.load_operations()
    assert "warning: skipped" not in capsys.readouterr().err
