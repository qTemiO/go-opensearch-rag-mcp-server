from fastmcp import FastMCP

mcp = FastMCP(name="Gorag MCP Server")


@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"


@mcp.tool
def extend_search(index: str, query: str) -> dict:
    return {"index": index, "query": query}


if __name__ == "__main__":
    mcp.run("streamable-http",  host="0.0.0.0", port=15000)
