"""Tests for `progress=`, the `Job` object and Ctrl-C reporting (P10-15). Mocked only."""

import io
from typing import Any

import httpx
import pytest
import respx

from reportnet_api import ReportnetClient, easy
from reportnet_api.jobs import Job, JobError, ProgressPrinter, progress_event, wait_for_job

BASE_URL = "https://api.reportnet.europa.eu"
POLL = "/orchestrator/jobs/pollForJobStatus/9"
URL = POLL + "?datasetId=1&dataflowId=2"


def _answers(*statuses: str):
    return [httpx.Response(200, json={"status": s}) for s in statuses]


def _event(**kw):
    base = {"kind": "job", "status": "QUEUED", "elapsed": 3.0, "job_id": "9"}
    return progress_event(**{**base, **kw})


def test_printer_non_tty_prints_only_on_change() -> None:
    out = io.StringIO()
    printer = ProgressPrinter(out, live=False)
    for status in ("QUEUED", "QUEUED", "IN_PROGRESS", "IN_PROGRESS", "FINISHED"):
        printer(_event(status=status))
    printer.close()
    assert out.getvalue().splitlines() == [
        "Job 9: QUEUED (3s)",
        "Job 9: IN_PROGRESS (3s)",
        "Job 9: FINISHED (3s)",
    ]


def test_printer_live_rewrites_one_line_and_closes_with_newline() -> None:
    out = io.StringIO()
    printer = ProgressPrinter(out, live=True)
    printer(_event(status="IN_PROGRESS"))
    printer(_event(status="FINISHED"))
    printer.close()
    printer.close()  # a second close adds nothing
    assert out.getvalue() == "\rJob 9: IN_PROGRESS (3s)\rJob 9: FINISHED (3s)   \n"


def test_printer_page_and_other_kinds() -> None:
    out = io.StringIO()
    printer = ProgressPrinter(out, live=False)
    printer(progress_event("page", elapsed=1.2, page=2, rows=20))
    printer(progress_event("file", elapsed=4.0))
    printer(progress_event("confirm", elapsed=5.0))
    assert out.getvalue().splitlines() == [
        "Read page 2, 20 rows so far (1s)",
        "Waiting for the export file (4s)",
        "Import finished, confirming statistics (5s)",
    ]


def test_printer_default_stream_is_stdout_not_a_tty(capsys) -> None:
    ProgressPrinter()(_event())  # pytest capture is not a tty and ipykernel isn't loaded
    assert capsys.readouterr().out == "Job 9: QUEUED (3s)\n"


def test_wait_for_job_progress_true_and_callable(capsys) -> None:
    events: list[dict[str, Any]] = []
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(side_effect=_answers("QUEUED", "IN_PROGRESS", "FINISHED") * 2)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            wait_for_job(client, {"pollingUrl": URL}, poll_interval=0, progress=True)
            wait_for_job(client, URL, poll_interval=0, progress=events.append)
    assert capsys.readouterr().out.splitlines() == [
        "Job 9: QUEUED (0s)",
        "Job 9: IN_PROGRESS (0s)",
        "Job 9: FINISHED (0s)",
    ]
    assert [e["status"] for e in events] == ["QUEUED", "IN_PROGRESS", "FINISHED"]
    assert events[0]["kind"] == "job"
    assert events[0]["job_id"] == "9"
    assert events[0]["page"] is None


def test_wait_for_job_default_is_silent(capsys) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(side_effect=_answers("QUEUED", "FINISHED"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            wait_for_job(client, URL, poll_interval=0)
    assert capsys.readouterr() == ("", "")


def test_progress_shows_failure_status_then_raises(capsys) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "CANCELED"}))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError, match="CANCELED"):
                wait_for_job(client, URL, progress=True)
    assert capsys.readouterr().out == "Job 9: CANCELED (0s)\n"


def _ctrl_c_on_sleep(monkeypatch) -> None:
    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("reportnet_api.jobs.time.sleep", interrupt)


def test_ctrl_c_with_progress_reports_job_id_and_reraises(capsys, monkeypatch) -> None:
    _ctrl_c_on_sleep(monkeypatch)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(return_value=_answers("QUEUED")[0])
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(KeyboardInterrupt):
                wait_for_job(client, URL, progress=True)
    err = capsys.readouterr().err
    assert "job 9" in err
    assert "keeps running on the server" in err


def test_ctrl_c_without_progress_stays_silent(capsys, monkeypatch) -> None:
    _ctrl_c_on_sleep(monkeypatch)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(return_value=_answers("QUEUED")[0])
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(KeyboardInterrupt):
                wait_for_job(client, URL)
    assert capsys.readouterr().err == ""


def test_job_status_wait_and_repr(capsys) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get(POLL).mock(side_effect=_answers("QUEUED", "IN_PROGRESS", "FINISHED"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            job = Job.from_polling_url(client, {"pollingUrl": URL}, kind="export")
            assert repr(job) == "Job(id=9, kind=export, last_status=None)"
            assert route.call_count == 0  # creating and repr never poll
            assert job.status == "QUEUED"
            assert route.call_count == 1  # exactly one poll
            assert "last_status=QUEUED" in repr(job)
            answer = job.wait(poll_interval=0, progress=True)
    assert answer["status"] == "FINISHED"
    assert job.last_status == "FINISHED"
    assert capsys.readouterr().out.splitlines()[-1] == "Job 9: FINISHED (0s)"


def test_job_wait_ctrl_c_reports_even_without_progress(capsys, monkeypatch) -> None:
    _ctrl_c_on_sleep(monkeypatch)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(return_value=_answers("QUEUED")[0])
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            job = Job.from_polling_url(client, URL)
            with pytest.raises(KeyboardInterrupt):
                job.wait()
    assert "job 9" in capsys.readouterr().err


def test_job_without_start_answer_url_raises() -> None:
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(JobError, match="did not start a job"):
            Job.from_polling_url(client, {"jobId": 1})


def test_read_tables_page_progress(no_schema_check) -> None:
    events: list[dict[str, Any]] = []

    def page(request: httpx.Request) -> httpx.Response:
        n = int(request.url.params["offset"])  # a 0-based row offset
        recs = [{"fields": [{"fieldName": "a", "value": str(n)}]}]
        return httpx.Response(
            200, json={"tables": [{"tableName": "T", "totalRecords": 2, "records": recs}]}
        )

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(url__regex=rf"{BASE_URL}/dataset/v1/.*").mock(side_effect=page)
        easy.read_tables(
            easy.connect("k", base_url=BASE_URL), 7, 1, page_size=1, progress=events.append
        )
    assert [(e["kind"], e["page"], e["rows"]) for e in events] == [("page", 1, 1), ("page", 2, 2)]


def test_easy_import_file_progress(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr("reportnet_api.jobs.time.sleep", lambda _s: None)
    csv = tmp_path / "a.csv"
    csv.write_text("x\n1\n")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/dataset/v2/importFileData/1").mock(
            return_value=httpx.Response(200, json={"jobId": 9, "pollingUrl": URL})
        )
        mock.get(POLL).mock(side_effect=_answers("IN_PROGRESS", "FINISHED"))
        stats = {"t": {"lastImportDate": 1, "numberOfRecordsImported": 1}}
        mock.get("/dataset/getImportRelatedStatistics/1").mock(
            side_effect=[httpx.Response(200, json={}), httpx.Response(200, json=stats)]
        )
        client = easy.connect("k", base_url=BASE_URL)
        assert easy.import_file(client, 1, 2, csv, timeout=5, progress=True, check=False) == stats
    assert capsys.readouterr().out.splitlines() == [
        "Job 9: IN_PROGRESS (0s)",
        "Job 9: FINISHED (0s)",
    ]


@pytest.fixture
def no_schema_check(monkeypatch):
    monkeypatch.setattr(easy, "_schema_table_names", lambda *a, **k: None)
