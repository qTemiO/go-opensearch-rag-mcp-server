import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings
from servers.search import schemas
from servers.search.utils import form_filter

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
async def search_documents(item: schemas.SearchDocumentsPayload) -> dict | None:
    """
    This tool help to find documents in opensearch index with search methodics

    * **index** - your opensearch index
    * **text** - query to search documents
    * **top_k** - number of document to receive 

    response:
    * **documents** - texts of documents
    * **scores** - relevant scores of documents
    * **sources** - names of sources books

    """
    logger.success(
        f"Search documents tool used, index: {item.index} {item.text}")

    payload = {
        "index": item.index,
        "text": item.text,
        "top_k": item.top_k
    }

    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(settings.go_opensearch_database_search_documents_endpoint, json=payload)
            data = await response.json()
            return data
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")
        return None


@search_mcp.tool
async def search_filter_documents(item: schemas.SearchFilterDocumentsPayload) -> dict | None:
    """
    This tool help to find documents in opensearch index with advanced search methodics and filters

    * **index** - your opensearch index
    * **text** - query to search documents
    * **top_k** - number of document to receive 
    * **allowed_books** - list of full name of allowed books (you may find all books in awailiable_books tool)
    * **forbidden_books** - list of full name of forbidden books or ban-books (you may find all books in awailiable_books tool)

    response:
    * **documents** - texts of documents
    * **scores** - relevant scores of documents
    * **sources** - names of sources books

    """
    logger.success(
        f"Search filter documents tool used, index: {item.index} {item.text}")

    filter_ = await form_filter(inclusive_books=item.allowed_books,
                                exclusive_books=item.forbidden_books)

    payload = {
        "filter": filter_,
        "index": item.index,
        "text": item.text,
        "top_k": item.top_k
    }

    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(settings.go_opensearch_database_search_filter_documents_endpoint, json=payload)
            data = await response.json()
            return data
    except Exception as error:
        logger.error(f"Error occured with books tool, {error}")
        return None
