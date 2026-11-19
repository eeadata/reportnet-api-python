# Generated from spec/api-docs.json by scripts/generate_resources.py.
# Do not edit by hand.

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import generated

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient


class ReleaseReceiptsResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def create_release_receipt(
        self,
        release_receipt_vo: generated.ReleaseReceiptVO,
    ) -> generated.ReleaseReceiptVO:
        """createReleaseReceipt"""
        params = None
        url = "/release-receipts"
        response = self._client.request(
            "POST",
            url,
            params=params,
            json=release_receipt_vo.model_dump(mode="json", exclude_none=True),
        )
        return generated.ReleaseReceiptVO.model_validate(response.json())

    def delete_release_receipt_by_dataflow_id(
        self,
        dataflow_id: int,
    ) -> None:
        """deleteReleaseReceiptByDataflowId"""
        params = None
        url = f"/release-receipts/dataflow/{dataflow_id}"
        self._client.request("DELETE", url, params=params)

    def get_release_receipt_by_dataflow_id(
        self,
        dataflow_id: int,
    ) -> generated.ReleaseReceiptVO:
        """getReleaseReceiptByDataflowId"""
        params = None
        url = f"/release-receipts/dataflow/{dataflow_id}"
        response = self._client.request("GET", url, params=params)
        return generated.ReleaseReceiptVO.model_validate(response.json())

    def update_release_receipt(
        self,
        release_receipt_vo: generated.ReleaseReceiptVO,
    ) -> generated.ReleaseReceiptVO:
        """updateReleaseReceipt"""
        params = None
        url = "/release-receipts"
        response = self._client.request(
            "PUT",
            url,
            params=params,
            json=release_receipt_vo.model_dump(mode="json", exclude_none=True),
        )
        return generated.ReleaseReceiptVO.model_validate(response.json())


class AsyncReleaseReceiptsResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def create_release_receipt(
        self,
        release_receipt_vo: generated.ReleaseReceiptVO,
    ) -> generated.ReleaseReceiptVO:
        """createReleaseReceipt"""
        params = None
        url = "/release-receipts"
        response = await self._client.request(
            "POST",
            url,
            params=params,
            json=release_receipt_vo.model_dump(mode="json", exclude_none=True),
        )
        return generated.ReleaseReceiptVO.model_validate(response.json())

    async def delete_release_receipt_by_dataflow_id(
        self,
        dataflow_id: int,
    ) -> None:
        """deleteReleaseReceiptByDataflowId"""
        params = None
        url = f"/release-receipts/dataflow/{dataflow_id}"
        await self._client.request("DELETE", url, params=params)

    async def get_release_receipt_by_dataflow_id(
        self,
        dataflow_id: int,
    ) -> generated.ReleaseReceiptVO:
        """getReleaseReceiptByDataflowId"""
        params = None
        url = f"/release-receipts/dataflow/{dataflow_id}"
        response = await self._client.request("GET", url, params=params)
        return generated.ReleaseReceiptVO.model_validate(response.json())

    async def update_release_receipt(
        self,
        release_receipt_vo: generated.ReleaseReceiptVO,
    ) -> generated.ReleaseReceiptVO:
        """updateReleaseReceipt"""
        params = None
        url = "/release-receipts"
        response = await self._client.request(
            "PUT",
            url,
            params=params,
            json=release_receipt_vo.model_dump(mode="json", exclude_none=True),
        )
        return generated.ReleaseReceiptVO.model_validate(response.json())
