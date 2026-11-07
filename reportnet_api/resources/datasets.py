# Generated from spec/api-docs.json by scripts/generate_resources.py.
# Do not edit by hand.

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

from .._core import stream_upload_file
from ..models import generated

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


class DatasetsResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def check_import_process(
        self,
        dataset_id: int,
    ) -> generated.CheckLockVO:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = None
        url = f"/dataset/checkImportProcess/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return generated.CheckLockVO.model_validate(response.json())

    def convert_iceberg_to_parquet_tables(
        self,
        dataflow_id: int,
        dataset_id: int,
        provider_id: int | None = None,
        table_schema_ids: list[str] | None = None,
    ) -> None:
        """convertIcebergToParquetTables"""
        params = {
            "dataflowId": dataflow_id,
            "providerId": provider_id,
            "tableSchemaIds": table_schema_ids,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/convertIcebergToParquetTables/{dataset_id}"
        self._client.request("POST", url, params=params)
        return None

    def convert_parquet_to_iceberg_tables(
        self,
        dataflow_id: int,
        dataset_id: int,
        provider_id: int | None = None,
        table_schema_ids: list[str] | None = None,
    ) -> None:
        """convertParquetToIcebergTables"""
        params = {
            "dataflowId": dataflow_id,
            "providerId": provider_id,
            "tableSchemaIds": table_schema_ids,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/convertParquetToIcebergTables/{dataset_id}"
        self._client.request("POST", url, params=params)
        return None

    def create_empty_tables_v3(
        self,
        dataset_id: int,
        table_schema_id: str | None = None,
    ) -> None:
        """createEmptyTablesV3"""
        params = {"tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/{dataset_id}/createEmptyTablesV3"
        self._client.request("POST", url, params=params)
        return None

    def create_public_files(
        self,
        dataflow_id: int,
        create_reference_dataset: bool | None = None,
        provider_id: int | None = None,
    ) -> None:
        """createPublicFiles"""
        params = {
            "createReferenceDataset": create_reference_dataset,
            "dataflowId": dataflow_id,
            "providerId": provider_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/createPublicFiles"
        self._client.request("POST", url, params=params)
        return None

    def delete_attachment(
        self,
        dataset_id: int,
        field_id: str,
        dataflow_id: int | None = None,
        field_name: str | None = None,
        file_name: str | None = None,
        provider_id: int | None = None,
        record_id: str | None = None,
        table_schema_name: str | None = None,
    ) -> None:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD, OBSERVER

        Test dataset: CUSTODIAN, STEWARD ,OBSERVER, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {
            "dataflowId": dataflow_id,
            "fieldName": field_name,
            "fileName": file_name,
            "providerId": provider_id,
            "recordId": record_id,
            "tableSchemaName": table_schema_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/field/{field_id}/attachment"
        self._client.request("DELETE", url, params=params)
        return None

    def delete_dataset_data(
        self,
        dataset_id: int,
        dataflow_id: int | None = None,
        delete_prefilled_tables: bool | None = None,
        provider_id: int | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """Allowed roles:

        Reporting dataset: REPORTER WRITE, LEAD REPORTER

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "deletePrefilledTables": delete_prefilled_tables,
            "providerId": provider_id,
            "preparationCode": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/deleteDatasetData"
        response = self._client.request("DELETE", url, params=params)
        return cast(dict[str, Any], response.json())

    def delete_table_data(
        self,
        dataset_id: int,
        table_schema_id: str,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """Allowed roles:

        Reporting dataset: REPORTER WRITE, LEAD REPORTER

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "providerId": provider_id,
            "preparationCode": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/deleteTableData/{table_schema_id}"
        response = self._client.request("DELETE", url, params=params)
        return cast(dict[str, Any], response.json())

    def download_imported_file(
        self,
        dataflow_id: int,
        dataset_id: int,
        file_name: str,
        dest: str | os.PathLike[str],
    ) -> None:
        """Downloads a specific imported file for a given dataset and a given filename"""
        params = {"dataflowId": dataflow_id, "datasetId": dataset_id, "fileName": file_name}
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/download-imported-file"
        self._client.download("GET", url, params=params, dest=dest)
        return None

    def duplicate_field_value_exists(
        self,
        dataset_id: int,
        table_schema_id: str,
        field_vo: generated.FieldVO,
    ) -> bool:
        """duplicateFieldValueExists"""
        params = {"tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/duplicateFieldValueExists/{dataset_id}"
        response = self._client.request(
            "POST", url, params=params, json=field_vo.model_dump(mode="json", exclude_none=True)
        )
        return cast(bool, response.json())

    def etl_export_dataset(
        self,
        dataset_id: int,
        dest: str | os.PathLike[str],
        column_name: str | None = None,
        data_provider_codes: str | None = None,
        filter_value: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> None:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Paging: live-tested (production and sandbox), `offset` is a 0-based ROW
        offset, not a page number: `offset=0` (or omitted) starts at the first
        row, then step by `limit` (`offset=limit`, `2*limit`, ...); an offset at
        or past the total returns no records. Sending `offset=1` skips the first
        row and overlaps the next page. (The backend source on `develop` reads as
        a 1-based page number, `limit * offset - limit`; the deployed builds do
        not follow it.) Keep the same `limit` on every call; `limit` defaults to
        10000 server-side. Do not use FME's 'new' paging mode on this backend.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "columnName": column_name,
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "filterValue": filter_value,
            "limit": limit,
            "offset": offset,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/etlExport"
        self._client.download("GET", url, params=params, dest=dest)
        return None

    def etl_export_dataset_v2(
        self,
        dataset_id: int,
        dest: str | os.PathLike[str],
        column_name: str | None = None,
        data_provider_codes: str | None = None,
        filter_value: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> None:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Paging: live-tested (production and sandbox), `offset` is a 0-based ROW
        offset, not a page number: `offset=0` (or omitted) starts at the first
        row, then step by `limit` (`offset=limit`, `2*limit`, ...); an offset at
        or past the total returns no records. Sending `offset=1` skips the first
        row and overlaps the next page. (The backend source on `develop` reads as
        a 1-based page number, `limit * offset - limit`; the deployed builds do
        not follow it.) Keep the same `limit` on every call; `limit` defaults to
        10000 server-side. Do not use FME's 'new' paging mode on this backend.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "columnName": column_name,
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "filterValue": filter_value,
            "limit": limit,
            "offset": offset,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v2/etlExport/{dataset_id}"
        self._client.download("GET", url, params=params, dest=dest)
        return None

    def etl_export_dataset_with_job(
        self,
        dataset_id: int,
        column_name: str | None = None,
        data_provider_codes: str | None = None,
        filter_value: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Async job-based export: returns job metadata, e.g. `{'pollingUrl': ...,
        'status': 'Preparing file'}`, never the exported data. Poll `pollingUrl`
        (Orchestrator, outside this client's spec coverage) until the job
        completes; this client has no polling helper.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "columnName": column_name,
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "filterValue": filter_value,
            "limit": limit,
            "offset": offset,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v3/etlExport/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    def etl_export_zip_csv(
        self,
        dataset_id: int,
        data_provider_codes: str | None = None,
        include_attachments: bool | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Async job-based export: returns job metadata, e.g. `{'pollingUrl': ...,
        'status': 'Preparing file'}`, never the exported data. Poll `pollingUrl`
        (Orchestrator, outside this client's spec coverage) until the job
        completes; this client has no polling helper.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "includeAttachments": include_attachments,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v4/etlExport/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    def etl_export_zip_parquet(
        self,
        dataset_id: int,
        data_provider_codes: str | None = None,
        include_attachments: bool | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Async job-based export: returns job metadata, e.g. `{'pollingUrl': ...,
        'status': 'Preparing file'}`, never the exported data. Poll `pollingUrl`
        (Orchestrator, outside this client's spec coverage) until the job
        completes; this client has no polling helper.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "includeAttachments": include_attachments,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v5/etlExport/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    def etl_import_dataset(
        self,
        dataset_id: int,
        etl_dataset_vo: generated.ETLDatasetVO,
        provider_id: int | None = None,
        replace_data: bool | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: REPORTER WRITE, LEAD REPORTER

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

         EU dataset: CUSTODIAN, STEWARD

        Note: `replace_data` is a real backend parameter (default false): when
        true the existing dataset data is replaced by the import. Confirmed in
        the production-line backend source; not live-tested (destructive)."""
        params = {"dataflowId": dataflow_id, "providerId": provider_id, "replaceData": replace_data}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/etlImport"
        response = self._client.request(
            "POST",
            url,
            params=params,
            json=etl_dataset_vo.model_dump(mode="json", exclude_none=True),
        )
        return cast(dict[str, Any], response.json())

    def etl_import_dataset_dl(
        self,
        dataflow_id: int,
        dataset_id: int,
        delimiter: str,
        file_path_in_s3: str,
        provider_id: int | None = None,
        replace_data: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """etlImportDatasetDL

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "providerId": provider_id,
            "replaceData": replace_data,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/{dataset_id}/etlImportDL"
        response = self._client.request(
            "POST",
            url,
            params=params,
            content=file_path_in_s3,
            headers={"Content-Type": "text/plain"},
        )
        return cast(dict[str, Any], response.json())

    def generate_import_presigned_url(
        self,
        dataset_id: int,
        delimiter: str | None = None,
        etl_import: bool | None = None,
        file_name: str | None = None,
        integration_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> generated.JobPresignedUrlInfo:
        """generateImportPresignedUrl

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "etlImport": etl_import,
            "fileName": file_name,
            "integrationId": integration_id,
            "providerId": provider_id,
            "replace": replace,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/{dataset_id}/generateImportPresignedUrl"
        response = self._client.request("GET", url, params=params)
        return generated.JobPresignedUrlInfo.model_validate(response.json())

    def get_attachment(
        self,
        dataset_id: int,
        field_id: str,
        dest: str | os.PathLike[str],
        field_name: str | None = None,
        file_name: str | None = None,
        provider_code: str | None = None,
        provider_id: int | None = None,
        record_id: str | None = None,
        table_schema_name: str | None = None,
        *,
        dataflow_id: int,
    ) -> None:
        """Allowed roles:

        Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

        EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT"""
        params = {
            "dataflowId": dataflow_id,
            "fieldName": field_name,
            "fileName": file_name,
            "providerCode": provider_code,
            "providerId": provider_id,
            "recordId": record_id,
            "tableSchemaName": table_schema_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/field/{field_id}/attachment"
        self._client.download("GET", url, params=params, dest=dest)
        return None

    def get_available_for_manual_editing_tables(
        self,
        dataset_id: int,
    ) -> list[generated.TableSchemaIdNameVO]:
        """getAvailableForManualEditingTables"""
        params = None
        url = f"/dataset/getAvailableForManualEditingTables/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return [generated.TableSchemaIdNameVO.model_validate(item) for item in response.json()]

    def get_iceberg_tables(
        self,
        dataflow_id: int,
        dataset_id: int | None = None,
        provider_id: int | None = None,
        preparation_code: str | None = None,
    ) -> list[generated.DatasetTableVO]:
        """getIcebergTables

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "datasetId": dataset_id,
            "providerId": provider_id,
            "preparationCode": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/getIcebergTables"
        response = self._client.request("GET", url, params=params)
        return [generated.DatasetTableVO.model_validate(item) for item in response.json()]

    def get_import_related_statistics(
        self,
        dataset_id: int,
    ) -> dict[str, Any]:
        """getImportRelatedStatistics"""
        params = None
        url = f"/dataset/getImportRelatedStatistics/{dataset_id}"
        response = self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    def get_record_geometry(
        self,
        dataflow_id: int,
        dataset_id: int,
        field_id: str,
        id_table_schema: str,
        record_id: str,
        download_file: bool | None = None,
        field_name: str | None = None,
        provider_id: int | None = None,
    ) -> str:
        """getRecordGeometry"""
        params = {
            "dataflowId": dataflow_id,
            "downloadFile": download_file,
            "fieldId": field_id,
            "fieldName": field_name,
            "idTableSchema": id_table_schema,
            "providerId": provider_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/record/{record_id}/geometry"
        response = self._client.request("GET", url, params=params)
        return response.text

    def get_released_dataset_data_info(
        self,
        collection_dataset_id: int,
        provider_code: str,
        table_schema_id: str,
    ) -> generated.ReleasedDatasetDataInfoVO:
        """getReleasedDatasetDataInfo"""
        params = {
            "collectionDatasetId": collection_dataset_id,
            "providerCode": provider_code,
            "tableSchemaId": table_schema_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/getReleasedDatasetDataInfo"
        response = self._client.request("GET", url, params=params)
        return generated.ReleasedDatasetDataInfoVO.model_validate(response.json())

    def import_big_file_data(
        self,
        dataset_id: int,
        file: str | os.PathLike[str],
        dataflow_id: int | None = None,
        delimiter: str | None = None,
        fme_job_id: str | None = None,
        integration_id: int | None = None,
        job_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "fmeJobId": fme_job_id,
            "integrationId": integration_id,
            "jobId": job_id,
            "providerId": provider_id,
            "replace": replace,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v2/importFileData/{dataset_id}"
        with stream_upload_file("file", file) as files:
            response = self._client.request("POST", url, params=params, files=files)
        return cast(dict[str, Any], response.json())

    def import_file_data(
        self,
        dataset_id: int,
        file: str | os.PathLike[str],
        dataflow_id: int | None = None,
        delimiter: str | None = None,
        fme_job_id: str | None = None,
        integration_id: int | None = None,
        job_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
    ) -> None:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "fmeJobId": fme_job_id,
            "integrationId": integration_id,
            "jobId": job_id,
            "providerId": provider_id,
            "replace": replace,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/importFileData"
        with stream_upload_file("file", file) as files:
            self._client.request("POST", url, params=params, files=files)
        return None

    def is_iceberg_table_created(
        self,
        dataset_id: int,
        table_schema_id: str,
        preparation_code: str | None = None,
    ) -> bool:
        """isIcebergTableCreated

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {"preparationCode": preparation_code}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/isIcebergTableCreated/{dataset_id}/{table_schema_id}"
        response = self._client.request("GET", url, params=params)
        return cast(bool, response.json())

    def list_imported_files(
        self,
        dataset_id: int,
    ) -> list[generated.ImportedFilesDirectoriesVO]:
        """Returns all imported files for a given dataset"""
        params = {"datasetId": dataset_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/list-imported-files"
        response = self._client.request("GET", url, params=params)
        return [
            generated.ImportedFilesDirectoriesVO.model_validate(item) for item in response.json()
        ]

    def restore_prefilled_tables(
        self,
        dataset_id: int,
        table_schema_id: str | None = None,
    ) -> None:
        """restorePrefilledTables"""
        params = {"tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/restorePrefilledTables/{dataset_id}"
        self._client.request("POST", url, params=params)
        return None

    def update_attachment(
        self,
        dataset_id: int,
        field_id: str,
        file: str | os.PathLike[str],
        dataflow_id: int | None = None,
        field_name: str | None = None,
        previous_file_name: str | None = None,
        provider_id: int | None = None,
        record_id: str | None = None,
        table_schema_name: str | None = None,
    ) -> None:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD , STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {
            "dataflowId": dataflow_id,
            "fieldName": field_name,
            "previousFileName": previous_file_name,
            "providerId": provider_id,
            "recordId": record_id,
            "tableSchemaName": table_schema_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/field/{field_id}/attachment"
        with stream_upload_file("file", file) as files:
            self._client.request("PUT", url, params=params, files=files)
        return None

    def update_geometry(
        self,
        dataset_id: int,
    ) -> None:
        """updateGeometry"""
        params = None
        url = f"/dataset/{dataset_id}/updateGeometry"
        self._client.request("PUT", url, params=params)
        return None

    def update_geometry_v2(
        self,
        dataset_id: int,
    ) -> None:
        """updateGeometryV2"""
        params = None
        url = f"/dataset/v2/{dataset_id}/updateGeometry"
        self._client.request("PUT", url, params=params)
        return None


class AsyncDatasetsResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def check_import_process(
        self,
        dataset_id: int,
    ) -> generated.CheckLockVO:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = None
        url = f"/dataset/checkImportProcess/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return generated.CheckLockVO.model_validate(response.json())

    async def convert_iceberg_to_parquet_tables(
        self,
        dataflow_id: int,
        dataset_id: int,
        provider_id: int | None = None,
        table_schema_ids: list[str] | None = None,
    ) -> None:
        """convertIcebergToParquetTables"""
        params = {
            "dataflowId": dataflow_id,
            "providerId": provider_id,
            "tableSchemaIds": table_schema_ids,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/convertIcebergToParquetTables/{dataset_id}"
        await self._client.request("POST", url, params=params)
        return None

    async def convert_parquet_to_iceberg_tables(
        self,
        dataflow_id: int,
        dataset_id: int,
        provider_id: int | None = None,
        table_schema_ids: list[str] | None = None,
    ) -> None:
        """convertParquetToIcebergTables"""
        params = {
            "dataflowId": dataflow_id,
            "providerId": provider_id,
            "tableSchemaIds": table_schema_ids,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/convertParquetToIcebergTables/{dataset_id}"
        await self._client.request("POST", url, params=params)
        return None

    async def create_empty_tables_v3(
        self,
        dataset_id: int,
        table_schema_id: str | None = None,
    ) -> None:
        """createEmptyTablesV3"""
        params = {"tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/{dataset_id}/createEmptyTablesV3"
        await self._client.request("POST", url, params=params)
        return None

    async def create_public_files(
        self,
        dataflow_id: int,
        create_reference_dataset: bool | None = None,
        provider_id: int | None = None,
    ) -> None:
        """createPublicFiles"""
        params = {
            "createReferenceDataset": create_reference_dataset,
            "dataflowId": dataflow_id,
            "providerId": provider_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/createPublicFiles"
        await self._client.request("POST", url, params=params)
        return None

    async def delete_attachment(
        self,
        dataset_id: int,
        field_id: str,
        dataflow_id: int | None = None,
        field_name: str | None = None,
        file_name: str | None = None,
        provider_id: int | None = None,
        record_id: str | None = None,
        table_schema_name: str | None = None,
    ) -> None:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD, OBSERVER

        Test dataset: CUSTODIAN, STEWARD ,OBSERVER, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {
            "dataflowId": dataflow_id,
            "fieldName": field_name,
            "fileName": file_name,
            "providerId": provider_id,
            "recordId": record_id,
            "tableSchemaName": table_schema_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/field/{field_id}/attachment"
        await self._client.request("DELETE", url, params=params)
        return None

    async def delete_dataset_data(
        self,
        dataset_id: int,
        dataflow_id: int | None = None,
        delete_prefilled_tables: bool | None = None,
        provider_id: int | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """Allowed roles:

        Reporting dataset: REPORTER WRITE, LEAD REPORTER

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "deletePrefilledTables": delete_prefilled_tables,
            "providerId": provider_id,
            "preparationCode": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/deleteDatasetData"
        response = await self._client.request("DELETE", url, params=params)
        return cast(dict[str, Any], response.json())

    async def delete_table_data(
        self,
        dataset_id: int,
        table_schema_id: str,
        dataflow_id: int | None = None,
        provider_id: int | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """Allowed roles:

        Reporting dataset: REPORTER WRITE, LEAD REPORTER

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "providerId": provider_id,
            "preparationCode": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/deleteTableData/{table_schema_id}"
        response = await self._client.request("DELETE", url, params=params)
        return cast(dict[str, Any], response.json())

    async def download_imported_file(
        self,
        dataflow_id: int,
        dataset_id: int,
        file_name: str,
        dest: str | os.PathLike[str],
    ) -> None:
        """Downloads a specific imported file for a given dataset and a given filename"""
        params = {"dataflowId": dataflow_id, "datasetId": dataset_id, "fileName": file_name}
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/download-imported-file"
        await self._client.download("GET", url, params=params, dest=dest)
        return None

    async def duplicate_field_value_exists(
        self,
        dataset_id: int,
        table_schema_id: str,
        field_vo: generated.FieldVO,
    ) -> bool:
        """duplicateFieldValueExists"""
        params = {"tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/duplicateFieldValueExists/{dataset_id}"
        response = await self._client.request(
            "POST", url, params=params, json=field_vo.model_dump(mode="json", exclude_none=True)
        )
        return cast(bool, response.json())

    async def etl_export_dataset(
        self,
        dataset_id: int,
        dest: str | os.PathLike[str],
        column_name: str | None = None,
        data_provider_codes: str | None = None,
        filter_value: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> None:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Paging: live-tested (production and sandbox), `offset` is a 0-based ROW
        offset, not a page number: `offset=0` (or omitted) starts at the first
        row, then step by `limit` (`offset=limit`, `2*limit`, ...); an offset at
        or past the total returns no records. Sending `offset=1` skips the first
        row and overlaps the next page. (The backend source on `develop` reads as
        a 1-based page number, `limit * offset - limit`; the deployed builds do
        not follow it.) Keep the same `limit` on every call; `limit` defaults to
        10000 server-side. Do not use FME's 'new' paging mode on this backend.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "columnName": column_name,
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "filterValue": filter_value,
            "limit": limit,
            "offset": offset,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/etlExport"
        await self._client.download("GET", url, params=params, dest=dest)
        return None

    async def etl_export_dataset_v2(
        self,
        dataset_id: int,
        dest: str | os.PathLike[str],
        column_name: str | None = None,
        data_provider_codes: str | None = None,
        filter_value: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> None:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Paging: live-tested (production and sandbox), `offset` is a 0-based ROW
        offset, not a page number: `offset=0` (or omitted) starts at the first
        row, then step by `limit` (`offset=limit`, `2*limit`, ...); an offset at
        or past the total returns no records. Sending `offset=1` skips the first
        row and overlaps the next page. (The backend source on `develop` reads as
        a 1-based page number, `limit * offset - limit`; the deployed builds do
        not follow it.) Keep the same `limit` on every call; `limit` defaults to
        10000 server-side. Do not use FME's 'new' paging mode on this backend.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "columnName": column_name,
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "filterValue": filter_value,
            "limit": limit,
            "offset": offset,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v2/etlExport/{dataset_id}"
        await self._client.download("GET", url, params=params, dest=dest)
        return None

    async def etl_export_dataset_with_job(
        self,
        dataset_id: int,
        column_name: str | None = None,
        data_provider_codes: str | None = None,
        filter_value: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Async job-based export: returns job metadata, e.g. `{'pollingUrl': ...,
        'status': 'Preparing file'}`, never the exported data. Poll `pollingUrl`
        (Orchestrator, outside this client's spec coverage) until the job
        completes; this client has no polling helper.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "columnName": column_name,
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "filterValue": filter_value,
            "limit": limit,
            "offset": offset,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v3/etlExport/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    async def etl_export_zip_csv(
        self,
        dataset_id: int,
        data_provider_codes: str | None = None,
        include_attachments: bool | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Async job-based export: returns job metadata, e.g. `{'pollingUrl': ...,
        'status': 'Preparing file'}`, never the exported data. Poll `pollingUrl`
        (Orchestrator, outside this client's spec coverage) until the job
        completes; this client has no polling helper.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "includeAttachments": include_attachments,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v4/etlExport/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    async def etl_export_zip_parquet(
        self,
        dataset_id: int,
        data_provider_codes: str | None = None,
        include_attachments: bool | None = None,
        provider_id: int | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

         EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

         Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Async job-based export: returns job metadata, e.g. `{'pollingUrl': ...,
        'status': 'Preparing file'}`, never the exported data. Poll `pollingUrl`
        (Orchestrator, outside this client's spec coverage) until the job
        completes; this client has no polling helper.

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataProviderCodes": data_provider_codes,
            "dataflowId": dataflow_id,
            "includeAttachments": include_attachments,
            "providerId": provider_id,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v5/etlExport/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    async def etl_import_dataset(
        self,
        dataset_id: int,
        etl_dataset_vo: generated.ETLDatasetVO,
        provider_id: int | None = None,
        replace_data: bool | None = None,
        *,
        dataflow_id: int,
    ) -> dict[str, Any]:
        """Allowed roles:

         Reporting dataset: REPORTER WRITE, LEAD REPORTER

         Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

         Reference dataset: CUSTODIAN, STEWARD

         Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

         EU dataset: CUSTODIAN, STEWARD

        Note: `replace_data` is a real backend parameter (default false): when
        true the existing dataset data is replaced by the import. Confirmed in
        the production-line backend source; not live-tested (destructive)."""
        params = {"dataflowId": dataflow_id, "providerId": provider_id, "replaceData": replace_data}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/etlImport"
        response = await self._client.request(
            "POST",
            url,
            params=params,
            json=etl_dataset_vo.model_dump(mode="json", exclude_none=True),
        )
        return cast(dict[str, Any], response.json())

    async def etl_import_dataset_dl(
        self,
        dataflow_id: int,
        dataset_id: int,
        delimiter: str,
        file_path_in_s3: str,
        provider_id: int | None = None,
        replace_data: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """etlImportDatasetDL

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "providerId": provider_id,
            "replaceData": replace_data,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/{dataset_id}/etlImportDL"
        response = await self._client.request(
            "POST",
            url,
            params=params,
            content=file_path_in_s3,
            headers={"Content-Type": "text/plain"},
        )
        return cast(dict[str, Any], response.json())

    async def generate_import_presigned_url(
        self,
        dataset_id: int,
        delimiter: str | None = None,
        etl_import: bool | None = None,
        file_name: str | None = None,
        integration_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
        *,
        dataflow_id: int,
    ) -> generated.JobPresignedUrlInfo:
        """generateImportPresignedUrl

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "etlImport": etl_import,
            "fileName": file_name,
            "integrationId": integration_id,
            "providerId": provider_id,
            "replace": replace,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/{dataset_id}/generateImportPresignedUrl"
        response = await self._client.request("GET", url, params=params)
        return generated.JobPresignedUrlInfo.model_validate(response.json())

    async def get_attachment(
        self,
        dataset_id: int,
        field_id: str,
        dest: str | os.PathLike[str],
        field_name: str | None = None,
        file_name: str | None = None,
        provider_code: str | None = None,
        provider_id: int | None = None,
        record_id: str | None = None,
        table_schema_name: str | None = None,
        *,
        dataflow_id: int,
    ) -> None:
        """Allowed roles:

        Reporting dataset: CUSTODIAN, STEWARD, OBSERVER, REPORTER WRITE, REPORTER READ, LEAD REPORTER, STEWARD SUPPORT

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE, EDITOR READ

        EU dataset: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT

        Data collection: CUSTODIAN, STEWARD, OBSERVER, STEWARD SUPPORT"""
        params = {
            "dataflowId": dataflow_id,
            "fieldName": field_name,
            "fileName": file_name,
            "providerCode": provider_code,
            "providerId": provider_id,
            "recordId": record_id,
            "tableSchemaName": table_schema_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/field/{field_id}/attachment"
        await self._client.download("GET", url, params=params, dest=dest)
        return None

    async def get_available_for_manual_editing_tables(
        self,
        dataset_id: int,
    ) -> list[generated.TableSchemaIdNameVO]:
        """getAvailableForManualEditingTables"""
        params = None
        url = f"/dataset/getAvailableForManualEditingTables/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return [generated.TableSchemaIdNameVO.model_validate(item) for item in response.json()]

    async def get_iceberg_tables(
        self,
        dataflow_id: int,
        dataset_id: int | None = None,
        provider_id: int | None = None,
        preparation_code: str | None = None,
    ) -> list[generated.DatasetTableVO]:
        """getIcebergTables

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "datasetId": dataset_id,
            "providerId": provider_id,
            "preparationCode": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/getIcebergTables"
        response = await self._client.request("GET", url, params=params)
        return [generated.DatasetTableVO.model_validate(item) for item in response.json()]

    async def get_import_related_statistics(
        self,
        dataset_id: int,
    ) -> dict[str, Any]:
        """getImportRelatedStatistics"""
        params = None
        url = f"/dataset/getImportRelatedStatistics/{dataset_id}"
        response = await self._client.request("GET", url, params=params)
        return cast(dict[str, Any], response.json())

    async def get_record_geometry(
        self,
        dataflow_id: int,
        dataset_id: int,
        field_id: str,
        id_table_schema: str,
        record_id: str,
        download_file: bool | None = None,
        field_name: str | None = None,
        provider_id: int | None = None,
    ) -> str:
        """getRecordGeometry"""
        params = {
            "dataflowId": dataflow_id,
            "downloadFile": download_file,
            "fieldId": field_id,
            "fieldName": field_name,
            "idTableSchema": id_table_schema,
            "providerId": provider_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/record/{record_id}/geometry"
        response = await self._client.request("GET", url, params=params)
        return response.text

    async def get_released_dataset_data_info(
        self,
        collection_dataset_id: int,
        provider_code: str,
        table_schema_id: str,
    ) -> generated.ReleasedDatasetDataInfoVO:
        """getReleasedDatasetDataInfo"""
        params = {
            "collectionDatasetId": collection_dataset_id,
            "providerCode": provider_code,
            "tableSchemaId": table_schema_id,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/getReleasedDatasetDataInfo"
        response = await self._client.request("GET", url, params=params)
        return generated.ReleasedDatasetDataInfoVO.model_validate(response.json())

    async def import_big_file_data(
        self,
        dataset_id: int,
        file: str | os.PathLike[str],
        dataflow_id: int | None = None,
        delimiter: str | None = None,
        fme_job_id: str | None = None,
        integration_id: int | None = None,
        job_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
    ) -> dict[str, Any]:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "fmeJobId": fme_job_id,
            "integrationId": integration_id,
            "jobId": job_id,
            "providerId": provider_id,
            "replace": replace,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v2/importFileData/{dataset_id}"
        with stream_upload_file("file", file) as files:
            response = await self._client.request("POST", url, params=params, files=files)
        return cast(dict[str, Any], response.json())

    async def import_file_data(
        self,
        dataset_id: int,
        file: str | os.PathLike[str],
        dataflow_id: int | None = None,
        delimiter: str | None = None,
        fme_job_id: str | None = None,
        integration_id: int | None = None,
        job_id: int | None = None,
        provider_id: int | None = None,
        replace: bool | None = None,
        table_schema_id: str | None = None,
        preparation_code: str | None = None,
    ) -> None:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD, STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD

        `preparation_code` (sent as `code`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {
            "dataflowId": dataflow_id,
            "delimiter": delimiter,
            "fmeJobId": fme_job_id,
            "integrationId": integration_id,
            "jobId": job_id,
            "providerId": provider_id,
            "replace": replace,
            "tableSchemaId": table_schema_id,
            "code": preparation_code,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/importFileData"
        with stream_upload_file("file", file) as files:
            await self._client.request("POST", url, params=params, files=files)
        return None

    async def is_iceberg_table_created(
        self,
        dataset_id: int,
        table_schema_id: str,
        preparation_code: str | None = None,
    ) -> bool:
        """isIcebergTableCreated

        `preparation_code` (sent as `preparationCode`; not in the swagger snapshot, read from the
        backend source) selects a preparation dataset instead of the regular one."""
        params = {"preparationCode": preparation_code}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/isIcebergTableCreated/{dataset_id}/{table_schema_id}"
        response = await self._client.request("GET", url, params=params)
        return cast(bool, response.json())

    async def list_imported_files(
        self,
        dataset_id: int,
    ) -> list[generated.ImportedFilesDirectoriesVO]:
        """Returns all imported files for a given dataset"""
        params = {"datasetId": dataset_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = "/dataset/list-imported-files"
        response = await self._client.request("GET", url, params=params)
        return [
            generated.ImportedFilesDirectoriesVO.model_validate(item) for item in response.json()
        ]

    async def restore_prefilled_tables(
        self,
        dataset_id: int,
        table_schema_id: str | None = None,
    ) -> None:
        """restorePrefilledTables"""
        params = {"tableSchemaId": table_schema_id}
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/restorePrefilledTables/{dataset_id}"
        await self._client.request("POST", url, params=params)
        return None

    async def update_attachment(
        self,
        dataset_id: int,
        field_id: str,
        file: str | os.PathLike[str],
        dataflow_id: int | None = None,
        field_name: str | None = None,
        previous_file_name: str | None = None,
        provider_id: int | None = None,
        record_id: str | None = None,
        table_schema_name: str | None = None,
    ) -> None:
        """Allowed roles:

        Reporting dataset: LEAD REPORTER, REPORTER WRITE, NATIONAL COORDINATOR

        Data collection: CUSTODIAN, STEWARD

        Test dataset: CUSTODIAN, STEWARD , STEWARD SUPPORT

        Reference dataset: CUSTODIAN, STEWARD

        Design dataset: CUSTODIAN, STEWARD, EDITOR WRITE

        EU dataset: CUSTODIAN, STEWARD"""
        params = {
            "dataflowId": dataflow_id,
            "fieldName": field_name,
            "previousFileName": previous_file_name,
            "providerId": provider_id,
            "recordId": record_id,
            "tableSchemaName": table_schema_name,
        }
        params = {k: v for k, v in params.items() if v is not None}
        url = f"/dataset/v1/{dataset_id}/field/{field_id}/attachment"
        with stream_upload_file("file", file) as files:
            await self._client.request("PUT", url, params=params, files=files)
        return None

    async def update_geometry(
        self,
        dataset_id: int,
    ) -> None:
        """updateGeometry"""
        params = None
        url = f"/dataset/{dataset_id}/updateGeometry"
        await self._client.request("PUT", url, params=params)
        return None

    async def update_geometry_v2(
        self,
        dataset_id: int,
    ) -> None:
        """updateGeometryV2"""
        params = None
        url = f"/dataset/v2/{dataset_id}/updateGeometry"
        await self._client.request("PUT", url, params=params)
        return None
