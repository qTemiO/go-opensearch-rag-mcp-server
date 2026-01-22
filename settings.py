from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
            env_file=os.getenv('ENV_FILE', Path(__file__).parent.joinpath(".env.dev").__str__()))

    # Service
    HOST: str = "0.0.0.0"
    PORT: int = 13005
    TEMP_DIRECTORY: Path = Path(__file__).parent.joinpath("tmp")

    # Gorag Service
    RAG_SERVICE_URL: str
    
    # Translator service
    TRANSLATOR_SERVICE_BASE_URL: str
    TRANSLATOR_SERVICE_MODEL_GARDEN: str
    TRANSLATOR_SERVICE_DETECT_LANGUAGE: str
    TRANSLATOR_SERVICE_TRANSLATE_TEXT: str


settings = Settings()
