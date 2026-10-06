"""agents_* (part 1) — agents and read access to the MCP server / model provider registries."""

from typing import Annotated, Any, Literal

from loguru import logger
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from goopendb_mcp.app import mcp
from goopendb_mcp.client import GoOpenDBError, get_client, segment
from goopendb_mcp.common import Limit, NameContains, Offset, Page, Uuid, annotations, contains, paginate, preview
from goopendb_mcp.tools import _store
from goopendb_mcp.tools._store import AGENTS, MCP_SERVERS, MODEL_PROVIDERS, NODES

StrList = Annotated[list[str], BeforeValidator(lambda v: v or [])]
AgentType = Literal["orchestrator", "agent"]


class Agent(BaseModel):
    model_config = ConfigDict(extra="allow")

    uuid: str
    name: str = ""
    agent_type: str = ""
    agent_description: str = ""
    system_prompt: str = ""
    mcp_permissions: StrList = []
    mcp_server_ids: StrList = []
    model_provider_id: str | None = None
    model_name_override: str | None = None
    model: str | None = None
    agents: StrList = []


class AgentSummary(BaseModel):
    uuid: str
    name: str
    agent_type: str
    agent_description: str = Field(description="Shortened; use agents_get_agent for full text and prompt.")
    mcp_permissions: list[str]
    mcp_server_ids: list[str]
    model_provider_id: str | None
    model_name_override: str | None
    model: str | None


def summarize_agent(raw: dict[str, Any]) -> AgentSummary:
    agent = Agent.model_validate(raw)
    return AgentSummary(
        uuid=agent.uuid,
        name=agent.name,
        agent_type=agent.agent_type,
        agent_description=preview(agent.agent_description),
        mcp_permissions=agent.mcp_permissions,
        mcp_server_ids=agent.mcp_server_ids,
        model_provider_id=agent.model_provider_id or None,
        model_name_override=agent.model_name_override or None,
        model=agent.model or None,
    )


# ---------------------------------------------------------------- arguments

Name = Annotated[str, Field(min_length=1, description="Unique, descriptive name, e.g. 'DnD::Worker::Search'.")]
AgentDescription = Annotated[
    str,
    Field(min_length=1, description="What the agent is responsible for. Orchestrators read it to route work."),
]
AgentTypeArg = Annotated[
    AgentType,
    Field(description="'orchestrator' routes work between nodes (the graph INPUT node); 'agent' is a worker."),
]
SystemPrompt = Annotated[str, Field(min_length=1, description="System prompt of the agent.")]
McpPermissions = Annotated[
    list[str],
    Field(
        description=(
            "Tool-name PREFIXES the agent may call on its MCP servers (matched with startswith). "
            "E.g. ['search_'] grants all search tools, ['search_documents'] only the search tools, "
            "['descriptions_get'] read-only descriptions. Empty list = the agent has no tools."
        )
    ),
]
McpServerIds = Annotated[
    list[str],
    Field(description="Ids of MCP servers from agents_list_mcp_servers that the agent connects to."),
]
ModelProviderId = Annotated[
    str,
    Field(description="Id from agents_list_model_providers. Preferred way to choose the model."),
]
ModelNameOverride = Annotated[
    str,
    Field(description="Model from the provider's available_models; omit to use its default_model."),
]
LegacyModel = Annotated[
    str,
    Field(
        pattern=r"^(openrouter|openai)::.+",
        description="Legacy model string '<openrouter|openai>::<model>'. Ignored when model_provider_id is set.",
    ),
]
SubAgents = Annotated[
    list[str],
    Field(description="Legacy constructor-mode sub-agent uuids. Leave empty for graph agents (routing uses edges)."),
]


def _clean_prefixes(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


async def check_agent_refs(
    mcp_server_ids: list[str] | None,
    model_provider_id: str | None,
    model_name_override: str | None,
) -> None:
    """GoOpenDB accepts dangling registry references; catch them before writing."""
    if mcp_server_ids:
        servers = await _store.get_many(MCP_SERVERS, mcp_server_ids)
        missing = [i for i in mcp_server_ids if i not in servers]
        disabled = [i for i in mcp_server_ids if i in servers and not servers[i].get("enabled", True)]
        if missing:
            raise GoOpenDBError(f"Unknown mcp_server_ids {missing}. Use agents_list_mcp_servers to get valid ids.")
        if disabled:
            logger.warning(f"Agent references disabled MCP servers {disabled}")

    if model_provider_id:
        provider = await _store.get_one(MODEL_PROVIDERS, model_provider_id)
        available = provider.get("available_models") or []
        if model_name_override and available and model_name_override not in available:
            raise GoOpenDBError(
                f"Model '{model_name_override}' is not offered by provider '{provider.get('name')}'. "
                f"Available models: {available}."
            )


# ------------------------------------------------------------------- agents


@mcp.tool(name="agents_list_agents", annotations=annotations("List agents", "read"))
async def agents_list_agents(
    name_contains: NameContains = None,
    agent_type: Annotated[AgentType | None, Field(description="Optional filter by agent type.")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AgentSummary]:
    """
    List agents (compact view without system prompts), sorted by name.
    Use agents_get_agent for the full record of one agent.
    """
    agents = [
        summarize_agent(a)
        for a in await _store.list_all(AGENTS)
        if contains(a.get("name"), name_contains) and (agent_type is None or a.get("agent_type") == agent_type)
    ]
    agents.sort(key=lambda a: a.name.casefold())
    return paginate(agents, limit, offset)


@mcp.tool(name="agents_get_agent", annotations=annotations("Get agent", "read"))
async def agents_get_agent(uuid: Uuid) -> Agent:
    """Return the full agent record, including its system prompt."""
    return Agent.model_validate(await _store.get_one(AGENTS, uuid))


@mcp.tool(name="agents_get_resolved_agent", annotations=annotations("Get agent with registries resolved", "read"))
async def agents_get_resolved_agent(uuid: Uuid) -> dict[str, Any]:
    """
    Return the agent exactly as agent-constructor sees it: mcp_server_ids and
    model_provider_id expanded into full records (disabled servers dropped),
    plus `warnings` for dangling references. Use it to debug why an agent
    has no tools or the wrong model.
    """
    await _store.get_one(AGENTS, uuid)
    return await get_client().get(f"{AGENTS.item_path}/{segment(uuid)}/resolved")


@mcp.tool(name="agents_create_agent", annotations=annotations("Create agent", "create"))
async def agents_create_agent(
    name: Name,
    agent_description: AgentDescription,
    agent_type: AgentTypeArg,
    system_prompt: SystemPrompt,
    mcp_permissions: McpPermissions = [],
    mcp_server_ids: McpServerIds = [],
    model_provider_id: ModelProviderId | None = None,
    model_name_override: ModelNameOverride | None = None,
    model: LegacyModel | None = None,
    agents: SubAgents = [],
) -> Agent:
    """
    Create an agent and return it with its new uuid.

    Choose the model with model_provider_id (+ optional model_name_override)
    from agents_list_model_providers; registry references are validated.
    Give tool access with mcp_server_ids + mcp_permissions. In a graph, every
    role is its own agent, referenced by a node via agent_id.
    """
    if not model_provider_id and not model:
        raise GoOpenDBError("Set model_provider_id (see agents_list_model_providers) or the legacy model string.")
    await check_agent_refs(mcp_server_ids, model_provider_id, model_name_override)
    logger.info(f"agents_create_agent name={name}")
    payload = _store.drop_none({
        "name": name,
        "agent_description": agent_description,
        "agent_type": agent_type,
        "system_prompt": system_prompt,
        "mcp_permissions": _clean_prefixes(mcp_permissions),
        "mcp_server_ids": mcp_server_ids,
        "model_provider_id": model_provider_id,
        "model_name_override": model_name_override,
        "model": model,
        "agents": agents,
    })
    return Agent.model_validate(await _store.create(AGENTS, payload))


@mcp.tool(name="agents_update_agent", annotations=annotations("Replace agent", "update"))
async def agents_update_agent(
    uuid: Uuid,
    name: Name,
    agent_description: AgentDescription,
    agent_type: AgentTypeArg,
    system_prompt: SystemPrompt,
    mcp_permissions: McpPermissions = [],
    mcp_server_ids: Annotated[
        list[str] | None, Field(description="New MCP server ids; omit to keep, [] to clear.")
    ] = None,
    model_provider_id: Annotated[
        str | None, Field(description="New provider id; omit to keep, '' to unlink.")
    ] = None,
    model_name_override: Annotated[
        str | None, Field(description="New model override; omit to keep, '' to use the provider default.")
    ] = None,
    model: LegacyModel | None = None,
    agents: SubAgents = [],
) -> Agent:
    """
    Replace all plain fields of an agent (fields not given are reset to their
    defaults). Registry references are kept unless given. Prefer
    agents_patch_agent to change a few fields.
    """
    await check_agent_refs(mcp_server_ids, model_provider_id, model_name_override)
    payload = _store.drop_none({
        "name": name,
        "agent_description": agent_description,
        "agent_type": agent_type,
        "system_prompt": system_prompt,
        "mcp_permissions": _clean_prefixes(mcp_permissions),
        "mcp_server_ids": mcp_server_ids,
        "model_provider_id": model_provider_id,
        "model_name_override": model_name_override,
        "model": model or "",
        "agents": agents,
    })
    return Agent.model_validate(await _store.update(AGENTS, uuid, payload, partial=False))


@mcp.tool(name="agents_patch_agent", annotations=annotations("Update agent fields", "update"))
async def agents_patch_agent(
    uuid: Uuid,
    name: Name | None = None,
    agent_description: AgentDescription | None = None,
    agent_type: AgentTypeArg | None = None,
    system_prompt: SystemPrompt | None = None,
    mcp_permissions: McpPermissions | None = None,
    mcp_server_ids: McpServerIds | None = None,
    model_provider_id: Annotated[str | None, Field(description="Provider id, '' to unlink.")] = None,
    model_name_override: Annotated[str | None, Field(description="Model override, '' to clear.")] = None,
    model: LegacyModel | None = None,
    agents: SubAgents | None = None,
) -> Agent:
    """Change only the given fields of an agent and return the updated agent."""
    payload = _store.drop_none({
        "name": name,
        "agent_description": agent_description,
        "agent_type": agent_type,
        "system_prompt": system_prompt,
        "mcp_permissions": _clean_prefixes(mcp_permissions),
        "mcp_server_ids": mcp_server_ids,
        "model_provider_id": model_provider_id,
        "model_name_override": model_name_override,
        "model": model,
        "agents": agents,
    })
    if not payload:
        raise GoOpenDBError("Nothing to change: pass at least one field besides uuid.")
    await check_agent_refs(mcp_server_ids, model_provider_id, model_name_override)
    return Agent.model_validate(await _store.update(AGENTS, uuid, payload, partial=True))


@mcp.tool(name="agents_delete_agent", annotations=annotations("Delete agent", "delete"))
async def agents_delete_agent(
    uuid: Uuid,
    force: Annotated[bool, Field(description="Delete even if nodes still use this agent.")] = False,
) -> str:
    """
    Delete an agent. Refuses if nodes still reference it (they would break
    their graphs) unless force=true.
    """
    users = [n for n in await _store.list_all(NODES) if n.get("agent_id") == uuid]
    if users and not force:
        names = [f"{n.get('name')} ({n.get('id')})" for n in users]
        raise GoOpenDBError(
            f"Agent '{uuid}' is used by nodes {names}. Delete or re-point those nodes first, or pass force=true."
        )
    await _store.delete(AGENTS, uuid)
    return f"Agent '{uuid}' deleted."


# --------------------------------------------------------- registries (read)


def _registry_filters(enabled: bool | None, name: str | None) -> dict[str, str]:
    params: dict[str, str] = {}
    if enabled is not None:
        params["enabled"] = "true" if enabled else "false"
    if name:
        params["name"] = name
    return params


@mcp.tool(name="agents_list_mcp_servers", annotations=annotations("List MCP servers", "read"))
async def agents_list_mcp_servers(
    enabled: Annotated[bool | None, Field(description="Filter by enabled flag; omit for all.")] = None,
    name: Annotated[str | None, Field(description="Exact name filter.")] = None,
) -> list[dict[str, Any]]:
    """
    List MCP servers registered for agents. An agent connects to the servers
    in its mcp_server_ids; secrets are never returned (only env var names).
    """
    return await _store.list_all(MCP_SERVERS, _registry_filters(enabled, name))


@mcp.tool(name="agents_get_mcp_server", annotations=annotations("Get MCP server", "read"))
async def agents_get_mcp_server(id: Annotated[str, Field(min_length=1, description="MCP server id.")]) -> dict[str, Any]:
    """Return one MCP server registry record (url, transport, auth settings, enabled flag)."""
    return await _store.get_one(MCP_SERVERS, id)


@mcp.tool(name="agents_list_model_providers", annotations=annotations("List model providers", "read"))
async def agents_list_model_providers(
    enabled: Annotated[bool | None, Field(description="Filter by enabled flag; omit for all.")] = None,
    name: Annotated[str | None, Field(description="Exact name filter.")] = None,
) -> list[dict[str, Any]]:
    """
    List LLM providers. Use an `id` as an agent's model_provider_id and,
    optionally, one of its `available_models` as model_name_override.
    """
    return await _store.list_all(MODEL_PROVIDERS, _registry_filters(enabled, name))


@mcp.tool(name="agents_get_model_provider", annotations=annotations("Get model provider", "read"))
async def agents_get_model_provider(
    id: Annotated[str, Field(min_length=1, description="Model provider id.")],
) -> dict[str, Any]:
    """Return one model provider registry record (type, default and available models)."""
    return await _store.get_one(MODEL_PROVIDERS, id)
