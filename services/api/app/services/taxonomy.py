"""
WordPress taxonomy management service
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from app.clients.wp_client import wordpress_client, WordPressAPIError
from app.models import Taxonomy, TaxonomyType
from app.deps import SessionLocal

logger = logging.getLogger(__name__)


class TaxonomyService:
    """Service for managing WordPress categories and tags"""

    def __init__(self):
        self.auto_create_missing = True  # Configuration option

    async def sync_taxonomies_from_wordpress(self) -> Tuple[int, int]:
        """
        Sync categories and tags from WordPress to local cache

        Returns:
            Tuple of (categories_synced, tags_synced)
        """
        db = SessionLocal()
        try:
            logger.info("Starting taxonomy sync from WordPress")

            # Fetch from WordPress
            wp_categories = await wordpress_client.get_categories()
            wp_tags = await wordpress_client.get_tags()

            categories_synced = 0
            tags_synced = 0

            # Sync categories
            for wp_cat in wp_categories:
                try:
                    existing = db.query(Taxonomy).filter(
                        Taxonomy.type == TaxonomyType.CATEGORY,
                        Taxonomy.wp_id == wp_cat["id"]
                    ).first()

                    if existing:
                        # Update existing
                        existing.name = wp_cat["name"]
                        existing.slug = wp_cat["slug"]
                        existing.description = wp_cat.get("description", "")
                        existing.updated_at = datetime.now()
                    else:
                        # Create new
                        taxonomy = Taxonomy.create_from_wp(TaxonomyType.CATEGORY, wp_cat)
                        db.add(taxonomy)

                    categories_synced += 1

                except Exception as e:
                    logger.warning(f"Failed to sync category {wp_cat.get('name', 'unknown')}: {str(e)}")

            # Sync tags
            for wp_tag in wp_tags:
                try:
                    existing = db.query(Taxonomy).filter(
                        Taxonomy.type == TaxonomyType.TAG,
                        Taxonomy.wp_id == wp_tag["id"]
                    ).first()

                    if existing:
                        # Update existing
                        existing.name = wp_tag["name"]
                        existing.slug = wp_tag["slug"]
                        existing.description = wp_tag.get("description", "")
                        existing.updated_at = datetime.now()
                    else:
                        # Create new
                        taxonomy = Taxonomy.create_from_wp(TaxonomyType.TAG, wp_tag)
                        db.add(taxonomy)

                    tags_synced += 1

                except Exception as e:
                    logger.warning(f"Failed to sync tag {wp_tag.get('name', 'unknown')}: {str(e)}")

            db.commit()

            logger.info(f"Taxonomy sync completed: {categories_synced} categories, {tags_synced} tags")
            return categories_synced, tags_synced

        except Exception as e:
            db.rollback()
            logger.error(f"Taxonomy sync failed: {str(e)}")
            raise
        finally:
            db.close()

    async def resolve_category_ids(self, category_names: List[str]) -> List[int]:
        """
        Resolve category names to WordPress IDs

        Args:
            category_names: List of category names

        Returns:
            List of WordPress category IDs
        """
        if not category_names:
            return []

        db = SessionLocal()
        try:
            category_ids = []

            for name in category_names:
                # Look up in local cache first
                taxonomy = db.query(Taxonomy).filter(
                    Taxonomy.type == TaxonomyType.CATEGORY,
                    Taxonomy.name == name
                ).first()

                if taxonomy and taxonomy.wp_id:
                    category_ids.append(taxonomy.wp_id)
                    logger.debug(f"Found cached category '{name}' -> ID {taxonomy.wp_id}")
                elif self.auto_create_missing:
                    # Create missing category
                    try:
                        wp_category = await self._create_missing_category(name)
                        category_ids.append(wp_category["id"])

                        # Cache the new category
                        new_taxonomy = Taxonomy.create_from_wp(TaxonomyType.CATEGORY, wp_category)
                        db.add(new_taxonomy)
                        db.commit()

                        logger.info(f"Created new category '{name}' -> ID {wp_category['id']}")

                    except Exception as e:
                        logger.warning(f"Failed to create category '{name}': {str(e)}")
                        # Use default category (usually ID 1)
                        category_ids.append(1)
                else:
                    logger.warning(f"Category '{name}' not found and auto-create disabled")
                    # Use default category
                    category_ids.append(1)

            return category_ids

        except Exception as e:
            db.rollback()
            logger.error(f"Category resolution failed: {str(e)}")
            # Return default category as fallback
            return [1] if category_names else []
        finally:
            db.close()

    async def resolve_tag_ids(self, tag_names: List[str]) -> List[int]:
        """
        Resolve tag names to WordPress IDs

        Args:
            tag_names: List of tag names

        Returns:
            List of WordPress tag IDs
        """
        if not tag_names:
            return []

        db = SessionLocal()
        try:
            tag_ids = []

            for name in tag_names:
                # Look up in local cache first
                taxonomy = db.query(Taxonomy).filter(
                    Taxonomy.type == TaxonomyType.TAG,
                    Taxonomy.name == name
                ).first()

                if taxonomy and taxonomy.wp_id:
                    tag_ids.append(taxonomy.wp_id)
                    logger.debug(f"Found cached tag '{name}' -> ID {taxonomy.wp_id}")
                elif self.auto_create_missing:
                    # Create missing tag
                    try:
                        wp_tag = await self._create_missing_tag(name)
                        tag_ids.append(wp_tag["id"])

                        # Cache the new tag
                        new_taxonomy = Taxonomy.create_from_wp(TaxonomyType.TAG, wp_tag)
                        db.add(new_taxonomy)
                        db.commit()

                        logger.info(f"Created new tag '{name}' -> ID {wp_tag['id']}")

                    except Exception as e:
                        logger.warning(f"Failed to create tag '{name}': {str(e)}")
                        # Skip this tag
                        continue
                else:
                    logger.warning(f"Tag '{name}' not found and auto-create disabled")

            return tag_ids

        except Exception as e:
            db.rollback()
            logger.error(f"Tag resolution failed: {str(e)}")
            return []
        finally:
            db.close()

    async def _create_missing_category(self, name: str) -> Dict[str, Any]:
        """Create a missing category in WordPress"""
        slug = self._generate_slug(name)

        return await wordpress_client.create_category(
            name=name,
            slug=slug,
            description=f"Auto-generated category: {name}"
        )

    async def _create_missing_tag(self, name: str) -> Dict[str, Any]:
        """Create a missing tag in WordPress"""
        slug = self._generate_slug(name)

        return await wordpress_client.create_tag(
            name=name,
            slug=slug,
            description=f"Auto-generated tag: {name}"
        )

    def _generate_slug(self, name: str) -> str:
        """
        Generate URL-friendly slug from name

        Args:
            name: Original name

        Returns:
            URL-friendly slug
        """
        import re
        import unicodedata

        # Normalize unicode characters
        slug = unicodedata.normalize('NFKD', name)

        # Convert to lowercase
        slug = slug.lower()

        # Replace Japanese characters with romanization (simplified)
        japanese_replacements = {
            'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
            'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
            'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
            'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
            'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
            'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
            'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
            'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
            'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
            'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
            'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
            'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
            'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
            'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
            'わ': 'wa', 'を': 'wo', 'ん': 'n'
        }

        for jp, en in japanese_replacements.items():
            slug = slug.replace(jp, en)

        # Replace common Japanese words
        common_replacements = {
            'テクノロジー': 'technology',
            'ビジネス': 'business',
            'ライフスタイル': 'lifestyle',
            'デザイン': 'design',
            'プログラミング': 'programming',
            'マーケティング': 'marketing',
            'デベロップメント': 'development'
        }

        for jp, en in common_replacements.items():
            slug = slug.replace(jp, en)

        # Remove non-alphanumeric characters except hyphens
        slug = re.sub(r'[^a-z0-9\-]', '-', slug)

        # Remove multiple consecutive hyphens
        slug = re.sub(r'-+', '-', slug)

        # Remove leading/trailing hyphens
        slug = slug.strip('-')

        # Limit length
        if len(slug) > 50:
            slug = slug[:50].rstrip('-')

        # Fallback if slug becomes empty
        if not slug:
            import hashlib
            slug = hashlib.md5(name.encode()).hexdigest()[:8]

        return slug

    async def get_cached_categories(self) -> List[Dict[str, Any]]:
        """Get cached categories from local database"""
        db = SessionLocal()
        try:
            categories = db.query(Taxonomy).filter(
                Taxonomy.type == TaxonomyType.CATEGORY
            ).order_by(Taxonomy.name).all()

            return [
                {
                    "id": cat.wp_id or 0,
                    "name": cat.name,
                    "slug": cat.slug,
                    "description": cat.description or "",
                    "updated_at": cat.updated_at.isoformat() if cat.updated_at else None
                }
                for cat in categories
            ]
        finally:
            db.close()

    async def get_cached_tags(self) -> List[Dict[str, Any]]:
        """Get cached tags from local database"""
        db = SessionLocal()
        try:
            tags = db.query(Taxonomy).filter(
                Taxonomy.type == TaxonomyType.TAG
            ).order_by(Taxonomy.name).all()

            return [
                {
                    "id": tag.wp_id or 0,
                    "name": tag.name,
                    "slug": tag.slug,
                    "description": tag.description or "",
                    "updated_at": tag.updated_at.isoformat() if tag.updated_at else None
                }
                for tag in tags
            ]
        finally:
            db.close()

    async def resolve_taxonomies_for_article(self, output_data: Dict[str, Any]) -> Dict[str, List[int]]:
        """
        Resolve all taxonomies for an article

        Args:
            output_data: Article output data containing categories and tags

        Returns:
            Dictionary with resolved category and tag IDs
        """
        categories = output_data.get("categories", [])
        tags = output_data.get("tags", [])

        # Resolve concurrently
        category_ids, tag_ids = await asyncio.gather(
            self.resolve_category_ids(categories),
            self.resolve_tag_ids(tags)
        )

        return {
            "categories": category_ids,
            "tags": tag_ids
        }

    def set_auto_create_missing(self, enabled: bool) -> None:
        """Configure auto-creation of missing taxonomies"""
        self.auto_create_missing = enabled
        logger.info(f"Auto-create missing taxonomies: {'enabled' if enabled else 'disabled'}")


# Create service instance
taxonomy_service = TaxonomyService()