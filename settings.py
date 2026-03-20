from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(
        Path(__file__).parent.joinpath(".env.production")))

    # Service
    HOST: str = "0.0.0.0"
    PORT: int = 13005
    TEMP_DIRECTORY: Path = Path(__file__).parent.joinpath("tmp")

    # Go-opensearch-database
    GO_OPENSEARCH_DATABASE_URL: str
    GO_OPENSEARCH_DATABASE_BOOKS_LIST_ENDPOINT: str = "/api/v1/books/list"
    GO_OPENSEARCH_DATABASE_BOOKS_DESCRIPTIONS_ENDPOINT: str = "/api/v1/books/descriptions"
    GO_OPENSEARCH_DATABASE_BOOKS_DESCRIPTION_ENDPOINT: str = "/api/v1/books/description"
    GO_OPENSEARCH_DATABASE_SEARCH_DOCUMENTS_ENDPOINT: str = "/api/v1/search/documents"
    GO_OPENSEARCH_DATABASE_SEARCH_FILTER_DOCUMENTS_ENDPOINT: str = "/api/v1/search/filter_documents"
    GO_OPENSEARCH_DATABASE_INDEXES_ENDPOINT: str = "/api/v1/index-manager/indexes"

    # Creds for tests
    TEST_PROVIDER_BASE_URL: Optional[str] = None
    TEST_API_KEY: Optional[str] = None
    TEST_MODEL_NAME: Optional[str] = None
    TEST_MCP_URL: Optional[str] = None

    @property
    def go_opensearch_database_books_list_endpoint(self) -> str:
        return f"{self.GO_OPENSEARCH_DATABASE_URL}{self.GO_OPENSEARCH_DATABASE_BOOKS_LIST_ENDPOINT}"

    @property
    def go_opensearch_database_search_documents_endpoint(self) -> str:
        return f"{self.GO_OPENSEARCH_DATABASE_URL}{self.GO_OPENSEARCH_DATABASE_SEARCH_DOCUMENTS_ENDPOINT}"

    @property
    def go_opensearch_database_search_filter_documents_endpoint(self) -> str:
        return f"{self.GO_OPENSEARCH_DATABASE_URL}{self.GO_OPENSEARCH_DATABASE_SEARCH_FILTER_DOCUMENTS_ENDPOINT}"

    @property
    def go_opensearch_database_books_descriptions_endpoint(self) -> str:
        return f"{self.GO_OPENSEARCH_DATABASE_URL}{self.GO_OPENSEARCH_DATABASE_BOOKS_DESCRIPTIONS_ENDPOINT}"

    @property
    def go_opensearch_database_books_description_endpoint(self) -> str:
        return f"{self.GO_OPENSEARCH_DATABASE_URL}{self.GO_OPENSEARCH_DATABASE_BOOKS_DESCRIPTION_ENDPOINT}"

    @property
    def go_opensearch_database_indexes_endpoint(self) -> str:
        return f"{self.GO_OPENSEARCH_DATABASE_URL}{self.GO_OPENSEARCH_DATABASE_INDEXES_ENDPOINT}"


settings = Settings()  # type: ignore
