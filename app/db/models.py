# app/db/models.py
from datetime import datetime
from typing import List, Optional
from sqlalchemy import BigInteger, Numeric, Text, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    preferred_role: Mapped[Optional[str]] = mapped_column(Text)
    experience_years: Mapped[Optional[float]] = mapped_column(Numeric)
    locations: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    resumes: Mapped[List["Resume"]] = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    ats_score: Mapped[Optional[float]] = mapped_column(Numeric)
    approved_keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="resumes")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="resume")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[Optional[str]] = mapped_column(Text) # linkedin/naukri
    title: Mapped[Optional[str]] = mapped_column(Text)
    company: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    apply_link: Mapped[Optional[str]] = mapped_column(Text)
    requirements: Mapped[Optional[dict]] = mapped_column(JSONB)
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="job", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("resumes.id", ondelete="SET NULL"))
    status: Mapped[Optional[str]] = mapped_column(Text) # applied/pending/rejected/failed
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="applications")
    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    resume: Mapped[Optional["Resume"]] = relationship("Resume", back_populates="applications")


class UserSession(Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    platform: Mapped[str] = mapped_column(Text, primary_key=True) # linkedin/naukri
    encrypted_cookie: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
