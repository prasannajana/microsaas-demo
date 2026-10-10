"""Application settings loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder secrets that must never be used outside local development.
PLACEHOLDER_SECRET_KEYS = frozenset(
    {
        "dev-secret-key-change-in-production",
        "your-secret-key-change-in-production",
        "your-secret-key",
        "changeme",
    }
)
MIN_PRODUCTION_SECRET_KEY_LENGTH = 32
JWT_ALGORITHM = "HS256"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Project Verification"
    # "production" enables strict startup checks (e.g. a real SECRET_KEY).
    ENV: Literal["development", "test", "production"] = "development"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/project_verification"

    # Auth
    SECRET_KEY: str = "dev-secret-key-change-in-production"  # noqa: S105 - dev default only
    # Pinned: only HS256 is accepted (validated below) to rule out algorithm confusion.
    ALGORITHM: str = JWT_ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Scanner
    SCAN_WORKDIR: str = "/tmp/project-verification"  # noqa: S108 - configurable via env
    SCAN_CLONE_TIMEOUT_SECONDS: int = 60
    # Overall wall-clock budget for one scan (metadata + clone + checks).
    SCAN_TOTAL_TIMEOUT_SECONDS: int = 120
    SCAN_MAX_REPO_SIZE_MB: int = 200
    # Maximum number of entries in the repository tree (checked before checkout).
    SCAN_MAX_FILES: int = 50_000
    # Scans run on a dedicated thread pool of this size.
    SCAN_CONCURRENCY: int = 2
    # Global cap on queued + running scans across all users (429 when reached).
    SCAN_MAX_QUEUED: int = 20
    SCANS_PER_HOUR_PER_USER: int = 10
    MAX_PROJECTS_PER_USER: int = 50
    # Optional: used ONLY for the GitHub metadata API call (higher rate limits).
    # Never sent on clones; private repositories are always rejected.
    GITHUB_TOKEN: str = ""

    @field_validator("ALGORITHM")
    @classmethod
    def _pin_algorithm(cls, value: str) -> str:
        if value != JWT_ALGORITHM:
            raise ValueError(f"ALGORITHM must be {JWT_ALGORITHM}")
        return value

    @field_validator("SCAN_CONCURRENCY", "SCAN_MAX_QUEUED", "SCAN_MAX_FILES")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be >= 1")
        return value

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.ENV == "production":
            key = self.SECRET_KEY.strip()
            if (
                key.lower() in PLACEHOLDER_SECRET_KEYS
                or len(key) < MIN_PRODUCTION_SECRET_KEY_LENGTH
            ):
                raise ValueError(
                    "SECRET_KEY must be set to a random value of at least "
                    f"{MIN_PRODUCTION_SECRET_KEY_LENGTH} characters when ENV=production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
