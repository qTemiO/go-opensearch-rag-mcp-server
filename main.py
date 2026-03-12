import asyncio
from datetime import datetime

from loguru import logger
from fastmcp import FastMCP

from servers import search_mcp, descriptions_mcp
from settings import settings

# Define main server
main_mcp = FastMCP(name="MainServer")


@main_mcp.tool
def current_time() -> str:
    """
    Current time in user location 
    """
    logger.success("Current time called")
    return str(datetime.now())


async def setup():
    await main_mcp.import_server(search_mcp, prefix="search")
    await main_mcp.import_server(descriptions_mcp, prefix="descriptions")

if __name__ == "__main__":
    asyncio.run(setup())
    main_mcp.run("streamable-http",  host=settings.HOST, port=settings.PORT)
