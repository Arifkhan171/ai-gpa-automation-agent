"""
AcadTrack — User Model
University of Loralai, Pakistan

Defines the 'users' table for the AcadTrack login/role system.
This is separate from src/models/database_models.py (Streamlit models).
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from backend.database import Base


VALID_ROLES = {"super_admin", "controller", "hod", "coordinator", "student"}


class User(Base):
    __tablename__ = "acadtrack_users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String(50), unique=True, nullable=False, index=True)
    email           = Column(String(100), unique=True, nullable=False)
    full_name       = Column(String(200), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(String(20), nullable=False)
    # Allowed: super_admin | controller | hod | coordinator | student
    department      = Column(String(100), nullable=True)
    phone           = Column(String(20), nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=func.now())
    last_login      = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"
