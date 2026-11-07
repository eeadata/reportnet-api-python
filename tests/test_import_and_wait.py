"""Tests for import_file_and_wait (sync + async), the statistics check and easy.import_file."""

import asyncio

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient, easy
from reportnet_api.jobs import JobError, import_statistics_changed
from reportnet_api.resources import datasets_ext

BASE_URL = "https://api.reportnet.europa.eu"
STATS = "/dataset/getImportRelatedStatistics/1"
BIG = "/dataset/v2/importFileData/1"
SMALL = "/dataset/v1/1/importFileData"
POLL = "/orchestrator/jobs/pollForJobStatus/9"
T = "tbl"
EMPTY: dict = {}
ONE = {T: {"lastImportDate": 100, "numberOfRecordsImported": 1, "fileExtension": "csv"}}
TWO = {T: {"lastImportDate": 200, "numberOfRecordsImported": 2, "fileExtension": "csv"}}
SAME_COUNT_NEW_DATE = {T: {"lastImportDate": 300, "numberOfRecordsImported": 1}}


@pytest.fixture
def csv(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x\n1\n")
    return f


def _job(mock):
    mock.post(BIG).mock(return_value=httpx.Response(200, json={"jobId": 9, "pollingUrl": POLL}))


def _stats(mock, *answers):
    return mock.get(STATS).mock(side_effect=[httpx.Response(200, json=a) for a in answers])


def test_statistics_changed_logic() -> None:
    assert not import_statistics_changed(ONE, ONE)
    assert import_statistics_changed(EMPTY, ONE)
    assert import_statistics_changed(ONE, TWO)
    assert import_statistics_changed(ONE, SAME_COUNT_NEW_DATE)
    assert not import_statistics_changed(ONE, {**ONE, "other": {}}, T)
    assert not import_statistics_changed(ONE, TWO, "other")
    assert import_statistics_changed(ONE, TWO, T)


def test_big_file_waits_for_job_then_statistics(csv) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        _job(mock)
        mock.get(POLL).mock(
            side_effect=[
                httpx.Response(200, json={"status": "IN_PROGRESS"}),
                httpx.Response(200, json={"status": "FINISHED"}),
            ]
        )
        _stats(mock, ONE, ONE, TWO)  # baseline, still old after job, merged
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_file_and_wait(
                1, csv, dataflow_id=2, table_schema_id=T, poll_interval=0
            )
    assert result == TWO


def test_small_file_polls_statistics_only(csv) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post(SMALL).mock(return_value=httpx.Response(200))
        _stats(mock, EMPTY, EMPTY, ONE)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_file_and_wait(1, csv, big_file=False, poll_interval=0)
    assert result == ONE


def test_job_failure(csv) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        _job(mock)
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FAILED"}))
        _stats(mock, EMPTY)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError, match="FAILED"):
                client.datasets.import_file_and_wait(1, csv, poll_interval=0)


def test_timeout_when_statistics_never_change(csv) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post(SMALL).mock(return_value=httpx.Response(200))
        mock.get(STATS).mock(return_value=httpx.Response(200, json=ONE))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError, match="within"):
                client.datasets.import_file_and_wait(
                    1, csv, big_file=False, poll_interval=0, timeout=0
                )


def test_job_timeout(csv) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        _job(mock)
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "QUEUED"}))
        _stats(mock, EMPTY)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError, match="did not finish"):
                client.datasets.import_file_and_wait(1, csv, poll_interval=0, timeout=0)


def test_trust_job_without_statistics_confirmation(csv) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        _job(mock)
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
        _stats(mock, ONE, ONE)  # never changes, but not required
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_file_and_wait(
                1, csv, confirm_statistics=False, poll_interval=0
            )
    assert result == ONE


def test_finished_job_with_unchanged_statistics_is_success(csv, monkeypatch) -> None:
    monkeypatch.setattr(datasets_ext, "_STATS_GRACE", 0.0)
    with respx.mock(base_url=BASE_URL) as mock:
        _job(mock)
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
        mock.get(STATS).mock(return_value=httpx.Response(200, json=ONE))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_file_and_wait(1, csv, poll_interval=0)
    assert result == ONE


@pytest.mark.parametrize("body", [b'{"jobId": 9}', b"null"])
def test_no_polling_url_with_trusting_job_raises_and_says_upload_was_sent(csv, body) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post(BIG).mock(return_value=httpx.Response(200, content=body))
        _stats(mock, EMPTY)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError, match="was uploaded"):
                client.datasets.import_file_and_wait(1, csv, confirm_statistics=False)


def test_non_dict_job_answer_falls_back_to_statistics(csv) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post(BIG).mock(return_value=httpx.Response(200, content=b"null"))
        _stats(mock, EMPTY, ONE)
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_file_and_wait(1, csv, poll_interval=0)
    assert result == ONE


def test_async_success_failure_and_timeout(csv) -> None:
    import asyncio

    async def run() -> None:
        async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
            with respx.mock(base_url=BASE_URL) as mock:
                _job(mock)
                mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
                _stats(mock, ONE, ONE, TWO)
                got = await client.datasets.import_file_and_wait(1, csv, poll_interval=0)
                assert got == TWO
            with respx.mock(base_url=BASE_URL) as mock:
                _job(mock)
                mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "REFUSED"}))
                _stats(mock, EMPTY)
                with pytest.raises(JobError, match="REFUSED"):
                    await client.datasets.import_file_and_wait(1, csv, poll_interval=0)
            with respx.mock(base_url=BASE_URL) as mock:
                mock.post(SMALL).mock(return_value=httpx.Response(200))
                mock.get(STATS).mock(return_value=httpx.Response(200, json=ONE))
                with pytest.raises(JobError, match="within"):
                    await client.datasets.import_file_and_wait(
                        1, csv, big_file=False, poll_interval=0, timeout=0
                    )

    asyncio.run(run())


def test_easy_import_file_checks_and_runs(csv) -> None:
    client = easy.connect("k", base_url=BASE_URL)
    with pytest.raises(ValueError, match="dataset_id"):
        easy.import_file(client, 0, 2, csv)
    with pytest.raises(FileNotFoundError):
        easy.import_file(client, 1, 2, csv.with_name("nope.csv"))
    with respx.mock(base_url=BASE_URL) as mock:
        _job(mock)
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
        _stats(mock, EMPTY, ONE)
        assert easy.import_file(client, 1, 2, csv, timeout=5, check=False) == ONE


def test_easy_import_file_403_hint(csv) -> None:
    client = easy.connect("k", base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(STATS).mock(return_value=httpx.Response(403))
        with pytest.raises(Exception, match="dataflow and dataset ids"):
            easy.import_file(client, 1, 2, csv, check=False)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Fake clock for import_file_and_wait: its sleeps advance it instead of waiting."""
    now = [0.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    async def async_sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(datasets_ext, "_monotonic", lambda: now[0])
    monkeypatch.setattr(datasets_ext, "_sleep", sleep)
    monkeypatch.setattr(datasets_ext, "_async_sleep", async_sleep)
    return now


def _slow_upload(clock: list[float]):
    def upload(request: httpx.Request) -> httpx.Response:
        clock[0] += 1000  # longer than the whole timeout below
        return httpx.Response(200)

    return upload


def test_timeout_starts_after_the_upload(csv, clock) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post(SMALL).mock(side_effect=_slow_upload(clock))
        _stats(mock, EMPTY, EMPTY, ONE)  # baseline, not merged yet, merged
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            result = client.datasets.import_file_and_wait(
                1, csv, big_file=False, poll_interval=5, timeout=60
            )
    assert result == ONE


def test_async_timeout_starts_after_the_upload(csv, clock) -> None:
    async def run() -> dict:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(SMALL).mock(side_effect=_slow_upload(clock))
            _stats(mock, EMPTY, EMPTY, ONE)
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                return await client.datasets.import_file_and_wait(
                    1, csv, big_file=False, poll_interval=5, timeout=60
                )

    assert asyncio.run(run()) == ONE
