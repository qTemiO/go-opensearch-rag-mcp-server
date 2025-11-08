from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(
        Path(__file__).parent.joinpath(".env.production")))

    # Service
    HOST: str = "0.0.0.0"
    PORT: int = 13005
    TEMP_DIRECTORY: Path = Path(__file__).parent.joinpath("tmp")


settings = Settings()