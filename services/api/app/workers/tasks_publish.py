"""
WordPress publishing tasks
"""
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

from celery import Task
from sqlalchemy.orm import Session

from app.workers.celery_app import celery
from app.deps import SessionLocal
from app.models import Article, ArticleStatus
from app.schemas import PublishRequest

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


@celery.task(bind=True, base=DatabaseTask, name="publish.article")
def task_publish_article(self, article_id: str, publish_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publish article to WordPress

    Args:
        article_id: UUID of the article to publish
        publish_data: Publishing configuration

    Returns:
        Publishing result
    """
    def run_with_db(self, db: Session, article_id: str, publish_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Get article
            article = db.query(Article).filter(Article.id == article_id).first()
            if not article:
                raise ValueError(f"Article {article_id} not found")

            if article.status != ArticleStatus.GENERATED:
                raise ValueError(f"Article {article_id} is not ready for publishing (status: {article.status})")

            # Update status
            article.status = ArticleStatus.PUBLISHING
            db.commit()

            logger.info(f"Starting WordPress publishing for {article_id}")

            # Parse publish request
            publish_request = PublishRequest(**publish_data)

            # Step 1: Resolve taxonomies
            logger.info(f"Resolving taxonomies for {article_id}")

            # Run async taxonomy resolution in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                taxonomy_ids = loop.run_until_complete(
                    _resolve_taxonomies(article.output_payload)
                )

                # Step 2: Prepare WordPress payload
                wp_payload = _prepare_wp_payload(article, publish_request, taxonomy_ids)

                # Step 3: Publish to WordPress
                logger.info(f"Publishing to WordPress for {article_id}")
                wp_result = loop.run_until_complete(
                    _publish_to_wordpress(article_id, wp_payload)
                )
            finally:
                loop.close()

            # Step 4: Update article with WordPress info
            article.mark_published(
                wp_post_id=wp_result["id"],
                wp_url=wp_result["link"]
            )
            db.commit()

            logger.info(f"WordPress publishing completed for {article_id}, post_id: {wp_result['id']}")

            return {
                "article_id": article_id,
                "wp_post_id": wp_result["id"],
                "wp_url": wp_result["link"],
                "status": wp_result["status"]
            }

        except Exception as e:
            logger.error(f"WordPress publishing failed for {article_id}: {str(e)}")

            # Update article status
            if 'article' in locals():
                article.status = ArticleStatus.FAILED
                db.commit()

            # Retry if not final attempt
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying WordPress publishing for {article_id} (attempt {self.request.retries + 1})")
                raise self.retry(countdown=60 * (2 ** self.request.retries))

            raise

    # Assign the method to the task
    self.run_with_db = run_with_db.__get__(self, type(self))
    return self.run_with_db(article_id, publish_data)


async def _resolve_taxonomies(output_data: Dict[str, Any]) -> Dict[str, list]:
    """Resolve category and tag names to WordPress IDs"""
    from app.services.taxonomy import taxonomy_service
    return await taxonomy_service.resolve_taxonomies_for_article(output_data)


def _prepare_wp_payload(article: Article, publish_request: PublishRequest, taxonomy_ids: Dict[str, list]) -> Dict[str, Any]:
    """Prepare WordPress API payload"""
    output = article.output_payload

    payload = {
        "title": output["title"],
        "content": output["body_html"],
        "excerpt": output["excerpt"],
        "slug": output["slug"],
        "status": publish_request.mode.value,
        "categories": taxonomy_ids["categories"],
        "tags": taxonomy_ids["tags"],
        "meta": {
            "description": output["meta_description"]
        }
    }

    # Handle scheduled posts
    if publish_request.mode.value == "schedule" and publish_request.schedule_at:
        payload["date"] = publish_request.schedule_at.isoformat()

    return payload


async def _publish_to_wordpress(article_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Publish to WordPress via REST API"""
    from app.clients.wp_client import wordpress_client

    return await wordpress_client.create_post(
        article_id=article_id,
        title=payload["title"],
        content=payload["content"],
        status=payload["status"],
        excerpt=payload.get("excerpt", ""),
        slug=payload.get("slug"),
        categories=payload.get("categories", []),
        tags=payload.get("tags", []),
        meta=payload.get("meta", {}),
        featured_media=payload.get("featured_media"),
        date=payload.get("date")
    )


@celery.task(bind=True, base=DatabaseTask, name="publish.upload_media")
def task_upload_media(self, article_id: str, media_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upload media to WordPress

    Args:
        article_id: UUID of the article
        media_data: Media upload configuration

    Returns:
        Media upload result
    """
    def run_with_db(self, db: Session, article_id: str, media_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.info(f"Starting media upload for {article_id}")

            # Extract media information
            file_data = media_data.get("file_data")
            filename = media_data.get("filename")
            mime_type = media_data.get("mime_type")
            title = media_data.get("title")
            alt_text = media_data.get("alt_text")

            if not all([file_data, filename, mime_type]):
                raise ValueError("Missing required media data: file_data, filename, mime_type")

            # Upload to WordPress
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                from app.clients.wp_client import wordpress_client

                wp_result = loop.run_until_complete(
                    wordpress_client.upload_media(
                        article_id=article_id,
                        file_data=file_data,
                        filename=filename,
                        mime_type=mime_type,
                        title=title,
                        alt_text=alt_text
                    )
                )
            finally:
                loop.close()

            logger.info(f"Media upload completed for {article_id}, media_id: {wp_result['id']}")

            return {
                "article_id": article_id,
                "media_id": wp_result["id"],
                "media_url": wp_result["source_url"]
            }

        except Exception as e:
            logger.error(f"Media upload failed for {article_id}: {str(e)}")

            # Retry if not final attempt
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying media upload for {article_id} (attempt {self.request.retries + 1})")
                raise self.retry(countdown=30 * (2 ** self.request.retries))

            raise

    # Assign the method to the task
    self.run_with_db = run_with_db.__get__(self, type(self))
    return self.run_with_db(article_id, media_data)