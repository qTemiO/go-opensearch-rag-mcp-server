import asyncio
from datetime import datetime

from loguru import logger
from fastmcp import FastMCP

from servers import search_mcp, translator_mcp
from settings import settings

# Define main server
main_mcp = FastMCP(name="MainApp")


@main_mcp.tool
def current_time() -> datetime:
    """
    Get current time of user
    """
    logger.success("Current time called")
    return f"Время сейчас: {datetime.now()}"


async def setup():
    await main_mcp.import_server(search_mcp, prefix="search")
    await main_mcp.import_server(translator_mcp, prefix="translator")
    await main_mcp.run_async("http",  host=settings.HOST, port=settings.PORT)

if __name__ == "__main__":
    asyncio.run(setup())
