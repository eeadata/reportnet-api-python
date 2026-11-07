"""Hand-written Dataflow resource (listings, dataflow detail, create, delete).

The Dataflow tag is absent from spec/api-docs.json ("Known spec-
snapshot gap"), and the four listing routes, create and delete are
`@ApiOperation(hidden = true)` in `DataflowControllerImpl` (`dataflow-service`).
This file is never touched by the generators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from .._exceptions import ReportnetAPIError

if TYPE_CHECKING:
    import httpx

    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient

DataflowKind = Literal["reporting", "reference", "business", "citizen_science"]
DataflowType = Literal["REPORTING", "REFERENCE", "BUSINESS", "CITIZEN_SCIENCE"]

_LIST_PATHS: dict[str, str] = {
    "reporting": "/dataflow/getDataflows",
    "reference": "/dataflow/referenceDataflows",
    "business": "/dataflow/businessDataflows",
    "citizen_science": "/dataflow/citizenScienceDataflows",
}


def _list_request(
    kind: str,
    filters: dict[str, str] | None,
    order_header: str | None,
    asc: bool | None,
    page_size: int | None,
    page_num: int | None,
) -> tuple[str, dict[str, Any], dict[str, str] | None]:
    try:
        path = _LIST_PATHS[kind]
    except KeyError:
        raise ValueError(f"kind must be one of {sorted(_LIST_PATHS)}, got {kind!r}") from None
    if (page_size is None) != (page_num is None):
        raise ValueError(
            "page_size and page_num must be given together (backend ignores either alone)"
        )
    params = {
        "orderHeader": order_header,
        "asc": None if asc is None else str(asc).lower(),
        "pageSize": page_size,
        "pageNum": page_num,
    }
    return path, {k: v for k, v in params.items() if v is not None}, filters


def _create_body(
    name: str,
    description: str,
    obligation_id: int | None,
    dataflow_type: str,
    fields: dict[str, Any] | None,
) -> dict[str, Any]:
    # What the web app sends (DataflowRepository.create); `releasable` is forced
    # to true server side anyway.
    body: dict[str, Any] = {
        "name": name,
        "description": description,
        "type": dataflow_type,
        "releasable": True,
    }
    if obligation_id is not None:
        body["obligation"] = {"obligationId": obligation_id}
    clash = sorted(set(fields or {}) & {"name", "description", "type", "obligation"})
    if clash:
        raise ValueError(f"pass {clash} as arguments, not in fields")
    body.update(fields or {})
    return body


def _created_id(response: httpx.Response) -> int:
    # ResponseEntity<String> holding the new id; tolerate a JSON-quoted string.
    text = response.text.strip().strip('"')
    if not text.isdigit():
        raise ReportnetAPIError(
            f"POST /dataflow answered {response.status_code} without a dataflow id: {text[:200]!r}",
            status_code=response.status_code,
            response_body=response.text,
            request=response.request,
            response=response,
        )
    return int(text)


def _json_or_none(response: httpx.Response) -> dict[str, Any] | None:
    # The backend swallows EEAException and returns null -> an empty 200 body.
    if not response.content.strip():
        return None
    result: dict[str, Any] = response.json()
    return result


class DataflowResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def dataflows(
        self,
        kind: DataflowKind = "reporting",
        *,
        filters: dict[str, str] | None = None,
        order_header: str | None = None,
        asc: bool | None = None,
        page_size: int | None = None,
        page_num: int | None = None,
    ) -> dict[str, Any]:
        """POST /dataflow/{getDataflows,referenceDataflows,businessDataflows,
        citizenScienceDataflows}: dataflows visible to the logged user.

        Returns the `PaginatedDataflowVO` dict: `dataflows`, `totalRecords`,
        `filteredRecords`. Backend rule is `isAuthenticated()`; an ApiKey
        signs in as the key's owner, so it lists the owner's dataflows.

        `asc=None` omits the param, which the backend treats as `False`: with
        `order_header` set that is a descending sort. Paging needs both
        `page_size` and `page_num` (0-based); giving only one raises
        `ValueError`. A backend-side failure comes back as an empty 200 page,
        indistinguishable from "no dataflows".
        """
        path, params, body = _list_request(kind, filters, order_header, asc, page_size, page_num)
        response = self._client.request("POST", path, params=params, json=body)
        result: dict[str, Any] = response.json()
        return result

    def dataflow_datasets(
        self, dataflow_id: int, *, provider_id: int | None = None
    ) -> dict[str, Any] | None:
        """GET /dataflow/v1/{dataflowId}: the dataflow with its datasets
        (`designDatasets`, `reportingDatasets`, `dataCollections`,
        `euDatasets`, `referenceDatasets`, `testDatasets`).

        Reporters must pass `provider_id`. Requires a dataflow role (or a
        matching ApiKey / data custodian-steward reference access).

        Returns `None` when the backend answers 200 with an empty body (it
        swallows its own errors, e.g. for an unknown dataflow).
        """
        params = {} if provider_id is None else {"providerId": provider_id}
        response = self._client.request("GET", f"/dataflow/v1/{dataflow_id}", params=params)
        return _json_or_none(response)

    def create_dataflow(
        self,
        name: str,
        description: str,
        *,
        obligation_id: int | None = None,
        dataflow_type: DataflowType = "REPORTING",
        fields: dict[str, Any] | None = None,
    ) -> int:
        """POST /dataflow: create a dataflow and return its new id.

        `DataflowControllerImpl#createDataFlow`, body a `DataFlowVO`. Requires
        the user role `DATA_CUSTODIAN`, `DATA_STEWARD`, `DATA_REQUESTER` or
        `ADMIN` (a login token; an ApiKey carries no such role). `name` and
        `description` must not be blank, and every type but `REFERENCE` needs
        `obligation_id` (a ROD obligation id), else `400`. `BUSINESS` needs an
        admin (`401` otherwise) plus `dataProviderGroupId`/`fmeUserId` in
        `fields`. `fields` adds other `DataFlowVO` keys as-is (e.g.
        `deadlineDate`, which must be after today for non-reference types);
        `name`, `description`, `type` or `obligation` in it raise `ValueError`.
        A 200 whose body is not an id raises `ReportnetAPIError`.

        The dataflow starts in `DESIGN` status, with the caller as its
        custodian. A name already used by any dataflow (case-insensitive)
        answers `500` "There was an unknown error creating the dataflow."
        """
        body = _create_body(name, description, obligation_id, dataflow_type, fields)
        response = self._client.request("POST", "/dataflow", json=body)
        return _created_id(response)

    def delete_dataflow(self, dataflow_id: int) -> None:
        """DELETE /dataflow/{dataflowId}: delete a dataflow with its design
        datasets, documents and representatives.

        `DataflowControllerImpl#deleteDataFlow`. Requires `DATAFLOW_STEWARD` or
        `DATAFLOW_CUSTODIAN` on the dataflow. `423` while a schema import or
        a schema copy into it is running. The backend logs and swallows its
        own failures (`DataflowServiceImpl#deleteDataFlow`), so a 200 does not
        prove the dataflow is gone: `dataflow_datasets()` afterwards does.
        """
        self._client.request("DELETE", f"/dataflow/{dataflow_id}")


class AsyncDataflowResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def dataflows(
        self,
        kind: DataflowKind = "reporting",
        *,
        filters: dict[str, str] | None = None,
        order_header: str | None = None,
        asc: bool | None = None,
        page_size: int | None = None,
        page_num: int | None = None,
    ) -> dict[str, Any]:
        """Async counterpart of DataflowResource.dataflows."""
        path, params, body = _list_request(kind, filters, order_header, asc, page_size, page_num)
        response = await self._client.request("POST", path, params=params, json=body)
        result: dict[str, Any] = response.json()
        return result

    async def dataflow_datasets(
        self, dataflow_id: int, *, provider_id: int | None = None
    ) -> dict[str, Any] | None:
        """Async counterpart of DataflowResource.dataflow_datasets."""
        params = {} if provider_id is None else {"providerId": provider_id}
        response = await self._client.request("GET", f"/dataflow/v1/{dataflow_id}", params=params)
        return _json_or_none(response)

    async def create_dataflow(
        self,
        name: str,
        description: str,
        *,
        obligation_id: int | None = None,
        dataflow_type: DataflowType = "REPORTING",
        fields: dict[str, Any] | None = None,
    ) -> int:
        """Async counterpart of DataflowResource.create_dataflow."""
        body = _create_body(name, description, obligation_id, dataflow_type, fields)
        response = await self._client.request("POST", "/dataflow", json=body)
        return _created_id(response)

    async def delete_dataflow(self, dataflow_id: int) -> None:
        """Async counterpart of DataflowResource.delete_dataflow."""
        await self._client.request("DELETE", f"/dataflow/{dataflow_id}")
