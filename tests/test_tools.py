import httpx

from goopendb_mcp.client import GoOpenDBClient, set_client
from tests.conftest import call

PROVIDER = {
    "id": "prov-1",
    "name": "OpenRouter",
    "enabled": True,
    "default_model": "m-default",
    "available_models": ["m-default", "m-fast"],
}


def _agent_args(**overrides):
    args = {
        "name": "Test::Orchestrator",
        "agent_description": "Routes work",
        "agent_type": "orchestrator",
        "system_prompt": "You route.",
        "model_provider_id": "prov-1",
    }
    return {**args, **overrides}


# ------------------------------------------------------------------ search


async def test_filtered_search_sends_terms_filter(client, fake):
    fake.books["dnd-index"] = ["Book A", "Book B"]
    result = await call(
        client, "search_documents_with_filter",
        index="dnd-index", text="spell", allowed_books=["Book A"], forbidden_books=["Book B"],
    )
    assert result["hits"] == [{"source": "Book A", "score": 0.5, "text": "passage"}]
    method, path, body = fake.requests[-1]
    assert path == "/api/v1/search/filter_documents"
    assert body["filter"] == {
        "bool": {
            "filter": [{"terms": {"document_name.keyword": ["Book A"]}}],
            "must_not": [{"terms": {"document_name.keyword": ["Book B"]}}],
        }
    }


async def test_filtered_search_rejects_unknown_book(client, fake):
    fake.books["dnd-index"] = ["Book A"]
    result = await call(client, "search_documents_with_filter", index="dnd-index", text="x", allowed_books=["Nope"])
    assert "Unknown book name(s): ['Nope']" in result["error"]
    assert "Book A" in result["error"]


async def test_filtered_search_without_filters_uses_plain_search(client, fake):
    fake.books["dnd-index"] = ["Book A"]
    await call(client, "search_documents_with_filter", index="dnd-index", text="x")
    assert fake.requests[-1][1] == "/api/v1/search/documents"


async def test_search_books_reports_unknown_index(client, fake):
    fake.books["dnd-index"] = ["Book A"]
    result = await call(client, "search_books", index="typo-index")
    assert "Unknown index 'typo-index'" in result["error"]


# ------------------------------------------------------------ descriptions


async def test_descriptions_write_replaces_instead_of_duplicating(client, fake):
    fake.books["idx"] = ["Book A"]
    await call(client, "descriptions_write", index="idx", book_name="Book A", description="first")
    await call(client, "descriptions_write", index="idx", book_name="Book A", description="second")
    assert await call(client, "descriptions_get_all", index="idx") == [
        {"book_name": "Book A", "index": "idx", "description": "second"}
    ]


async def test_descriptions_get_by_name_missing_is_an_error(client, fake):
    result = await call(client, "descriptions_get_by_name", index="idx", book_name="Book A")
    assert "has no description" in result["error"]


# ------------------------------------------------------------------ agents


async def test_create_agent_returns_generated_uuid(client, fake):
    fake.providers["prov-1"] = PROVIDER
    agent = await call(client, "agents_create_agent", **_agent_args(mcp_permissions=[" search_ ", "search_"]))
    assert agent["uuid"] in fake.store["agents"]
    assert agent["mcp_permissions"] == ["search_"]


async def test_create_agent_keeps_free_form_permission_prefixes(client, fake):
    # Old server silently dropped anything but search/descriptions/agents.
    fake.providers["prov-1"] = PROVIDER
    agent = await call(
        client, "agents_create_agent", **_agent_args(mcp_permissions=["search_documents", "calculate_expression"])
    )
    assert agent["mcp_permissions"] == ["search_documents", "calculate_expression"]


async def test_create_agent_validates_registry_references(client, fake):
    fake.providers["prov-1"] = PROVIDER
    result = await call(client, "agents_create_agent", **_agent_args(model_name_override="gpt-unknown"))
    assert "Available models" in result["error"]

    result = await call(client, "agents_create_agent", **_agent_args(mcp_server_ids=["missing"]))
    assert "Unknown mcp_server_ids ['missing']" in result["error"]

    result = await call(client, "agents_create_agent", **_agent_args(model_provider_id=None))
    assert "model_provider_id" in result["error"]
    assert not fake.store["agents"]


async def test_get_missing_agent_has_actionable_error(client, fake):
    result = await call(client, "agents_get_agent", uuid="nope")
    assert result["error"] == "No agent with id 'nope'. Use agents_list_agents to find valid ids."


async def test_list_agents_paginates_and_hides_prompts(client, fake):
    for i in range(5):
        fake.add("agents", {"name": f"A{i}", "agent_type": "agent", "system_prompt": "long prompt"})
    page = await call(client, "agents_list_agents", limit=2, offset=2)
    assert [a["name"] for a in page["items"]] == ["A2", "A3"]
    assert page["has_more"] and page["next_offset"] == 4 and page["total"] == 5
    assert "system_prompt" not in page["items"][0]


async def test_patch_agent_changes_only_given_fields(client, fake):
    agent = fake.add("agents", {"name": "A", "agent_type": "agent", "system_prompt": "p"})
    updated = await call(client, "agents_patch_agent", uuid=agent["uuid"], system_prompt="new")
    assert updated["system_prompt"] == "new" and updated["name"] == "A"
    assert fake.requests[-2][2] == {"system_prompt": "new"}


async def test_delete_agent_refuses_while_used_by_nodes(client, fake):
    agent = fake.add("agents", {"name": "A", "agent_type": "agent"})
    fake.add("nodes", {"name": "N", "agent_id": agent["uuid"], "type": "CUSTOM"})
    result = await call(client, "agents_delete_agent", uuid=agent["uuid"])
    assert "is used by nodes" in result["error"]
    assert await call(client, "agents_delete_agent", uuid=agent["uuid"], force=True)
    assert not fake.store["agents"]


# ------------------------------------------------------------------ graphs


async def _build_graph(client, fake):
    orchestrator = fake.add("agents", {"name": "Orch", "agent_type": "orchestrator", "model": "openai::x"})
    worker = fake.add("agents", {"name": "Worker", "agent_type": "agent", "model": "openai::x"})
    entry = await call(client, "agents_create_node", agent_id=orchestrator["uuid"], name="Entry", description="d", type="INPUT")
    work = await call(client, "agents_create_node", agent_id=worker["uuid"], name="Work", description="d", type="OUTPUT")
    there = await call(client, "agents_create_edge", from_node_id=entry["id"], to_node_id=work["id"], name="there")
    back = await call(client, "agents_create_edge", from_node_id=work["id"], to_node_id=entry["id"], name="back")
    graph = await call(
        client, "agents_create_graph", name="G", description="test",
        node_ids=[entry["id"], work["id"]], edge_ids=[there["id"], back["id"]],
    )
    return graph, entry, work


async def test_graph_building_flow_returns_ids_and_fills_names(client, fake):
    graph, entry, work = await _build_graph(client, fake)
    assert graph["id"] in fake.store["graphs"]
    assert graph["nodes"] == [{"id": entry["id"], "name": "Entry"}, {"id": work["id"], "name": "Work"}]
    assert await call(client, "agents_validate_graph", uuid=graph["id"]) == {"valid": True, "errors": [], "warnings": []}

    full = await call(client, "agents_get_full_graph", uuid=graph["id"])
    assert {a["name"] for a in full["agents"]} == {"Orch", "Worker"}
    assert full["missing"] == []


async def test_validate_graph_reports_constructor_rule_violations(client, fake):
    graph, entry, work = await _build_graph(client, fake)
    extra = await call(client, "agents_create_node", agent_id=work["agent_id"], name="Extra", description="d", type="INPUT")
    branch = await call(client, "agents_create_edge", from_node_id=work["id"], to_node_id=extra["id"], name="branch")
    await call(
        client, "agents_patch_graph", uuid=graph["id"],
        node_ids=[entry["id"], work["id"], extra["id"]],
        edge_ids=[e["id"] for e in fake.store["edges"].values()],
    )
    report = await call(client, "agents_validate_graph", uuid=graph["id"])
    assert not report["valid"]
    assert any("exactly one INPUT" in e for e in report["errors"])
    assert any("only orchestrator nodes may branch" in e for e in report["errors"])
    assert branch["id"]


async def test_create_edge_rejects_unknown_nodes(client, fake):
    result = await call(client, "agents_create_edge", from_node_id="a", to_node_id="b", name="x")
    assert "Unknown node ids ['a', 'b']" in result["error"]


async def test_delete_node_refuses_while_referenced(client, fake):
    graph, entry, _ = await _build_graph(client, fake)
    result = await call(client, "agents_delete_node", uuid=entry["id"])
    assert "Remove those references first" in result["error"]


# ---------------------------------------------------------------- registry


async def test_registry_delete_conflict_is_explained(client, fake):
    fake.providers["prov-1"] = PROVIDER
    fake.add("agents", {"name": "A", "agent_type": "agent", "model_provider_id": "prov-1"})
    result = await call(client, "registry_delete_model_provider", id="prov-1")
    assert "still referenced by agents" in result["error"]
    assert await call(client, "registry_delete_model_provider", id="prov-1", force=True)


# ------------------------------------------------------------------ client


async def test_unreachable_service_is_reported(client, fake):
    def refuse(request):
        raise httpx.ConnectError("refused")

    set_client(GoOpenDBClient("http://goopendb.test", timeout=5, transport=httpx.MockTransport(refuse)))
    result = await call(client, "search_list_indexes")
    assert "GoOpenDB is unreachable" in result["error"]
