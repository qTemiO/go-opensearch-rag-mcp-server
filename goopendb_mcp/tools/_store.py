"""
Shared CRUD plumbing for the agent-constructor collections
(agents, nodes, edges, graphs) and the two registries.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from goopendb_mcp.client import GoOpenDBError, get_client, segment


@dataclass(frozen=True)
class Collection:
    label: str
    list_path: str
    list_key: str
    item_path: str
    item_key: str
    id_key: str
    list_tool: str


AGENTS = Collection("agent", "/api/v1/agents/agents", "agents", "/api/v1/agents/agent", "agent", "uuid", "agents_list_agents")
NODES = Collection("node", "/api/v1/agents/nodes", "nodes", "/api/v1/agents/node", "node", "id", "agents_list_nodes")
EDGES = Collection("edge", "/api/v1/agents/edges", "edges", "/api/v1/agents/edge", "edge", "id", "agents_list_edges")
GRAPHS = Collection("graph", "/api/v1/agents/graphs", "graphs", "/api/v1/agents/graph", "graph", "id", "agents_list_graphs")
MCP_SERVERS = Collection(
    "MCP server", "/api/v1/mcp-servers/mcp-servers", "mcp_servers",
    "/api/v1/mcp-servers/mcp-server", "mcp_server", "id", "agents_list_mcp_servers",
)
MODEL_PROVIDERS = Collection(
    "model provider", "/api/v1/model-providers/model-providers", "model_providers",
    "/api/v1/model-providers/model-provider", "model_provider", "id", "agents_list_model_providers",
)

# Writes are not refreshed in OpenSearch, so a new record shows up in list
# results only after the next refresh (1s by default).
DISCOVERY_DELAYS = (0.3, 0.5, 1.0, 1.5, 2.0)


async def list_all(collection: Collection, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = await get_client().get(collection.list_path, params=params)
    return list((data or {}).get(collection.list_key) or [])


async def get_one(collection: Collection, record_id: str) -> dict[str, Any]:
    try:
        data = await get_client().get(f"{collection.item_path}/{segment(record_id)}")
    except GoOpenDBError as error:
        if error.status == 404 or "not found" in str(error).lower():
            raise GoOpenDBError(
                f"No {collection.label} with id '{record_id}'. Use {collection.list_tool} to find valid ids.",
                status=404,
            ) from error
        raise
    record = (data or {}).get(collection.item_key)
    if not record:
        raise GoOpenDBError(
            f"No {collection.label} with id '{record_id}'. Use {collection.list_tool} to find valid ids.",
            status=404,
        )
    return record


async def get_many(collection: Collection, record_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Map id -> record for the requested ids using a single list call."""
    wanted = set(record_ids)
    return {r[collection.id_key]: r for r in await list_all(collection) if r.get(collection.id_key) in wanted}


async def create(collection: Collection, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Create a record and return it with its generated id.

    GoOpenDB answers create calls with a bare "Written successfully", so the
    new id is found by diffing the list before and after the write.
    """
    before = {r.get(collection.id_key) for r in await list_all(collection)}
    await get_client().post(collection.item_path, json=payload)

    for delay in DISCOVERY_DELAYS:
        await asyncio.sleep(delay)
        fresh = [
            r for r in await list_all(collection)
            if r.get(collection.id_key) not in before and r.get("name") == payload.get("name")
        ]
        if fresh:
            exact = [r for r in fresh if all(r.get(k) == v for k, v in payload.items())]
            return (exact or fresh)[-1]

    raise GoOpenDBError(
        f"The {collection.label} '{payload.get('name')}' was written, but its id is not visible yet. "
        f"Do not create it again: find it with {collection.list_tool}(name_contains=...)."
    )


async def update(collection: Collection, record_id: str, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    """PUT or PATCH a record that is known to exist, then return its new state."""
    await get_one(collection, record_id)
    method = get_client().patch if partial else get_client().put
    data = await method(f"{collection.item_path}/{segment(record_id)}", json=payload)
    if isinstance(data, dict) and data.get("is_updated") is False:
        raise GoOpenDBError(f"GoOpenDB did not update {collection.label} '{record_id}'. Retry or check the service logs.")
    if collection.item_key in (data or {}):
        return data[collection.item_key]
    return await get_one(collection, record_id)


async def delete(collection: Collection, record_id: str, params: dict[str, Any] | None = None) -> None:
    await get_one(collection, record_id)
    data = await get_client().delete(f"{collection.item_path}/{segment(record_id)}", params=params)
    if isinstance(data, dict) and data.get("is_deleted") is False:
        raise GoOpenDBError(f"GoOpenDB did not delete {collection.label} '{record_id}'. Retry or check the service logs.")


def drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if v is not None}
