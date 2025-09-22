"""
Perplexity API client for article generation
"""
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)

from app.deps import get_settings
from app.schemas import GenerateInput
from app.utils.logging import log_perplexity_call

logger = logging.getLogger(__name__)


@dataclass
class PerplexityResponse:
    """Perplexity API response wrapper"""
    content: str
    usage: Dict[str, int]
    model: str
    finish_reason: str


class PerplexityAPIError(Exception):
    """Perplexity API error"""
    pass


class PerplexityRateLimitError(PerplexityAPIError):
    """Rate limit exceeded"""
    pass


class PerplexityClient:
    """Perplexity API client"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.settings.pplx_api_key}",
            "Content-Type": "application/json"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PerplexityRateLimitError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 3500,
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None,
        search_domain_filter: Optional[List[str]] = None
    ) -> PerplexityResponse:
        """
        Make API call to Perplexity with retry logic

        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            response_format: Response format (e.g., {"type": "json_object"})
            search_domain_filter: Domain filter for search

        Returns:
            PerplexityResponse object

        Raises:
            PerplexityAPIError: API error
            PerplexityRateLimitError: Rate limit exceeded
        """
        start_time = time.time()

        payload = {
            "model": self.settings.pplx_model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": max_tokens,
            "disable_search": self.settings.pplx_disable_search
        }

        if response_format:
            payload["response_format"] = response_format

        if search_domain_filter and not self.settings.pplx_disable_search:
            payload["search_domain_filter"] = search_domain_filter[:20]  # Max 20 domains

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload
                )

                # Handle rate limiting
                if response.status_code == 429:
                    raise PerplexityRateLimitError("Rate limit exceeded")

                # Handle other errors
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Perplexity API error {response.status_code}: {error_detail}")
                    raise PerplexityAPIError(f"API error {response.status_code}: {error_detail}")

                result = response.json()
                choice = result["choices"][0]

                # Calculate latency
                latency_ms = int((time.time() - start_time) * 1000)

                # Estimate tokens (rough approximation)
                tokens_estimated = len(choice["message"]["content"]) // 4

                # Log the call
                log_perplexity_call(
                    article_id="unknown",  # Will be set by caller
                    call_type="generation",
                    tokens_estimated=tokens_estimated,
                    latency_ms=latency_ms,
                    success=True
                )

                return PerplexityResponse(
                    content=choice["message"]["content"],
                    usage=result.get("usage", {}),
                    model=result["model"],
                    finish_reason=choice["finish_reason"]
                )

        except httpx.TimeoutException as e:
            logger.error(f"Perplexity API timeout: {str(e)}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Perplexity API request error: {str(e)}")
            raise PerplexityAPIError(f"Request error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity API call: {str(e)}")
            raise PerplexityAPIError(f"Unexpected error: {str(e)}")

    async def generate_outline(self, input_data: GenerateInput) -> Dict[str, Any]:
        """
        Generate article outline using Perplexity API

        Args:
            input_data: Article generation input

        Returns:
            Article outline structure
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_outline_prompt(input_data)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        search_domains = None
        if input_data.references:
            search_domains = [url.host for url in input_data.references]

        response = await self._call_api(
            messages=messages,
            max_tokens=2000,
            response_format={"type": "json_object"},
            search_domain_filter=search_domains
        )

        try:
            outline = json.loads(response.content)
            logger.info(f"Generated outline with {len(outline.get('sections', []))} sections")
            return outline
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse outline JSON: {response.content}")
            raise PerplexityAPIError(f"Invalid JSON response: {str(e)}")

    async def generate_section(
        self,
        input_data: GenerateInput,
        section: Dict[str, Any],
        target_chars: int = 2000
    ) -> str:
        """
        Generate content for a specific section

        Args:
            input_data: Article generation input
            section: Section information from outline
            target_chars: Target character count for this section

        Returns:
            HTML content for the section
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_section_prompt(input_data, section, target_chars)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        search_domains = None
        if input_data.references:
            search_domains = [url.host for url in input_data.references]

        response = await self._call_api(
            messages=messages,
            max_tokens=4000,
            search_domain_filter=search_domains
        )

        logger.info(f"Generated section '{section.get('h2', 'Unknown')}' with {len(response.content)} characters")
        return response.content

    async def finalize_article(
        self,
        input_data: GenerateInput,
        outline: Dict[str, Any],
        sections: List[str]
    ) -> Dict[str, Any]:
        """
        Finalize article with metadata and structure

        Args:
            input_data: Original input data
            outline: Article outline
            sections: Generated section contents

        Returns:
            Complete article data structure
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_finalization_prompt(input_data, outline, sections)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self._call_api(
            messages=messages,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        try:
            article_data = json.loads(response.content)
            logger.info("Finalized article with metadata")
            return article_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse finalization JSON: {response.content}")
            raise PerplexityAPIError(f"Invalid JSON response: {str(e)}")

    def _build_system_prompt(self) -> str:
        """Build system prompt for Perplexity"""
        return """あなたは日本語の専門ライター兼SEOスペシャリストです。

### 重要なルール:
1. 必ず日本語で回答してください
2. 正確で信頼性の高い情報のみを使用
3. 読みやすく構造化された文章を作成
4. SEOに最適化された見出し構造を使用
5. 安全なHTMLタグのみを使用（h2, h3, p, ul, ol, li, strong, em, a）
6. 誤解を招く情報や推測は避ける
7. 著作権を侵害しない
8. 政治的・宗教的な偏見を避ける

### 文章品質基準:
- 明確で簡潔な表現
- 論理的な構成
- 適切な専門用語の使用
- 読者の理解レベルに合わせた説明
- 具体例や根拠の提示"""

    def _build_outline_prompt(self, input_data: GenerateInput) -> str:
        """Build outline generation prompt"""
        references_text = ""
        if input_data.references:
            references_text = f"\n参考URL: {', '.join(str(url) for url in input_data.references)}"

        must_topics_text = ""
        if input_data.must_topics:
            must_topics_text = f"\n必須トピック: {', '.join(input_data.must_topics)}"

        bans_text = ""
        if input_data.bans:
            bans_text = f"\n禁止事項: {', '.join(input_data.bans)}"

        return f"""以下の情報に基づいて記事の見出し構成を作成してください。

### 記事情報:
要約: {input_data.summary}
目的: {input_data.goal}
想定読者: {input_data.audience}
トーン: {input_data.tone.value}
目標文字数: {input_data.target_chars}字{references_text}{must_topics_text}{bans_text}

### 要求事項:
- H2見出しを6-9個作成
- 各H2に対してH3見出しを2-3個作成
- 見出しは論理的な順序で配置
- SEOを意識したキーワード含有
- 読者の関心を引く魅力的な見出し

### 出力形式:
以下のJSON形式で出力してください:

```json
{{
  "title": "記事タイトル",
  "sections": [
    {{
      "h2": "H2見出し1",
      "h3": ["H3見出し1-1", "H3見出し1-2"]
    }},
    {{
      "h2": "H2見出し2",
      "h3": ["H3見出し2-1", "H3見出し2-2", "H3見出し2-3"]
    }}
  ]
}}
```

JSONのみを出力してください。"""

    def _build_section_prompt(
        self,
        input_data: GenerateInput,
        section: Dict[str, Any],
        target_chars: int
    ) -> str:
        """Build section generation prompt"""
        h2_title = section.get("h2", "")
        h3_titles = section.get("h3", [])

        must_topics_text = ""
        if input_data.must_topics:
            must_topics_text = f"\n必須トピック: {', '.join(input_data.must_topics)}"

        return f"""以下の見出し構成に基づいて、詳細なコンテンツを作成してください。

### セクション情報:
H2見出し: {h2_title}
H3見出し: {', '.join(h3_titles)}

### 記事コンテキスト:
要約: {input_data.summary}
目的: {input_data.goal}
想定読者: {input_data.audience}
トーン: {input_data.tone.value}{must_topics_text}

### 要求事項:
- 目標文字数: 約{target_chars}文字
- H2, H3見出しを適切に使用
- 各H3セクションに具体的な内容を記述
- 論理的で読みやすい構成
- 専門性と信頼性を重視
- 具体例や根拠を含める

### 使用可能HTMLタグ:
h2, h3, p, ul, ol, li, strong, em, a（hrefは信頼できるURLのみ）

### 出力:
HTMLコンテンツのみを出力してください。説明文は不要です。"""

    def _build_finalization_prompt(
        self,
        input_data: GenerateInput,
        outline: Dict[str, Any],
        sections: List[str]
    ) -> str:
        """Build finalization prompt"""
        content_preview = "\n".join(sections)[:1000] + "..."

        return f"""以下の記事コンテンツに基づいて、完全な記事データを作成してください。

### 元の要求:
要約: {input_data.summary}
目的: {input_data.goal}
想定読者: {input_data.audience}

### 記事コンテンツ概要:
{content_preview}

### 要求事項:
- SEOに最適化されたタイトル
- URLフレンドリーなslug（英数字とハイフンのみ）
- 魅力的な抜粋文
- メタディスクリプション（150文字以内）
- 関連するタグ（最大10個）
- 適切なカテゴリ（最大5個）
- FAQ（質問と回答のペア、最大5個）
- CTA（行動喚起）HTML

### 出力形式:
以下のJSON形式で出力してください:

```json
{{
  "title": "記事タイトル",
  "slug": "article-slug",
  "excerpt": "記事の抜粋",
  "meta_description": "メタディスクリプション",
  "tags": ["タグ1", "タグ2"],
  "categories": ["カテゴリ1"],
  "faq": [
    {{
      "question": "質問",
      "answer_html": "HTML形式の回答"
    }}
  ],
  "cta_html": "<p>行動喚起のHTML</p>",
  "schema_org": {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "記事タイトル"
  }}
}}
```

JSONのみを出力してください。"""


# Create global client instance
perplexity_client = PerplexityClient()