"""agents_* (part 2) — nodes, edges and graphs of agent-constructor."""

import asyncio
from collections import deque
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from goopendb_mcp.client import GoOpenDBError
from goopendb_mcp.app import mcp
from goopendb_mcp.common import Limit, NameContains, Offset, Page, Uuid, annotations, contains, paginate, preview
from goopendb_mcp.tools import _store
from goopendb_mcp.tools._store import AGENTS, EDGES, GRAPHS, NODES
from goopendb_mcp.tools.agents import AgentSummary, summarize_agent

NodeType = Literal["INPUT", "CUSTOM", "OUTPUT"]


class Node(BaseModel):
    id: str
    name: str = ""
    agent_id: str = ""
    type: str = ""
    description: str = ""


class NodeSummary(BaseModel):
    id: str
    name: str
    agent_id: str
    type: str


class Edge(BaseModel):
    id: str
    name: str
    from_node_id: str
    to_node_id: str


class Ref(BaseModel):
    id: str
    name: str


class Graph(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    nodes: list[Ref] = []
    edges: list[Ref] = []


class GraphSummary(BaseModel):
    id: str
    name: str
    description: str
    node_count: int
    edge_count: int


class FullGraph(BaseModel):
    graph: Graph
    nodes: list[Node]
    edges: list[Edge]
    agents: list[AgentSummary] = Field(description="Agents used by the graph's nodes.")
    missing: list[str] = Field(description="References that point to deleted records.")


class GraphReport(BaseModel):
    valid: bool = Field(description="True when agent-constructor will accept the graph.")
    errors: list[str] = Field(description="Problems that make agent-constructor reject or break the graph.")
    warnings: list[str] = Field(description="Likely mistakes that do not block execution.")


def to_edge(raw: dict[str, Any]) -> Edge:
    return Edge(id=raw["id"], name=raw.get("name", ""), from_node_id=raw.get("from", ""), to_node_id=raw.get("to", ""))


def to_graph(raw: dict[str, Any]) -> Graph:
    return Graph(
        id=raw["id"],
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        nodes=[Ref.model_validate(r) for r in raw.get("nodes") or []],
        edges=[Ref.model_validate(r) for r in raw.get("edges") or []],
    )


# -------------------------------------------------------------------- nodes

NodeName = Annotated[str, Field(min_length=1, description="Unique, descriptive node name.")]
NodeAgentId = Annotated[str, Field(min_length=1, description="uuid of the agent this node runs.")]
NodeDescription = Annotated[
    str,
    Field(
        min_length=1,
        description="What the node does. Orchestrators see it when choosing the next node; often the agent's role summary.",
    ),
]
NodeTypeArg = Annotated[
    NodeType,
    Field(description="INPUT: the single entry node (an orchestrator). CUSTOM: worker. OUTPUT: produces the final answer."),
]


@mcp.tool(name="agents_list_nodes", annotations=annotations("List nodes", "read"))
async def agents_list_nodes(
    name_contains: NameContains = None,
    agent_id: Annotated[str | None, Field(description="Only nodes running this agent.")] = None,
    type: Annotated[NodeType | None, Field(description="Only nodes of this type.")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[NodeSummary]:
    """List nodes (without descriptions), sorted by name. Use agents_get_node for the full node."""
    nodes = [
        NodeSummary(id=n["id"], name=n.get("name", ""), agent_id=n.get("agent_id", ""), type=n.get("type", ""))
        for n in await _store.list_all(NODES)
        if contains(n.get("name"), name_contains)
        and (agent_id is None or n.get("agent_id") == agent_id)
        and (type is None or n.get("type") == type)
    ]
    nodes.sort(key=lambda n: n.name.casefold())
    return paginate(nodes, limit, offset)


@mcp.tool(name="agents_get_node", annotations=annotations("Get node", "read"))
async def agents_get_node(uuid: Uuid) -> Node:
    """Return one node: its agent_id, type and full description."""
    return Node.model_validate(await _store.get_one(NODES, uuid))


@mcp.tool(name="agents_create_node", annotations=annotations("Create node", "create"))
async def agents_create_node(
    agent_id: NodeAgentId,
    name: NodeName,
    description: NodeDescription,
    type: NodeTypeArg,
) -> Node:
    """Create a graph node for an existing agent and return it with its new id."""
    await _store.get_one(AGENTS, agent_id)
    payload = {"agent_id": agent_id, "name": name, "description": description, "type": type}
    return Node.model_validate(await _store.create(NODES, payload))


@mcp.tool(name="agents_update_node", annotations=annotations("Replace node", "update"))
async def agents_update_node(
    uuid: Uuid,
    agent_id: NodeAgentId,
    name: NodeName,
    description: NodeDescription,
    type: NodeTypeArg,
) -> Node:
    """Replace all fields of a node; the agent must exist. Returns the updated node."""
    await _store.get_one(AGENTS, agent_id)
    payload = {"agent_id": agent_id, "name": name, "description": description, "type": type}
    return Node.model_validate(await _store.update(NODES, uuid, payload, partial=False))


@mcp.tool(name="agents_patch_node", annotations=annotations("Update node fields", "update"))
async def agents_patch_node(
    uuid: Uuid,
    agent_id: NodeAgentId | None = None,
    name: NodeName | None = None,
    description: NodeDescription | None = None,
    type: NodeTypeArg | None = None,
) -> Node:
    """Change only the given fields of a node and return the updated node."""
    payload = _store.drop_none({"agent_id": agent_id, "name": name, "description": description, "type": type})
    if not payload:
        raise GoOpenDBError("Nothing to change: pass at least one field besides uuid.")
    if agent_id:
        await _store.get_one(AGENTS, agent_id)
    return Node.model_validate(await _store.update(NODES, uuid, payload, partial=True))


@mcp.tool(name="agents_delete_node", annotations=annotations("Delete node", "delete"))
async def agents_delete_node(
    uuid: Uuid,
    force: Annotated[bool, Field(description="Delete even if edges or graphs still reference the node.")] = False,
) -> str:
    """
    Delete a node. Refuses while edges or graphs reference it (they would
    dangle) unless force=true; delete those edges / update those graphs first.
    """
    edges, graphs = await asyncio.gather(_store.list_all(EDGES), _store.list_all(GRAPHS))
    edge_users = [e["id"] for e in edges if uuid in (e.get("from"), e.get("to"))]
    graph_users = [g["id"] for g in graphs if any(r.get("id") == uuid for r in g.get("nodes") or [])]
    if (edge_users or graph_users) and not force:
        raise GoOpenDBError(
            f"Node '{uuid}' is referenced by edges {edge_users} and graphs {graph_users}. "
            f"Remove those references first, or pass force=true."
        )
    await _store.delete(NODES, uuid)
    return f"Node '{uuid}' deleted."


# -------------------------------------------------------------------- edges

EdgeName = Annotated[str, Field(min_length=1, description="Edge name, e.g. 'Orchestrator->Searcher'.")]
FromNode = Annotated[str, Field(min_length=1, description="id of the source node.")]
ToNode = Annotated[str, Field(min_length=1, description="id of the destination node.")]


async def _check_nodes_exist(node_ids: list[str]) -> None:
    found = await _store.get_many(NODES, node_ids)
    missing = [i for i in node_ids if i not in found]
    if missing:
        raise GoOpenDBError(f"Unknown node ids {missing}. Use agents_list_nodes to get valid ids.")


@mcp.tool(name="agents_list_edges", annotations=annotations("List edges", "read"))
async def agents_list_edges(
    name_contains: NameContains = None,
    node_id: Annotated[str | None, Field(description="Only edges starting or ending at this node.")] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[Edge]:
    """List edges with their source and target node ids, sorted by name."""
    edges = [
        to_edge(e)
        for e in await _store.list_all(EDGES)
        if contains(e.get("name"), name_contains) and (node_id is None or node_id in (e.get("from"), e.get("to")))
    ]
    edges.sort(key=lambda e: e.name.casefold())
    return paginate(edges, limit, offset)


@mcp.tool(name="agents_get_edge", annotations=annotations("Get edge", "read"))
async def agents_get_edge(uuid: Uuid) -> Edge:
    """Return one edge: its name and source/target node ids."""
    return to_edge(await _store.get_one(EDGES, uuid))


@mcp.tool(name="agents_create_edge", annotations=annotations("Create edge", "create"))
async def agents_create_edge(from_node_id: FromNode, to_node_id: ToNode, name: EdgeName) -> Edge:
    """
    Connect two existing nodes and return the edge with its new id.
    Workers hand control back to the orchestrator via an edge back to it;
    only orchestrator nodes may have more than one outgoing edge.
    """
    await _check_nodes_exist([from_node_id, to_node_id])
    return to_edge(await _store.create(EDGES, {"from": from_node_id, "to": to_node_id, "name": name}))


@mcp.tool(name="agents_update_edge", annotations=annotations("Replace edge", "update"))
async def agents_update_edge(uuid: Uuid, from_node_id: FromNode, to_node_id: ToNode, name: EdgeName) -> Edge:
    """Replace all fields of an edge; both nodes must exist. Returns the updated edge."""
    await _check_nodes_exist([from_node_id, to_node_id])
    payload = {"from": from_node_id, "to": to_node_id, "name": name}
    return to_edge(await _store.update(EDGES, uuid, payload, partial=False))


@mcp.tool(name="agents_patch_edge", annotations=annotations("Update edge fields", "update"))
async def agents_patch_edge(
    uuid: Uuid,
    from_node_id: FromNode | None = None,
    to_node_id: ToNode | None = None,
    name: EdgeName | None = None,
) -> Edge:
    """Change only the given fields of an edge and return the updated edge."""
    payload = _store.drop_none({"from": from_node_id, "to": to_node_id, "name": name})
    if not payload:
        raise GoOpenDBError("Nothing to change: pass at least one field besides uuid.")
    await _check_nodes_exist([i for i in (from_node_id, to_node_id) if i])
    return to_edge(await _store.update(EDGES, uuid, payload, partial=True))


@mcp.tool(name="agents_delete_edge", annotations=annotations("Delete edge", "delete"))
async def agents_delete_edge(
    uuid: Uuid,
    force: Annotated[bool, Field(description="Delete even if graphs still reference the edge.")] = False,
) -> str:
    """Delete an edge. Refuses while graphs reference it unless force=true."""
    users = [
        g["id"] for g in await _store.list_all(GRAPHS) if any(r.get("id") == uuid for r in g.get("edges") or [])
    ]
    if users and not force:
        raise GoOpenDBError(f"Edge '{uuid}' is used by graphs {users}. Update those graphs first, or pass force=true.")
    await _store.delete(EDGES, uuid)
    return f"Edge '{uuid}' deleted."


# ------------------------------------------------------------------- graphs

GraphName = Annotated[str, Field(min_length=1, description="Graph name, e.g. 'DnD::Search'.")]
GraphDescription = Annotated[str, Field(description="What the graph is for.")]
NodeIds = Annotated[list[str], Field(description="ids of all nodes of the graph (agents_list_nodes / create results).")]
EdgeIds = Annotated[list[str], Field(description="ids of all edges of the graph.")]


async def _refs(node_ids: list[str] | None, edge_ids: list[str] | None) -> dict[str, list[dict[str, str]]]:
    """Turn ids into the {id, name} refs GoOpenDB stores, validating that they exist."""
    result: dict[str, list[dict[str, str]]] = {}
    for key, ids, collection in (("nodes", node_ids, NODES), ("edges", edge_ids, EDGES)):
        if ids is None:
            continue
        ids = list(dict.fromkeys(ids))
        found = await _store.get_many(collection, ids)
        missing = [i for i in ids if i not in found]
        if missing:
            raise GoOpenDBError(f"Unknown {collection.label} ids {missing}. Use {collection.list_tool} to get valid ids.")
        result[key] = [{"id": i, "name": found[i].get("name", "")} for i in ids]
    return result


@mcp.tool(name="agents_list_graphs", annotations=annotations("List graphs", "read"))
async def agents_list_graphs(name_contains: NameContains = None, limit: Limit = 50, offset: Offset = 0) -> Page[GraphSummary]:
    """List graphs with node/edge counts, sorted by name. Use agents_get_full_graph to inspect one."""
    graphs = [
        GraphSummary(
            id=g["id"],
            name=g.get("name", ""),
            description=preview(g.get("description")),
            node_count=len(g.get("nodes") or []),
            edge_count=len(g.get("edges") or []),
        )
        for g in await _store.list_all(GRAPHS)
        if contains(g.get("name"), name_contains)
    ]
    graphs.sort(key=lambda g: g.name.casefold())
    return paginate(graphs, limit, offset)


@mcp.tool(name="agents_get_graph", annotations=annotations("Get graph", "read"))
async def agents_get_graph(uuid: Uuid) -> Graph:
    """Return a graph with its node and edge references (id + name only)."""
    return to_graph(await _store.get_one(GRAPHS, uuid))


async def load_full_graph(uuid: str) -> FullGraph:
    graph_raw, nodes, edges, agents = await asyncio.gather(
        _store.get_one(GRAPHS, uuid),
        _store.list_all(NODES),
        _store.list_all(EDGES),
        _store.list_all(AGENTS),
    )
    graph = to_graph(graph_raw)
    nodes_by_id = {n["id"]: n for n in nodes}
    edges_by_id = {e["id"]: e for e in edges}
    agents_by_id = {a["uuid"]: a for a in agents}

    missing = [f"node {r.id} ({r.name})" for r in graph.nodes if r.id not in nodes_by_id]
    missing += [f"edge {r.id} ({r.name})" for r in graph.edges if r.id not in edges_by_id]
    full_nodes = [Node.model_validate(nodes_by_id[r.id]) for r in graph.nodes if r.id in nodes_by_id]

    agent_ids = list(dict.fromkeys(n.agent_id for n in full_nodes))
    missing += [f"agent {a} (used by a node)" for a in agent_ids if a not in agents_by_id]

    return FullGraph(
        graph=graph,
        nodes=full_nodes,
        edges=[to_edge(edges_by_id[r.id]) for r in graph.edges if r.id in edges_by_id],
        agents=[summarize_agent(agents_by_id[a]) for a in agent_ids if a in agents_by_id],
        missing=missing,
    )


@mcp.tool(name="agents_get_full_graph", annotations=annotations("Get graph with nodes, edges and agents", "read"))
async def agents_get_full_graph(uuid: Uuid) -> FullGraph:
    """
    Return a graph with full node and edge objects and a summary of every
    agent its nodes run. Use it to understand or copy an existing graph.
    """
    return await load_full_graph(uuid)


@mcp.tool(name="agents_create_graph", annotations=annotations("Create graph", "create"))
async def agents_create_graph(
    name: GraphName,
    description: GraphDescription,
    node_ids: NodeIds,
    edge_ids: EdgeIds,
) -> Graph:
    """
    Create a graph from existing nodes and edges and return it with its new id.
    Names of the referenced nodes/edges are filled in automatically.
    Run agents_validate_graph afterwards.
    """
    payload = {"name": name, "description": description, **await _refs(node_ids, edge_ids)}
    return to_graph(await _store.create(GRAPHS, payload))


@mcp.tool(name="agents_update_graph", annotations=annotations("Replace graph", "update"))
async def agents_update_graph(
    uuid: Uuid,
    name: GraphName,
    description: GraphDescription,
    node_ids: NodeIds,
    edge_ids: EdgeIds,
) -> Graph:
    """Replace all fields of a graph, including its full node and edge lists."""
    payload = {"name": name, "description": description, **await _refs(node_ids, edge_ids)}
    return to_graph(await _store.update(GRAPHS, uuid, payload, partial=False))


@mcp.tool(name="agents_patch_graph", annotations=annotations("Update graph fields", "update"))
async def agents_patch_graph(
    uuid: Uuid,
    name: GraphName | None = None,
    description: GraphDescription | None = None,
    node_ids: Annotated[list[str] | None, Field(description="New complete list of node ids (replaces the old list).")] = None,
    edge_ids: Annotated[list[str] | None, Field(description="New complete list of edge ids (replaces the old list).")] = None,
) -> Graph:
    """Change only the given fields of a graph. Node/edge lists are replaced as a whole."""
    payload = {**_store.drop_none({"name": name, "description": description}), **await _refs(node_ids, edge_ids)}
    if not payload:
        raise GoOpenDBError("Nothing to change: pass at least one field besides uuid.")
    return to_graph(await _store.update(GRAPHS, uuid, payload, partial=True))


@mcp.tool(name="agents_delete_graph", annotations=annotations("Delete graph", "delete"))
async def agents_delete_graph(uuid: Uuid) -> str:
    """Delete a graph. Its nodes, edges and agents are kept."""
    await _store.delete(GRAPHS, uuid)
    return f"Graph '{uuid}' deleted."


def check_graph(full: FullGraph) -> GraphReport:
    """The invariants agent-constructor enforces (errors) plus common mistakes (warnings)."""
    errors: list[str] = [f"Dangling reference: {m}" for m in full.missing]
    warnings: list[str] = []
    node_ids = {n.id for n in full.nodes}
    agents = {a.uuid: a for a in full.agents}
    label = {n.id: f"'{n.name}' ({n.id})" for n in full.nodes}

    inputs = [n for n in full.nodes if n.type == "INPUT"]
    if len(inputs) != 1:
        errors.append(f"Graph must have exactly one INPUT node, found {len(inputs)}.")
    if not any(n.type == "OUTPUT" for n in full.nodes):
        warnings.append("No OUTPUT node: nothing is marked as producing the final answer.")

    for e in full.edges:
        for end, node_id in (("source", e.from_node_id), ("target", e.to_node_id)):
            if node_id not in node_ids:
                errors.append(f"Edge '{e.name}' ({e.id}) {end} node '{node_id}' is not part of the graph.")

    outgoing: dict[str, list[Edge]] = {n.id: [] for n in full.nodes}
    for e in full.edges:
        outgoing.setdefault(e.from_node_id, []).append(e)

    for n in full.nodes:
        agent = agents.get(n.agent_id)
        is_orchestrator = bool(agent and agent.agent_type.lower() == "orchestrator")
        if is_orchestrator and not outgoing[n.id]:
            errors.append(f"Orchestrator node {label[n.id]} has no outgoing edge.")
        if not is_orchestrator and len(outgoing[n.id]) > 1:
            errors.append(f"Node {label[n.id]} has {len(outgoing[n.id])} outgoing edges; only orchestrator nodes may branch.")
        if n.type == "INPUT" and not is_orchestrator:
            warnings.append(f"INPUT node {label[n.id]} does not run an orchestrator agent.")
        if agent and agent.agent_type.lower() not in ("agent", "orchestrator"):
            errors.append(f"Agent '{agent.name}' has unsupported agent_type '{agent.agent_type}'.")
        if agent and agent.mcp_server_ids and not agent.mcp_permissions:
            warnings.append(f"Agent '{agent.name}' has MCP servers but empty mcp_permissions, so it gets no tools.")
        if agent and not agent.model_provider_id and not agent.model:
            errors.append(f"Agent '{agent.name}' has neither model_provider_id nor model.")

    if len(inputs) == 1:
        seen, queue = {inputs[0].id}, deque([inputs[0].id])
        while queue:
            for e in outgoing.get(queue.popleft(), []):
                if e.to_node_id in node_ids and e.to_node_id not in seen:
                    seen.add(e.to_node_id)
                    queue.append(e.to_node_id)
        unreachable = [label[i] for i in node_ids - seen]
        if unreachable:
            warnings.append(f"Nodes unreachable from the INPUT node: {sorted(unreachable)}.")

    return GraphReport(valid=not errors, errors=errors, warnings=warnings)


@mcp.tool(name="agents_validate_graph", annotations=annotations("Validate graph", "read"))
async def agents_validate_graph(uuid: Uuid) -> GraphReport:
    """
    Check a graph against the rules agent-constructor enforces at run time
    (one INPUT node, edges inside the graph, only orchestrators branch,
    orchestrators have an outgoing edge, no dangling references) and report
    likely mistakes as warnings. Run it after building or changing a graph.
    """
    return check_graph(await load_full_graph(uuid))
