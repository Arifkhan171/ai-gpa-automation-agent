"""
AcadTrack — FastAPI Backend Configuration
University of Loralai, Pakistan

BASE_DIR is resolved from this file's location at import time.
That means DATABASE_URL and all file paths are always absolute,
and the server works from any working directory on any OS
(Windows backslashes are converted to forward slashes for SQLite).
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/config.py  →  parent = backend/  →  parent.parent = project root
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# SQLite requires forward slashes even on Windows
# Path.as_posix() converts  D:\foo\bar  →  D:/foo/bar
_DB_URL = "sqlite:///" + (BASE_DIR / "gpa_system.db").as_posix()


class Settings(BaseSettings):
    # ── Application identity ─────────────────────────────────────────
    APP_NAME: str = "AcadTrack"
    APP_VERSION: str = "1.0.0"

    # ── Database ─────────────────────────────────────────────────────
    # Default is the absolute path built above.
    # .env can override this, but only if it also uses an absolute path.
    DATABASE_URL: str = _DB_URL

    # ── JWT / Auth ───────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ── University metadata ──────────────────────────────────────────
    UNIVERSITY_NAME: str = "University of Loralai"
    DEPARTMENT: str = "CS Department"

    # ── Email / SMTP ─────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "AcadTrack UoL"
    SMTP_FROM_EMAIL: str = ""
    EMAIL_ENABLED: bool = False

    # ── SMS / Twilio ─────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    SMS_ENABLED: bool = False

    # ── Notification queue ───────────────────────────────────────────
    NOTIFICATION_RETRY_MAX: int = 3
    NOTIFICATION_RETRY_DELAY_MINUTES: int = 5

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Single shared instance — import this everywhere
settings = Settings()

# Absolute paths used by routers — forward-slash safe on Windows too
LOGO_PATH: str = (BASE_DIR / "src" / "dashboard" / "assets" / "uol_logo.png").as_posix()
