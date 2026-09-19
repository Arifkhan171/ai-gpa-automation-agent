"""
AcadTrack — Auth Router
University of Loralai, Pakistan

Endpoints:
  POST   /api/v1/auth/login                  — public
  GET    /api/v1/auth/me                     — authenticated
  POST   /api/v1/auth/logout                 — authenticated
  POST   /api/v1/auth/change-password        — authenticated
  POST   /api/v1/auth/users                  — super_admin only
  GET    /api/v1/auth/users                  — super_admin | hod
  PATCH  /api/v1/auth/users/{user_id}/deactivate — super_admin only
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models.user_model import User
from src.models.database_models import Student
from backend.schemas.auth_schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserInfo,
    UserResponse,
)
from backend.utils.auth_utils import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# ── POST /login ───────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username + password.
    Returns a JWT Bearer token and basic user info.
    """
    # 1. Look up the user
    user = db.query(User).filter(User.username == body.username).first()
    if not user:
        # Student auto-login: check if the username matches a roll_no in Student table
        student = (
            db.query(Student)
            .filter(Student.roll_no.ilike(body.username))
            .first()
        )
        if student:
            # Auto-create a User record for this student
            new_student_user = User(
                username=student.roll_no,
                email=f"{student.roll_no.replace('/', '_').replace(' ', '_')}@student.uol.edu.pk",
                full_name=student.student_name,
                hashed_password=hash_password("Student@123"),
                role="student",
                department=student.department,
                is_active=True,
            )
            db.add(new_student_user)
            db.commit()
            db.refresh(new_student_user)
            user = new_student_user
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

    # 2. Verify password
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # 3. Reject inactive accounts
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    # 4. Record login time
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # 5. Issue JWT
    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        expires_delta=timedelta(minutes=expire_minutes),
    )

    # 6. Return full response
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
        user=UserInfo(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            department=user.department,
            email=user.email,
        ),
    )


# ── GET /me ───────────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


# ── POST /logout ──────────────────────────────────────────────────────────────
@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout (stateless — instructs the client to discard the token).
    JWT cannot be server-side revoked; the frontend must delete the token.
    """
    return {"message": "Logged out successfully"}


# ── POST /change-password ─────────────────────────────────────────────────────
@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the authenticated user's password."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# ── POST /users ───────────────────────────────────────────────────────────────
@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("super_admin")),
):
    """Create a new AcadTrack user account. Requires super_admin role."""
    # Unique username check
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )
    # Unique email check
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        department=body.department,
        phone=body.phone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ── GET /users ────────────────────────────────────────────────────────────────
@router.get("/users", response_model=list[UserResponse])
def list_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("super_admin", "hod")),
):
    """List all users. Accessible by super_admin and hod."""
    query = db.query(User)
    if role is not None:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    return query.all()


# ── PATCH /users/{user_id}/deactivate ────────────────────────────────────────
@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("super_admin")),
):
    """Deactivate a user account. Requires super_admin role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.is_active = False
    db.commit()
    return {"message": "User deactivated"}
