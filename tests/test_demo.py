import pytest

import reportnet_api
from reportnet_api import easy
from reportnet_api.demo import DEMO_DATAFLOW_ID, demo_client


def test_version_is_a_string() -> None:
    assert isinstance(reportnet_api.__version__, str)
    assert reportnet_api.__version__


def test_demo_runs_the_notebook_helpers_without_network(capsys: pytest.CaptureFixture[str]) -> None:
    c = demo_client()
    assert "DEMO MODE" in capsys.readouterr().out
    flows = easy.list_dataflows(c)
    assert flows["id"].tolist() == [DEMO_DATAFLOW_ID]
    assert "DEMO DATA" in flows["name"].iloc[0]
    datasets = easy.list_datasets(c, DEMO_DATAFLOW_ID)
    assert datasets["kind"].tolist() == ["design", "reporting", "reporting"]
    assert easy.list_tables(c, 102)["name"].tolist() == ["Stations"]
    df = easy.read_table(c, 102, DEMO_DATAFLOW_ID, dtypes="schema")
    assert len(df) == 3 and str(df["Id"].dtype) == "Int64"
    assert df["Latitude"].isna().tolist() == [False, False, True]
    assert easy.list_providers(c)["code"].tolist() == ["AT", "BE"]
    flow = easy.find_dataflow(c, "demo")
    assert flow.dataset("BE").id == 103
    assert easy.is_data_lake(c, DEMO_DATAFLOW_ID) is False


def test_demo_pages_and_pandas_free_read() -> None:
    c = demo_client(quiet=True)
    rows = easy.read_records(c, 102, DEMO_DATAFLOW_ID, page_size=2)
    assert [r["Station"] for r in rows] == ["Vienna Centre", "Graz South", "Linz Harbour"]


def test_demo_refuses_anything_it_does_not_fake() -> None:
    import pytest

    from reportnet_api import NotFoundError, ReportnetAPIError

    c = demo_client(quiet=True)
    with pytest.raises(ReportnetAPIError, match="Demo mode has no") as err:
        c.datasets.check_import_process(102)
    assert err.value.status_code == 501
    with pytest.raises(NotFoundError, match="only knows datasets"):
        easy.list_tables(c, 1)  # a dataflow id used as a dataset id
    with pytest.raises(NotFoundError, match="only knows dataflow 1"):
        easy.list_datasets(c, 999)
