from functools import lru_cache
import logging
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CamoufoxHeadlessMode = bool | Literal["virtual"]


class Settings(BaseSettings):
    api_key: SecretStr = Field(description="Shared secret required to call the API.")
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_url_length: int = Field(default=2048, ge=128, le=8192)
    allow_private_ips: bool = False
    log_level: str = "INFO"
    camoufox_headless: CamoufoxHeadlessMode = "virtual"
    camoufox_wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = (
        "networkidle"
    )
    camoufox_post_load_wait_ms: int = Field(default=0, ge=0, le=10_000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in logging.getLevelNamesMapping():
            raise ValueError("LOG_LEVEL must be a valid Python logging level")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
