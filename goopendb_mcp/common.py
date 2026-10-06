from typing import Annotated, Generic, Literal, TypeVar

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

T = TypeVar("T")

Kind = Literal["read", "create", "update", "delete"]


def annotations(title: str, kind: Kind) -> ToolAnnotations:
    """Standard MCP hints. GoOpenDB is an internal system, so openWorldHint is False."""
    return ToolAnnotations(
        title=title,
        readOnlyHint=kind == "read",
        destructiveHint=kind in ("update", "delete"),
        idempotentHint=kind != "create",
        openWorldHint=False,
    )


class Page(BaseModel, Generic[T]):
    total: int = Field(description="Number of items matching the filters.")
    count: int = Field(description="Number of items in this page.")
    offset: int
    has_more: bool
    next_offset: int | None = Field(description="Offset of the next page, null on the last page.")
    items: list[T]


def paginate(items: list[T], limit: int, offset: int) -> Page[T]:
    page = items[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < len(items)
    return Page[T](
        total=len(items),
        count=len(page),
        offset=offset,
        has_more=has_more,
        next_offset=next_offset if has_more else None,
        items=page,
    )


def preview(text: str | None, length: int = 200) -> str:
    """Shorten long prompts in list views; full text is available via get tools."""
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= length else text[: length - 1] + "…"


def contains(value: str | None, needle: str | None) -> bool:
    return not needle or needle.casefold() in (value or "").casefold()


Limit = Annotated[int, Field(ge=1, le=200, description="Maximum number of items to return.")]
Offset = Annotated[int, Field(ge=0, description="Number of items to skip (for pagination).")]
NameContains = Annotated[
    str | None,
    Field(description="Optional case-insensitive substring filter on the name."),
]
Index = Annotated[
    str,
    Field(
        min_length=1,
        description="Exact OpenSearch index name, e.g. 'dnd-index'. Use search_list_indexes to discover names.",
    ),
]
Uuid = Annotated[str, Field(min_length=1, description="Record id (UUID) as returned by list/get/create tools.")]
