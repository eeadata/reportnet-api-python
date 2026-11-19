"""Tests for the Representative resource (sync + async) and easy.list_providers."""

import asyncio
import json

import httpx
import pytest
import respx

from reportnet_api import AsyncReportnetClient, ReportnetClient, easy

BASE_URL = "https://api.reportnet.europa.eu"
GROUPS = [
    {"dataProviderGroupId": 1, "label": "Member countries"},
    {"dataProviderGroupId": 2, "label": "All countries"},
]
PROVIDERS = [
    {"id": 2, "group": None, "label": "Austria", "code": "AT", "groupId": 1},
    {"id": 6, "group": None, "label": "Belgium", "code": "BE", "groupId": 1},
]
REPS = [
    {
        "id": 10,
        "dataProviderId": 2,
        "dataProviderGroupId": 1,
        "leadReporters": [],
        "receiptDownloaded": False,
        "receiptOutdated": False,
        "hasDatasets": True,
        "restrictFromPublic": False,
    }
]


def test_sync_routes() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/representative/v1/dataflow/5").mock(return_value=httpx.Response(200, json=REPS))
        mock.get("/representative/dataProvider/countryGroups").mock(
            return_value=httpx.Response(200, json=GROUPS)
        )
        mock.get("/representative/dataProvider/1").mock(
            return_value=httpx.Response(200, json=PROVIDERS)
        )
        mock.get("/representative/dataProvider/id/2").mock(
            return_value=httpx.Response(200, json=PROVIDERS[0])
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            assert client.representative.representatives(5) == REPS
            assert client.representative.data_provider_groups() == GROUPS
            assert client.representative.data_providers(1) == PROVIDERS
            assert client.representative.data_provider(2) == PROVIDERS[0]


def test_async_routes() -> None:
    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/representative/v1/dataflow/5").mock(
                return_value=httpx.Response(200, json=[])
            )
            mock.get("/representative/dataProvider/1").mock(
                return_value=httpx.Response(200, json=PROVIDERS)
            )
            mock.get("/representative/dataProvider/countryGroups").mock(
                return_value=httpx.Response(200, json=GROUPS)
            )
            mock.get("/representative/dataProvider/id/2").mock(
                return_value=httpx.Response(200, json=PROVIDERS[0])
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                assert await client.representative.representatives(5) == []
                assert await client.representative.data_providers(1) == PROVIDERS
                assert await client.representative.data_provider_groups() == GROUPS
                assert await client.representative.data_provider(2) == PROVIDERS[0]

    asyncio.run(run())


def test_easy_list_providers() -> None:
    pytest.importorskip("pandas")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/representative/dataProvider/1").mock(
            return_value=httpx.Response(200, json=PROVIDERS)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            df = easy.list_providers(client)
    assert list(df.columns) == ["provider_id", "code", "label", "group_id"]
    assert df["code"].tolist() == ["AT", "BE"]


def test_easy_list_providers_rejects_bad_group() -> None:
    pytest.importorskip("pandas")
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(ValueError, match="group_id"):
            easy.list_providers(client, 0)


def test_easy_list_providers_handles_null_answer() -> None:
    pytest.importorskip("pandas")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/representative/dataProvider/99").mock(
            return_value=httpx.Response(200, content=b"null")
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            df = easy.list_providers(client, 99)
    assert df.empty
    assert list(df.columns) == ["provider_id", "code", "label", "group_id"]


def test_easy_list_providers_403_gets_hint_and_404_propagates() -> None:
    pytest.importorskip("pandas")
    from reportnet_api import ForbiddenError, NotFoundError

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/representative/dataProvider/1").mock(return_value=httpx.Response(403))
        mock.get("/representative/dataProvider/2").mock(return_value=httpx.Response(404))
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ForbiddenError, match="mix up"):
                easy.list_providers(client, 1)
            with pytest.raises(NotFoundError):
                easy.list_providers(client, 2)


# --- Lead reporters export/import, create and validate (hidden routes) ---

EXPORT_CSV = b'Representing,Email\n"AT","a@example.org"\n"BE",""\n'
RESULT_CSV = b'Representing,Email,Imported\n"AT","a@example.org","OK - imported"\n'
REPS_5 = [{**REPS[0], "id": 77}, {**REPS[0], "id": 78, "dataProviderId": 6}]


def _uploaded(request: httpx.Request) -> bytes:
    """The file part's bytes of a multipart request."""
    body = request.content
    start = body.index(b"\r\n\r\n", body.index(b'name="file"')) + 4
    return body[start : body.index(b"\r\n--", start)]


def test_sync_lead_reporter_routes(tmp_path) -> None:
    upload = tmp_path / "Lead-Reporters.csv"
    upload.write_bytes(EXPORT_CSV)
    with respx.mock(base_url=BASE_URL) as mock:
        export = mock.get("/representative/export/5").mock(
            return_value=httpx.Response(200, content=EXPORT_CSV)
        )
        imported = mock.post("/representative/import/5/group/1").mock(
            return_value=httpx.Response(200, content=RESULT_CSV)
        )
        create_rep = mock.post("/representative/5").mock(return_value=httpx.Response(200, json=77))
        reps = mock.get("/representative/v1/dataflow/5").mock(
            return_value=httpx.Response(200, json=REPS_5)
        )
        create_lead = mock.post("/representative/77/leadReporter/dataflow/5").mock(
            return_value=httpx.Response(200, json=901)
        )
        validate = mock.put("/representative/validateLeadReporters/dataflow/5").mock(
            return_value=httpx.Response(200)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            rep = client.representative
            assert rep.export_lead_reporters_file(5) == EXPORT_CSV
            assert rep.import_lead_reporters_file(5, 1, upload) == RESULT_CSV
            assert rep.create_representative(5, data_provider_id=2) == 77
            assert rep.create_representative(5, data_provider_id=2, data_provider_group_id=1) == 77
            new_id = rep.create_lead_reporter(
                representative_id=77, dataflow_id=5, email="a@example.org"
            )
            assert new_id == 901
            rep.validate_lead_reporters(5)

    assert export.calls.last.request.headers["Accept"] == "*/*"
    request = imported.calls.last.request
    assert request.headers["Accept"] == "*/*"
    assert b'name="file"; filename="Lead-Reporters.csv"' in request.content
    assert _uploaded(request) == EXPORT_CSV
    # The group id is sent only when given (Reportnet doesn't read it)
    assert json.loads(create_rep.calls[0].request.content) == {"dataProviderId": 2}
    assert json.loads(create_rep.calls[1].request.content) == {
        "dataProviderId": 2,
        "dataProviderGroupId": 1,
    }
    # Representative id first in the path, dataflow id second; checked against the dataflow
    assert reps.call_count == 1
    assert create_lead.calls.last.request.url.path == "/representative/77/leadReporter/dataflow/5"
    assert json.loads(create_lead.calls.last.request.content) == {"email": "a@example.org"}
    assert validate.call_count == 1
    assert validate.calls.last.request.method == "PUT"
    assert validate.calls.last.request.content == b""


def test_async_lead_reporter_routes(tmp_path) -> None:
    upload = tmp_path / "list.CSV"
    upload.write_bytes(EXPORT_CSV)

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/representative/export/5").mock(
                return_value=httpx.Response(200, content=EXPORT_CSV)
            )
            imported = mock.post("/representative/import/5/group/2").mock(
                return_value=httpx.Response(200, content=RESULT_CSV)
            )
            create_rep = mock.post("/representative/5").mock(
                return_value=httpx.Response(200, text="78")
            )
            mock.get("/representative/v1/dataflow/5").mock(
                return_value=httpx.Response(200, json=REPS_5)
            )
            create_lead = mock.post("/representative/78/leadReporter/dataflow/5").mock(
                return_value=httpx.Response(200, json=902)
            )
            validate = mock.put("/representative/validateLeadReporters/dataflow/5").mock(
                return_value=httpx.Response(200)
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                rep = client.representative
                assert await rep.export_lead_reporters_file(5) == EXPORT_CSV
                assert await rep.import_lead_reporters_file(5, 2, upload) == RESULT_CSV
                new_id = await rep.create_representative(
                    5, data_provider_id=6, data_provider_group_id=2
                )
                assert new_id == 78
                lead_id = await rep.create_lead_reporter(
                    representative_id=78, dataflow_id=5, email="b@example.org"
                )
                assert lead_id == 902
                await rep.validate_lead_reporters(5)
            assert imported.calls.last.request.headers["Accept"] == "*/*"
            assert json.loads(create_rep.calls.last.request.content) == {
                "dataProviderId": 6,
                "dataProviderGroupId": 2,
            }
            assert create_lead.called
            assert validate.calls.last.request.method == "PUT"

    asyncio.run(run())


def test_create_lead_reporter_is_keyword_only() -> None:
    with ReportnetClient(base_url=BASE_URL, token="t") as client:
        with pytest.raises(TypeError):
            client.representative.create_lead_reporter(77, 5, "a@example.org")  # type: ignore[misc]

    async def run() -> None:
        async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(TypeError):
                await client.representative.create_lead_reporter(77, 5, "a@example.org")  # type: ignore[misc]

    asyncio.run(run())


def test_create_lead_reporter_refuses_a_representative_of_another_dataflow() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/representative/v1/dataflow/5").mock(
            return_value=httpx.Response(200, json=REPS_5)
        )
        create_lead = mock.post("/representative/99/leadReporter/dataflow/5").mock(
            return_value=httpx.Response(200, json=1)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ValueError, match="Representative 99"):
                client.representative.create_lead_reporter(
                    representative_id=99, dataflow_id=5, email="a@example.org"
                )
            assert not create_lead.called
            # check=False skips the lookup
            assert (
                client.representative.create_lead_reporter(
                    representative_id=99, dataflow_id=5, email="a@example.org", check=False
                )
                == 1
            )

    async def run() -> None:
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/representative/v1/dataflow/5").mock(
                return_value=httpx.Response(200, json=[])
            )
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                with pytest.raises(ValueError, match="dataflow 5"):
                    await client.representative.create_lead_reporter(
                        representative_id=77, dataflow_id=5, email="a@example.org"
                    )

    asyncio.run(run())


def test_import_normalises_line_ends_and_blank_lines(tmp_path) -> None:
    upload = tmp_path / "crlf.csv"
    upload.write_bytes(b'\xef\xbb\xbfRepresenting,Email\r\n"AT","a@example.org"\r\n\r\n"BE",""\r\n')
    with respx.mock(base_url=BASE_URL) as mock:
        imported = mock.post("/representative/import/5/group/1").mock(
            return_value=httpx.Response(200, content=RESULT_CSV)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            client.representative.import_lead_reporters_file(5, 1, upload)
    request = imported.calls.last.request
    assert _uploaded(request) == EXPORT_CSV
    assert b'filename="crlf.csv"' in request.content


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("list.txt", EXPORT_CSV, r"\.csv"),
        ("list.csv", b'"AT","a@example.org"\n', "header"),
        ("list.csv", b"", "header"),
        ("result.csv", RESULT_CSV, "line 2"),
        ("list.csv", b'Representing,Email\n"AT","a@x.org","x"\n', "exactly two"),
        ("list.csv", b'Representing,Email\n"AT"\n', "exactly two"),
    ],
)
def test_import_refuses_files_reportnet_would_misread(tmp_path, name, content, message) -> None:
    upload = tmp_path / name
    upload.write_bytes(content)
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        route = mock.post("/representative/import/5/group/1")
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ValueError, match=message):
                client.representative.import_lead_reporters_file(5, 1, upload)

        async def run() -> None:
            async with AsyncReportnetClient(base_url=BASE_URL, token="t") as client:
                with pytest.raises(ValueError, match=message):
                    await client.representative.import_lead_reporters_file(5, 1, upload)

        asyncio.run(run())
        assert not route.called


@pytest.mark.parametrize("body", [b"", b"null", "²".encode(), b"12a", b"-3"])
def test_create_without_id_in_answer_raises(body: bytes) -> None:
    from reportnet_api import ReportnetAPIError

    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/representative/5").mock(return_value=httpx.Response(200, content=body))
        mock.post("/representative/7/leadReporter/dataflow/5").mock(
            return_value=httpx.Response(200, content=body)
        )
        with ReportnetClient(base_url=BASE_URL, token="t") as client:
            with pytest.raises(ReportnetAPIError, match="representative"):
                client.representative.create_representative(5, data_provider_id=2)
            with pytest.raises(ReportnetAPIError, match="lead reporter"):
                client.representative.create_lead_reporter(
                    representative_id=7, dataflow_id=5, email="a@example.org", check=False
                )


def test_lead_reporter_errors_propagate() -> None:
    from reportnet_api import ForbiddenError, ReportnetAPIError

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/representative/export/5").mock(return_value=httpx.Response(403))
        mock.post("/representative/5").mock(
            return_value=httpx.Response(400, json={"message": "Error creating representative"})
        )
        with ReportnetClient(base_url=BASE_URL, token="t", token_scheme="ApiKey") as client:
            with pytest.raises(ForbiddenError):
                client.representative.export_lead_reporters_file(5)
            with pytest.raises(ReportnetAPIError) as excinfo:
                client.representative.create_representative(5, data_provider_id=2)
            assert excinfo.value.status_code == 400
