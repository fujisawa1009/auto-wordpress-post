"""
SQLAlchemy database models
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, JSON,
    Enum as SQLEnum, Boolean, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.deps import Base


class ArticleStatus(str, Enum):
    """Article processing status"""
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class JobType(str, Enum):
    """Job type enumeration"""
    GENERATE = "generate"
    PUBLISH = "publish"
    MEDIA_UPLOAD = "media_upload"


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaxonomyType(str, Enum):
    """Taxonomy type enumeration"""
    CATEGORY = "category"
    TAG = "tag"


class Article(Base):
    """Article model"""
    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_payload = Column(JSON, nullable=False)
    output_payload = Column(JSON, nullable=True)
    status = Column(SQLEnum(ArticleStatus), default=ArticleStatus.PENDING, nullable=False)
    slug = Column(String(255), unique=True, nullable=True)
    char_count = Column(Integer, default=0)
    idempotency_key = Column(String(64), unique=True, nullable=True)
    wp_post_id = Column(Integer, nullable=True)
    wp_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, status={self.status})>"

    @classmethod
    def create_from_input(cls, input_data: Dict[str, Any], idempotency_key: Optional[str] = None) -> "Article":
        """Create new article from input data"""
        return cls(
            input_payload=input_data,
            idempotency_key=idempotency_key,
            status=ArticleStatus.PENDING
        )

    def store_output(self, output_data: Dict[str, Any], status: ArticleStatus, char_count: int = 0) -> None:
        """Store generation output"""
        self.output_payload = output_data
        self.status = status
        self.char_count = char_count
        if output_data and "slug" in output_data:
            self.slug = output_data["slug"]

    def mark_published(self, wp_post_id: int, wp_url: str) -> None:
        """Mark article as published"""
        self.wp_post_id = wp_post_id
        self.wp_url = wp_url
        self.status = ArticleStatus.PUBLISHED


class Job(Base):
    """Background job model"""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(SQLEnum(JobType), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    tries = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, type={self.type}, status={self.status})>"

    def mark_running(self) -> None:
        """Mark job as running"""
        self.status = JobStatus.RUNNING
        self.tries += 1

    def mark_succeeded(self, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark job as succeeded"""
        self.status = JobStatus.SUCCEEDED
        self.result = result
        self.last_error = None

    def mark_failed(self, error: str) -> None:
        """Mark job as failed"""
        self.status = JobStatus.FAILED
        self.last_error = error


class Taxonomy(Base):
    """WordPress taxonomy cache (categories/tags)"""
    __tablename__ = "taxonomies"

    id = Column(Integer, primary_key=True)
    type = Column(SQLEnum(TaxonomyType), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    wp_id = Column(Integer, unique=True, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('type', 'name', name='unique_type_name'),
        UniqueConstraint('type', 'slug', name='unique_type_slug'),
    )

    def __repr__(self) -> str:
        return f"<Taxonomy(type={self.type}, name={self.name}, wp_id={self.wp_id})>"

    @classmethod
    def create_from_wp(cls, type_: TaxonomyType, wp_data: Dict[str, Any]) -> "Taxonomy":
        """Create taxonomy from WordPress API response"""
        return cls(
            type=type_,
            name=wp_data["name"],
            slug=wp_data["slug"],
            wp_id=wp_data["id"],
            description=wp_data.get("description", "")
        )