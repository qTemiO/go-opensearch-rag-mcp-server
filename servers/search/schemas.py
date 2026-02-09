from pydantic import BaseModel, Field


class SearchDocumentsPayload(BaseModel):
    index: str = Field()
    text: str = Field()
    top_k: int = Field(ge=10)


class SearchFilterDocumentsPayload(BaseModel):
    index: str = Field()
    text: str = Field()
    top_k: int = Field(ge=10)
    allowed_books: list[str] = Field(default=[])
    forbidden_books: list[str] = Field(default=[])
