"""
AcadTrack — Auth Pydantic Schemas
University of Loralai, Pakistan

Pydantic v2 models for request/response validation on auth endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

# ── Valid roles ───────────────────────────────────────────────────────────────
_VALID_ROLES = {"super_admin", "controller", "hod", "coordinator", "student"}


# ── Request models ────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class UserCreate(BaseModel):
    username:   str           = Field(min_length=3,  max_length=50)
    email:      EmailStr
    full_name:  str           = Field(min_length=2)
    password:   str           = Field(min_length=6)
    role:       str
    department: Optional[str] = None
    phone:      Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in _VALID_ROLES:
            raise ValueError(
                f"Invalid role '{v}'. Must be one of: {', '.join(sorted(_VALID_ROLES))}"
            )
        return v


# ── Response models ───────────────────────────────────────────────────────────
class UserInfo(BaseModel):
    """Lightweight user info embedded inside TokenResponse."""
    id:         int
    username:   str
    full_name:  str
    role:       str
    department: Optional[str] = None
    email:      str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int   # seconds until expiry
    user:         UserInfo


class UserResponse(BaseModel):
    """Full user record returned from /users endpoints."""
    id:         int
    username:   str
    full_name:  str
    email:      str
    role:       str
    department: Optional[str] = None
    phone:      Optional[str] = None
    is_active:  bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
