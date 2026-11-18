import json
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from tick.core.paths import DataPaths


def parse_cors_origins(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    if not value.strip():
        return []
    if value.strip().startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ValueError("CORS_ORIGINS JSON must be a list")
        return [str(item) for item in parsed]
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "tick"
    environment: str = "development"
    debug: bool = False
    docs_enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    api_prefix: str = "/api"
    static_dir: str = ""
    # Relative paths resolve against the process cwd (usually backend/).
    data_dir: Path = Field(default=Path("./data"))
    cors_origins: Annotated[
        list[str],
        NoDecode,
        BeforeValidator(parse_cors_origins),
    ] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("static_dir", mode="before")
    @classmethod
    def empty_static_dir(cls, value: object) -> object:
        if value is None:
            return ""
        return value

    @field_validator("data_dir", mode="before")
    @classmethod
    def parse_data_dir(cls, value: object) -> object:
        if value is None or value == "":
            return Path("./data")
        return value

    @property
    def paths(self) -> DataPaths:
        return DataPaths(root=self.data_dir.expanduser().resolve())


settings = Settings()
