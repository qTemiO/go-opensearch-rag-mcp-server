"""
Thin async client for the GoOpenDB HTTP API.

Every non-2xx answer and every transport failure is turned into a `ToolError`
with an actionable message, so tools never hand an error body to the model
as if it were data.
"""

from typing import Any
from urllib.parse import quote

import httpx
from fastmcp.exceptions import ToolError
from loguru import logger

from goopendb_mcp.settings import settings


class GoOpenDBError(ToolError):
    """A GoOpenDB call failed. The message is meant to be read by the model."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def segment(value: str) -> str:
    """Escape a value used as a single URL path segment (index names, ids)."""
    return quote(value, safe="")


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:500] or response.reason_phrase

    if isinstance(body, dict):
        # GoOpenDB answers with either {"Detail": ...} or {"detail": ...}.
        for key in ("Detail", "detail", "error", "message"):
            if body.get(key):
                return str(body[key])
        return str(body)[:500]
    return str(body)[:500]


def _hint(status: int, detail: str) -> str:
    lowered = detail.lower()
    if status == 404 or "not found" in lowered:
        return "Check the id/name; use the matching list tool to discover valid values."
    if status == 409:
        return "The record conflicts with an existing one; reuse it or pick another name/id."
    if status in (400, 422):
        return "Fix the arguments mentioned above and retry."
    if status >= 500:
        return "GoOpenDB or OpenSearch failed; retry once, and if it persists report the error."
    return ""


class GoOpenDBClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform a request and return the decoded JSON body (None for empty bodies)."""
        try:
            response = await self._http.request(method, path, json=json, params=params)
        except httpx.TimeoutException as error:
            raise GoOpenDBError(
                f"GoOpenDB {method} {path} timed out. Retry, or reduce the amount "
                f"of requested data (e.g. a smaller top_k)."
            ) from error
        except httpx.HTTPError as error:
            logger.error(f"GoOpenDB transport error on {method} {path}: {error!r}")
            raise GoOpenDBError(
                f"GoOpenDB is unreachable ({type(error).__name__}). "
                f"The service may be down; retry later."
            ) from error

        if response.is_error:
            detail = _extract_detail(response)
            logger.warning(f"GoOpenDB {method} {path} -> {response.status_code}: {detail}")
            hint = _hint(response.status_code, detail)
            raise GoOpenDBError(
                f"GoOpenDB {method} {path} failed with HTTP {response.status_code}: "
                f"{detail}. {hint}".strip(),
                status=response.status_code,
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, **kwargs)


_client: GoOpenDBClient | None = None


def get_client() -> GoOpenDBClient:
    """Process-wide client: one connection pool shared by every tool call."""
    global _client
    if _client is None:
        _client = GoOpenDBClient(
            settings.GO_OPENSEARCH_DATABASE_URL,
            settings.REQUEST_TIMEOUT_SECONDS,
        )
    return _client


def set_client(client: GoOpenDBClient | None) -> None:
    """Replace the shared client (used by tests)."""
    global _client
    _client = client
