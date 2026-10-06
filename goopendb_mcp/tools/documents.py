"""documents_* — generic JSON documents with per-index semantic fields."""

from typing import Annotated, Any, Literal

from loguru import logger
from pydantic import BaseModel, Field, model_validator

from goopendb_mcp.app import mcp
from goopendb_mcp.client import get_client, segment
from goopendb_mcp.common import annotations

GenericIndex = Annotated[
    str,
    Field(min_length=1, description="Name of a generic index created with documents_create_index."),
]
DocumentId = Annotated[str, Field(min_length=1, description="Document id, e.g. 'news-1'.")]
FieldPath = Annotated[
    str,
    Field(pattern=r"^document\..+", description="Path inside the document, always prefixed with 'document.', e.g. 'document.title'."),
]


class FilterCondition(BaseModel):
    """One AND-ed condition. Strings are compared exactly and case-sensitively."""

    field: FieldPath
    operator: Literal["eq", "in", "gt", "gte", "lt", "lte", "exists"] = Field(
        description="eq: equals; in: any of a list; gt/gte/lt/lte: comparison; exists: field has a value."
    )
    value: Any = Field(
        default=None,
        description="Scalar for eq/gt/gte/lt/lte, list for in, omitted for exists. E.g. 'science', 2024, ['a','b'].",
    )

    @model_validator(mode="after")
    def _check_value(self) -> "FilterCondition":
        if self.operator == "exists":
            if self.value is not None:
                raise ValueError("operator 'exists' takes no value")
        elif self.operator == "in":
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("operator 'in' needs a non-empty list value")
        elif self.value is None or isinstance(self.value, (list, dict)):
            raise ValueError(f"operator '{self.operator}' needs a scalar value")
        return self

    def to_api(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"field": self.field, "operator": self.operator}
        if self.operator != "exists":
            payload["value"] = self.value
        return payload


Filters = Annotated[
    list[FilterCondition],
    Field(description="Conditions combined with AND. Empty list means no filtering."),
]


class Document(BaseModel):
    id: str
    score: float | None = Field(default=None, description="Relevance score (search results only).")
    document: dict[str, Any]


class DocumentPage(BaseModel):
    offset: int
    count: int
    has_more: bool = Field(description="True when the page is full, so another page may exist.")
    next_offset: int | None
    documents: list[Document]


def _documents(data: Any) -> list[Document]:
    return [Document.model_validate(item) for item in (data or {}).get("documents") or []]


@mcp.tool(name="documents_search", annotations=annotations("Search generic documents", "read"))
async def documents_search(
    index: GenericIndex,
    field: Annotated[
        str,
        Field(
            pattern=r"^document\..+",
            description="One of the index's semantic_fields to search in, e.g. 'document.title'.",
        ),
    ],
    text: Annotated[str, Field(min_length=1, description="What to look for (matched by text and by meaning).")],
    filters: Filters = [],
    top_k: Annotated[int, Field(ge=1, le=100, description="Maximum number of results.")] = 10,
) -> list[Document]:
    """
    Hybrid search over one semantic field of a generic index, optionally
    narrowed by filters. Results are best first; an empty list means no match.
    """
    logger.info(f"documents_search index={index} field={field}")
    data = await get_client().post(
        "/api/v1/search/generic",
        json={
            "index": index,
            "field": field,
            "text": text,
            "top_k": top_k,
            "filters": [f.to_api() for f in filters],
        },
    )
    return _documents(data)


@mcp.tool(name="documents_filter", annotations=annotations("Filter generic documents", "read"))
async def documents_filter(
    index: GenericIndex,
    filters: Filters = [],
    limit: Annotated[int, Field(ge=1, le=100, description="Page size.")] = 20,
    offset: Annotated[int, Field(ge=0, description="Documents to skip.")] = 0,
) -> DocumentPage:
    """
    List documents of a generic index matching exact field conditions (any
    field, not only semantic ones). With no filters it pages through everything.
    Ordering is not stable between calls, so do not rely on it for deep paging.
    """
    data = await get_client().post(
        f"/api/v1/documents/{segment(index)}/filter",
        json={"filters": [f.to_api() for f in filters], "limit": limit, "offset": offset},
    )
    documents = _documents(data)
    has_more = len(documents) == limit
    return DocumentPage(
        offset=offset,
        count=len(documents),
        has_more=has_more,
        next_offset=offset + limit if has_more else None,
        documents=documents,
    )


@mcp.tool(name="documents_get", annotations=annotations("Get generic document", "read"))
async def documents_get(index: GenericIndex, id: DocumentId) -> Document:
    """Return one document of a generic index by id."""
    data = await get_client().get(f"/api/v1/documents/{segment(index)}/{segment(id)}")
    return Document.model_validate(data)


@mcp.tool(name="documents_create_index", annotations=annotations("Create generic index", "create"))
async def documents_create_index(
    index: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,254}$", description="New index name, e.g. 'news-index'."),
    ],
    semantic_fields: Annotated[
        list[FieldPath],
        Field(
            min_length=1,
            description=(
                "Paths whose string (or list of strings) values are embedded for documents_search, "
                "e.g. ['document.title', 'document.description.author']. Cannot be changed later."
            ),
        ),
    ],
) -> dict[str, Any]:
    """
    Create an index for arbitrary JSON documents. Fails with 409 if it exists.
    Other fields of the documents remain usable in filters.
    """
    logger.info(f"documents_create_index index={index} fields={semantic_fields}")
    return await get_client().post(
        "/api/v1/index-manager/generic-index",
        json={"index": index, "semantic_fields": list(dict.fromkeys(semantic_fields))},
    )


@mcp.tool(name="documents_upsert", annotations=annotations("Create or replace generic document", "update"))
async def documents_upsert(
    index: GenericIndex,
    document: Annotated[
        dict[str, Any],
        Field(description="The document itself, e.g. {'title': '...', 'category': 'science', 'year': 2026}."),
    ],
    id: Annotated[
        str | None,
        Field(description="Optional id. Omit to generate one; an existing id is fully replaced."),
    ] = None,
) -> Document:
    """
    Store a JSON document in a generic index. With an existing id the whole
    document is replaced (use documents_patch to change only some fields).
    Returns the stored document with its id.
    """
    payload: dict[str, Any] = {"document": document}
    if id:
        payload["id"] = id
    data = await get_client().post(f"/api/v1/documents/{segment(index)}", json=payload)
    return Document.model_validate(data)


@mcp.tool(name="documents_patch", annotations=annotations("Patch generic document", "update"))
async def documents_patch(
    index: GenericIndex,
    id: DocumentId,
    changes: Annotated[
        dict[str, Any],
        Field(
            min_length=1,
            description=(
                "Fields to change. Objects merge recursively, arrays and scalars are replaced, "
                "null removes a field. E.g. {'description': {'author': 'Анна'}, 'category': null}."
            ),
        ),
    ],
) -> Document:
    """Change some fields of an existing document and return the updated document."""
    data = await get_client().patch(
        f"/api/v1/documents/{segment(index)}/{segment(id)}",
        json={"document": changes},
    )
    return Document.model_validate(data)


@mcp.tool(name="documents_delete", annotations=annotations("Delete generic document", "delete"))
async def documents_delete(index: GenericIndex, id: DocumentId) -> str:
    """Delete one document (and its vectors) from a generic index."""
    await get_client().delete(f"/api/v1/documents/{segment(index)}/{segment(id)}")
    return f"Document '{id}' deleted from '{index}'."
