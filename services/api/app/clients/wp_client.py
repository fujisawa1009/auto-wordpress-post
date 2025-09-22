"""
WordPress REST API client
"""
import base64
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)

from app.deps import get_settings
from app.schemas import PublishRequest
from app.utils.logging import log_wordpress_call

logger = logging.getLogger(__name__)


class WordPressAPIError(Exception):
    """WordPress API error"""
    pass


class WordPressAuthError(WordPressAPIError):
    """WordPress authentication error"""
    pass


class WordPressNotFoundError(WordPressAPIError):
    """WordPress resource not found"""
    pass


class WordPressClient:
    """WordPress REST API client"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = f"{self.settings.wp_base_url.rstrip('/')}/wp-json/wp/v2"
        self.headers = self._get_auth_headers()

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for WordPress API"""
        credentials = f"{self.settings.wp_username}:{self.settings.wp_application_password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "User-Agent": "AutoWordPressPost/1.0"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to WordPress API

        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base_url)
            data: Request data for POST/PUT
            params: Query parameters

        Returns:
            Response data

        Raises:
            WordPressAPIError: API error
            WordPressAuthError: Authentication error
            WordPressNotFoundError: Resource not found
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=data,
                    params=params
                )

                # Handle authentication errors
                if response.status_code == 401:
                    raise WordPressAuthError("WordPress authentication failed")

                # Handle not found errors
                if response.status_code == 404:
                    raise WordPressNotFoundError(f"WordPress resource not found: {endpoint}")

                # Handle other client errors
                if 400 <= response.status_code < 500:
                    error_detail = response.text
                    logger.error(f"WordPress API client error {response.status_code}: {error_detail}")
                    raise WordPressAPIError(f"Client error {response.status_code}: {error_detail}")

                # Handle server errors
                if response.status_code >= 500:
                    error_detail = response.text
                    logger.error(f"WordPress API server error {response.status_code}: {error_detail}")
                    raise WordPressAPIError(f"Server error {response.status_code}: {error_detail}")

                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"WordPress API timeout: {str(e)}")
            raise
        except httpx.RequestError as e:
            logger.error(f"WordPress API request error: {str(e)}")
            raise WordPressAPIError(f"Request error: {str(e)}")

    async def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get all categories from WordPress

        Returns:
            List of category objects
        """
        try:
            response = await self._make_request("GET", "categories", params={"per_page": 100})
            logger.info(f"Retrieved {len(response)} categories from WordPress")
            return response

        except Exception as e:
            log_wordpress_call("unknown", "get_categories", success=False, error=str(e))
            raise

    async def get_tags(self) -> List[Dict[str, Any]]:
        """
        Get all tags from WordPress

        Returns:
            List of tag objects
        """
        try:
            response = await self._make_request("GET", "tags", params={"per_page": 100})
            logger.info(f"Retrieved {len(response)} tags from WordPress")
            return response

        except Exception as e:
            log_wordpress_call("unknown", "get_tags", success=False, error=str(e))
            raise

    async def create_category(self, name: str, slug: Optional[str] = None, description: str = "") -> Dict[str, Any]:
        """
        Create a new category in WordPress

        Args:
            name: Category name
            slug: Category slug (auto-generated if not provided)
            description: Category description

        Returns:
            Created category object
        """
        data = {
            "name": name,
            "description": description
        }

        if slug:
            data["slug"] = slug

        try:
            response = await self._make_request("POST", "categories", data=data)
            logger.info(f"Created category '{name}' with ID {response['id']}")
            log_wordpress_call("unknown", "create_category", success=True, name=name)
            return response

        except Exception as e:
            log_wordpress_call("unknown", "create_category", success=False, error=str(e), name=name)
            raise

    async def create_tag(self, name: str, slug: Optional[str] = None, description: str = "") -> Dict[str, Any]:
        """
        Create a new tag in WordPress

        Args:
            name: Tag name
            slug: Tag slug (auto-generated if not provided)
            description: Tag description

        Returns:
            Created tag object
        """
        data = {
            "name": name,
            "description": description
        }

        if slug:
            data["slug"] = slug

        try:
            response = await self._make_request("POST", "tags", data=data)
            logger.info(f"Created tag '{name}' with ID {response['id']}")
            log_wordpress_call("unknown", "create_tag", success=True, name=name)
            return response

        except Exception as e:
            log_wordpress_call("unknown", "create_tag", success=False, error=str(e), name=name)
            raise

    async def create_post(
        self,
        article_id: str,
        title: str,
        content: str,
        status: str = "draft",
        excerpt: str = "",
        slug: Optional[str] = None,
        categories: Optional[List[int]] = None,
        tags: Optional[List[int]] = None,
        meta: Optional[Dict[str, str]] = None,
        featured_media: Optional[int] = None,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new post in WordPress

        Args:
            article_id: Internal article ID for logging
            title: Post title
            content: Post content (HTML)
            status: Post status (draft, publish, future)
            excerpt: Post excerpt
            slug: Post slug
            categories: List of category IDs
            tags: List of tag IDs
            meta: Post meta fields
            featured_media: Featured image media ID
            date: Publication date (ISO format)

        Returns:
            Created post object
        """
        data = {
            "title": title,
            "content": content,
            "status": status,
            "excerpt": excerpt
        }

        if slug:
            data["slug"] = slug

        if categories:
            data["categories"] = categories

        if tags:
            data["tags"] = tags

        if meta:
            data["meta"] = meta

        if featured_media:
            data["featured_media"] = featured_media

        if date:
            data["date"] = date

        try:
            response = await self._make_request("POST", "posts", data=data)
            wp_post_id = response["id"]
            wp_url = response["link"]

            logger.info(f"Created WordPress post ID {wp_post_id} for article {article_id}")
            log_wordpress_call(
                article_id, "create_post", wp_post_id=wp_post_id,
                success=True, status=status, title=title
            )

            return response

        except Exception as e:
            log_wordpress_call(article_id, "create_post", success=False, error=str(e))
            raise

    async def update_post(
        self,
        article_id: str,
        post_id: int,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Update an existing post in WordPress

        Args:
            article_id: Internal article ID for logging
            post_id: WordPress post ID
            **kwargs: Fields to update

        Returns:
            Updated post object
        """
        try:
            response = await self._make_request("POST", f"posts/{post_id}", data=kwargs)
            logger.info(f"Updated WordPress post ID {post_id} for article {article_id}")
            log_wordpress_call(article_id, "update_post", wp_post_id=post_id, success=True)
            return response

        except Exception as e:
            log_wordpress_call(article_id, "update_post", wp_post_id=post_id, success=False, error=str(e))
            raise

    async def delete_post(self, article_id: str, post_id: int, force: bool = False) -> Dict[str, Any]:
        """
        Delete a post from WordPress

        Args:
            article_id: Internal article ID for logging
            post_id: WordPress post ID
            force: Permanently delete (bypass trash)

        Returns:
            Deletion result
        """
        params = {"force": force} if force else None

        try:
            response = await self._make_request("DELETE", f"posts/{post_id}", params=params)
            logger.info(f"Deleted WordPress post ID {post_id} for article {article_id}")
            log_wordpress_call(article_id, "delete_post", wp_post_id=post_id, success=True)
            return response

        except Exception as e:
            log_wordpress_call(article_id, "delete_post", wp_post_id=post_id, success=False, error=str(e))
            raise

    async def upload_media(
        self,
        article_id: str,
        file_data: bytes,
        filename: str,
        mime_type: str,
        title: Optional[str] = None,
        alt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload media file to WordPress

        Args:
            article_id: Internal article ID for logging
            file_data: File binary data
            filename: Original filename
            mime_type: File MIME type
            title: Media title
            alt_text: Alt text for images

        Returns:
            Uploaded media object
        """
        headers = self._get_auth_headers()
        headers["Content-Type"] = mime_type
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/media",
                    headers=headers,
                    content=file_data
                )

                if response.status_code != 201:
                    error_detail = response.text
                    raise WordPressAPIError(f"Media upload failed {response.status_code}: {error_detail}")

                media_data = response.json()
                media_id = media_data["id"]

                # Update media metadata if provided
                if title or alt_text:
                    update_data = {}
                    if title:
                        update_data["title"] = title
                    if alt_text:
                        update_data["alt_text"] = alt_text

                    await self._make_request("POST", f"media/{media_id}", data=update_data)

                logger.info(f"Uploaded media ID {media_id} for article {article_id}")
                log_wordpress_call(article_id, "upload_media", success=True, media_id=media_id)

                return media_data

        except Exception as e:
            log_wordpress_call(article_id, "upload_media", success=False, error=str(e))
            raise

    async def get_post(self, post_id: int) -> Dict[str, Any]:
        """
        Get a post from WordPress

        Args:
            post_id: WordPress post ID

        Returns:
            Post object
        """
        return await self._make_request("GET", f"posts/{post_id}")

    async def search_posts(self, search: str, per_page: int = 10) -> List[Dict[str, Any]]:
        """
        Search posts in WordPress

        Args:
            search: Search query
            per_page: Results per page

        Returns:
            List of matching posts
        """
        params = {
            "search": search,
            "per_page": per_page
        }

        return await self._make_request("GET", "posts", params=params)

    def format_wp_date(self, dt: datetime) -> str:
        """
        Format datetime for WordPress API

        Args:
            dt: Datetime object

        Returns:
            WordPress-compatible date string
        """
        # WordPress expects ISO 8601 format in site timezone
        return dt.isoformat()

    async def test_connection(self) -> bool:
        """
        Test WordPress API connection

        Returns:
            True if connection successful
        """
        try:
            await self._make_request("GET", "")
            logger.info("WordPress API connection test successful")
            return True
        except Exception as e:
            logger.error(f"WordPress API connection test failed: {str(e)}")
            return False


# Create global client instance
wordpress_client = WordPressClient()