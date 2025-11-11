import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings

search_mcp = FastMCP(name="SearchServer")


@search_mcp.tool
async def get_availiable_books(index: str) -> list[str] | None:
    """
    This tool help to define which books are loaded and for what book you can ask questions 

    Index - Opensearch index. In system prompt may found it
    """
    logger.success(f"Search Books tool used, index: {index}")

    payload = {
        "index": index
    }
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(settings.RAG_SERVICE_URL, json=payload)
            books = await response.json()
            return books.get("books", [])
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")
