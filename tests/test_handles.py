"""Tests for the Dataflow/Dataset handles (mocked)."""

import pandas as pd
import pytest

from reportnet_api import ForbiddenError, easy
from reportnet_api.handles import Dataflow, find_dataflow

TOKEN = "SECRET-TOKEN-123"


def _datasets(extra=()):
    rows = [
        (1, "Design", "design", None),
        (2, "Austria reporting", "reporting", 10),
        (3, "Austria test", "test", 10),
        (4, "Greece reporting", "reporting", 11),
        *extra,
    ]
    return pd.DataFrame(rows, columns=["dataset_id", "name", "kind", "provider_id"])


def _providers():
    return pd.DataFrame(
        [(10, "AT", "Austria", 1), (11, "EL", "Greece", 1)],
        columns=["provider_id", "code", "label", "group_id"],
    )


@pytest.fixture
def flow(monkeypatch):
    client = easy.connect(TOKEN)
    monkeypatch.setattr(easy, "list_datasets", lambda *a, **k: _datasets())
    monkeypatch.setattr(easy, "list_providers", lambda *a, **k: _providers())
    return Dataflow(id=5, name="Air", status="DRAFT", big_data=False, client=client)


def test_dataset_by_id(flow):
    assert flow.dataset(4).name == "Greece reporting"
    with pytest.raises(LookupError):
        flow.dataset(99)


def test_dataset_by_country_code(flow):
    ds = flow.dataset("el")
    assert ds.id == 4 and ds.country_code == "EL"


def test_code_matching_two_datasets_lists_candidates(flow):
    with pytest.raises(LookupError) as err:
        flow.dataset("AT")
    assert "2" in str(err.value) and "3" in str(err.value)
    assert flow.dataset("AT", kind="test").id == 3


def test_exact_name_beats_substring(flow, monkeypatch):
    monkeypatch.setattr(
        easy, "list_datasets", lambda *a, **k: _datasets([(5, "Austria", "reporting", None)])
    )
    assert flow.dataset("austria").id == 5


def test_unknown_key_lists_available(flow):
    with pytest.raises(LookupError) as err:
        flow.dataset("nothing")
    assert "Greece reporting" in str(err.value) and "AT" in str(err.value)


def test_forbidden_providers_fall_back_to_names(flow, monkeypatch):
    def deny(*a, **k):
        raise ForbiddenError("no", status_code=403, response_body="", request=None, response=None)

    monkeypatch.setattr(easy, "list_providers", deny)
    assert flow.dataset("Greece reporting").id == 4
    with pytest.raises(LookupError, match="providers"):
        flow.dataset("EL")


def test_missing_provider_gives_none_country(flow):
    assert flow.dataset(1).country_code is None


def test_repr_hides_client(flow):
    assert "client" not in repr(flow) and TOKEN not in repr(flow)
    assert TOKEN not in repr(flow.dataset(4))


def _flows(names=("Air quality 2025", "Air quality archive", "Water")):
    return pd.DataFrame(
        [(5 + i, n, "DRAFT") for i, n in enumerate(names)], columns=["id", "name", "status"]
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(easy, "list_dataflows", lambda *a, **k: _flows())
    monkeypatch.setattr(easy, "is_data_lake", lambda *a, **k: True)
    return easy.connect(TOKEN)


def test_find_by_name_unique(client):
    flow = find_dataflow(client, "water")
    assert flow.id == 7 and flow.big_data is True and flow.status == "DRAFT"


def test_find_ambiguous_lists_candidates(client):
    with pytest.raises(LookupError) as err:
        find_dataflow(client, "air quality")
    assert "5" in str(err.value) and "6" in str(err.value)


def test_find_exact_name_wins(client, monkeypatch):
    monkeypatch.setattr(
        easy, "list_dataflows", lambda *a, **k: _flows(("Air quality", "Air quality 2025"))
    )
    assert find_dataflow(client, "AIR QUALITY").id == 5


def test_find_by_int_id(client, monkeypatch):
    assert find_dataflow(client, 7).name == "Water"

    # Not in the listing but readable: handle named after the id.
    monkeypatch.setattr(easy, "list_datasets", lambda *a, **k: _datasets())
    assert find_dataflow(client, 99).name == "99"

    def refuse(*a, **k):
        raise LookupError("empty")

    monkeypatch.setattr(easy, "list_datasets", refuse)
    with pytest.raises(LookupError):
        find_dataflow(client, 98)


def test_find_no_match(client):
    with pytest.raises(LookupError, match="Water"):
        find_dataflow(client, "zzz")


def test_easy_find_dataflow_delegates(client):
    assert easy.find_dataflow(client, "water").id == 7


def test_tables_delegates(flow, monkeypatch):
    seen = []
    frame = pd.DataFrame({"name": ["T"]})
    monkeypatch.setattr(easy, "list_tables", lambda c, i: seen.append(i) or frame)
    assert flow.dataset(4).tables is frame and seen == [4]


def test_refresh_returns_new_handle(flow, monkeypatch):
    monkeypatch.setattr(easy, "list_dataflows", lambda *a, **k: _flows(("Renamed",)))
    monkeypatch.setattr(easy, "is_data_lake", lambda *a, **k: False)
    new = flow.refresh()
    assert new is not flow and new.id == 5 and new.name == "Renamed"
    assert flow.name == "Air"


def test_find_by_int_id_survives_unreadable_listing(client, monkeypatch):
    def deny(*a, **k):
        raise ForbiddenError("no", status_code=403, response_body="", request=None, response=None)

    monkeypatch.setattr(easy, "list_dataflows", deny)
    monkeypatch.setattr(easy, "list_datasets", lambda *a, **k: _datasets())
    assert find_dataflow(client, 7).id == 7
    with pytest.raises(ForbiddenError):  # a name needs the listing
        find_dataflow(client, "water")


def test_country_code_without_dataset_never_falls_back_to_a_name(flow):
    # "de" is inside "Design", but DE is a real provider with no dataset here.
    monkey = _providers()
    monkey.loc[len(monkey)] = (12, "DE", "Germany", 1)
    flow._cache["codes"] = {int(r.provider_id): r.code for r in monkey.itertuples()}
    with pytest.raises(LookupError, match="DE"):
        flow.dataset("DE")


def test_short_key_without_readable_providers_is_not_a_substring_guess(flow, monkeypatch):
    def deny(*a, **k):
        raise ForbiddenError("no", status_code=403, response_body="", request=None, response=None)

    monkeypatch.setattr(easy, "list_providers", deny)
    with pytest.raises(LookupError, match="providers"):
        flow.dataset("DE")


def test_numpy_integer_keys(flow, monkeypatch):
    import numpy as np

    assert flow.dataset(np.int64(4)).id == 4
    monkeypatch.setattr(easy, "list_dataflows", lambda *a, **k: _flows())
    monkeypatch.setattr(easy, "is_data_lake", lambda *a, **k: False)
    assert find_dataflow(flow.client, np.int64(7)).id == 7


def test_id_lookup_survives_any_provider_failure(flow, monkeypatch):
    from reportnet_api import ServerError

    def boom(*a, **k):
        raise ServerError("x", status_code=500, response_body="", request=None, response=None)

    monkeypatch.setattr(easy, "list_providers", boom)
    ds = flow.dataset(4)
    assert ds.id == 4 and ds.country_code is None


def _ds(flow):
    return flow.dataset(4)


def test_read_passes_ids_and_provider(flow, monkeypatch):
    seen = {}

    def fake(client, dataset_id, dataflow_id, table=None, **kw):
        seen.update(ds=dataset_id, flow=dataflow_id, table=table, **kw)
        return "frame"

    monkeypatch.setattr(easy, "read_table", fake)
    assert _ds(flow).read("T") == "frame"
    assert seen == {"ds": 4, "flow": 5, "table": "T", "provider_id": 11}
    _ds(flow).read("T", provider_id=99)
    assert seen["provider_id"] == 99


def test_read_all_passes_ids_and_options(flow, monkeypatch):
    seen = {}

    def fake(client, dataset_id, dataflow_id, **kw):
        seen.update(ds=dataset_id, flow=dataflow_id, **kw)
        return {}

    monkeypatch.setattr(easy, "read_tables", fake)
    _ds(flow).read_all(page_size=50)
    assert seen == {"ds": 4, "flow": 5, "provider_id": 11, "page_size": 50}


def test_validation_methods_delegate(flow, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(easy, "validation_errors", lambda c, d, f, **k: calls.append(("e", d, f)))
    monkeypatch.setattr(easy, "validation_summary", lambda c, d, f: calls.append(("s", d, f)))
    monkeypatch.setattr(
        easy, "export_validations", lambda c, d, dest, **k: calls.append(("x", d, str(dest)))
    )
    ds = _ds(flow)
    ds.validation_errors()
    ds.validation_summary()
    ds.export_validations(tmp_path / "v.csv")
    assert calls == [("e", 4, 5), ("s", 4, 5), ("x", 4, str(tmp_path / "v.csv"))]


def test_find_digit_string_is_an_id_and_empty_is_rejected(client):
    assert find_dataflow(client, " 7 ").name == "Water"
    with pytest.raises(ValueError):
        find_dataflow(client, "  ")


def test_export_upload_validate_delegate(flow, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        easy, "export_to_file", lambda c, d, f, dest, **k: calls.append(("x", d, f, k)) or dest
    )
    monkeypatch.setattr(
        easy, "import_file", lambda c, d, f, path, **k: calls.append(("u", d, f, k)) or {}
    )
    monkeypatch.setattr(
        easy, "validate_and_wait", lambda c, d, f, **k: calls.append(("v", d, f, k)) or None
    )
    ds = _ds(flow)
    ds.export(tmp_path / "e.zip", file_format="parquet")
    ds.upload(tmp_path / "T.csv", replace=True)
    ds.validate(released=True)
    assert calls == [
        ("x", 4, 5, {"file_format": "parquet"}),
        ("u", 4, 5, {"replace": True, "provider_id": 11}),
        ("v", 4, 5, {"released": True}),
    ]


def test_read_many_stacks_and_skips(flow, monkeypatch):
    from reportnet_api.handles import read_many

    data = {
        2: {"T": pd.DataFrame({"a": [1, 2]})},
        3: {"T": pd.DataFrame({"a": []})},
        4: {"Other": pd.DataFrame({"a": [9]})},
    }
    monkeypatch.setattr(easy, "read_tables", lambda c, d, f, **k: data[d])
    sets = [flow.dataset(2), flow.dataset(3), flow.dataset(4)]
    with pytest.warns(RuntimeWarning, match="3 Austria test; 4 Greece reporting"):
        out = read_many(sets, "T")
    assert list(out.columns) == ["dataset", "country", "a"]
    assert out["country"].tolist() == ["AT", "AT"] and out["a"].tolist() == [1, 2]
    with pytest.warns(RuntimeWarning):
        assert read_many(sets[1:], "T").empty


def test_upload_passes_delimiter(flow, monkeypatch, tmp_path):
    f = tmp_path / "T.csv"
    f.write_text("a|b\n1|2\n")
    seen = {}

    class Datasets:
        def import_file_and_wait(self, dataset_id, path, **kw):
            seen.update(kw)
            return {}

    checked = {}

    def check(client, dataset_id, path, *, delimiter=None):
        checked["delimiter"] = delimiter
        return []

    monkeypatch.setattr(easy, "check_import_file", check)  # else it fetches the real schema
    flow.client.datasets = Datasets()
    _ds(flow).upload(f, delimiter="|")
    assert seen["delimiter"] == "|" and seen["provider_id"] == 11
    assert checked["delimiter"] == "|"


def test_find_by_id_lets_an_authentication_error_through(client, monkeypatch):
    from reportnet_api import AuthenticationError

    def deny(*a, **k):
        raise AuthenticationError(
            "401", status_code=401, response_body="", request=None, response=None
        )

    monkeypatch.setattr(easy, "list_dataflows", deny)
    monkeypatch.setattr(easy, "list_datasets", deny)
    with pytest.raises(AuthenticationError):
        find_dataflow(client, 99)


def test_reads_refuse_a_data_lake_dataflow(monkeypatch):
    from reportnet_api.handles import DataLakeError, read_many

    client = easy.connect(TOKEN)
    monkeypatch.setattr(easy, "list_datasets", lambda *a, **k: _datasets())
    monkeypatch.setattr(easy, "list_providers", lambda *a, **k: _providers())
    lake = Dataflow(id=5, name="Lake", status=None, big_data=True, client=client)
    ds = lake.dataset(4)
    assert ds.big_data is True
    for call in (ds.read, ds.read_all, lambda: read_many([ds], "T")):
        with pytest.raises(DataLakeError, match="export"):
            call()
    seen = {}
    monkeypatch.setattr(easy, "read_tables", lambda c, d, f, **k: seen.update(k) or {})
    ds.read_all(allow_data_lake=True)
    assert seen["provider_id"] == 11
