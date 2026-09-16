"""
AcadTrack — Database Layer
University of Loralai, Pakistan

Connects to the SAME gpa_system.db that the Streamlit app already uses.
Models are defined in src/models/database_models.py — NOT here.

Usage in a FastAPI route:
    from backend.database import get_db
    from sqlalchemy.orm import Session

    def my_route(db: Session = Depends(get_db)):
        ...
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from backend.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
# check_same_thread=False is required for SQLite when used with FastAPI because
# multiple threads (one per request) share the same connection pool.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,          # set True temporarily to see SQL in the terminal
)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ── Declarative base ──────────────────────────────────────────────────────────
# This Base is local to the backend package.
# The Streamlit app has its own Base in src/models/database_models.py;
# both point at the same DB file so they share the same physical tables.
class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
def get_db():
    """
    Yield a SQLAlchemy session, then close it when the request finishes.
    Use as a FastAPI Depends() parameter.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Initialisation helper ─────────────────────────────────────────────────────
def init_db() -> None:
    """
    Create any tables registered against this backend's Base.
    (The Streamlit models live in src/ and are managed separately.)
    Call this once on application startup.
    """
    Base.metadata.create_all(bind=engine)
