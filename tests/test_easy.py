from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient, RetryPolicy, easy
from reportnet_api.jobs import JobError

BASE = "https://api.reportnet.europa.eu"


def test_connect_detects_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPORTNET_API_KEY", raising=False)
    with pytest.raises(ValueError, match="No credential"):
        easy.connect()
    assert easy.connect("abc")._core.build_headers()["Authorization"] == "ApiKey abc"
    c = easy.connect("Bearer xyz", base_url=BASE)
    assert c._core.build_headers()["Authorization"] == "Bearer xyz"
    monkeypatch.setenv("REPORTNET_API_KEY", "fromenv")
    assert easy.connect()._core.build_headers()["Authorization"] == "ApiKey fromenv"


@respx.mock
def test_list_datasets_flattens() -> None:
    respx.get(f"{BASE}/dataflow/v1/5").respond(
        json={
            "designDatasets": [{"id": 1, "dataSetName": "d"}],
            "reportingDatasets": [{"id": 2, "dataSetName": "r", "dataProviderId": 9}],
        }
    )
    df = easy.list_datasets(easy.connect("k"), 5)
    assert df["dataset_id"].tolist() == [1, 2]
    assert df["kind"].tolist() == ["design", "reporting"]


def _row_offset_backend(
    rows: list[str], *, total: bool = True
) -> Callable[[httpx.Request], httpx.Response]:
    """Fake ETL export with the live semantics: `offset` is a 0-based row offset."""

    def page(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        limit = int(request.url.params["limit"])
        recs = [
            {"countryCode": "GR", "fields": [{"fieldName": "a", "value": v}]}
            for v in rows[offset : offset + limit]
        ]
        table: dict[str, Any] = {"tableName": "T", "records": recs}
        if total:
            table["totalRecords"] = len(rows)
        return httpx.Response(200, json={"tables": [table]})

    return page


@respx.mock
def test_read_tables_pages_until_complete(no_schema_check: None) -> None:
    # Live (sandbox, 2026-10-27): offset is a row offset; offset=1 would skip row 0.
    route = respx.get(url__regex=rf"{BASE}/dataset/v1/.*").mock(
        side_effect=_row_offset_backend(["r0", "r1", "r2", "r3", "r4"])
    )
    df = easy.read_table(easy.connect("k"), 7, 1, page_size=2)
    assert df["a"].tolist() == ["r0", "r1", "r2", "r3", "r4"]
    assert df["country_code"].tolist() == ["GR"] * 5
    assert [c.request.url.params["offset"] for c in route.calls] == ["0", "2", "4"]


@respx.mock
def test_read_tables_pages_without_total_records(no_schema_check: None) -> None:
    # Backend omits totalRecords unless a filter (e.g. tableSchemaId) is given.
    route = respx.get(url__regex=rf"{BASE}/dataset/v1/.*").mock(
        side_effect=_row_offset_backend(["a", "b", "c", "d", "e"], total=False)
    )
    df = easy.read_table(easy.connect("k"), 7, 1, page_size=2)
    assert df["a"].tolist() == ["a", "b", "c", "d", "e"]
    assert route.call_count == 3


def test_read_table_needs_name_when_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    import pandas as pd

    monkeypatch.setattr(
        easy, "read_tables", lambda *a, **k: {"A": pd.DataFrame(), "B": pd.DataFrame()}
    )
    with pytest.raises(ValueError, match="pass table_name"):
        easy.read_table(None, 1, 1)  # type: ignore[arg-type]


def test_placeholder_ids_give_clear_error() -> None:
    with pytest.raises(ValueError, match="list_dataflows"):
        easy.list_datasets(easy.connect("k"), None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="dataset_id"):
        easy.list_tables(easy.connect("k"), 0)


@respx.mock
def test_forbidden_gets_hint() -> None:
    from reportnet_api import ForbiddenError

    respx.get(f"{BASE}/dataflow/v1/5").respond(403)
    with pytest.raises(ForbiddenError, match=r"Reporter-level only.*mix up"):
        easy.list_datasets(easy.connect("k"), 5)


@respx.mock
def test_list_datasets_empty_body_is_not_no_datasets() -> None:
    respx.get(f"{BASE}/dataflow/v1/5").respond(200)
    with pytest.raises(LookupError, match="unknown or this credential has no access"):
        easy.list_datasets(easy.connect("k"), 5)


@respx.mock
def test_list_datasets_real_empty_dataflow_is_empty_frame() -> None:
    respx.get(f"{BASE}/dataflow/v1/5").respond(json={"id": 5, "reportingDatasets": []})
    assert easy.list_datasets(easy.connect("k"), 5).empty


@pytest.fixture
def no_schema_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(easy, "_schema_table_names", lambda *a, **k: None)


def _rec(rid: str, value: str) -> dict[str, Any]:
    return {"id_record": rid, "fields": [{"fieldName": "a", "value": value}]}


@respx.mock
def test_read_tables_stops_and_dedups_when_offset_is_ignored(no_schema_check: None) -> None:
    # Backend that ignores `offset`: same full page every time must not loop forever.
    recs = [_rec("r1", "x"), _rec("r2", "y")]
    route = respx.get(url__regex=rf"{BASE}/dataset/v1/.*").respond(
        json={"tables": [{"tableName": "T", "records": recs}]}
    )
    with pytest.warns(RuntimeWarning, match="duplicate"):
        df = easy.read_table(easy.connect("k"), 7, 1, page_size=2)
    assert df["a"].tolist() == ["x", "y"]
    assert route.call_count == 2


@respx.mock
def test_read_tables_warns_when_total_differs(no_schema_check: None) -> None:
    pages = [
        httpx.Response(
            200,
            json={"tables": [{"tableName": "T", "totalRecords": 3, "records": [_rec("r1", "x")]}]},
        ),
        httpx.Response(
            200, json={"tables": [{"tableName": "T", "totalRecords": 3, "records": []}]}
        ),
    ]
    respx.get(url__regex=rf"{BASE}/dataset/v1/.*").mock(side_effect=pages)
    with pytest.warns(RuntimeWarning, match="totalRecords=3"):
        df = easy.read_table(easy.connect("k"), 7, 1, page_size=10)
    assert len(df) == 1


@respx.mock
def test_read_tables_warns_on_table_missing_from_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(easy, "_schema_table_names", lambda *a, **k: {"T", "U"})
    respx.get(url__regex=rf"{BASE}/dataset/v1/.*").respond(
        json={"tables": [{"tableName": "T", "records": [_rec("r1", "x")]}]}
    )
    with pytest.warns(RuntimeWarning, match=r"\['U'\]"):
        easy.read_tables(easy.connect("k"), 7, 1)


@respx.mock
def test_read_tables_warns_when_export_has_no_rows(no_schema_check: None) -> None:
    # Live (sandbox, 2026-11-06): a data-lake dataset answers 200 with empty tables.
    respx.get(url__regex=rf"{BASE}/dataset/v1/.*").respond(
        json={"tables": [{"tableName": "T", "records": []}]}
    )
    with pytest.warns(RuntimeWarning, match="data-lake"):
        out = easy.read_tables(easy.connect("k"), 7, 1)
    assert out["T"].empty


def _vrow(code: str, rule: str) -> dict[str, Any]:
    return {
        "shortCode": code,
        "levelError": "ERROR",
        "typeEntity": "FIELD",
        "nameTableSchema": "T",
        "nameFieldSchema": "f",
        "message": "m",
        "numberOfRecords": 3,
        "idRule": rule,
    }


@respx.mock
def test_validation_errors_uses_lake_route_and_pages() -> None:
    respx.get(f"{BASE}/dataflow/v1/5").respond(json={"bigData": True})
    old = respx.get(url__regex=rf"{BASE}/validation/listGroupValidations/.*")

    def page(request: httpx.Request) -> httpx.Response:
        n = int(request.url.params["pageNum"])
        errs = [[_vrow("FC4", "r1"), _vrow("TU3", "r2")], [_vrow("X1", "r3")]][n]
        return httpx.Response(200, json={"errors": errs, "totalRecords": 3})

    dl = respx.get(url__regex=rf"{BASE}/validation/listGroupValidationsDL/.*").mock(
        side_effect=page
    )
    df = easy.validation_errors(easy.connect("k"), 9, 5, page_size=2)
    assert df["short_code"].tolist() == ["FC4", "TU3", "X1"]
    assert df["records"].tolist() == [3, 3, 3]
    assert dl.call_count == 2 and not old.called


@respx.mock
def test_validation_errors_old_route_and_empty() -> None:
    respx.get(f"{BASE}/dataflow/v1/5").respond(json={"bigData": False})
    respx.get(url__regex=rf"{BASE}/validation/listGroupValidations/.*").respond(
        json={"errors": [], "totalRecords": 0}
    )
    df = easy.validation_errors(easy.connect("k"), 9, 5)
    assert df.empty and "short_code" in df.columns


@respx.mock
def test_export_validations_saves_file(tmp_path: Path) -> None:
    respx.post(f"{BASE}/validation/export/9").respond(200)
    respx.get(url__regex=rf"{BASE}/validation/downloadFile/9.*").respond(
        content=b"Entity,Table\nTABLE,T\n"
    )
    out = easy.export_validations(easy.connect("k"), 9, tmp_path / "v.csv")
    assert out.read_bytes().startswith(b"Entity,Table")


@respx.mock
def test_validation_summary_groups_by_table_and_level() -> None:
    respx.get(f"{BASE}/dataflow/v1/5").respond(json={"bigData": False})
    respx.get(url__regex=rf"{BASE}/validation/listGroupValidations/.*").respond(
        json={"errors": [_vrow("A", "r1"), _vrow("B", "r2")], "totalRecords": 2}
    )
    df = easy.validation_summary(easy.connect("k"), 9, 5)
    assert df.to_dict("records") == [{"table": "T", "level": "ERROR", "rules": 2, "records": 6}]


@respx.mock
def test_validate_and_wait_waits_for_new_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("reportnet_api.easy.time.sleep", lambda s: None)
    old = {"eventType": "VALIDATION_FINISHED_EVENT", "insertDate": 100, "content": {"datasetId": 9}}
    other = {
        "eventType": "VALIDATION_FINISHED_EVENT",
        "insertDate": 999,
        "content": {"datasetId": 8},
    }
    new = {"eventType": "VALIDATION_FINISHED_EVENT", "insertDate": 200, "content": {"datasetId": 9}}
    answers = iter([[old, other], [old, other], [new, old, other]])
    respx.get(f"{BASE}/notification/findUserNotifications").mock(
        side_effect=lambda r: httpx.Response(200, json={"userNotifications": next(answers)})
    )
    start = respx.put(f"{BASE}/orchestrator/jobs/addValidationJob/9").respond(200)
    respx.get(f"{BASE}/dataflow/v1/5").respond(json={"bigData": False})
    respx.get(url__regex=rf"{BASE}/validation/listGroupValidations/.*").respond(
        json={"errors": [_vrow("A", "r1")], "totalRecords": 1}
    )
    df = easy.validate_and_wait(easy.connect("k"), 9, 5)
    assert start.called and df["short_code"].tolist() == ["A"]


@respx.mock
def test_validate_and_wait_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("reportnet_api.easy.time.sleep", lambda s: None)
    respx.get(f"{BASE}/notification/findUserNotifications").respond(json={"userNotifications": []})
    respx.put(f"{BASE}/orchestrator/jobs/addValidationJob/9").respond(200)
    with pytest.raises(JobError):
        easy.validate_and_wait(easy.connect("k"), 9, 5, timeout=0)


JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2ln-_x"


def _auth(client: ReportnetClient) -> str:
    return client._core.build_headers()["Authorization"]


def test_connect_detects_raw_jwt_and_scheme_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPORTNET_API_KEY", raising=False)
    assert _auth(easy.connect(JWT)) == f"Bearer {JWT}"
    assert _auth(easy.connect("a.b")) == "ApiKey a.b"  # two parts: not a JWT
    assert _auth(easy.connect("1234-uuid", scheme="bearer")) == "Bearer 1234-uuid"
    assert _auth(easy.connect(JWT, scheme="ApiKey")) == f"ApiKey {JWT}"
    assert _auth(easy.connect("Bearer abc", scheme="ApiKey")) == "ApiKey abc"
    with pytest.raises(ValueError, match="scheme"):
        easy.connect("k", scheme="Basic")


def test_connect_token_provider_and_retry() -> None:
    tokens = iter(["t1", "t2"])
    c = easy.connect(token_provider=lambda: next(tokens))
    assert _auth(c) == "Bearer t1"
    assert _auth(c) == "Bearer t2"
    assert _auth(easy.connect(token_provider=lambda: "x", scheme="ApiKey")) == "ApiKey x"
    with pytest.raises(ValueError, match="not both"):
        easy.connect("k", token_provider=lambda: "x")
    assert easy.connect("k")._retry is None
    assert easy.connect("k", retry=False)._retry is None
    assert easy.connect("k", retry=True)._retry == RetryPolicy()
    policy = RetryPolicy(retries=1)
    assert easy.connect("k", retry=policy)._retry is policy


def test_connect_interactive_uses_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def getpass(p: str) -> str:
        prompts.append(p)
        return JWT

    monkeypatch.setattr("reportnet_api.easy.getpass.getpass", getpass)
    c = easy.connect_interactive(base_url=BASE, retry=True)
    assert _auth(c) == f"Bearer {JWT}"
    assert len(prompts) == 1 and JWT not in prompts[0]


def test_client_repr_hides_secret() -> None:
    c = easy.connect("sekrit-key", base_url=BASE)
    assert "sekrit-key" not in repr(c)
    assert repr(c) == "ReportnetClient(base_url='https://api.reportnet.europa.eu', scheme='ApiKey')"
    a = AsyncReportnetClient(BASE, "sekrit", token_scheme="Bearer")
    assert "sekrit" not in repr(a) and "scheme='Bearer'" in repr(a)


@respx.mock
def test_check_access_alive_and_dataflow(capsys: pytest.CaptureFixture[str]) -> None:
    respx.post(f"{BASE}/dataflow/getDataflows").respond(json={"dataflows": []})
    respx.get(f"{BASE}/dataflow/v1/5").respond(json={"designDatasets": [{"id": 1}]})
    rows = easy.check_access(easy.connect("secret-key"), 5)
    by_check = {r["check"]: r for r in rows}
    assert by_check["credential"]["result"] == "ApiKey"
    assert by_check["credential alive"]["result"] == "yes"
    assert by_check["dataflow 5"]["result"] == "reachable"
    expected = [r for r in rows if r["check"].startswith("expected:")]
    assert expected and all(r["detail"] == "not probed now" for r in expected)
    out = capsys.readouterr().out
    assert "secret-key" not in out and "expected:" in out
    assert [c.request.method for c in respx.calls] == ["POST", "GET"]


@respx.mock
def test_check_access_dead_key_skips_dataflow() -> None:
    respx.post(f"{BASE}/dataflow/getDataflows").respond(
        500, text='{"status":500,"message":"401 UNAUTHORIZED"}{"message":"No message available"}'
    )
    rows = easy.check_access(easy.connect("dead"), 5, show=False)
    by_check = {r["check"]: r for r in rows}
    assert by_check["credential alive"]["result"] == "no (rejected)"
    assert by_check["dataflow 5"]["result"] == "skipped"
    assert len(respx.calls) == 1


@respx.mock
def test_check_access_access_denied_500_is_rejected_and_hints_scheme() -> None:
    # Live (2026-10-26): the listing route answers a dead key, or a Bearer token
    # sent as ApiKey, with this body.
    respx.post(f"{BASE}/dataflow/getDataflows").respond(
        500,
        text='{"status":500,"message":"Access is denied"}{"message":"No message available"}',
    )
    rows = easy.check_access(easy.connect("11111111-2222-3333-4444-555555555555"), show=False)
    alive = {r["check"]: r for r in rows}["credential alive"]
    assert alive["result"] == "no (rejected)"
    assert "scheme='Bearer'" in alive["detail"]


@respx.mock
def test_check_access_dataflow_verdicts() -> None:
    respx.post(f"{BASE}/dataflow/getDataflows").respond(json={})
    respx.get(f"{BASE}/dataflow/v1/1").respond(
        500, json={"message": "status 500 reading DataFlowControllerZuul#accessReferenceEntity(X)"}
    )
    respx.get(f"{BASE}/dataflow/v1/2").respond(403, json={"message": "Forbidden"})
    respx.get(f"{BASE}/dataflow/v1/3").respond(200, text="")
    client = easy.connect(JWT)
    assert easy.check_access(client, 1, show=False)[2]["result"] == "not found"
    assert easy.check_access(client, 2, show=False)[2]["result"] == "no access"
    assert easy.check_access(client, 3, show=False)[2]["result"] == "unclear"
    with pytest.raises(ValueError, match="positive integer id"):
        easy.check_access(client, 0)


@respx.mock
def test_check_access_network_error() -> None:
    respx.post(f"{BASE}/dataflow/getDataflows").mock(side_effect=httpx.ConnectError("down"))
    rows = easy.check_access(easy.connect("k"), show=False)
    assert rows[1]["result"] == "unknown"


def test_connect_scheme_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    uuid = "11111111-2222-3333-4444-555555555555"
    monkeypatch.setenv("REPORTNET_TOKEN_SCHEME", "bearer")
    assert "scheme='Bearer'" in repr(easy.connect(uuid))
    assert "scheme='ApiKey'" in repr(easy.connect(uuid, scheme="ApiKey"))  # argument wins
    monkeypatch.setenv("REPORTNET_TOKEN_SCHEME", "ApiKey")
    assert "scheme='Bearer'" in repr(easy.connect("Bearer " + uuid))  # explicit prefix wins
    assert "scheme='ApiKey'" in repr(easy.connect(uuid))
    assert "scheme='ApiKey'" in repr(easy.connect(token_provider=lambda: uuid))
    monkeypatch.delenv("REPORTNET_TOKEN_SCHEME")
    assert "scheme='Bearer'" in repr(easy.connect(token_provider=lambda: uuid))


def test_connect_rejects_bad_env_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORTNET_TOKEN_SCHEME", "Basic")
    with pytest.raises(ValueError, match="REPORTNET_TOKEN_SCHEME"):
        easy.connect("k")


@respx.mock
def test_read_records_pages_and_needs_no_pandas(
    no_schema_check: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    real_import = builtins.__import__

    # Stands in for builtins.__import__, whose other parameters vary; forwarded as is.
    def no_pandas(name: str, *a: Any, **k: Any) -> ModuleType:
        if name == "pandas" or name.startswith("pandas."):
            raise ImportError("pandas is blocked in this test")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_pandas)
    route = respx.get(url__regex=rf"{BASE}/dataset/v1/.*").mock(
        side_effect=_row_offset_backend(["r0", "r1", "r2", "r3", "r4"])
    )
    rows = easy.read_records(easy.connect("k"), 7, 1, page_size=2)
    assert rows == [{"country_code": "GR", "a": f"r{i}"} for i in range(5)]
    assert route.call_count == 3


@respx.mock
def test_read_records_table_selection(no_schema_check: None) -> None:
    respx.get(url__regex=rf"{BASE}/dataset/v1/.*").mock(side_effect=_row_offset_backend(["x"]))
    client = easy.connect("k")
    assert easy.read_records(client, 7, 1, table_name="T")[0]["a"] == "x"
    assert list(easy.read_all_records(client, 7, 1)) == ["T"]
    with pytest.raises(KeyError, match="available"):
        easy.read_records(client, 7, 1, table_name="Nope")


def test_read_table_without_name_ignores_empty_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    import pandas as pd

    tables = {"Empty": pd.DataFrame(), "Full": pd.DataFrame({"a": [1]})}
    monkeypatch.setattr(easy, "read_tables", lambda *a, **k: tables)
    assert easy.read_table(None, 1, 1)["a"].tolist() == [1]  # type: ignore[arg-type]
    monkeypatch.setattr(easy, "read_all_records", lambda *a, **k: {"E": [], "F": [{"a": 1}]})
    assert easy.read_records(None, 1, 1) == [{"a": 1}]  # type: ignore[arg-type]


def test_page_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="page_size"):
        easy.read_records(easy.connect("k"), 7, 1, page_size=0)


@respx.mock
def test_warnings_point_at_the_callers_line(no_schema_check: None) -> None:
    import warnings

    respx.get(url__regex=rf"{BASE}/dataset/v1/.*").respond(json={"tables": []})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        easy.read_all_records(easy.connect("k"), 7, 1)
    assert caught and all(w.filename == __file__ for w in caught)


def test_read_table_when_every_table_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    import pandas as pd

    monkeypatch.setattr(
        easy, "read_tables", lambda *a, **k: {"A": pd.DataFrame(), "B": pd.DataFrame()}
    )
    with pytest.raises(ValueError, match="All 2 tables are empty"):
        easy.read_table(None, 1, 1)  # type: ignore[arg-type]


def test_page_size_accepts_numpy_ints_and_rejects_bools(no_schema_check: None) -> None:
    import numpy as np

    client = easy.connect("k")
    for bad in (True, 2.5, "10", -1):
        with pytest.raises(ValueError, match="page_size"):
            easy.read_records(client, 7, 1, page_size=bad)
    with respx.mock:
        respx.get(url__regex=rf"{BASE}/dataset/v1/.*").respond(json={"tables": []})
        with pytest.warns(RuntimeWarning):
            easy.read_all_records(client, 7, 1, page_size=np.int64(500))


@respx.mock
def test_validation_errors_explicit_lake_skips_detection() -> None:
    flow = respx.get(f"{BASE}/dataflow/v1/5").respond(json={"bigData": False})
    old = respx.get(url__regex=rf"{BASE}/validation/listGroupValidations/.*")
    dl = respx.get(url__regex=rf"{BASE}/validation/listGroupValidationsDL/.*").respond(
        json={"errors": [_vrow("FC4", "r1")], "totalRecords": 1}
    )
    df = easy.validation_errors(easy.connect("k"), 9, 5, data_lake=True)
    assert df["short_code"].tolist() == ["FC4"]
    assert dl.called and not old.called and not flow.called


@respx.mock
def test_validation_errors_explicit_relational_skips_detection() -> None:
    flow = respx.get(f"{BASE}/dataflow/v1/5").respond(json={"bigData": True})
    dl = respx.get(url__regex=rf"{BASE}/validation/listGroupValidationsDL/.*")
    old = respx.get(url__regex=rf"{BASE}/validation/listGroupValidations/.*").respond(
        json={"errors": [_vrow("A", "r1")], "totalRecords": 1}
    )
    df = easy.validation_errors(easy.connect("k"), 9, 5, data_lake=False)
    assert df["short_code"].tolist() == ["A"]
    assert old.called and not dl.called and not flow.called


@respx.mock
def test_validate_and_wait_passes_data_lake_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("reportnet_api.easy.time.sleep", lambda s: None)
    old = {"eventType": "VALIDATION_FINISHED_EVENT", "insertDate": 100, "content": {"datasetId": 9}}
    new = {"eventType": "VALIDATION_FINISHED_EVENT", "insertDate": 200, "content": {"datasetId": 9}}
    answers = iter([[old], [new, old]])
    respx.get(f"{BASE}/notification/findUserNotifications").mock(
        side_effect=lambda r: httpx.Response(200, json={"userNotifications": next(answers)})
    )
    respx.put(f"{BASE}/orchestrator/jobs/addValidationJob/9").respond(200)
    flow = respx.get(f"{BASE}/dataflow/v1/5").respond(200, content=b"")
    dl = respx.get(url__regex=rf"{BASE}/validation/listGroupValidationsDL/.*").respond(
        json={"errors": [_vrow("FC4", "r1")], "totalRecords": 1}
    )
    df = easy.validate_and_wait(easy.connect("k"), 9, 5, data_lake=True)
    assert df["short_code"].tolist() == ["FC4"] and dl.called and not flow.called
