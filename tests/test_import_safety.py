from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any, NoReturn, cast

import pandas as pd
import pytest

from reportnet_api import ReportnetAPIError, ReportnetClient, easy
from reportnet_api.jobs import JobError
from tests.helpers import api_error

Calls = list[tuple[int, dict[str, Any], str]]


def _client(
    monkeypatch: pytest.MonkeyPatch, calls: Calls | None = None
) -> tuple[ReportnetClient, Calls]:
    schema = {
        "TestTable": [
            ("Id", "NUMBER_INTEGER"),
            ("Amount", "NUMBER_DECIMAL"),
            ("Day", "DATE"),
            ("At", "DATETIME"),
            ("Note", "TEXT"),
        ],
        "Other": [("Id", "NUMBER_INTEGER")],
    }
    monkeypatch.setattr(easy, "_schema_fields", lambda c, d: schema)
    done: Calls = calls if calls is not None else []

    def fake(dataset_id: int, path: str | Path, **kw: Any) -> dict[str, Any]:
        done.append((dataset_id, kw, Path(path).read_text()))
        return {"tid": {"numberOfRecordsImported": 1}}

    # A duck-typed fake: easy only uses client.datasets.import_file_and_wait here.
    return cast(ReportnetClient, NS(datasets=NS(import_file_and_wait=fake))), done


def _csv(tmp_path: Path, text: str, name: str = "TestTable.csv") -> Path:
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return f


H = "Id,Amount,Day,At,Note"


def test_check_ok_any_delimiter_and_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    c, _ = _client(monkeypatch)
    assert easy.check_import_file(c, 1, _csv(tmp_path, H + "\n1,2,3,4,5\n")) == []
    assert (
        easy.check_import_file(c, 1, _csv(tmp_path, H.replace(",", "|") + "\n", "testtable.csv"))
        == []
    )
    assert easy.check_import_file(c, 1, _csv(tmp_path, "﻿" + H + "\r\n")) == []


def test_check_reports_partial_header_wrong_delimiter_and_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    c, _ = _client(monkeypatch)
    (msg,) = easy.check_import_file(c, 1, _csv(tmp_path, "Id,Note\n1,x\n"))
    assert "missing" in msg and "Amount" in msg
    (msg,) = easy.check_import_file(c, 1, _csv(tmp_path, H.replace(",", "|") + "\n"), delimiter=",")
    assert "does not match" in msg
    (msg,) = easy.check_import_file(c, 1, _csv(tmp_path, H + "\n", "Nope.csv"))
    assert "matches no table" in msg
    (msg,) = easy.check_import_file(c, 1, _csv(tmp_path, H + ",Zed\n"))
    assert "unknown" in msg and "Zed" in msg


def test_check_skips_non_csv_and_unreadable_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    c, _ = _client(monkeypatch)
    assert easy.check_import_file(c, 1, tmp_path / "anything.zip") == []

    def boom(*a: object) -> NoReturn:
        raise api_error(ReportnetAPIError, 500, "", "x")

    monkeypatch.setattr(easy, "_schema_fields", boom)
    assert easy.check_import_file(c, 1, _csv(tmp_path, "zzz\n")) == []


def test_import_file_blocks_bad_file_and_unconfirmed_replace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    c, calls = _client(monkeypatch)
    with pytest.raises(ValueError, match="would be rejected"):
        easy.import_file(c, 1, 1, _csv(tmp_path, "Id\n1\n"))
    assert calls == []
    good = _csv(tmp_path, H + "\n1,2,3,4,5\n")
    with pytest.raises(ValueError, match="confirm=True"):
        easy.import_file(c, 1, 1, good, replace=True)
    assert calls == []
    easy.import_file(c, 1, 1, good, replace=True, confirm=True)
    assert calls[0][1]["replace"] is True
    easy.import_file(c, 1, 1, _csv(tmp_path, "Id\n1\n"), check=False)
    assert len(calls) == 2


def test_import_file_adds_headers_hint_to_cancelled_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    c, _ = _client(monkeypatch)

    def cancel(*a: object, **k: object) -> NoReturn:
        raise JobError("Job CANCELED: The uploaded files do not contain any records.")

    monkeypatch.setattr(c.datasets, "import_file_and_wait", cancel)
    with pytest.raises(JobError, match="wrong headers"):
        easy.import_file(c, 1, 1, _csv(tmp_path, H + "\n"))


def test_import_dataframe_writes_full_header_in_schema_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c, calls = _client(monkeypatch)
    df = pd.DataFrame(
        {
            "Note": ["a", None],
            "Id": pd.array([1, None], dtype="Int64"),
            "Day": pd.to_datetime(["2026-11-07", None]),
            "At": pd.to_datetime(["2026-11-07T10:30:00Z", None], utc=True),
        }
    )
    easy.import_dataframe(c, 1, 1, "TestTable", df)
    _dataset_id, kw, text = calls[0]
    assert kw["delimiter"] == ","
    assert text == ("Id,Amount,Day,At,Note\n1,,2026-11-07,2026-11-07T10:30:00Z,a\n,,,,\n")


def test_import_dataframe_rejects_bad_input(monkeypatch: pytest.MonkeyPatch) -> None:
    c, calls = _client(monkeypatch)
    with pytest.raises(KeyError, match="Nope"):
        easy.import_dataframe(c, 1, 1, "Nope", pd.DataFrame())
    with pytest.raises(ValueError, match="not fields"):
        easy.import_dataframe(c, 1, 1, "TestTable", pd.DataFrame({"Bogus": [1]}))
    with pytest.raises(ValueError, match="delimiter or a line break"):
        easy.import_dataframe(c, 1, 1, "TestTable", pd.DataFrame({"Note": ["a,b"]}))
    with pytest.raises(ValueError, match="confirm=True"):
        easy.import_dataframe(c, 1, 1, "TestTable", pd.DataFrame({"Id": [1]}), replace=True)
    assert calls == []


def test_check_reads_header_of_a_non_utf8_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Excel often saves cp1252/latin-1; only the (ASCII) header line is needed.
    c, _ = _client(monkeypatch)
    f = tmp_path / "TestTable.csv"
    f.write_bytes((H + "\n1,2,2026-01-01,x,caf\xe9\n").encode("latin-1"))
    assert easy.check_import_file(c, 1, f) == []


def test_decimals_are_written_as_plain_digits() -> None:
    fmt = easy._format_cell
    assert fmt(1e-07, "NUMBER_DECIMAL") == "0.0000001"
    assert fmt(1e16, "NUMBER_DECIMAL") == "10000000000000000"
    assert fmt(3.0, "NUMBER_DECIMAL") == "3"
    assert fmt(2.5, "NUMBER_DECIMAL") == "2.5"
    assert fmt(4.0, "NUMBER_INTEGER") == "4"


def test_import_dataframe_rejects_duplicate_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    c, calls = _client(monkeypatch)
    df = pd.DataFrame([[1, 2]], columns=["Id", "Id"])
    with pytest.raises(ValueError, match="Duplicate column names"):
        easy.import_dataframe(c, 1, 1, "TestTable", df)
    assert calls == []


def test_decimals_from_a_typed_read_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    # apply_schema_dtypes makes Float64 columns; iterating them yields numpy floats.
    import numpy as np

    fmt = easy._format_cell
    typed = pd.Series([1e-07, 2.5, None, -0.0, 1e16], dtype="Float64")
    assert [fmt(v, "NUMBER_DECIMAL") for v in typed] == [
        "0.0000001",
        "2.5",
        "",
        "0",
        "10000000000000000",
    ]
    assert fmt(np.float32(1e-07), "NUMBER_DECIMAL") == "0.0000001"
    assert fmt(np.float64("nan"), "NUMBER_DECIMAL") == ""
    with pytest.raises(ValueError, match="cannot be stored"):
        fmt(float("inf"), "NUMBER_DECIMAL")
    c, calls = _client(monkeypatch)
    frame = easy.apply_schema_dtypes(
        {"T": pd.DataFrame({"Id": ["1"], "Amount": ["0.0000001"]})},
        {"T": {"Id": "NUMBER_INTEGER", "Amount": "NUMBER_DECIMAL"}},
    )["T"]
    easy.import_dataframe(c, 1, 1, "TestTable", frame)
    assert calls[0][2].splitlines()[1] == "1,0.0000001,,,"
