import warnings

import pandas as pd
import pytest

from reportnet_api import easy

TYPES = {
    "T": {
        "i": "NUMBER_INTEGER",
        "d": "NUMBER_DECIMAL",
        "dt": "DATE",
        "ts": "DATETIME",
        "b": "BOOLEAN",
        "s": "TEXT",
        "p": "POINT",
    }
}


def _frame(**cols):
    return {"T": pd.DataFrame(cols)}


def test_live_formats_convert_and_empty_becomes_na():
    # Value text as read live from a sandbox dataset; '' for empty cells.
    out = easy.apply_schema_dtypes(
        _frame(
            i=["-42", ""],
            d=["3.14159", ""],
            dt=["2026-11-07", ""],
            ts=["2026-11-07T10:30:00Z", ""],
            s=["hello", ""],
            p=["", ""],
        ),
        TYPES,
    )["T"]
    assert out["i"].tolist()[0] == -42 and out["i"].isna().tolist() == [False, True]
    assert str(out["i"].dtype) == "Int64" and str(out["d"].dtype) == "Float64"
    assert out["d"].iloc[0] == pytest.approx(3.14159)
    assert out["dt"].iloc[0] == pd.Timestamp("2026-11-07") and out["dt"].isna().tolist()[1]
    assert out["ts"].iloc[0] == pd.Timestamp("2026-11-07T10:30:00Z")
    assert out["s"].tolist() == ["hello", ""]  # text untouched, '' kept
    assert out["p"].tolist() == ["", ""]  # geometry untouched


def test_boolean_true_false_any_case():
    out = easy.apply_schema_dtypes(_frame(b=["true", "FALSE", ""]), TYPES)["T"]
    assert str(out["b"].dtype) == "boolean"
    assert out["b"].tolist()[:2] == [True, False] and out["b"].isna().tolist()[2]


@pytest.mark.parametrize(
    ("col", "values"),
    [
        ("i", ["1", "x"]),
        ("i", ["1.5"]),
        ("d", ["1,5"]),
        ("dt", ["07/11/2026"]),
        ("b", ["yes"]),
    ],
)
def test_misfit_column_stays_text_with_warning(col, values):
    frames = _frame(**{col: values})
    with pytest.warns(RuntimeWarning, match=f"column '{col}'"):
        out = easy.apply_schema_dtypes(frames, TYPES)["T"]
    assert out[col].tolist() == values


def test_unknown_table_or_column_untouched_and_input_not_mutated():
    frames = {"Other": pd.DataFrame({"x": ["1"]}), "T": pd.DataFrame({"i": ["1"], "zz": ["1"]})}
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = easy.apply_schema_dtypes(frames, TYPES)
    assert out["Other"]["x"].tolist() == ["1"]
    assert out["T"]["zz"].tolist() == ["1"]
    assert frames["T"]["i"].tolist() == ["1"]  # original still text


def test_read_tables_rejects_unknown_dtypes_value():
    with pytest.raises(ValueError, match="dtypes"):
        easy.read_tables(easy.connect("k"), 1, 1, dtypes="bogus")  # type: ignore[arg-type]


def _rec(rid, **fields):
    return {
        "id_record": rid,
        "countryCode": "",
        "fields": [{"fieldName": k, "value": v} for k, v in fields.items()],
    }


def test_read_tables_dtypes_schema_and_default(monkeypatch):
    import httpx
    import respx

    base = "https://api.reportnet.europa.eu"
    body = {
        "tables": [
            {
                "tableName": "T",
                "totalRecords": 2,
                "records": [_rec("a", i="1", d="2.5"), _rec("b", i="", d="")],
            }
        ]
    }
    monkeypatch.setattr(easy, "_schema_table_names", lambda *a, **k: None)
    monkeypatch.setattr(
        easy,
        "_schema_field_types",
        lambda *a, **k: {"T": {"i": "NUMBER_INTEGER", "d": "NUMBER_DECIMAL"}},
    )
    with respx.mock:
        respx.get(url__regex=rf"{base}/dataset/v1/.*").mock(
            return_value=httpx.Response(200, json=body)
        )
        typed = easy.read_table(easy.connect("k"), 7, 1, dtypes="schema")
        plain = easy.read_table(easy.connect("k"), 7, 1)
    assert str(typed["i"].dtype) == "Int64" and typed["i"].isna().tolist() == [False, True]
    assert plain["i"].tolist() == ["1", ""]  # default unchanged
