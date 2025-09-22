"""
Structured logging configuration
"""
import os
import logging
import logging.config
from typing import Dict, Any

import structlog
from pythonjsonlogger import jsonlogger


def setup_logging() -> None:
    """Setup structured logging with JSON format"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Configure standard library logging
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "json_file": {
                "class": "logging.FileHandler",
                "filename": "/tmp/app.json.log",
                "formatter": "json",
                "level": log_level,
            },
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
                "level": log_level,
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": log_level,
                "handlers": ["console", "json_file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "celery": {
                "level": log_level,
                "handlers": ["console", "json_file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get structured logger instance"""
    return structlog.get_logger(name)


def log_article_generation(
    article_id: str,
    action: str,
    status: str,
    **kwargs: Any
) -> None:
    """Log article generation events with structured data"""
    logger = get_logger("article_generation")
    logger.info(
        "Article generation event",
        article_id=article_id,
        action=action,
        status=status,
        **kwargs
    )


def log_perplexity_call(
    article_id: str,
    call_type: str,
    tokens_estimated: int = 0,
    latency_ms: int = 0,
    success: bool = True,
    error: str = None
) -> None:
    """Log Perplexity API calls with metrics"""
    logger = get_logger("perplexity_api")
    logger.info(
        "Perplexity API call",
        article_id=article_id,
        call_type=call_type,
        tokens_estimated=tokens_estimated,
        latency_ms=latency_ms,
        success=success,
        error=error
    )


def log_wordpress_call(
    article_id: str,
    action: str,
    wp_post_id: int = None,
    success: bool = True,
    error: str = None,
    **kwargs: Any
) -> None:
    """Log WordPress API calls"""
    logger = get_logger("wordpress_api")
    logger.info(
        "WordPress API call",
        article_id=article_id,
        action=action,
        wp_post_id=wp_post_id,
        success=success,
        error=error,
        **kwargs
    )


def sanitize_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize data for logging (remove PII, truncate large content)"""
    sanitized = {}

    for key, value in data.items():
        if key in ["body_html", "content", "summary"]:
            # Truncate long content and hash for privacy
            if isinstance(value, str) and len(value) > 100:
                import hashlib
                content_hash = hashlib.md5(value.encode()).hexdigest()[:8]
                sanitized[f"{key}_hash"] = content_hash
                sanitized[f"{key}_length"] = len(value)
            else:
                sanitized[key] = value
        elif key in ["password", "token", "key", "secret"]:
            # Hide sensitive data
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value

    return sanitized