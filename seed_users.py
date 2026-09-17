#!/usr/bin/env python3
"""
AcadTrack — Default User Seeder
University of Loralai, Pakistan

Creates the four default AcadTrack login accounts.
Safe to run multiple times — existing users are skipped.

Usage (from project root):
    python seed_users.py
"""

import os
import sys

# ── Ensure project root is on the path ───────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Imports (after path fix) ──────────────────────────────────────────────────
from backend.database import SessionLocal, engine, Base
from backend.models.user_model import User  # registers User with Base
from backend.utils.auth_utils import hash_password

# ── Default user definitions ──────────────────────────────────────────────────
DEFAULT_USERS = [
    {
        "username":  "admin",
        "password":  "Admin@123",
        "role":      "super_admin",
        "full_name": "System Administrator",
        "email":     "admin@uol.edu.pk",
        "department":"Administration",
    },
    {
        "username":  "coordinator",
        "password":  "Coord@123",
        "role":      "coordinator",
        "full_name": "GPA Coordinator",
        "email":     "coordinator@uol.edu.pk",
        "department":"CS",
    },
    {
        "username":  "hod",
        "password":  "Hod@123",
        "role":      "hod",
        "full_name": "Head of Department CS",
        "email":     "hod@uol.edu.pk",
        "department":"CS",
    },
    {
        "username":  "controller",
        "password":  "Controller@1",
        "role":      "controller",
        "full_name": "Controller of Examinations",
        "email":     "controller@uol.edu.pk",
        "department":"Examination",
    },
]


def seed() -> None:
    print("🌱  AcadTrack — Seeding default users...\n")

    # Create tables if they don't exist (idempotent)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    created = 0
    skipped = 0

    try:
        for data in DEFAULT_USERS:
            existing = db.query(User).filter(User.username == data["username"]).first()
            if existing:
                print(f"  ⏭  SKIPPED  : {data['username']:15s}  (already exists)")
                skipped += 1
            else:
                user = User(
                    username=data["username"],
                    email=data["email"],
                    full_name=data["full_name"],
                    hashed_password=hash_password(data["password"]),
                    role=data["role"],
                    department=data["department"],
                    is_active=True,
                )
                db.add(user)
                db.commit()
                print(f"  ✅  CREATED  : {data['username']:15s}  role={data['role']}")
                created += 1
    except Exception as exc:
        db.rollback()
        print(f"\n❌  ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

    print(f"\n📊  Summary: {created} users created, {skipped} users skipped")


if __name__ == "__main__":
    seed()
