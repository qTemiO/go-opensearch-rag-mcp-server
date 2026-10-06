"""
Tool names are a public contract: agent-constructor grants tools to agents by
name prefix (`mcp_permissions`), and agents in the database already rely on them.
"""

from goopendb_mcp.app import mcp

LEGACY_TOOLS = {
    "current_time",
    "search_books", "search_documents", "search_documents_with_filter",
    "descriptions_get_all", "descriptions_get_by_name", "descriptions_write", "descriptions_delete",
    *(
        f"agents_{action}_{kind}"
        for kind in ("agent", "node", "edge", "graph")
        for action in ("get", "create", "update", "patch", "delete")
    ),
    "agents_list_agents", "agents_list_nodes", "agents_list_edges", "agents_list_graphs",
    "agents_get_full_graph",
}


async def _tools():
    return {tool.name: tool for tool in await mcp.list_tools()}


async def test_legacy_tool_names_are_kept():
    missing = LEGACY_TOOLS - set(await _tools())
    assert not missing


async def test_search_permission_grants_read_only_tools():
    # Agents with mcp_permissions=["search"] must not gain write access.
    for name, tool in (await _tools()).items():
        if name.startswith("search"):
            assert tool.annotations.readOnlyHint, name


async def test_every_tool_is_annotated_and_documented():
    for name, tool in (await _tools()).items():
        assert tool.annotations is not None, name
        assert tool.annotations.title, name
        assert tool.description and len(tool.description) > 20, name
