from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UEM_API_", env_file=".env", extra="ignore")

    environment: str = "development"
    data_dir: Path = Path("data")
    log_level: str = "INFO"
    version: str = Field(default="0.1.0", frozen=True)
