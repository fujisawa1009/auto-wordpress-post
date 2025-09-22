"""
WordPress taxonomy management API routes
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Taxonomy, TaxonomyType
from app.schemas import TaxonomyResponse, TaxonomyItem, ErrorResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/sync",
    response_model=TaxonomyResponse,
    summary="Sync WordPress taxonomies",
    description="Fetch and cache WordPress categories and tags"
)
async def sync_taxonomies(
    db: Session = Depends(get_db)
) -> TaxonomyResponse:
    """Sync WordPress categories and tags with local cache"""
    try:
        from app.services.taxonomy import taxonomy_service

        logger.info("Starting taxonomy sync with WordPress")

        # Use actual WordPress API via taxonomy service
        categories_synced, tags_synced = await taxonomy_service.sync_taxonomies_from_wordpress()

        # Get the synced data for response
        wp_categories = await taxonomy_service.get_cached_categories()
        wp_tags = await taxonomy_service.get_cached_tags()

        # Convert to response format
        categories = [
            TaxonomyItem(
                id=cat["id"],
                name=cat["name"],
                slug=cat["slug"],
                description=cat.get("description", "")
            )
            for cat in wp_categories
        ]

        tags = [
            TaxonomyItem(
                id=tag["id"],
                name=tag["name"],
                slug=tag["slug"],
                description=tag.get("description", "")
            )
            for tag in wp_tags
        ]

        logger.info(f"Taxonomy sync completed: {categories_synced} categories, {tags_synced} tags")

        return TaxonomyResponse(
            categories=categories,
            tags=tags,
            synced_at=datetime.now()
        )

    except Exception as e:
        logger.error(f"Taxonomy sync failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync taxonomies"
        )


@router.get(
    "/categories",
    response_model=List[TaxonomyItem],
    summary="Get cached categories",
    description="Retrieve cached WordPress categories"
)
async def get_categories(
    db: Session = Depends(get_db)
) -> List[TaxonomyItem]:
    """Get cached categories"""
    try:
        categories = db.query(Taxonomy).filter(
            Taxonomy.type == TaxonomyType.CATEGORY
        ).order_by(Taxonomy.name).all()

        return [
            TaxonomyItem(
                id=cat.wp_id or 0,
                name=cat.name,
                slug=cat.slug,
                description=cat.description
            )
            for cat in categories
        ]

    except Exception as e:
        logger.error(f"Failed to get categories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories"
        )


@router.get(
    "/tags",
    response_model=List[TaxonomyItem],
    summary="Get cached tags",
    description="Retrieve cached WordPress tags"
)
async def get_tags(
    db: Session = Depends(get_db)
) -> List[TaxonomyItem]:
    """Get cached tags"""
    try:
        tags = db.query(Taxonomy).filter(
            Taxonomy.type == TaxonomyType.TAG
        ).order_by(Taxonomy.name).all()

        return [
            TaxonomyItem(
                id=tag.wp_id or 0,
                name=tag.name,
                slug=tag.slug,
                description=tag.description
            )
            for tag in tags
        ]

    except Exception as e:
        logger.error(f"Failed to get tags: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tags"
        )


@router.post(
    "/categories",
    response_model=TaxonomyItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create category",
    description="Create new WordPress category"
)
async def create_category(
    name: str,
    slug: str = None,
    description: str = "",
    db: Session = Depends(get_db)
) -> TaxonomyItem:
    """Create new category in WordPress"""
    try:
        # TODO: Implement actual WordPress API call to create category
        # This is a placeholder implementation

        logger.info(f"Creating category: {name}")

        # Check if category already exists
        existing = db.query(Taxonomy).filter(
            Taxonomy.type == TaxonomyType.CATEGORY,
            Taxonomy.name == name
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category already exists"
            )

        # Mock WordPress API call
        wp_response = {
            "id": 999,  # Mock ID
            "name": name,
            "slug": slug or name.lower().replace(" ", "-"),
            "description": description
        }

        # Create local cache entry
        taxonomy = Taxonomy.create_from_wp(TaxonomyType.CATEGORY, wp_response)
        db.add(taxonomy)
        db.commit()
        db.refresh(taxonomy)

        logger.info(f"Created category {name} with ID {wp_response['id']}")

        return TaxonomyItem(
            id=wp_response["id"],
            name=wp_response["name"],
            slug=wp_response["slug"],
            description=wp_response["description"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create category {name}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category"
        )


@router.post(
    "/tags",
    response_model=TaxonomyItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create new WordPress tag"
)
async def create_tag(
    name: str,
    slug: str = None,
    description: str = "",
    db: Session = Depends(get_db)
) -> TaxonomyItem:
    """Create new tag in WordPress"""
    try:
        # TODO: Implement actual WordPress API call to create tag
        # This is a placeholder implementation

        logger.info(f"Creating tag: {name}")

        # Check if tag already exists
        existing = db.query(Taxonomy).filter(
            Taxonomy.type == TaxonomyType.TAG,
            Taxonomy.name == name
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tag already exists"
            )

        # Mock WordPress API call
        wp_response = {
            "id": 999,  # Mock ID
            "name": name,
            "slug": slug or name.lower().replace(" ", "-"),
            "description": description
        }

        # Create local cache entry
        taxonomy = Taxonomy.create_from_wp(TaxonomyType.TAG, wp_response)
        db.add(taxonomy)
        db.commit()
        db.refresh(taxonomy)

        logger.info(f"Created tag {name} with ID {wp_response['id']}")

        return TaxonomyItem(
            id=wp_response["id"],
            name=wp_response["name"],
            slug=wp_response["slug"],
            description=wp_response["description"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create tag {name}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tag"
        )