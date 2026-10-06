"""registry_* — write access to the MCP server and model provider registries."""

from typing import Annotated, Any, Literal

from loguru import logger
from pydantic import Field

from goopendb_mcp.app import mcp
from goopendb_mcp.client import GoOpenDBError, get_client, segment
from goopendb_mcp.common import annotations
from goopendb_mcp.tools import _store
from goopendb_mcp.tools._store import MCP_SERVERS, MODEL_PROVIDERS

RecordId = Annotated[str, Field(min_length=1, description="Registry record id.")]
EnvVar = Annotated[
    str,
    Field(pattern=r"^[A-Z][A-Z0-9_]*$", description="NAME of the environment variable holding the secret, never the secret itself."),
]
Force = Annotated[
    bool,
    Field(description="If agents still reference the record, detach it from them and delete anyway."),
]

# ------------------------------------------------------------- MCP servers

ServerName = Annotated[str, Field(min_length=1, description="Unique name among enabled servers.")]
ServerUrl = Annotated[str, Field(pattern=r"^https?://.+", description="Absolute http(s) URL, e.g. 'http://mcp-1c:8000/mcp'.")]
Transport = Annotated[Literal["streamable_http", "sse", "stdio"], Field(description="MCP transport.")]
AuthType = Annotated[
    Literal["none", "bearer", "header"],
    Field(description="'bearer' sends Authorization: Bearer <secret>; 'header' sends <auth_header_name>: <secret>."),
]
Headers = Annotated[dict[str, str], Field(description="Static, non-secret headers sent with every request.")]
Timeout = Annotated[int, Field(ge=1, le=3600, description="Request timeout in seconds.")]


def _check_auth(auth_type: str | None, auth_env_var: str | None, auth_header_name: str | None) -> None:
    if auth_type in ("bearer", "header") and not auth_env_var:
        raise GoOpenDBError(f"auth_type '{auth_type}' requires auth_env_var.")
    if auth_type == "header" and not auth_header_name:
        raise GoOpenDBError("auth_type 'header' requires auth_header_name.")


async def _delete_with_conflict(collection: _store.Collection, record_id: str, force: bool) -> str:
    await _store.get_one(collection, record_id)
    try:
        await get_client().delete(
            f"{collection.item_path}/{segment(record_id)}",
            params={"force": "true"} if force else None,
        )
    except GoOpenDBError as error:
        if error.status == 409:
            raise GoOpenDBError(
                f"The {collection.label} '{record_id}' is still referenced by agents. "
                f"Re-point those agents first, or pass force=true to detach it from them."
            ) from error
        raise
    return f"{collection.label.capitalize()} '{record_id}' deleted."


@mcp.tool(name="registry_create_mcp_server", annotations=annotations("Register MCP server", "create"))
async def registry_create_mcp_server(
    name: ServerName,
    url: ServerUrl,
    description: Annotated[str, Field(description="What the server provides.")] = "",
    transport: Transport = "streamable_http",
    auth_type: AuthType = "none",
    auth_env_var: EnvVar | None = None,
    auth_header_name: Annotated[str | None, Field(description="Header name for auth_type 'header'.")] = None,
    headers: Headers = {},
    timeout_seconds: Timeout = 30,
    enabled: bool = True,
) -> dict[str, Any]:
    """Register an MCP server that agents can reference in mcp_server_ids. Returns the record with its id."""
    _check_auth(auth_type, auth_env_var, auth_header_name)
    logger.info(f"registry_create_mcp_server name={name}")
    data = await get_client().post(
        MCP_SERVERS.item_path,
        json=_store.drop_none({
            "name": name, "url": url, "description": description, "transport": transport,
            "auth_type": auth_type, "auth_env_var": auth_env_var, "auth_header_name": auth_header_name,
            "headers": headers, "timeout_seconds": timeout_seconds, "enabled": enabled,
        }),
    )
    return (data or {}).get(MCP_SERVERS.item_key) or data


@mcp.tool(name="registry_update_mcp_server", annotations=annotations("Update MCP server", "update"))
async def registry_update_mcp_server(
    id: RecordId,
    name: ServerName | None = None,
    url: ServerUrl | None = None,
    description: str | None = None,
    transport: Transport | None = None,
    auth_type: AuthType | None = None,
    auth_env_var: EnvVar | None = None,
    auth_header_name: str | None = None,
    headers: Headers | None = None,
    timeout_seconds: Timeout | None = None,
    enabled: Annotated[bool | None, Field(description="false hides the server from agents without deleting it.")] = None,
) -> dict[str, Any]:
    """Change only the given fields of a registered MCP server."""
    payload = _store.drop_none({
        "name": name, "url": url, "description": description, "transport": transport,
        "auth_type": auth_type, "auth_env_var": auth_env_var, "auth_header_name": auth_header_name,
        "headers": headers, "timeout_seconds": timeout_seconds, "enabled": enabled,
    })
    if not payload:
        raise GoOpenDBError("Nothing to change: pass at least one field besides id.")
    return await _store.update(MCP_SERVERS, id, payload, partial=True)


@mcp.tool(name="registry_delete_mcp_server", annotations=annotations("Delete MCP server", "delete"))
async def registry_delete_mcp_server(id: RecordId, force: Force = False) -> str:
    """Delete a registered MCP server. Fails while agents reference it unless force=true."""
    return await _delete_with_conflict(MCP_SERVERS, id, force)


# --------------------------------------------------------- model providers

ProviderName = Annotated[str, Field(min_length=1, description="Unique name among enabled providers.")]
ProviderType = Annotated[Literal["openrouter", "openai", "local"], Field(description="Provider API flavour.")]
BaseUrl = Annotated[str, Field(description="OpenAI-compatible base URL, e.g. 'http://vllm:8000/v1'. May be empty for openrouter/openai.")]
Models = Annotated[list[str], Field(description="Models agents may pick via model_name_override.")]
ExtraParams = Annotated[dict[str, Any], Field(description="Extra parameters passed to the model client, e.g. {'temperature': 0.2}.")]


@mcp.tool(name="registry_create_model_provider", annotations=annotations("Register model provider", "create"))
async def registry_create_model_provider(
    name: ProviderName,
    provider_type: ProviderType,
    default_model: Annotated[str, Field(min_length=1, description="Model used when an agent sets no override.")],
    api_key_env_var: EnvVar,
    base_url: BaseUrl = "",
    available_models: Models = [],
    extra_params: ExtraParams = {},
    enabled: bool = True,
) -> dict[str, Any]:
    """Register an LLM provider that agents can reference as model_provider_id. Returns the record with its id."""
    logger.info(f"registry_create_model_provider name={name}")
    models = list(dict.fromkeys([default_model, *available_models]))
    data = await get_client().post(
        MODEL_PROVIDERS.item_path,
        json={
            "name": name, "provider_type": provider_type, "default_model": default_model,
            "api_key_env_var": api_key_env_var, "base_url": base_url, "available_models": models,
            "extra_params": extra_params, "enabled": enabled,
        },
    )
    return (data or {}).get(MODEL_PROVIDERS.item_key) or data


@mcp.tool(name="registry_update_model_provider", annotations=annotations("Update model provider", "update"))
async def registry_update_model_provider(
    id: RecordId,
    name: ProviderName | None = None,
    provider_type: ProviderType | None = None,
    default_model: str | None = None,
    api_key_env_var: EnvVar | None = None,
    base_url: str | None = None,
    available_models: Annotated[list[str] | None, Field(description="New complete list of models.")] = None,
    extra_params: ExtraParams | None = None,
    enabled: Annotated[bool | None, Field(description="false hides the provider from agents without deleting it.")] = None,
) -> dict[str, Any]:
    """Change only the given fields of a registered model provider."""
    payload = _store.drop_none({
        "name": name, "provider_type": provider_type, "default_model": default_model,
        "api_key_env_var": api_key_env_var, "base_url": base_url, "available_models": available_models,
        "extra_params": extra_params, "enabled": enabled,
    })
    if not payload:
        raise GoOpenDBError("Nothing to change: pass at least one field besides id.")
    return await _store.update(MODEL_PROVIDERS, id, payload, partial=True)


@mcp.tool(name="registry_delete_model_provider", annotations=annotations("Delete model provider", "delete"))
async def registry_delete_model_provider(id: RecordId, force: Force = False) -> str:
    """Delete a registered model provider. Fails while agents reference it unless force=true."""
    return await _delete_with_conflict(MODEL_PROVIDERS, id, force)
