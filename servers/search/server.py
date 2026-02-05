import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings

search_mcp = FastMCP(name="SearchServer")


@search_mcp.tool
async def get_availiable_books(index: str) -> list[str] | None:
    """
    This tool help to define which books are loaded in opensearch index 

    * **index** - your opensearch index

    response - list of books in string 
    """
    logger.success(f"Search Books tool used, index: {index}")

    payload = {
        "index": index
    }
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(settings.go_opensearch_database_books_list_endpoint, json=payload)
            books = await response.json()
            return books.get("books", [])
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")


@search_mcp.tool
async def search_documents(index: str, text: str, top_k: int) -> dict | None:
    """
    This tool help to find raw documents in opensearch index without search methodics

    * **index** - your opensearch index
    * **text** - query to search documents
    * **top_k** - number of document to receive 

    response:
    * **documents** - texts of documents
    * **scores** - relevant scores of documents
    * **sources** - names of sources books

    """
    logger.success(f"Search Books tool used, index: {index}")

    payload = {
        "index": index,
        "text": text,
        "top_k": top_k
    }

    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(settings.go_opensearch_database_search_documents_endpoint, json=payload)
            data = await response.json()
            return data
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")
        return None
