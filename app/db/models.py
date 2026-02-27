# app/db/models.py
"""
Recruitment AI — Database Schema
Tables covering the active hiring pipeline:
  users, job_requests, candidates, candidate_evaluations,
  notifications, jd_form_data, jd_memories
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, Enum as SAEnum, JSON,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.db.database import Base


# ── Enums ──────────────────────────────────────────────

class UserRole(str, enum.Enum):
    team_lead = "team_lead"
    hr = "hr"


class JobStatus(str, enum.Enum):
    draft = "draft"
    pending_hr = "pending_hr"
    rejected = "rejected"
    active = "active"
    closed = "closed"
    cancelled = "cancelled"


class JDSource(str, enum.Enum):
    ai_created = "ai_created"
    manual = "manual"
    linked = "linked"


class NotificationType(str, enum.Enum):
    job_submitted = "job_submitted"
    job_cancelled = "job_cancelled"
    job_activated = "job_activated"
    job_rejected = "job_rejected"
    closing_reminder = "closing_reminder"
    cv_evaluation_complete = "cv_evaluation_complete"
    general = "general"


class CandidateStage(str, enum.Enum):
    applied = "applied"
    cv_evaluated = "cv_evaluated"
    shortlisted = "shortlisted"
    interviewed = "interviewed"
    offer_made = "offer_made"
    hired = "hired"
    rejected = "rejected"


def _utc_now():
    return datetime.now(timezone.utc)


# ── 1. Users ───────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    department = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=_utc_now)

    # relationships
    job_requests = relationship(
        "JobRequest", back_populates="creator",
        foreign_keys="JobRequest.creator_id",
    )
    notifications = relationship("Notification", back_populates="user")


# ── 2. Job Requests ───────────────────────────────────

class JobRequest(Base):
    __tablename__ = "job_requests"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    role_title = Column(String(255), nullable=False)
    jd_text = Column(Text, nullable=True)
    department = Column(String(120), nullable=True)
    location = Column(String(120), nullable=True)
    experience_min = Column(Integer, nullable=True)
    experience_max = Column(Integer, nullable=True)
    budget = Column(Float, nullable=True)
    adjustable_budget = Column(Float, nullable=True)
    headcount = Column(Integer, default=1)
    hired_count = Column(Integer, default=0)

    end_date = Column(DateTime, nullable=True)
    status = Column(SAEnum(JobStatus), default=JobStatus.draft, nullable=False)
    rejection_reason = Column(Text, nullable=True)

    jd_source = Column(SAEnum(JDSource), nullable=True)
    profile_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    # relationships
    creator = relationship(
        "User", back_populates="job_requests",
        foreign_keys=[creator_id],
    )
    candidates = relationship("Candidate", back_populates="job")


# ── 3. Candidates ─────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=False)

    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    current_salary = Column(Float, nullable=True)
    expected_salary = Column(Float, nullable=True)
    resume_text = Column(Text, nullable=True)

    stage = Column(SAEnum(CandidateStage), default=CandidateStage.applied)
    applied_at = Column(DateTime, default=_utc_now)

    # relationships
    job = relationship("JobRequest", back_populates="candidates")
    evaluation = relationship(
        "CandidateEvaluation", back_populates="candidate",
        uselist=False,
    )


# ── 4. Candidate Evaluations ──────────────────────────

class CandidateEvaluation(Base):
    __tablename__ = "candidate_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(
        Integer, ForeignKey("candidates.id"), unique=True, nullable=False,
    )
    job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=False)

    overall_score = Column(Float, nullable=True)
    grade = Column(String(5), nullable=True)
    is_above_threshold = Column(Boolean, default=False)

    persona_scores = Column(JSON, nullable=True)
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    evaluated_at = Column(DateTime, default=_utc_now)
    is_automated = Column(Boolean, default=False)

    # relationships
    candidate = relationship("Candidate", back_populates="evaluation")
    job = relationship("JobRequest")


# ── 5. Notifications ─────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(
        SAEnum(NotificationType), default=NotificationType.general,
    )
    is_read = Column(Boolean, default=False)
    related_job_id = Column(
        Integer, ForeignKey("job_requests.id"), nullable=True,
    )
    created_at = Column(DateTime, default=_utc_now)

    # relationships
    user = relationship("User", back_populates="notifications")
    job = relationship("JobRequest")


# ── 6. JD Form Data ──────────────────────────────────

class JDFormData(Base):
    __tablename__ = "jd_form_data"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(255), nullable=False)
    department = Column(String(120), nullable=False)
    location = Column(String(120), nullable=True)
    employment_type = Column(String(50), default="Full-time")
    work_mode = Column(String(50), nullable=True)
    travel_required = Column(String(50), nullable=True)
    reporting_to = Column(String(200), nullable=True)
    experience = Column(String(100), nullable=True)
    minimum_education = Column(String(200), nullable=True)
    salary = Column(String(100), nullable=True)
    urgency = Column(String(50), nullable=True)
    new_or_scaling = Column(String(100), nullable=True)
    must_have_skills = Column(Text, nullable=True)
    other_skills = Column(Text, nullable=True)
    key_responsibilities = Column(Text, nullable=True)
    generated_jd = Column(Text, nullable=True)
    generated_profile = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utc_now)


# ── 7. JD Memory ─────────────────────────────────────

class JDMemory(Base):
    __tablename__ = "jd_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    preferences_summary = Column(Text, nullable=True)
    edit_patterns = Column(JSON, nullable=True)
    total_jds_analyzed = Column(Integer, default=0)
    last_analyzed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    # relationships
    user = relationship("User")
