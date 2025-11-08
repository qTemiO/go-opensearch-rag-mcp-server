from datetime import datetime

from loguru import logger
from fastmcp import FastMCP

from settings import settings

mcp = FastMCP(name="Gorag MCP Server")


@mcp.tool
def current_time() -> datetime:
    """
    Current time in user location 
    """
    logger.success("Current time called")
    return datetime.now()


@mcp.tool
def enchant_prompt(prompt: str) -> str:
    """
    Enchants prompt for better generation
    """
    logger.success("Enchant prompt called")
    return f"New prompt: {prompt}!"


@mcp.tool
def extend_search(index: str, query: str) -> dict:
    """
    Extends search for new documents by given index and query
    """
    logger.success("Extend search called")
    return {"index": index, "query": query, "documents": ["doc1 test", "doc2 test"]}


if __name__ == "__main__":
    mcp.run("streamable-http",  host=settings.HOST, port=settings.PORT)
