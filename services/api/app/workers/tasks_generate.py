"""
Article generation tasks
"""
import hashlib
import json
import logging
import asyncio
from typing import Dict, Any, Optional

from celery import Task
from sqlalchemy.orm import Session

from app.workers.celery_app import celery
from app.deps import SessionLocal
from app.models import Article, ArticleStatus, Job, JobStatus
from app.schemas import GenerateInput, ArticleOutput
from app.services.generation import generation_service
from app.services.sanitizer import count_ja_chars_from_html

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management"""

    def __call__(self, *args, **kwargs):
        """Execute task with database session"""
        db = SessionLocal()
        try:
            return self.run_with_db(db, *args, **kwargs)
        finally:
            db.close()

    def run_with_db(self, db: Session, *args, **kwargs):
        """Override this method in subclasses"""
        raise NotImplementedError


@celery.task(bind=True, base=DatabaseTask, name="generate.article")
def task_generate_article(self, article_id: str) -> Dict[str, Any]:
    """
    Generate article content using Perplexity API

    Args:
        article_id: UUID of the article to generate

    Returns:
        Generation result
    """
    def run_with_db(self, db: Session, article_id: str) -> Dict[str, Any]:
        try:
            # Get article
            article = db.query(Article).filter(Article.id == article_id).first()
            if not article:
                raise ValueError(f"Article {article_id} not found")

            # Update status
            article.status = ArticleStatus.GENERATING
            db.commit()

            logger.info(f"Starting article generation for {article_id}")

            # Parse input
            input_data = GenerateInput(**article.input_payload)

            # Use the generation service
            logger.info(f"Using generation service for {article_id}")

            # Run async generation in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                final_content = loop.run_until_complete(
                    generation_service.generate_complete_article(input_data)
                )
            finally:
                loop.close()

            # Validate and store
            output = ArticleOutput(**final_content)
            char_count = count_ja_chars_from_html(output.body_html)

            article.store_output(
                output_data=output.dict(),
                status=ArticleStatus.GENERATED,
                char_count=char_count
            )
            db.commit()

            logger.info(f"Article generation completed for {article_id}, char_count: {char_count}")

            return {
                "article_id": article_id,
                "status": "generated",
                "char_count": char_count
            }

        except Exception as e:
            logger.error(f"Article generation failed for {article_id}: {str(e)}")

            # Update article status
            if 'article' in locals():
                article.status = ArticleStatus.FAILED
                db.commit()

            # Retry if not final attempt
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying article generation for {article_id} (attempt {self.request.retries + 1})")
                raise self.retry(countdown=60 * (2 ** self.request.retries))

            raise

    # Assign the method to the task
    self.run_with_db = run_with_db.__get__(self, type(self))
    return self.run_with_db(article_id)




@celery.task(name="generate.cleanup_old_results")
def cleanup_old_results():
    """Clean up old generation results"""
    logger.info("Cleaning up old generation results")
    # TODO: Implement cleanup logic
    return {"cleaned": 0}


def generate_idempotency_key(input_data: Dict[str, Any]) -> str:
    """Generate idempotency key from input data"""
    # Remove non-deterministic fields
    clean_data = {k: v for k, v in input_data.items() if k not in ['author']}

    # Create hash
    json_str = json.dumps(clean_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()[:32]