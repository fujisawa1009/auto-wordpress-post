"""
Article preview routes
"""
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Article
from app.services.sanitizer import sanitize_html

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


@router.get(
    "/{article_id}",
    response_class=HTMLResponse,
    summary="Preview article",
    description="Display article preview with HTML template"
)
async def preview_article(
    request: Request,
    article_id: UUID,
    db: Session = Depends(get_db)
) -> HTMLResponse:
    """Display article preview in HTML format"""
    try:
        # Get article
        article = db.query(Article).filter(Article.id == article_id).first()

        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )

        # Prepare article data for template
        article_data = {
            "article_id": str(article.id),
            "status": article.status.value,
            "char_count": article.char_count,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
            "wp_post_id": article.wp_post_id,
            "wp_url": article.wp_url,
            "output": None
        }

        # Sanitize and prepare output if available
        if article.output_payload:
            output = article.output_payload.copy()

            # Sanitize HTML content for safe display
            if "body_html" in output:
                output["body_html"] = sanitize_html(output["body_html"])

            # Sanitize FAQ answers
            if "faq" in output:
                for faq_item in output["faq"]:
                    if "answer_html" in faq_item:
                        faq_item["answer_html"] = sanitize_html(faq_item["answer_html"])

            # Sanitize CTA HTML
            if "cta_html" in output:
                output["cta_html"] = sanitize_html(output["cta_html"])

            article_data["output"] = output

        logger.info(f"Rendering preview for article {article_id}")

        return templates.TemplateResponse(
            "preview.html",
            {"request": request, "article": article_data}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to render preview for article {article_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to render article preview"
        )


@router.get(
    "/{article_id}/raw",
    summary="Get raw article data",
    description="Get raw article data in JSON format for debugging"
)
async def get_raw_article(
    article_id: UUID,
    db: Session = Depends(get_db)
) -> dict:
    """Get raw article data for debugging"""
    try:
        article = db.query(Article).filter(Article.id == article_id).first()

        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )

        return {
            "id": str(article.id),
            "status": article.status.value,
            "char_count": article.char_count,
            "created_at": article.created_at.isoformat(),
            "updated_at": article.updated_at.isoformat(),
            "wp_post_id": article.wp_post_id,
            "wp_url": article.wp_url,
            "input_payload": article.input_payload,
            "output_payload": article.output_payload,
            "slug": article.slug,
            "idempotency_key": article.idempotency_key
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get raw article data for {article_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve article data"
        )