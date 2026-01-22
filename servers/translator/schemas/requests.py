from pydantic import BaseModel, Field


class TranslateTextRequest(BaseModel):
    source_language: str = Field(description="Translating source language in iso 639_1")
    target_language: str = Field(description="Translating target language in iso 639_1")
    text: str = Field(description="Text to translate")