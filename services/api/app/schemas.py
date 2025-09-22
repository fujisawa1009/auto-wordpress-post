"""
Pydantic schemas for request/response validation
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, HttpUrl, Field, validator
from pydantic.types import constr


class ToneType(str, Enum):
    """Article tone types"""
    TECH = "tech"
    BUSINESS = "business"
    CASUAL = "casual"
    FORMAL = "formal"
    ACADEMIC = "academic"


class PublishMode(str, Enum):
    """WordPress publish modes"""
    DRAFT = "draft"
    PUBLISH = "publish"
    SCHEDULE = "schedule"


class InternalLink(BaseModel):
    """Internal link schema"""
    anchor: str = Field(..., min_length=1, max_length=100)
    url: HttpUrl


class FAQ(BaseModel):
    """FAQ schema"""
    question: str = Field(..., min_length=5, max_length=200)
    answer_html: str = Field(..., min_length=10)


class GenerateInput(BaseModel):
    """Article generation input schema"""
    summary: str = Field(..., min_length=50, max_length=1000, description="Article summary (50-1000 chars)")
    goal: str = Field(..., min_length=20, max_length=500, description="Article goal/purpose")
    audience: str = Field(..., min_length=10, max_length=200, description="Target audience")
    must_topics: List[str] = Field(default=[], description="Must-include topics")
    bans: List[str] = Field(default=[], description="Prohibited topics/words")
    references: List[HttpUrl] = Field(default=[], max_items=5, description="Reference URLs (max 5)")
    tone: ToneType = Field(default=ToneType.TECH, description="Article tone")
    target_chars: int = Field(default=10000, ge=9000, le=11000, description="Target character count")
    author: Optional[str] = Field(None, max_length=100, description="Author name")
    internal_links: List[InternalLink] = Field(default=[], max_items=10, description="Internal link candidates")

    @validator('must_topics')
    def validate_must_topics(cls, v):
        """Validate must topics"""
        if len(v) > 10:
            raise ValueError("Maximum 10 must topics allowed")
        return v

    @validator('bans')
    def validate_bans(cls, v):
        """Validate banned topics"""
        if len(v) > 20:
            raise ValueError("Maximum 20 banned items allowed")
        return v


class ArticleOutput(BaseModel):
    """Article output schema"""
    title: str = Field(..., min_length=10, max_length=100)
    slug: constr(regex=r'^[a-z0-9-]+$', min_length=3, max_length=50)
    excerpt: str = Field(..., min_length=50, max_length=300)
    meta_description: str = Field(..., min_length=50, max_length=160)
    tags: List[str] = Field(default=[], max_items=10)
    categories: List[str] = Field(default=[], max_items=5)
    hero_image_prompt: Optional[str] = Field(None, max_length=500)
    body_html: str = Field(..., min_length=1000)
    faq: List[FAQ] = Field(default=[], max_items=10)
    internal_links: List[InternalLink] = Field(default=[], max_items=15)
    cta_html: str = Field(default="")
    schema_org: Dict[str, Any] = Field(default={})

    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags"""
        for tag in v:
            if len(tag) < 2 or len(tag) > 30:
                raise ValueError("Tag length must be between 2-30 characters")
        return v

    @validator('categories')
    def validate_categories(cls, v):
        """Validate categories"""
        for category in v:
            if len(category) < 2 or len(category) > 50:
                raise ValueError("Category length must be between 2-50 characters")
        return v


class GenerateResponse(BaseModel):
    """Article generation response"""
    article_id: str
    status: str
    message: Optional[str] = None


class ArticleResponse(BaseModel):
    """Article retrieval response"""
    article_id: str
    status: str
    char_count: int
    output: Optional[ArticleOutput] = None
    wp_post_id: Optional[int] = None
    wp_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PublishRequest(BaseModel):
    """WordPress publish request"""
    mode: PublishMode
    schedule_at: Optional[datetime] = Field(None, description="Schedule datetime for future posts")

    @validator('schedule_at')
    def validate_schedule_at(cls, v, values):
        """Validate schedule datetime"""
        if values.get('mode') == PublishMode.SCHEDULE and not v:
            raise ValueError("schedule_at is required for scheduled posts")
        if v and v <= datetime.now():
            raise ValueError("schedule_at must be in the future")
        return v


class PublishResponse(BaseModel):
    """WordPress publish response"""
    wp_post_id: int
    wp_url: str
    status: str
    message: Optional[str] = None


class TaxonomyItem(BaseModel):
    """Taxonomy item schema"""
    id: int
    name: str
    slug: str
    description: Optional[str] = None


class TaxonomyResponse(BaseModel):
    """Taxonomy sync response"""
    categories: List[TaxonomyItem]
    tags: List[TaxonomyItem]
    synced_at: datetime


class ErrorResponse(BaseModel):
    """Error response schema"""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    timestamp: datetime = Field(default_factory=datetime.now)