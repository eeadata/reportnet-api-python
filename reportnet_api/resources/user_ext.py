"""Hand-written User resource (login-token refresh).

The UserManagement tag is absent from spec/api-docs.json ("Known
spec-snapshot gap"), and `/user/refreshToken` is `@ApiOperation(hidden =
true)` in `UserManagementControllerImpl` (`user-management-service`). This
file is never touched by the generators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..async_client import AsyncReportnetClient
    from ..client import ReportnetClient

_REFRESH_PATH = "/user/refreshToken"


class UserResource:
    def __init__(self, client: ReportnetClient) -> None:
        self._client = client

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """POST /user/refreshToken: renew a web-app login.

        `refresh_token` is the refresh token (a JWT) issued together with the
        login, not the UUID `accessToken`. Returns the `TokenVO` dict: a new UUID
        `accessToken` (Reportnet's cache key for the fresh JWT), a new
        `refreshToken` (use it for the next refresh), `accessTokenExpiration`,
        `preferredUsername`, `userId`, `roles`, `groups`.

        The route has no auth rule (the web app calls it after a 401, with
        its expired token), so the client's own credential doesn't matter.
        """
        response = self._client.request(
            "POST", _REFRESH_PATH, params={"refreshToken": refresh_token}
        )
        result: dict[str, Any] = response.json()
        return result


class AsyncUserResource:
    def __init__(self, client: AsyncReportnetClient) -> None:
        self._client = client

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Async counterpart of UserResource.refresh_token."""
        response = await self._client.request(
            "POST", _REFRESH_PATH, params={"refreshToken": refresh_token}
        )
        result: dict[str, Any] = response.json()
        return result
