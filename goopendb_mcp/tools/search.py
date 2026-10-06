"""search_* — read-only retrieval over RAG (book) indexes."""

from typing import Annotated

from loguru import logger
from pydantic import BaseModel, Field

from goopendb_mcp.app import mcp
from goopendb_mcp.client import GoOpenDBError, get_client
from goopendb_mcp.common import Index, annotations

TopK = Annotated[
    int,
    Field(
        ge=1,
        le=50,
        description=(
            "How many passages to return. 10 is a good default; each passage is "
            "expanded with neighbouring chunks, so large values produce a lot of text."
        ),
    ),
]
Query = Annotated[
    str,
    Field(
        min_length=1,
        description=(
            "Natural-language query with the full user intent, in the language of the "
            "books (e.g. 'описание заговора Ядовитые брызги'), not bare keywords."
        ),
    ),
]
BookNames = Annotated[
    list[str],
    Field(description="Exact book names as returned by search_books. Empty list disables this filter."),
]


class SearchHit(BaseModel):
    source: str = Field(description="Book the passage comes from.")
    score: float = Field(description="Relevance score, higher is better.")
    text: str


class SearchResult(BaseModel):
    index: str
    query: str
    hits: list[SearchHit]


async def list_rag_indexes() -> list[str]:
    data = await get_client().get("/api/v1/index-manager/indexes")
    return sorted((data or {}).get("indexes") or [])


async def list_books(index: str) -> list[str]:
    data = await get_client().post("/api/v1/books/list", json={"index": index})
    return sorted((data or {}).get("books") or [])


def _to_result(index: str, query: str, data: dict) -> SearchResult:
    documents = data.get("documents") or []
    scores = data.get("scores") or []
    sources = data.get("sources") or []
    hits = [
        SearchHit(
            text=text,
            score=round(scores[i], 4) if i < len(scores) else 0.0,
            source=sources[i] if i < len(sources) else "",
        )
        for i, text in enumerate(documents)
    ]
    return SearchResult(index=index, query=query, hits=hits)


async def _search(index: str, text: str, top_k: int) -> SearchResult:
    data = await get_client().post(
        "/api/v1/search/documents",
        json={"index": index, "text": text, "top_k": top_k},
    )
    return _to_result(index, text, data or {})


def check_books(requested: list[str], available: list[str]) -> None:
    unknown = [book for book in requested if book not in available]
    if unknown:
        raise GoOpenDBError(
            f"Unknown book name(s): {unknown}. Book names must match exactly; "
            f"available books: {available}"
        )


@mcp.tool(name="search_list_indexes", annotations=annotations("List RAG indexes", "read"))
async def search_list_indexes() -> list[str]:
    """
    List the RAG (book) indexes that can be searched with search_documents.

    Generic JSON-document indexes (documents_* tools) are not listed here.
    """
    return await list_rag_indexes()


@mcp.tool(name="search_books", annotations=annotations("List books in an index", "read"))
async def search_books(index: Index) -> list[str]:
    """
    List the names of all books loaded into a RAG index.

    Use it to discover exact book names before search_documents_with_filter,
    descriptions_* or books_* tools. Returns an empty list for an empty index.
    """
    logger.info(f"search_books index={index}")
    books = await list_books(index)
    if not books and index not in await list_rag_indexes():
        raise GoOpenDBError(f"Unknown index '{index}'. Use search_list_indexes to see available indexes.")
    return books


@mcp.tool(name="search_documents", annotations=annotations("Semantic search", "read"))
async def search_documents(index: Index, text: Query, top_k: TopK = 10) -> SearchResult:
    """
    Hybrid (keyword + semantic) search over all books of one RAG index, with
    reranking and context expansion. Returns passages with their source book
    and relevance score, best first.

    Use search_documents_with_filter instead to restrict or exclude books.
    """
    logger.info(f"search_documents index={index} top_k={top_k}")
    return await _search(index, text, top_k)


@mcp.tool(
    name="search_documents_with_filter",
    annotations=annotations("Semantic search in selected books", "read"),
)
async def search_documents_with_filter(
    index: Index,
    text: Query,
    allowed_books: BookNames = [],
    forbidden_books: BookNames = [],
    top_k: TopK = 10,
) -> SearchResult:
    """
    Same as search_documents, but only searches in `allowed_books` and/or
    skips `forbidden_books`. Book names are validated against search_books;
    an unknown name is reported as an error together with the valid names.
    """
    logger.info(
        f"search_documents_with_filter index={index} top_k={top_k} "
        f"allowed={allowed_books} forbidden={forbidden_books}"
    )
    if allowed_books or forbidden_books:
        check_books(allowed_books + forbidden_books, await list_books(index))

    bool_query: dict = {}
    if allowed_books:
        bool_query["filter"] = [{"terms": {"document_name.keyword": allowed_books}}]
    if forbidden_books:
        bool_query["must_not"] = [{"terms": {"document_name.keyword": forbidden_books}}]

    if not bool_query:
        return await _search(index, text, top_k)

    data = await get_client().post(
        "/api/v1/search/filter_documents",
        json={"index": index, "text": text, "top_k": top_k, "filter": {"bool": bool_query}},
    )
    return _to_result(index, text, data or {})


@mcp.resource(
    "resource://indexes",
    name="rag_indexes",
    description="RAG (book) indexes available for search.",
    mime_type="application/json",
)
async def indexes_resource() -> list[str]:
    return await list_rag_indexes()
