import json
from typing import Annotated

from pydantic import BeforeValidator, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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


settings = Settings()
