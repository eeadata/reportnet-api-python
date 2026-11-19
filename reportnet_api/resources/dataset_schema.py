# Generated from spec/api-docs.json by scripts/generate_resources.py.
# Do not edit by hand.

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .._core import stream_upload_file
from ..models import generated

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


class DatasetSchemaResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def export_field_schemas(
        self,
        dataset_schema_id: str,
        dataset_id: int | None = None,
        table_schema_id: str | None = None,
    ) -> str:
        """Allowed roles: CUSTODIAN, STEWARD, EDITOR WRITE"""
        params = {"datasetId": dataset_id, "tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/{dataset_schema_id}/exportFieldSchemas"
        response = self._client.request(
            "GET", url, params=params, headers={"Accept": "application/octet-stream, */*;q=0.1"}
        )
        return response.text

    def export_field_schemas_from_dataset(
        self,
        dataset_id: int,
    ) -> str:
        """Allowed roles: CUSTODIAN, STEWARD, EDITOR WRITE"""
        params = None
        url = f"/dataschema/v1/dataset/{dataset_id}/exportFieldSchemas"
        response = self._client.request(
            "GET", url, params=params, headers={"Accept": "application/octet-stream, */*;q=0.1"}
        )
        return response.text

    def find_data_schema_by_dataset_id(
        self,
        dataset_id: int,
    ) -> generated.DataSetSchemaVO:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, OBSERVER, REPORTER WRITE, REPORTER READ, NATIONAL COORDINATOR, STEWARD SUPPORT

        Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Test dataset: CUSTODIAN, STEWARD ,OBSERVER, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Design dataset: CUSTODIAN, STEWARD, EDITOR READ, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT"""
        params = None
        url = f"/dataschema/v1/datasetId/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return generated.DataSetSchemaVO.model_validate(response.json())

    def get_simple_schema(
        self,
        dataset_id: int,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> generated.SimpleDatasetSchemaVO:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, REPORTER WRITE, REPORTER READ, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {"dataflowId": dataflow_id, "providerId": provider_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/getSimpleSchema/dataset/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return generated.SimpleDatasetSchemaVO.model_validate(response.json())

    def get_table_schemas_ids(
        self,
        dataset_id: int,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> list[generated.TableSchemaIdNameVO]:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, REPORTER WRITE, REPORTER READ, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {"dataflowId": dataflow_id, "providerId": provider_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/getTableSchemasIds/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return [generated.TableSchemaIdNameVO.model_validate(item) for item in response.json()]

    def import_field_schemas(
        self,
        dataset_schema_id: str,
        file: str | os.PathLike[str],
        dataset_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
    ) -> None:
        """Allowed roles: CUSTODIAN, STEWARD, EDITOR WRITE"""
        params = {"datasetId": dataset_id, "replace": replace, "tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/{dataset_schema_id}/importFieldSchemas"
        with stream_upload_file("file", file) as files:
            self._client.request("POST", url, params=params, files=files)

    def update_manually_editable_by_dataset_id(
        self,
        dataset_id: int,
        manually_editable: bool,
    ) -> None:
        """updateManuallyEditableByDatasetId"""
        params = {"manuallyEditable": manually_editable}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/updateManuallyEditable/{dataset_id}"
        self._client.request("PUT", url, params=params)


class AsyncDatasetSchemaResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def export_field_schemas(
        self,
        dataset_schema_id: str,
        dataset_id: int | None = None,
        table_schema_id: str | None = None,
    ) -> str:
        """Allowed roles: CUSTODIAN, STEWARD, EDITOR WRITE"""
        params = {"datasetId": dataset_id, "tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/{dataset_schema_id}/exportFieldSchemas"
        response = await self._client.request(
            "GET", url, params=params, headers={"Accept": "application/octet-stream, */*;q=0.1"}
        )
        return response.text

    async def export_field_schemas_from_dataset(
        self,
        dataset_id: int,
    ) -> str:
        """Allowed roles: CUSTODIAN, STEWARD, EDITOR WRITE"""
        params = None
        url = f"/dataschema/v1/dataset/{dataset_id}/exportFieldSchemas"
        response = await self._client.request(
            "GET", url, params=params, headers={"Accept": "application/octet-stream, */*;q=0.1"}
        )
        return response.text

    async def find_data_schema_by_dataset_id(
        self,
        dataset_id: int,
    ) -> generated.DataSetSchemaVO:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, OBSERVER, REPORTER WRITE, REPORTER READ, NATIONAL COORDINATOR, STEWARD SUPPORT

        Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Test dataset: CUSTODIAN, STEWARD ,OBSERVER, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Design dataset: CUSTODIAN, STEWARD, EDITOR READ, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT"""
        params = None
        url = f"/dataschema/v1/datasetId/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return generated.DataSetSchemaVO.model_validate(response.json())

    async def get_simple_schema(
        self,
        dataset_id: int,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> generated.SimpleDatasetSchemaVO:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, REPORTER WRITE, REPORTER READ, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {"dataflowId": dataflow_id, "providerId": provider_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/getSimpleSchema/dataset/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return generated.SimpleDatasetSchemaVO.model_validate(response.json())

    async def get_table_schemas_ids(
        self,
        dataset_id: int,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
    ) -> list[generated.TableSchemaIdNameVO]:
        """Allowed roles:

        Reporting dataset: STEWARD, LEAD REPORTER, CUSTODIAN, REPORTER WRITE, REPORTER READ, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {"dataflowId": dataflow_id, "providerId": provider_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/getTableSchemasIds/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return [generated.TableSchemaIdNameVO.model_validate(item) for item in response.json()]

    async def import_field_schemas(
        self,
        dataset_schema_id: str,
        file: str | os.PathLike[str],
        dataset_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
    ) -> None:
        """Allowed roles: CUSTODIAN, STEWARD, EDITOR WRITE"""
        params = {"datasetId": dataset_id, "replace": replace, "tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/v1/{dataset_schema_id}/importFieldSchemas"
        with stream_upload_file("file", file) as files:
            await self._client.request("POST", url, params=params, files=files)

    async def update_manually_editable_by_dataset_id(
        self,
        dataset_id: int,
        manually_editable: bool,
    ) -> None:
        """updateManuallyEditableByDatasetId"""
        params = {"manuallyEditable": manually_editable}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataschema/updateManuallyEditable/{dataset_id}"
        await self._client.request("PUT", url, params=params)
