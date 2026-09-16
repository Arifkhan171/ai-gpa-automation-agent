"""
AcadTrack — FastAPI Backend Configuration
University of Loralai, Pakistan

All settings are loaded from environment variables (or a .env file).
Sensible defaults are provided so the server runs out-of-the-box with
the existing SQLite database.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application identity ─────────────────────────────────────────
    APP_NAME: str = "AcadTrack"
    APP_VERSION: str = "1.0.0"

    # ── Database ─────────────────────────────────────────────────────
    # Points to the existing SQLite file one level above backend/
    DATABASE_URL: str = "sqlite:///../gpa_system.db"

    # ── JWT / Auth ───────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ── University metadata ──────────────────────────────────────────
    UNIVERSITY_NAME: str = "University of Loralai"
    DEPARTMENT: str = "CS Department"

    model_config = SettingsConfigDict(
        env_file=".env",          # load from .env when present
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",           # ignore unknown env vars
    )


# Single shared instance — import this everywhere
settings = Settings()
