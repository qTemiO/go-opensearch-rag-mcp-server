"""descriptions_* — short summaries attached to books of a RAG index."""

from typing import Annotated

from loguru import logger
from pydantic import BaseModel, Field

from goopendb_mcp.app import mcp
from goopendb_mcp.client import GoOpenDBError, get_client, segment
from goopendb_mcp.common import Index, annotations
from goopendb_mcp.tools.search import check_books, list_books

BookName = Annotated[
    str,
    Field(min_length=1, description="Exact book name as returned by search_books."),
]


class Description(BaseModel):
    book_name: str
    index: str
    description: str


def _to_description(payload: dict) -> Description:
    return Description(
        book_name=payload.get("book_name", ""),
        index=payload.get("parent_index", ""),
        description=payload.get("description", ""),
    )


async def _find(index: str, book_name: str) -> Description | None:
    try:
        data = await get_client().get(
            f"/api/v1/books/description/{segment(index)}",
            params={"book_name": book_name},
        )
    except GoOpenDBError as error:
        if error.status == 404:
            return None
        raise
    return _to_description((data or {}).get("description") or {})


@mcp.tool(name="descriptions_get_all", annotations=annotations("List book descriptions", "read"))
async def descriptions_get_all(index: Index) -> list[Description]:
    """
    Return all book descriptions stored for a RAG index. Books without a
    description are simply absent; an empty list means none were written yet.
    """
    data = await get_client().get(f"/api/v1/books/descriptions/{segment(index)}")
    return [_to_description(item) for item in (data or {}).get("descriptions") or []]


@mcp.tool(name="descriptions_get_by_name", annotations=annotations("Get book description", "read"))
async def descriptions_get_by_name(index: Index, book_name: BookName) -> Description:
    """Return the description of one book. Fails with a clear error if the book has none."""
    description = await _find(index, book_name)
    if description is None:
        raise GoOpenDBError(
            f"Book '{book_name}' in index '{index}' has no description. "
            f"Use descriptions_get_all to see which books have one."
        )
    return description


@mcp.tool(name="descriptions_write", annotations=annotations("Create or replace book description", "update"))
async def descriptions_write(
    index: Index,
    book_name: BookName,
    description: Annotated[
        str,
        Field(min_length=1, description="Summary of the book: topic, contents, when it is useful to search it."),
    ],
) -> Description:
    """
    Create the description of a book, or replace it if one already exists
    (a book never ends up with two descriptions). The book must exist in the
    index (see search_books).
    """
    logger.info(f"descriptions_write index={index} book={book_name}")
    check_books([book_name], await list_books(index))

    if await _find(index, book_name) is not None:
        await get_client().delete(
            f"/api/v1/books/description/{segment(index)}",
            params={"book_name": book_name},
        )
    await get_client().post(
        "/api/v1/books/description",
        json={"index": index, "book_name": book_name, "description": description},
    )
    return Description(index=index, book_name=book_name, description=description)


@mcp.tool(name="descriptions_delete", annotations=annotations("Delete book description", "delete"))
async def descriptions_delete(index: Index, book_name: BookName) -> str:
    """Delete the description of a book. The book itself and its passages are kept."""
    logger.info(f"descriptions_delete index={index} book={book_name}")
    if await _find(index, book_name) is None:
        return f"Book '{book_name}' in index '{index}' had no description; nothing to delete."
    await get_client().delete(
        f"/api/v1/books/description/{segment(index)}",
        params={"book_name": book_name},
    )
    return f"Description of '{book_name}' in index '{index}' deleted."
