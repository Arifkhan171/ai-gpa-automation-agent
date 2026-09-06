"""
Database Models - Agentic GPA Calculation System
Tech Lead: Arif Khan
Branch: feature/calculator-db

5 SQLAlchemy models: Student, Subject, Mark, SemesterGPA, CGPA
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roll_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    student_name: Mapped[str] = mapped_column(String(200), nullable=False)
    father_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    marks: Mapped[List["Mark"]] = relationship(
        "Mark", back_populates="student", cascade="all, delete-orphan"
    )
    semester_gpas: Mapped[List["SemesterGPA"]] = relationship(
        "SemesterGPA", back_populates="student", cascade="all, delete-orphan"
    )
    cgpa: Mapped[Optional["CGPA"]] = relationship(
        "CGPA", back_populates="student", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Student id={self.id} roll_no={self.roll_no} name={self.student_name}>"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    credit_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    marks: Mapped[List["Mark"]] = relationship(
        "Mark", back_populates="subject", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subject id={self.id} name={self.subject_name} credit_hours={self.credit_hours}>"


class Mark(Base):
    __tablename__ = "marks"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "subject_id", "semester", "academic_year",
            name="uq_mark_student_subject_sem_year",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)

    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)

    total_marks: Mapped[float] = mapped_column(Float, nullable=False)
    obtained_marks: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    grade_point: Mapped[float] = mapped_column(Float, nullable=False)
    quality_points: Mapped[float] = mapped_column(Float, nullable=False)

    is_non_credit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    approved_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="marks")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="marks")

    def __repr__(self) -> str:
        return (
            f"<Mark student_id={self.student_id} subject_id={self.subject_id} "
            f"sem={self.semester} year={self.academic_year} gp={self.grade_point}>"
        )


class SemesterGPA(Base):
    __tablename__ = "semester_gpa"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "semester", "academic_year",
            name="uq_semester_gpa_student_sem_year",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)

    total_credit_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_quality_points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # NULL when every subject in the semester is non-credit (credit_hours = 0)
    gpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    student: Mapped["Student"] = relationship("Student", back_populates="semester_gpas")

    def __repr__(self) -> str:
        return f"<SemesterGPA student_id={self.student_id} sem={self.semester} gpa={self.gpa}>"


class CGPA(Base):
    __tablename__ = "cgpa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), unique=True, nullable=False, index=True
    )

    total_credit_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_quality_points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cgpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    semesters_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    student: Mapped["Student"] = relationship("Student", back_populates="cgpa")

    def __repr__(self) -> str:
        return f"<CGPA student_id={self.student_id} cgpa={self.cgpa}>"