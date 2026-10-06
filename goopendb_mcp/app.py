from fastmcp import FastMCP

INSTRUCTIONS = """\
Tools for GoOpenDB: a document store (RAG book indexes and generic JSON indexes)
and the configuration store of agent-constructor (agents, nodes, edges, graphs,
MCP server and model provider registries).

Tool name prefixes are permission scopes used by agent-constructor
(`mcp_permissions` is a list of tool-name prefixes):
- search_*        read-only retrieval: indexes, books, semantic search
- descriptions_*  book descriptions
- books_*         corpus management: load text, rename/delete books, create indexes
- documents_*     generic JSON documents: create index, upsert, patch, delete, get
- agents_*        agents, nodes, edges, graphs; read access to the registries
- registry_*      write access to the MCP server / model provider registries

Typical RAG flow: search_list_indexes -> search_books -> search_documents
(or search_documents_with_filter to restrict books).
Graph building flow: agents_list_model_providers / agents_list_mcp_servers ->
agents_create_agent (one per role) -> agents_create_node -> agents_create_edge ->
agents_create_graph -> agents_validate_graph. Create tools return the new id.
"""

mcp = FastMCP(name="goopendb_mcp", instructions=INSTRUCTIONS, mask_error_details=True)

