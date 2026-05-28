from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Enum,
    JSON,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"


class MistakeType(str, enum.Enum):
    concept = "concept"
    calculation = "calculation"
    careless = "careless"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    first_name = Column(String, nullable=False, default="")
    last_name = Column(String, nullable=False, default="")
    role = Column(Enum(UserRole), default=UserRole.student)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, default=False)
    exam_target = Column(String, nullable=True)
    subjects = Column(JSON, default=list)
    study_hours = Column(String, nullable=True)
    exam_date = Column(String, nullable=True)
    onboarding_complete = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat_logs = relationship("ChatLog", back_populates="user", cascade="all,delete")
    topic_performances = relationship(
        "TopicPerformance", back_populates="user", cascade="all,delete"
    )
    memory_trackings = relationship(
        "MemoryTracking", back_populates="user", cascade="all,delete"
    )
    study_plans = relationship("StudyPlan", back_populates="user", cascade="all,delete")
    sessions = relationship("UserSession", back_populates="user", cascade="all,delete")
    quiz_attempts = relationship(
        "QuizAttempt", back_populates="user", cascade="all,delete"
    )
    backup_codes = relationship(
        "BackupCode", back_populates="user", cascade="all,delete"
    )
    notes = relationship("Note", back_populates="user", cascade="all,delete")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    refresh_token_hash = Column(String, nullable=False, index=True)
    device_name = Column(String, nullable=True)
    device_fp = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    location = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sessions")


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    purpose = Column(String, nullable=False)  # register | login | device | reset
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BackupCode(Base):
    __tablename__ = "backup_codes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    code_hash = Column(String, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="backup_codes")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    subject = Column(String, nullable=True)
    topic = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    sources = Column(JSON, default=list)
    is_academic = Column(Boolean, default=True)
    language = Column(String, default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chat_logs")


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    topic = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    flashcards = Column(JSON, default=list)
    exam_questions = Column(JSON, default=list)
    is_indexed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notes")


class TopicPerformance(Base):
    __tablename__ = "topic_performance"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    score = Column(Float, default=0.0)
    ai_dependency_count = Column(Integer, default=0)
    concept_errors = Column(Integer, default=0)
    calc_errors = Column(Integer, default=0)
    careless_errors = Column(Integer, default=0)
    total_attempts = Column(Integer, default=0)
    is_weak = Column(Boolean, default=False)
    is_high_ai_dep = Column(Boolean, default=False)
    last_practiced = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="topic_performances")


class MemoryTracking(Base):
    __tablename__ = "memory_tracking"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    retention_score = Column(Float, default=100.0)
    decay_rate = Column(Float, default=0.1)
    last_reviewed = Column(DateTime(timezone=True), server_default=func.now())
    next_revision = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="memory_trackings")


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    priority = Column(Integer, default=1)
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="study_plans")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    student_answer = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    mistake_type = Column(Enum(MistakeType), nullable=True)
    mistake_reason = Column(Text, nullable=True)
    score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="quiz_attempts")


class DailyActivity(Base):
    __tablename__ = "daily_activity"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    date = Column(String, nullable=False)
    chat_count = Column(Integer, default=0)
    quiz_count = Column(Integer, default=0)
    notes_count = Column(Integer, default=0)
    study_mins = Column(Integer, default=0)
