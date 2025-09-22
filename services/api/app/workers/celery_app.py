"""
Celery application configuration
"""
import os
from celery import Celery
from celery.signals import setup_logging

from app.deps import get_settings


def create_celery_app() -> Celery:
    """Create and configure Celery application"""
    settings = get_settings()

    celery_app = Celery(
        "auto-wordpress-post",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=[
            "app.workers.tasks_generate",
            "app.workers.tasks_publish"
        ]
    )

    # Configuration
    celery_app.conf.update(
        # Task settings
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Tokyo",
        enable_utc=True,

        # Task routing
        task_routes={
            "generate.*": {"queue": "generation"},
            "publish.*": {"queue": "publishing"},
        },

        # Worker settings
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_disable_rate_limits=False,

        # Result backend settings
        result_expires=3600,  # 1 hour
        result_persistent=True,

        # Retry settings
        task_default_retry_delay=60,  # 1 minute
        task_max_retries=3,

        # Beat schedule (if needed)
        beat_schedule={
            "cleanup-old-results": {
                "task": "app.workers.tasks_generate.cleanup_old_results",
                "schedule": 3600.0,  # Every hour
            },
        },
    )

    return celery_app


# Create celery instance
celery = create_celery_app()


@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure logging for Celery"""
    from app.utils.logging import setup_logging
    setup_logging()