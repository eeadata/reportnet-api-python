from __future__ import annotations

import json
import math
import re
from http import HTTPStatus

import httpx


class ReportnetAPIError(Exception):
    """Base exception for all Reportnet API errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: str,
        request: httpx.Request,
        response: httpx.Response,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.request = request
        self.response = response

    def explain(self) -> str:
        """A few plain-language lines: what happened, the likely cause, what to try.

        Built from the status, the Authorization scheme used and the server's
        message, including patterns seen live. Heuristic: the cause is the most
        likely one, not a certainty.
        """
        return "\n".join(_explain(self))


class ValidationError(ReportnetAPIError):
    """400 / 422 — request rejected as invalid."""


class AuthenticationError(ReportnetAPIError):
    """401 — missing or invalid credentials."""


class ForbiddenError(ReportnetAPIError):
    """403 — authenticated but not authorized for this operation."""


class NotFoundError(ReportnetAPIError):
    """404 — resource does not exist."""


class LockedError(ReportnetAPIError):
    """423 — another operation holds a lock on the dataflow or dataset."""


class TooManyRequestsError(ReportnetAPIError):
    """429 — too many requests."""

    @property
    def retry_after(self) -> float | None:
        """Seconds from a numeric `Retry-After` header, or None if absent or not a finite number."""
        try:
            seconds = float(self.response.headers["Retry-After"])
        except (KeyError, ValueError):
            return None
        return seconds if math.isfinite(seconds) else None


class ServerError(ReportnetAPIError):
    """5xx — server-side failure."""


_STATUS_EXCEPTIONS: dict[int, type[ReportnetAPIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    422: ValidationError,
    423: LockedError,
    429: TooManyRequestsError,
}


_APIKEY_HINT = (
    "ApiKey credentials are Reporter-level only and only work for the dataflow "
    "they were issued for; Custodian/Steward-gated endpoints need a Bearer JWT "
    "for a user holding that role"
)
_BEARER_FORBIDDEN_HINT = (
    "check that this user holds the required role (e.g. Custodian/Steward) on "
    "this dataflow; some endpoints (e.g. the ETL family) are gated separately "
    "from roles and can 403 even when the role is correct"
)
_BEARER_401_HINT = "the Bearer token may have expired or be invalid; get a fresh one"
_APIKEY_401_HINT = "check that the ApiKey is correct and has not been revoked"
_LOCKED_HINT = (
    "another operation (for example an import job still QUEUED or IN_PROGRESS for this "
    "dataset, or a clone or snapshot job) holds a lock on this dataflow or dataset; "
    "wait for it to finish and try again"
)
_TOO_MANY_HINT = (
    "slow down and retry later (see `retry_after` on the exception); the Reportnet "
    "backend itself sets no rate limit, so this likely comes from infrastructure in "
    "front of the API"
)


def _hint(response: httpx.Response) -> str | None:
    """Short tip for 401/403 (tailored to the Authorization scheme used), 423 and 429."""
    if response.status_code == HTTPStatus.LOCKED:
        return _LOCKED_HINT
    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return _TOO_MANY_HINT
    if response.status_code not in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        return None
    scheme = response.request.headers.get("Authorization", "").split(" ", 1)[0].lower()
    if response.status_code == HTTPStatus.UNAUTHORIZED:
        return _APIKEY_401_HINT if scheme == "apikey" else _BEARER_401_HINT
    return _APIKEY_HINT if scheme == "apikey" else _BEARER_FORBIDDEN_HINT


_REASON_MAX = 200


def _server_reason(response: httpx.Response) -> str | None:
    """Server's JSON `message` (truncated), else a short plain-text snippet.

    Only the first JSON object is read: a dead ApiKey gets two objects glued
    together. An HTML body (gateway error page) gives nothing; it stays on
    `.response_body`.
    """
    text = response.text.strip()
    if not text:
        return None
    try:
        body, _ = json.JSONDecoder().raw_decode(text)
    except ValueError:
        if "<" in text:
            return None
        reason = re.sub(r"\s+", " ", text)
    else:
        message = body.get("message") if isinstance(body, dict) else None
        if not isinstance(message, str) or not message.strip():
            return None
        reason = re.sub(r"\s+", " ", message.strip())
    if len(reason) > _REASON_MAX:
        reason = reason[:_REASON_MAX] + "..."
    return reason


def _is_rejected_credential_500(body: str) -> bool:
    """Live bodies of a rejected credential answered as HTTP 500 (2026-10-26).

    `/dataflow/v1/{id}` says "401 UNAUTHORIZED"; the listing route says "Access
    is denied". A Bearer token sent as `ApiKey` gets the same answer.
    """
    return "401 UNAUTHORIZED" in body or "Access is denied" in body


def _explain(err: ReportnetAPIError) -> list[str]:
    status = err.status_code
    request = err.request
    scheme = request.headers.get("Authorization", "").split(" ", 1)[0].lower()
    path = request.url.path
    reason = _server_reason(err.response)
    lines = [f"{request.method} {path} failed with HTTP {status}."]
    if reason:
        lines.append(f"The server said: {reason}")
    if status == HTTPStatus.INTERNAL_SERVER_ERROR and _is_rejected_credential_500(
        err.response_body
    ):
        lines.append(
            "Likely cause: the credential was rejected upstream (a revoked or expired ApiKey "
            "shows up as a 500 like this, even for plain reads), or it was sent with the "
            "wrong scheme."
        )
        lines.append(
            "Try: regenerate the ApiKey in the dataflow's Settings, or get a fresh Bearer token. "
            "A Bearer token sent as an ApiKey fails the same way: Bearer tokens are bare "
            'UUIDs here, not JWTs, so connect(token, scheme="Bearer").'
        )
    elif (
        status == HTTPStatus.INTERNAL_SERVER_ERROR and "accessReferenceEntity" in err.response_body
    ):
        lines.append(
            "Likely cause: the dataflow id does not exist, or is not visible to this "
            "credential (the gateway reports this as a 500, not a 404)."
        )
        lines.append("Try: check the dataflow id (list_dataflows) and that it is not a dataset id.")
    elif status == HTTPStatus.LOCKED:
        lines.append(
            "Likely cause: another operation (often an import job still QUEUED or "
            "IN_PROGRESS) holds a lock on this dataset or dataflow; the server's own text "
            "can be vague."
        )
        lines.append("Try: wait for that job to finish (see wait_for_job), then repeat the call.")
    elif status == HTTPStatus.FORBIDDEN and scheme == "bearer" and "/etl" in path:
        lines.append(
            "Likely cause: the ETL endpoints are gated separately from dataflow roles; a "
            "Bearer user can get 403 here even as Custodian/Steward."
        )
        lines.append("Try: use a dataflow ApiKey for ETL calls, or ask the dataflow admins.")
    elif status == HTTPStatus.FORBIDDEN and scheme == "apikey":
        lines.append(
            "Likely cause: ApiKeys are Reporter-level and work only for the dataflow they "
            "were issued for, so Custodian/Steward-only routes refuse them."
        )
        lines.append("Try: use a Bearer token of a user holding that role on this dataflow.")
    elif (hint := _hint(err.response)) is not None:
        lines.append(f"Hint: {hint}.")
    elif status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        lines.append("Likely cause: a server-side failure; the request itself may be fine.")
        lines.append("Try: check the server's message above, then retry later.")
    elif status == HTTPStatus.NOT_FOUND:
        lines.append("Likely cause: the id in the request does not exist for this credential.")
        lines.append("Try: check dataflow and dataset ids are not mixed up.")
    elif status in (400, 422):
        lines.append("Likely cause: a parameter was missing or invalid.")
        lines.append("Try: compare the arguments with the method's docstring.")
    return lines


def error_for_response(response: httpx.Response) -> ReportnetAPIError | None:
    """Return the exception matching `response`'s status, or None if successful."""
    if response.is_success:
        return None

    exc_cls = _STATUS_EXCEPTIONS.get(response.status_code)
    if exc_cls is None and response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        exc_cls = ServerError
    if exc_cls is None:
        exc_cls = ReportnetAPIError

    message = f"{response.request.method} {response.request.url} -> {response.status_code}"
    reason = _server_reason(response)
    if reason:
        message += f": {reason}"
    hint = _hint(response)
    if hint:
        message += f" (hint: {hint})"
    return exc_cls(
        message,
        status_code=response.status_code,
        response_body=response.text,
        request=response.request,
        response=response,
    )
