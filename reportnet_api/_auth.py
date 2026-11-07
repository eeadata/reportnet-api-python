from __future__ import annotations

from collections.abc import Callable

TokenLike = str | Callable[[], str]


class TokenProvider:
    """Wraps a static token/key string or a zero-arg callable that returns one.

    `scheme` is the `Authorization` header scheme, e.g. `"Bearer"` for a JWT
    or `"ApiKey"` for a Reportnet dataflow-scoped API key — the API uses
    different schemes for different credential types.
    """

    def __init__(self, token: TokenLike, scheme: str = "Bearer") -> None:
        self._token = token
        self._scheme = scheme

    @property
    def scheme(self) -> str:
        return self._scheme

    def get_token(self) -> str:
        if callable(self._token):
            return self._token()
        return self._token

    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"{self._scheme} {self.get_token()}"}
