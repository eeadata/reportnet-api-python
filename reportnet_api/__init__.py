from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from ._core import RetryPolicy
from ._exceptions import (
    AuthenticationError,
    ForbiddenError,
    LockedError,
    NotFoundError,
    ReportnetAPIError,
    ServerError,
    TooManyRequestsError,
    ValidationError,
)
from .async_client import AsyncReportnetClient
from .client import ReportnetClient
from .discover import find

try:
    __version__ = _version("reportnet-api")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0+unknown"

__all__ = [
    "AsyncReportnetClient",
    "AuthenticationError",
    "ForbiddenError",
    "LockedError",
    "NotFoundError",
    "ReportnetAPIError",
    "ReportnetClient",
    "RetryPolicy",
    "ServerError",
    "TooManyRequestsError",
    "ValidationError",
    "__version__",
    "find",
]
