from pydantic import BaseModel, Field


class SearchDocumentsPayload(BaseModel):
    index: str = Field()
    text: str = Field()
    top_k: int = Field(ge=10)


class Description(BaseModel):
    book_name: str
    parent_index: str
    description: str


class DescriptionWrite(BaseModel):
    index: str
    book_name: str
    description: str


class DescriptionDelete(BaseModel):
    index: str
    book_name: str
