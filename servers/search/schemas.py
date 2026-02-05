from pydantic import BaseModel, Field


class SearchDocumentsPayload(BaseModel):
    index: str = Field()
    text: str = Field()
    top_k: int = Field(ge=10)
