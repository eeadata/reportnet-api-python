"""Hand-written Representative resource (providers and a dataflow's representatives).

The Representative tag is absent from spec/api-docs.json ("Known
spec-snapshot gap"), and the provider lookups are `@ApiOperation(hidden =
true)` in `RepresentativeControllerImpl` (`dataflow-service`), as are the
lead reporters export/import and the create/validate routes (written from the
`develop` source). This file is never
touched by the generators.

Roles: the read routes take a dataflow role or an ApiKey (see each method).
Everything that exports, imports or creates (`export_lead_reporters_file`,
`import_lead_reporters_file`, `create_representative`, `create_lead_reporter`,
`validate_lead_reporters`) is `secondLevelAuthorize(dataflowId,
DATAFLOW_CUSTODIAN | DATAFLOW_STEWARD | DATAFLOW_STEWARD_SUPPORT)`: no ApiKey
branch, so only such a user's login token (Bearer) passes; an ApiKey gets 403.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

from .._core import ACCEPT_ANY
from .._exceptions import ReportnetAPIError

if TYPE_CHECKING:
    import httpx

    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


def _created_id(response: httpx.Response, what: str) -> int:
    """The new id a create route answers (a JSON `Long`, so plain ASCII digits)."""
    text = response.text.strip().strip('"')
    if not (text.isascii() and text.isdecimal()):
        raise ReportnetAPIError(
            f"Creating a {what} answered {response.status_code} without an id: {text[:200]!r}",
            status_code=response.status_code,
            response_body=response.text,
            request=response.request,
            response=response,
        )
    return int(text)


def _upload(file: str | os.PathLike[str]) -> dict[str, tuple[str, bytes, str]]:
    """The lead reporters CSV as Reportnet's import can read it, as an httpx `files=` mapping.

    `importLeadReportersFile` drops the first line, splits the rest on `\\n`
    and each line on the delimiter (`,`) without reading quotes, strips `"`
    from both values and `\\r` only from the email. So: the name must end in
    `.csv` (else 400), line ends become `\\n` (a CRLF file's `AT\\r` code
    would match no provider), blank lines are dropped (each would come back
    as an unknown-code error), the first line must be the `Representing,Email`
    header, and every other line must have exactly two values (with more, the
    backend silently ignores the email; this includes Reportnet's own import
    result CSV, which has a third `Imported` column). Raises `ValueError`.
    """
    name = os.path.basename(os.fspath(file))
    if not name.lower().endswith(".csv"):
        raise ValueError(f"The lead reporters file must be a .csv file: {name!r}")
    with open(file, "rb") as fh:
        text = fh.read().decode("utf-8-sig")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in normalized.split("\n") if line.strip()]
    if not lines or lines[0].split(",")[0].strip().strip('"').casefold() != "representing":
        raise ValueError(
            f"{name}: the first line must be the header `Representing,Email` "
            "(Reportnet discards the first line whatever it holds)"
        )
    for number, line in enumerate(lines[1:], start=2):
        if len(line.split(",")) != 2:
            raise ValueError(
                f"{name}: data line {number} must have exactly two comma-separated values "
                "(provider code and email; Reportnet does not read quotes, and a result CSV with "
                "an `Imported` column can't be imported again)"
            )
    data = ("\n".join(lines) + "\n").encode("utf-8")
    return {"file": (name, data, "text/csv")}


def _representative_body(
    data_provider_id: int, data_provider_group_id: int | None
) -> dict[str, Any]:
    body: dict[str, Any] = {"dataProviderId": data_provider_id}
    if data_provider_group_id is not None:
        body["dataProviderGroupId"] = data_provider_group_id
    return body


def _check_representative(
    representative_id: int, dataflow_id: int, representatives: list[dict[str, Any]]
) -> None:
    if not any(rep.get("id") == representative_id for rep in representatives or []):
        raise ValueError(
            f"Representative {representative_id} is not one of dataflow {dataflow_id}'s "
            "representatives (Reportnet would add the lead reporter to it anyway)"
        )


_EXPORT_PATH = "/representative/export/{}"
_IMPORT_PATH = "/representative/import/{}/group/{}"
_VALIDATE_PATH = "/representative/validateLeadReporters/dataflow/{}"
_CREATE_LEAD_PATH = "/representative/{}/leadReporter/dataflow/{}"


class RepresentativeResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def representatives(self, dataflow_id: int) -> list[dict[str, Any]]:
        """GET /representative/v1/dataflow/{dataflowId}: a dataflow's representatives.

        Each item has `id`, `dataProviderId` (the `providerId` other endpoints
        take; resolve it with `data_provider()`), `dataProviderGroupId`,
        `leadReporters` (a list that includes email addresses: personal data),
        `receiptDownloaded`, `receiptOutdated`, `hasDatasets` and
        `restrictFromPublic`. Backend rule: a dataflow role (custodian,
        steward, editor, observer, lead reporter, reporter write, steward
        support), an ApiKey for the dataflow, or ADMIN. A dataflow without
        representatives (e.g. a design dataflow) gives an empty list.
        """
        response = self._client.request("GET", f"/representative/v1/dataflow/{dataflow_id}")
        return cast(list[dict[str, Any]], response.json())

    def data_provider_groups(self) -> list[dict[str, Any]]:
        """GET /representative/dataProvider/countryGroups: the country provider groups.

        Items are `{"dataProviderGroupId", "label"}` (note the key: the items of
        `data_providers()` call the same id `groupId`); live there are two, `1`
        "Member countries" and `2` "All countries: member countries
        PLUS other countries and territories". Any authenticated user.
        """
        response = self._client.request("GET", "/representative/dataProvider/countryGroups")
        return cast(list[dict[str, Any]], response.json())

    def data_providers(self, group_id: int) -> list[dict[str, Any]]:
        """GET /representative/dataProvider/{groupId}: the providers in a group.

        Items are `{"id", "group", "label", "code", "groupId"}`: `id` is the
        `providerId`, `code` the country code, `groupId` the group (same value
        as `dataProviderGroupId` on `data_provider_groups()` items; `group` was
        always `None` live). Live: group 1 has 33 member countries, e.g.
        id 2 = Austria `AT`. Any authenticated user.
        """
        response = self._client.request("GET", f"/representative/dataProvider/{group_id}")
        return cast(list[dict[str, Any]], response.json())

    def data_provider(self, data_provider_id: int) -> dict[str, Any]:
        """GET /representative/dataProvider/id/{id}: one provider (same fields as
        `data_providers()` items). Any authenticated user.
        """
        response = self._client.request(
            "GET", f"/representative/dataProvider/id/{data_provider_id}"
        )
        return cast(dict[str, Any], response.json())

    def export_lead_reporters_file(self, dataflow_id: int) -> bytes:
        """GET /representative/export/{dataflowId}: the web app's "Export lead reporters" CSV.

        `RepresentativeControllerImpl#exportLeadReportersFile` (hidden),
        `RepresentativeServiceImpl#exportFile`. Returns the file's bytes
        (`Dataflow-<id>-Lead-Reporters.csv`, no BOM): a header line
        `Representing,Email` (not quoted), then one line per lead reporter
        with every value quoted (`"AT","someone@example.org"`), and `"AT",""`
        for a representative without lead reporters. The delimiter is the
        platform's `exportDataDelimiter` (`,` in `configuration/consulKV.json`);
        lines end in `\\n`. `Representing` is the data provider's code: the file
        carries no provider group, label or flags. Emails are personal data.
        Requires DATAFLOW_CUSTODIAN, DATAFLOW_STEWARD or DATAFLOW_STEWARD_SUPPORT
        (login token only, see the module docstring).
        """
        response = self._client.request(
            "GET", _EXPORT_PATH.format(dataflow_id), headers=dict(ACCEPT_ANY)
        )
        return response.content

    def import_lead_reporters_file(
        self, dataflow_id: int, group_id: int, file: str | os.PathLike[str]
    ) -> bytes:
        """POST /representative/import/{dataflowId}/group/{groupId}: add lead reporters from a CSV.

        `RepresentativeControllerImpl#importFileCountryTemplate` (hidden),
        `RepresentativeServiceImpl#importLeadReportersFile`; multipart `file`
        in `export_lead_reporters_file()`'s format (`Representing,Email`).
        `group_id` is the provider group whose codes `Representing` holds.
        Only adds: nothing is removed or changed.

        The backend discards the first line (so a BOM there is harmless),
        splits the rest on `\\n` and each line on the delimiter without reading
        quotes, and strips `\\r` only from the email. This method therefore
        checks and cleans the file before sending it (see `_upload`): `.csv`
        name, header first, line ends turned into `\\n`, blank lines dropped,
        exactly two comma-separated values per data line; otherwise it raises
        `ValueError` and sends nothing.

        Returns the backend's result CSV (`Representing,Email,Imported`), one
        line per data line, `Imported` being:
        - "OK - imported": a lead reporter was added, or a new representative
          was created (also for a line with a blank email);
        - "KO - invalid email": the email is malformed. **For a provider the
          dataflow doesn't have yet, the representative is still created**, so
          a KO line does not mean nothing changed;
        - empty: that email is already a lead reporter of that representative
          in Reportnet (nothing done);
        - "KO - imported user already exists ... for the same Representative.":
          the same email appears twice for one provider within this file;
        - "KO - imported Representative already exists": a blank email for a
          provider the dataflow already has;
        - "Error during import, country (company) code doesn't correspond to
          a country (company) in ReportNet": unknown code for `group_id`.

        Errors: an empty file or an unknown dataflow answers 400, but an I/O
        error while reading is only logged and answers 200 with a partial
        result, and a line with more than two values has its email ignored
        (refused here before sending), so read the result lines. Not retried.
        Requires DATAFLOW_CUSTODIAN, DATAFLOW_STEWARD or DATAFLOW_STEWARD_SUPPORT.
        """
        response = self._client.request(
            "POST",
            _IMPORT_PATH.format(dataflow_id, group_id),
            files=_upload(file),
            headers=dict(ACCEPT_ANY),
        )
        return response.content

    def create_representative(
        self, dataflow_id: int, *, data_provider_id: int, data_provider_group_id: int | None = None
    ) -> int:
        """POST /representative/{dataflowId}: add a representative (data provider) to a dataflow.

        `RepresentativeControllerImpl#createRepresentative` (hidden), body a
        `RepresentativeVO` with `dataProviderId` (a `data_providers()` item's
        `id`). Reportnet never reads `dataProviderGroupId`: it is sent only
        when given, for the record. Returns the new representative's id, for
        `create_lead_reporter()`. It starts without lead reporters, datasets
        or receipt.

        Errors: a provider the dataflow already has answers 400
        (REPRESENTATIVE_DUPLICATED behind a generic message); an unknown
        `data_provider_id` answers 500 (a foreign-key violation passed on by a
        catch-all). `@LockMethod` without lock criteria: the lock is global,
        across all dataflows, so concurrent calls (from anyone) can get 423.
        Requires DATAFLOW_CUSTODIAN, DATAFLOW_STEWARD or DATAFLOW_STEWARD_SUPPORT.
        """
        response = self._client.request(
            "POST",
            f"/representative/{dataflow_id}",
            json=_representative_body(data_provider_id, data_provider_group_id),
        )
        return _created_id(response, "representative")

    def create_lead_reporter(
        self, *, representative_id: int, dataflow_id: int, email: str, check: bool = True
    ) -> int:
        """POST /representative/{representativeId}/leadReporter/dataflow/{dataflowId}: add a lead reporter.

        `RepresentativeControllerImpl#createLeadReporter` (hidden), body
        `{"email": ...}`. Returns the new lead reporter's id. Keyword-only:
        Reportnet authorizes on `dataflow_id` but loads the representative by
        `representative_id` alone, so swapped or mismatched ids would silently
        add the lead reporter to another dataflow's representative. With
        `check` (default) this first reads `representatives(dataflow_id)` and
        raises `ValueError` if `representative_id` isn't among them.

        The backend lower-cases the email and checks its form (400 otherwise);
        the same email twice on one representative answers 400. An email
        without a Reportnet account is still added, marked `invalid`, and gets
        its permissions later through `validate_lead_reporters()`.
        `@LockMethod` per representative. The email is personal data.
        Requires DATAFLOW_CUSTODIAN, DATAFLOW_STEWARD or DATAFLOW_STEWARD_SUPPORT.
        """
        if check:
            _check_representative(representative_id, dataflow_id, self.representatives(dataflow_id))
        response = self._client.request(
            "POST", _CREATE_LEAD_PATH.format(representative_id, dataflow_id), json={"email": email}
        )
        return _created_id(response, "lead reporter")

    def validate_lead_reporters(self, dataflow_id: int) -> None:
        """PUT /representative/validateLeadReporters/dataflow/{dataflowId}: recheck lead reporters.

        `RepresentativeControllerImpl#validateLeadReporters` (hidden; the
        mapping is declared on the `RepresentativeController` interface).
        Rechecks the dataflow's `invalid` lead reporters against the registered
        users and grants the ones now found their permissions. Asynchronous
        (`@Async`): answers 200 at once, and the outcome only reaches the web
        app as a notification (VALIDATE_LEAD_REPORTERS_COMPLETED/FAILED_EVENT),
        so reread `representatives()` to see it.
        Requires DATAFLOW_CUSTODIAN, DATAFLOW_STEWARD or DATAFLOW_STEWARD_SUPPORT.
        """
        self._client.request("PUT", _VALIDATE_PATH.format(dataflow_id))


class AsyncRepresentativeResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def representatives(self, dataflow_id: int) -> list[dict[str, Any]]:
        """Async counterpart of RepresentativeResource.representatives."""
        response = await self._client.request("GET", f"/representative/v1/dataflow/{dataflow_id}")
        return cast(list[dict[str, Any]], response.json())

    async def data_provider_groups(self) -> list[dict[str, Any]]:
        """Async counterpart of RepresentativeResource.data_provider_groups."""
        response = await self._client.request("GET", "/representative/dataProvider/countryGroups")
        return cast(list[dict[str, Any]], response.json())

    async def data_providers(self, group_id: int) -> list[dict[str, Any]]:
        """Async counterpart of RepresentativeResource.data_providers."""
        response = await self._client.request("GET", f"/representative/dataProvider/{group_id}")
        return cast(list[dict[str, Any]], response.json())

    async def data_provider(self, data_provider_id: int) -> dict[str, Any]:
        """Async counterpart of RepresentativeResource.data_provider."""
        response = await self._client.request(
            "GET", f"/representative/dataProvider/id/{data_provider_id}"
        )
        return cast(dict[str, Any], response.json())

    async def export_lead_reporters_file(self, dataflow_id: int) -> bytes:
        """Async counterpart of RepresentativeResource.export_lead_reporters_file."""
        response = await self._client.request(
            "GET", _EXPORT_PATH.format(dataflow_id), headers=dict(ACCEPT_ANY)
        )
        return response.content

    async def import_lead_reporters_file(
        self, dataflow_id: int, group_id: int, file: str | os.PathLike[str]
    ) -> bytes:
        """Async counterpart of RepresentativeResource.import_lead_reporters_file."""
        response = await self._client.request(
            "POST",
            _IMPORT_PATH.format(dataflow_id, group_id),
            files=_upload(file),
            headers=dict(ACCEPT_ANY),
        )
        return response.content

    async def create_representative(
        self, dataflow_id: int, *, data_provider_id: int, data_provider_group_id: int | None = None
    ) -> int:
        """Async counterpart of RepresentativeResource.create_representative."""
        response = await self._client.request(
            "POST",
            f"/representative/{dataflow_id}",
            json=_representative_body(data_provider_id, data_provider_group_id),
        )
        return _created_id(response, "representative")

    async def create_lead_reporter(
        self, *, representative_id: int, dataflow_id: int, email: str, check: bool = True
    ) -> int:
        """Async counterpart of RepresentativeResource.create_lead_reporter."""
        if check:
            reps = await self.representatives(dataflow_id)
            _check_representative(representative_id, dataflow_id, reps)
        response = await self._client.request(
            "POST", _CREATE_LEAD_PATH.format(representative_id, dataflow_id), json={"email": email}
        )
        return _created_id(response, "lead reporter")

    async def validate_lead_reporters(self, dataflow_id: int) -> None:
        """Async counterpart of RepresentativeResource.validate_lead_reporters."""
        await self._client.request("PUT", _VALIDATE_PATH.format(dataflow_id))
