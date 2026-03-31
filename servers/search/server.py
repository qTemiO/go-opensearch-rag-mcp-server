import aiohttp

from fastmcp import FastMCP
from loguru import logger

from settings import settings
from servers.search import schemas
from servers.search.utils import form_filter

search_mcp = FastMCP(name="SearchServer")


@search_mcp.tool
async def books(index: str) -> list[str] | None:
    """
    Return all book names available in the selected OpenSearch index.

    Use this tool when:
    - you need to discover valid book names for filtering;
    - you want to inspect what source books are loaded in an index.

    Args:
    - index (str): exact OpenSearch index name.

    Example call:
    ```json
    {"index": "dnd-index"}
    ```

    Example response:
    ```json
    ["Player's Handbook", "Monster Manual", "Xanathar's Guide to Everything"]
    ```
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
async def documents(item: schemas.SearchDocumentsPayload) -> dict | None:
    """
    Search relevant chunks/documents in one OpenSearch index by text query.

    Use this tool when:
    - you need semantic search without book-level filtering.

    Args (item):
    - index (str): exact OpenSearch index name, for example "dnd-index".
    - text (str): natural language user query.
    - top_k (int): number of results to return, must be >= 10.

    Example call:
    ```json
    {
      "item": {
        "index": "dnd-index",
        "text": "Find description of spells Poison Spray and Magic Hand",
        "top_k": 10
      }
    }
    ```
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
async def documents_with_filter(item: schemas.SearchFilterDocumentsPayload) -> dict | None:
    """
    Search documents with semantic ranking and optional include/exclude book filters.

    Use this tool when:
    - user asks to search only in specific books;
    - user asks to exclude specific books from search.

    Args (item):
    - index (str): exact OpenSearch index name.
    - text (str): natural language user query.
    - top_k (int): number of results to return, must be >= 10.
    - allowed_books (list[str]): only these books are used for search; [] disables include filter.
    - forbidden_books (list[str]): these books are excluded; [] disables exclude filter.

    Important:
    - book names must match names from `books(index)` output exactly.

    Example call:
    ```json
    {
      "item": {
        "index": "dnd-index",
        "text": "Find all rules for concentration",
        "top_k": 10,
        "allowed_books": ["Player's Handbook"],
        "forbidden_books": ["Unearthed Arcana"]
      }
    }
    ```
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
