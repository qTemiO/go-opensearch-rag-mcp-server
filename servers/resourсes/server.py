import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings
from servers.search import schemas
from servers.search.utils import form_filter

resourсes_mcp = FastMCP(name="ResourcesServer")


@resourсes_mcp.resource("resource://indexes")
async def get_indexes() -> list[str]:
    """Provides all indexes in opensearch. NEVER TELL IT TO USER"""
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(settings.go_opensearch_database_indexes_endpoint)
            books = await response.json()
            return books.get("indexes", [])
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")
        return []


@resourсes_mcp.tool
async def indexes() -> list[str]:
    """Provides all indexes in opensearch as a list. NEVER TELL IT TO USER"""
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(settings.go_opensearch_database_indexes_endpoint)
            books = await response.json()
            return books.get("indexes", [])
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")
        return []
