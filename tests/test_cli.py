import io
from pathlib import Path

import pytest

from reportnet_api import cli


def run(*argv):
    out = io.StringIO()
    code = cli.main(list(argv), out=out)
    return code, out.getvalue()


def test_demo_listings_are_csv():
    code, text = run("--demo", "dataflows")
    assert code == 0 and text.splitlines()[0] == "id,name,status"
    assert "DEMO DATA" in text
    code, text = run("--demo", "datasets", "1")
    assert code == 0 and "102,Austria,reporting,2" in text
    code, text = run("--demo", "tables", "102")
    assert "Stations" in text


def test_demo_read_to_stdout_and_file(tmp_path):
    code, text = run("--demo", "read", "102", "1")
    lines = text.splitlines()
    assert code == 0 and lines[0] == "country_code,Id,Station,Latitude,Commissioned"
    assert lines[1] == "AT,1,Vienna Centre,48.2082,2019-04-01" and len(lines) == 4
    target = tmp_path / "out.csv"
    code, text = run("--demo", "read", "103", "1", "--table", "Stations", "--out", str(target))
    assert code == 0 and text == ""
    assert target.read_text().splitlines()[1].startswith("BE,1,Brussels Ring")


def test_find_and_guide_need_no_credential(monkeypatch):
    monkeypatch.delenv("REPORTNET_API_KEY", raising=False)
    code, text = run("find", "export", "table")
    assert code == 0 and "easy.export_table" in text
    code, text = run("guide")
    assert code == 0 and "Reportnet cheat sheet" in text


def test_errors_are_short_messages_not_tracebacks(monkeypatch, capsys):
    monkeypatch.delenv("REPORTNET_API_KEY", raising=False)
    assert cli.main(["dataflows"]) == 2
    assert "REPORTNET_API_KEY" in capsys.readouterr().err
    assert cli.main(["--demo", "datasets", "999"]) == 1
    assert "only knows dataflow 1" in capsys.readouterr().err


def test_no_write_commands_and_credential_not_an_argument():
    choices = set(cli.build_parser()._subparsers._group_actions[0].choices)
    assert choices == {
        "check",
        "dataflows",
        "datasets",
        "tables",
        "read",
        "export",
        "find",
        "guide",
    }
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--token", "x", "dataflows"])


def test_check_exit_code_reflects_the_probe(monkeypatch):
    monkeypatch.setenv("REPORTNET_API_KEY", "k")
    monkeypatch.setenv("REPORTNET_BASE_URL", "http://127.0.0.1:9")  # nothing listens here
    code, text = run("check")
    assert code == 1 and "credential alive: unknown" in text


def test_missing_credential_message_is_for_the_command_line(monkeypatch, capsys):
    monkeypatch.delenv("REPORTNET_API_KEY", raising=False)
    assert cli.main(["dataflows"]) == 2
    err = capsys.readouterr().err
    assert "REPORTNET_API_KEY" in err and "--demo" in err


def test_read_out_leaves_no_file_on_failure(tmp_path):
    target = tmp_path / "out.csv"
    code, _ = run("--demo", "read", "102", "1", "--table", "Nope", "--out", str(target))
    assert code != 0 and not target.exists() and list(tmp_path.iterdir()) == []


def test_unwritable_out_is_a_message_not_a_traceback(capsys):
    assert cli.main(["--demo", "read", "102", "1", "--out", "/nonexistent/dir/x.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_read_out_file_gets_the_usual_permissions(tmp_path):
    import stat

    target = tmp_path / "out.csv"
    assert run("--demo", "read", "102", "1", "--out", str(target))[0] == 0
    mode = stat.S_IMODE(Path(target).stat().st_mode)
    assert mode == 0o666 & ~cli._UMASK


def test_export_closes_the_progress_line_on_failure(monkeypatch, capsys):
    from reportnet_api import easy
    from reportnet_api.jobs import JobError

    closed = []
    monkeypatch.setattr(cli.ProgressPrinter, "close", lambda self: closed.append(True))

    def fail(*a, **k):
        raise JobError("job CANCELED")

    monkeypatch.setattr(easy, "export_to_file", fail)
    assert cli.main(["--demo", "export", "102", "1", "x.zip"]) == 1
    assert closed == [True] and "job CANCELED" in capsys.readouterr().err
