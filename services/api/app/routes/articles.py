"""
Article management API routes
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Article, ArticleStatus
from app.schemas import (
    GenerateInput, GenerateResponse, ArticleResponse,
    PublishRequest, PublishResponse, ErrorResponse
)
from app.workers.tasks_generate import task_generate_article, generate_idempotency_key
from app.workers.tasks_publish import task_publish_article
from app.services.sanitizer import count_ja_chars_from_html, sanitize_html

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate article content",
    description="Start article generation process using Perplexity API"
)
async def generate_article(
    input_data: GenerateInput,
    db: Session = Depends(get_db)
) -> GenerateResponse:
    """Generate article from input summary"""
    try:
        # Generate idempotency key
        idempotency_key = generate_idempotency_key(input_data.dict())

        # Check for existing article with same input
        existing_article = db.query(Article).filter(
            Article.idempotency_key == idempotency_key
        ).first()

        if existing_article:
            logger.info(f"Returning existing article {existing_article.id} for idempotency key {idempotency_key}")
            return GenerateResponse(
                article_id=str(existing_article.id),
                status=existing_article.status.value,
                message="Article with same input already exists"
            )

        # Create new article
        article = Article.create_from_input(
            input_data=input_data.dict(),
            idempotency_key=idempotency_key
        )

        db.add(article)
        db.commit()
        db.refresh(article)

        # Start generation task
        task_generate_article.delay(str(article.id))

        logger.info(f"Started article generation for {article.id}")

        return GenerateResponse(
            article_id=str(article.id),
            status=article.status.value,
            message="Article generation started"
        )

    except Exception as e:
        logger.error(f"Failed to start article generation: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start article generation"
        )


@router.get(
    "/{article_id}",
    response_model=ArticleResponse,
    summary="Get article",
    description="Retrieve article by ID with current status and content"
)
async def get_article(
    article_id: UUID,
    db: Session = Depends(get_db)
) -> ArticleResponse:
    """Get article by ID"""
    article = db.query(Article).filter(Article.id == article_id).first()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )

    # Sanitize output for preview if available
    output = None
    if article.output_payload:
        output = article.output_payload.copy()
        if "body_html" in output:
            output["body_html"] = sanitize_html(output["body_html"])

    return ArticleResponse(
        article_id=str(article.id),
        status=article.status.value,
        char_count=article.char_count,
        output=output,
        wp_post_id=article.wp_post_id,
        wp_url=article.wp_url,
        created_at=article.created_at,
        updated_at=article.updated_at
    )


@router.post(
    "/{article_id}/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Publish article to WordPress",
    description="Publish generated article to WordPress with specified mode"
)
async def publish_article(
    article_id: UUID,
    publish_data: PublishRequest,
    db: Session = Depends(get_db)
) -> PublishResponse:
    """Publish article to WordPress"""
    try:
        # Get article
        article = db.query(Article).filter(Article.id == article_id).first()

        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )

        if article.status != ArticleStatus.GENERATED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Article is not ready for publishing (status: {article.status.value})"
            )

        if article.wp_post_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Article has already been published"
            )

        # Start publishing task
        task_result = task_publish_article.delay(str(article.id), publish_data.dict())

        logger.info(f"Started WordPress publishing for {article.id}")

        # Return immediate response (actual publishing is async)
        return PublishResponse(
            wp_post_id=0,  # Will be updated when task completes
            wp_url="",  # Will be updated when task completes
            status="publishing",
            message="WordPress publishing started"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start WordPress publishing for {article_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start WordPress publishing"
        )


@router.post(
    "/{article_id}/regenerate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate article content",
    description="Regenerate article with same input parameters"
)
async def regenerate_article(
    article_id: UUID,
    db: Session = Depends(get_db)
) -> GenerateResponse:
    """Regenerate article content"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()

        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )

        # Reset article status and clear output
        article.status = ArticleStatus.PENDING
        article.output_payload = None
        article.char_count = 0
        article.wp_post_id = None
        article.wp_url = None

        db.commit()

        # Start generation task
        task_generate_article.delay(str(article.id))

        logger.info(f"Started article regeneration for {article.id}")

        return GenerateResponse(
            article_id=str(article.id),
            status=article.status.value,
            message="Article regeneration started"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start article regeneration for {article_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start article regeneration"
        )


@router.delete(
    "/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete article",
    description="Delete article and associated data"
)
async def delete_article(
    article_id: UUID,
    db: Session = Depends(get_db)
) -> None:
    """Delete article"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()

        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )

        # TODO: Cancel any running tasks for this article

        db.delete(article)
        db.commit()

        logger.info(f"Deleted article {article_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete article {article_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete article"
        )