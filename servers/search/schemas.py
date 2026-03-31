from pydantic import BaseModel, Field


class SearchDocumentsPayload(BaseModel):
    """Payload for semantic search over one OpenSearch index."""

    index: str = Field(
        description="Exact OpenSearch index name where the search is performed.",
        examples=["dnd-index"],
    )
    text: str = Field(
        description="Natural-language search query. Use full user intent, not keywords only.",
        examples=[
            "Find a description of the spell Magic Hand and Poison Spray.",
            "What does the rage mechanic do for a barbarian?",
        ],
    )
    top_k: int = Field(
        ge=10,
        description="How many top chunks/documents to return. Must be >= 10.",
        examples=[10, 15, 20],
    )


class SearchFilterDocumentsPayload(BaseModel):
    """Payload for semantic search with optional include/exclude book filters."""

    index: str = Field(
        description="Exact OpenSearch index name where the search is performed.",
        examples=["dnd-index"],
    )
    text: str = Field(
        description="Natural-language search query. Use full user intent.",
        examples=[
            "Find all mentions of polymorph limitations.",
            "How does concentration work for spells?",
        ],
    )
    top_k: int = Field(
        ge=10,
        description="How many top chunks/documents to return. Must be >= 10.",
        examples=[10, 20],
    )
    allowed_books: list[str] = Field(
        default_factory=list,
        description="Only search in these books. Pass [] to disable include filter.",
        examples=[
            ["Player's Handbook", "Xanathar's Guide to Everything"],
            [],
        ],
    )
    forbidden_books: list[str] = Field(
        default_factory=list,
        description="Exclude these books from results. Pass [] to disable exclude filter.",
        examples=[
            ["Unearthed Arcana"],
            [],
        ],
    )
