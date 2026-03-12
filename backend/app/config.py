from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./ai_match_mvp.db"
    deepseek_api_key: str | None = None
    ai_extraction_enabled: bool = True

    auth_required: bool = True
    privileged_roles: str = "admin,matchmaker"
    allow_legacy_headers: bool = False
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allow_sqlite_in_production: bool = False

    jwt_secret_key: str = "change_me_in_production"
    jwt_issuer: str = "ai-match-backend"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=120, ge=1, le=1440)
    jwt_leeway_seconds: int = Field(default=5, ge=0, le=300)

    @property
    def privileged_role_set(self) -> set[str]:
        return {item.strip().lower() for item in self.privileged_roles.split(",") if item.strip()}

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development_like(self) -> bool:
        return self.environment in {"development", "test"}

    @property
    def legacy_headers_enabled(self) -> bool:
        return self.allow_legacy_headers and self.environment == "test"

    @property
    def ai_ready(self) -> bool:
        return self.ai_extraction_enabled and bool(self.deepseek_api_key)

    def validate_runtime_requirements(self) -> None:
        if self.is_production:
            if not self.auth_required:
                raise ValueError("Production mode requires auth_required=True")
            if self.allow_legacy_headers:
                raise ValueError("Production mode forbids allow_legacy_headers=True")
            if self.jwt_secret_key == "change_me_in_production" or len(self.jwt_secret_key) < 32:
                raise ValueError("Production mode requires a JWT secret key with at least 32 characters")
            if self.database_url.startswith("sqlite") and not self.allow_sqlite_in_production:
                raise ValueError("Production mode forbids SQLite unless allow_sqlite_in_production=True")

        if self.ai_extraction_enabled and not self.deepseek_api_key and self.is_production:
            raise ValueError("Production mode requires DEEPSEEK_API_KEY when ai_extraction_enabled=True")


@lru_cache
def get_settings() -> Settings:
    return Settings()
