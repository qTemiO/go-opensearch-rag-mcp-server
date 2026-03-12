import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings
from servers.descriptions import schemas

descriptions_mcp = FastMCP(name="DescriptionsServer")


@descriptions_mcp.tool
async def all_descriptions(index: str) -> list[schemas.Description] | None:
    """
    This tool help to get all descriptions in opensearch index 

    * **index** - your opensearch index
    """
    logger.success(f"All descriptions tool used, index: {index}")
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(settings.go_opensearch_database_books_descriptions_endpoint + f"/{index}")
            books = await response.json()
            return books.get("descriptions", [])
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")


@descriptions_mcp.tool
async def get_description(index: str, book_name: str) -> schemas.Description | None:
    """
    This tool help to get description by book name 

    * **index** - your opensearch index
    * **book_name** - book name from this index
    """
    params = {
        "book_name": book_name
    }

    logger.success(f"Get description tool used, index: {index}")
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(settings.go_opensearch_database_books_description_endpoint + f"/{index}", params=params)
            books = await response.json()
            description = schemas.Description.model_validate(
                books.get("description"))
            return description
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")


@descriptions_mcp.tool
async def write_description(item: schemas.DescriptionWrite) -> str | None:
    """
    This tool help to get description by book name 

    * **index** - your opensearch index
    * **book_name** - book name from this index
    * **description** - summary text of this book 
    """
    payload = item.model_dump()

    logger.success(f"Write description tool used, index: {payload}")
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(settings.go_opensearch_database_books_description_endpoint, json=payload)
            status = await response.json()
            return status
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")
