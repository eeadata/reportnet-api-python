"""Tests for the shared Orchestrator job poller and the *_to_file / wait_for_job helpers."""

import asyncio

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient
from reportnet_api.jobs import JobError

BASE_URL = "https://api.reportnet.europa.eu"
POLL = "/orchestrator/jobs/pollForJobStatus/9"
DOWNLOAD = "/orchestrator/jobs/downloadEtlExportedFile/9"
FINISHED = {"status": "FINISHED", "downloadUrl": DOWNLOAD + "?datasetId=1&dataflowId=2"}

# (method name, starting route)
EXPORTS = [
    ("export_zip_csv_to_file", "/dataset/v4/etlExport/1"),
    ("export_zip_parquet_to_file", "/dataset/v5/etlExport/1"),
    ("export_dataset_with_job_to_file", "/dataset/v3/etlExport/1"),
]


def _start(mock: respx.MockRouter, route: str) -> None:
    mock.get(route).mock(
        return_value=httpx.Response(200, json={"pollingUrl": POLL + "?datasetId=1&dataflowId=2"})
    )


@pytest.mark.parametrize(("name", "route"), EXPORTS)
def test_export_to_file_polls_then_downloads(tmp_path, name, route) -> None:
    dest = tmp_path / "out.zip"
    with respx.mock(base_url=BASE_URL) as mock:
        _start(mock, route)
        mock.get(POLL).mock(
            side_effect=[
                httpx.Response(200, json={"status": "QUEUED"}),
                httpx.Response(200, json={"status": "IN_PROGRESS"}),
                httpx.Response(200, json=FINISHED),
            ]
        )
        mock.get(DOWNLOAD).mock(return_value=httpx.Response(200, content=b"PK"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            getattr(client.datasets, name)(1, dataflow_id=2, dest=dest, poll_interval=0)
    assert dest.read_bytes() == b"PK"


@pytest.mark.parametrize(("name", "route"), EXPORTS)
def test_async_export_to_file(tmp_path, name, route) -> None:
    dest = tmp_path / "out.zip"

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            _start(mock, route)
            mock.get(POLL).mock(return_value=httpx.Response(200, json=FINISHED))
            mock.get(DOWNLOAD).mock(return_value=httpx.Response(200, content=b"PK"))
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                await getattr(client.datasets, name)(1, dataflow_id=2, dest=dest, poll_interval=0)

    asyncio.run(run())
    assert dest.read_bytes() == b"PK"


@pytest.mark.parametrize(
    "status", ["FAILED", "REFUSED", "CANCELED", "CANCELED_BY_ADMIN", "ABORTED", "CANCELLED"]
)
def test_wait_for_job_failure_statuses(status) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": status}))
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(JobError, match=status),
        ):
            client.datasets.wait_for_job({"jobId": 9, "pollingUrl": POLL}, poll_interval=0)


def test_wait_for_job_error_answer_and_missing_url() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(
            return_value=httpx.Response(200, json={"error": "Could not find job with id 9"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(JobError, match="Could not find job"):
                client.datasets.wait_for_job(POLL)
            with pytest.raises(JobError, match="did not start a job"):
                client.datasets.wait_for_job({"status": "x"})


def test_wait_for_job_times_out() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "IN_PROGRESS"}))
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(JobError, match="did not finish"),
        ):
            client.datasets.wait_for_job(POLL, poll_interval=0, timeout=0)


def test_wait_for_import_job_returns_finished_answer() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(POLL).mock(
            side_effect=[
                httpx.Response(200, json={"status": "IN_PROGRESS"}),
                httpx.Response(200, json={"status": "FINISHED"}),
            ]
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            answer = client.datasets.wait_for_job(
                {"jobId": 9, "pollingUrl": POLL + "?datasetId=1&dataflowId=2"}, poll_interval=0
            )
    assert answer == {"status": "FINISHED"}


def test_export_finished_without_download_url(tmp_path) -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        _start(mock, "/dataset/v4/etlExport/1")
        mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
        with (
            ReportnetClient(base_url=BASE_URL, token="t") as client,
            pytest.raises(JobError, match="download URL"),
        ):
            client.datasets.export_zip_csv_to_file(
                1, dataflow_id=2, dest=tmp_path / "x", poll_interval=0
            )


def test_async_wait_for_job_failure_and_timeout() -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FAILED"}))
                with pytest.raises(JobError, match="FAILED"):
                    await client.datasets.wait_for_job(POLL, poll_interval=0)
                mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "QUEUED"}))
                with pytest.raises(JobError, match="did not finish"):
                    await client.datasets.wait_for_job(POLL, poll_interval=0, timeout=0)
                mock.get(POLL).mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
                assert await client.datasets.wait_for_job(POLL) == {"status": "FINISHED"}

    asyncio.run(run())


def test_easy_export_to_file(tmp_path) -> None:
    from reportnet_api.easy import export_to_file

    dest = tmp_path / "out.zip"
    with respx.mock(base_url=BASE_URL) as mock:
        _start(mock, "/dataset/v5/etlExport/1")
        mock.get(POLL).mock(return_value=httpx.Response(200, json=FINISHED))
        mock.get(DOWNLOAD).mock(return_value=httpx.Response(200, content=b"PK"))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert export_to_file(client, 1, 2, dest, file_format="parquet") == dest
            with pytest.raises(ValueError, match="file_format"):
                export_to_file(client, 1, 2, dest, file_format="xml")  # type: ignore[arg-type]
    assert dest.read_bytes() == b"PK"


def test_failed_job_message_includes_info() -> None:
    from reportnet_api.jobs import _check

    with pytest.raises(JobError, match="CANCELED: File name does not match"):
        _check({"status": "CANCELED", "info": "File name does not match any table name."})
    with pytest.raises(JobError, match=r"^Job FAILED$"):
        _check({"status": "FAILED"})


_MASTER_DATA_LAKES = [
    "QUEUED",
    "IN_PROGRESS",
    "REFUSED",
    "CANCELED",
    "FAILED",
    "FINISHED",
    "CANCELED_BY_ADMIN",
]
_DEVELOP = ["QUEUED", "IN_PROGRESS", "ABORTED", "CANCELLED", "FAILED", "FINISHED"]


@pytest.mark.parametrize("status", sorted(set(_MASTER_DATA_LAKES + _DEVELOP)))
def test_every_backend_status_is_handled_deliberately(status: str) -> None:
    import warnings

    from reportnet_api.jobs import _check

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a known status must not warn
        if status == "FINISHED":
            assert _check({"status": status}) is True
        elif status in ("QUEUED", "IN_PROGRESS"):
            assert _check({"status": status}) is False
        else:
            with pytest.raises(JobError, match=status):
                _check({"status": status})


@pytest.mark.parametrize("answer", [{"status": "SOMETHING_NEW"}, {}, {"status": None}])
def test_unknown_status_keeps_waiting_but_warns(answer: dict) -> None:
    from reportnet_api.jobs import _check

    with pytest.warns(RuntimeWarning, match="Unrecognised job status"):
        assert _check(answer) is False


def test_status_sets_cover_both_enums_without_overlap() -> None:
    from reportnet_api.jobs import JOB_FAILED_STATUSES, JOB_FINISHED_STATUS, JOB_RUNNING_STATUSES

    everything = set(_MASTER_DATA_LAKES + _DEVELOP)
    assert JOB_RUNNING_STATUSES | JOB_FAILED_STATUSES | {JOB_FINISHED_STATUS} == everything
    assert not JOB_RUNNING_STATUSES & JOB_FAILED_STATUSES
    assert JOB_FINISHED_STATUS not in JOB_FAILED_STATUSES
