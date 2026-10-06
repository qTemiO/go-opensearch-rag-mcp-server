"""books_* — managing the corpus of RAG indexes. Every tool here writes data."""

from typing import Annotated, Any

from loguru import logger
from pydantic import Field

from goopendb_mcp.app import mcp
from goopendb_mcp.client import GoOpenDBError, get_client
from goopendb_mcp.common import Index, annotations
from goopendb_mcp.tools.search import check_books, list_books, list_rag_indexes

BookName = Annotated[
    str,
    Field(min_length=1, description="Exact book name as returned by search_books."),
]
IndexName = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9][a-z0-9_.-]{0,254}$",
        description="New index name: lowercase latin letters, digits, '_', '-', '.'; e.g. 'lore-index'.",
    ),
]


@mcp.tool(name="books_create_index", annotations=annotations("Create RAG index", "create"))
async def books_create_index(index: IndexName) -> str:
    """
    Create an empty RAG index (hybrid search pipeline, passage embeddings) that
    books_load_text can fill. Fails if the index already exists.
    """
    if index in await list_rag_indexes():
        raise GoOpenDBError(f"Index '{index}' already exists; load books into it or choose another name.")
    logger.info(f"books_create_index index={index}")
    created = await get_client().post("/api/v1/index-manager/index", json={"index_name": index})
    if created is False:
        raise GoOpenDBError(f"GoOpenDB refused to create index '{index}'. Check the name and retry.")
    return f"Index '{index}' created."


@mcp.tool(name="books_load_text", annotations=annotations("Load book text", "create"))
async def books_load_text(
    index: Index,
    book_name: Annotated[str, Field(min_length=1, description="Name the passages will be searchable under.")],
    text: Annotated[str, Field(min_length=1, description="Plain text of the book or fragment.")],
    metadata: Annotated[
        dict[str, Any] | None,
        Field(description="Optional JSON object copied into every chunk, e.g. {'author': 'Иванов', 'year': 2024}."),
    ] = None,
    append: Annotated[
        bool,
        Field(description="Set true to add more text to a book that already exists in the index."),
    ] = False,
) -> str:
    """
    Split text into chunks and index it under `book_name` in a RAG index.

    Loading is additive: calling it twice with the same text creates duplicate
    passages, so loading into an existing book requires append=true. New
    passages become searchable after OpenSearch refresh (about a second).
    """
    if not append and book_name in await list_books(index):
        raise GoOpenDBError(
            f"Book '{book_name}' already exists in '{index}'. Pass append=true to add text to it, "
            f"or books_delete it first to reload from scratch."
        )
    logger.info(f"books_load_text index={index} book={book_name} chars={len(text)}")
    payload: dict[str, Any] = {"index": index, "book_name": book_name, "text": text}
    if metadata:
        payload["metadata"] = metadata
    await get_client().post("/api/v1/books/text", json=payload)
    return f"Loaded {len(text)} characters into '{book_name}' in index '{index}'."


@mcp.tool(name="books_rename", annotations=annotations("Rename book", "update"))
async def books_rename(index: Index, old_book_name: BookName, new_book_name: BookName) -> str:
    """Rename a book in a RAG index (all its passages). Descriptions are not renamed."""
    books = await list_books(index)
    check_books([old_book_name], books)
    if new_book_name in books:
        raise GoOpenDBError(f"Book '{new_book_name}' already exists in '{index}'; pick another name.")
    logger.info(f"books_rename index={index} {old_book_name!r} -> {new_book_name!r}")
    data = await get_client().put(
        "/api/v1/books/rename",
        json={"index": index, "old_book_name": old_book_name, "new_book_name": new_book_name},
    )
    if not (data or {}).get("is_update"):
        raise GoOpenDBError(f"GoOpenDB did not rename '{old_book_name}'. Retry or check the service logs.")
    return f"Book '{old_book_name}' renamed to '{new_book_name}' in '{index}'."


@mcp.tool(name="books_delete", annotations=annotations("Delete book", "delete"))
async def books_delete(index: Index, book_name: BookName) -> str:
    """
    Permanently delete a book and all of its passages from a RAG index.
    Its description (if any) is kept; remove it with descriptions_delete.
    """
    check_books([book_name], await list_books(index))
    logger.info(f"books_delete index={index} book={book_name}")
    data = await get_client().delete("/api/v1/books/book", json={"index": index, "book_name": book_name})
    if not (data or {}).get("is_deleted"):
        raise GoOpenDBError(f"GoOpenDB did not delete '{book_name}'. Retry or check the service logs.")
    return f"Book '{book_name}' deleted from '{index}'."
