"""
Dependency injection and configuration management
"""
import os
from functools import lru_cache
from typing import Generator

from pydantic import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session


class Settings(BaseSettings):
    """Application settings"""

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    debug: bool = False
    secret_key: str = "change-this-in-production"

    # Database
    database_url: str

    # Redis
    redis_url: str

    # Perplexity API
    pplx_api_key: str
    pplx_model: str = "sonar-pro"
    pplx_disable_search: bool = True

    # WordPress
    wp_base_url: str
    wp_username: str
    wp_application_password: str

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Database setup
settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()