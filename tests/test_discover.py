import reportnet_api
from reportnet_api import easy, find


def test_find_exported_and_matches_names():
    assert reportnet_api.find is find
    calls = {m.call for m in find("export")}
    assert "easy.export_table" in calls
    assert "client.datasets.etl_export_dataset" in calls


def test_find_all_words_and_underscore_equivalence():
    assert {m.call for m in find("import_file")} == {m.call for m in find("import file")}
    assert all("read" in m.call or "read" in m.summary.lower() for m in find("read table"))


def test_find_is_case_insensitive_and_covers_handles():
    calls = {m.call for m in find("UPLOAD")}
    assert "ds.upload" in calls


def test_find_empty_and_no_match():
    assert find("") == []
    assert "No match" in str(find("zzzqqq"))


def test_summary_never_a_roles_table_and_str_is_a_table():
    hits = find("etl")
    assert hits and all(not m.summary.lower().startswith("allowed roles") for m in hits)
    assert str(hits).splitlines()[0].startswith(hits[0].call)
    assert hits[0].doc_link.startswith("docs/reference/datasets.md#")


def test_guide_prints_and_returns(capsys):
    text = easy.guide()
    assert capsys.readouterr().out.strip() == text.strip()
    assert "find(" in text
    assert easy.guide(show=False) == text
    assert capsys.readouterr().out == ""


def test_guide_names_real_helpers():
    for name in (
        "connect_interactive",
        "check_access",
        "list_dataflows",
        "list_datasets",
        "find_dataflow",
        "list_tables",
        "read_table",
        "read_tables",
        "read_many",
        "validation_summary",
        "validation_errors",
        "validate_and_wait",
        "export_validations",
        "export_table",
        "export_to_file",
        "import_file",
    ):
        assert hasattr(easy, name) and name in easy.guide(show=False)
