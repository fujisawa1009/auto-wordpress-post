"""
Article generation service with character count control
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional

from app.schemas import GenerateInput, ArticleOutput
from app.clients.pplx_client import perplexity_client
from app.services.sanitizer import (
    sanitize_html, count_ja_chars_from_html,
    validate_article_length, extract_headings
)
from app.utils.logging import log_article_generation

logger = logging.getLogger(__name__)


class ArticleGenerationService:
    """Service for generating articles with character control"""

    def __init__(self):
        self.min_section_chars = 1500
        self.max_section_chars = 3000
        self.adjustment_threshold = 1000  # Characters outside target range

    async def generate_complete_article(self, input_data: GenerateInput) -> Dict[str, Any]:
        """
        Generate complete article with character control

        Args:
            input_data: Article generation input

        Returns:
            Complete article data

        Raises:
            Exception: Generation failure
        """
        article_id = "temp"  # Will be set by caller

        try:
            log_article_generation(article_id, "start", "generating")

            # Step 1: Generate outline
            logger.info("Starting outline generation")
            outline = await perplexity_client.generate_outline(input_data)
            log_article_generation(article_id, "outline_generated", "success",
                                 sections=len(outline.get("sections", [])))

            # Step 2: Calculate target characters per section
            sections = outline.get("sections", [])
            if not sections:
                raise ValueError("No sections generated in outline")

            target_per_section = input_data.target_chars // len(sections)
            target_per_section = max(self.min_section_chars,
                                   min(self.max_section_chars, target_per_section))

            # Step 3: Generate sections
            logger.info(f"Generating {len(sections)} sections with ~{target_per_section} chars each")
            section_contents = []

            for i, section in enumerate(sections):
                logger.info(f"Generating section {i+1}/{len(sections)}: {section.get('h2', 'Unknown')}")

                section_content = await perplexity_client.generate_section(
                    input_data, section, target_per_section
                )

                # Sanitize section content
                section_content = sanitize_html(section_content)
                section_contents.append(section_content)

                log_article_generation(article_id, "section_generated", "success",
                                     section_index=i, chars=count_ja_chars_from_html(section_content))

            # Step 4: Merge sections
            logger.info("Merging sections")
            merged_content = self._merge_sections(section_contents)

            # Step 5: Character count adjustment
            logger.info("Adjusting character count")
            adjusted_content = await self._adjust_character_count(
                input_data, merged_content, sections
            )

            # Step 6: Final validation and sanitization
            final_content = sanitize_html(adjusted_content)
            final_char_count = count_ja_chars_from_html(final_content)

            # Step 7: Generate metadata
            logger.info("Generating article metadata")
            article_data = await perplexity_client.finalize_article(
                input_data, outline, section_contents
            )

            # Set the final content
            article_data["body_html"] = final_content

            # Validate structure
            validation_result = validate_article_length(
                final_content, input_data.target_chars
            )

            log_article_generation(article_id, "generation_completed", "success",
                                 char_count=final_char_count,
                                 target_chars=input_data.target_chars,
                                 is_valid=validation_result["is_valid"])

            logger.info(f"Article generation completed: {final_char_count} characters "
                       f"(target: {input_data.target_chars})")

            return article_data

        except Exception as e:
            log_article_generation(article_id, "generation_failed", "error", error=str(e))
            logger.error(f"Article generation failed: {str(e)}")
            raise

    async def _adjust_character_count(
        self,
        input_data: GenerateInput,
        content: str,
        sections: List[Dict[str, Any]]
    ) -> str:
        """
        Adjust content to meet target character count

        Args:
            input_data: Original input data
            content: Current content
            sections: Section structure

        Returns:
            Adjusted content
        """
        current_chars = count_ja_chars_from_html(content)
        target_chars = input_data.target_chars

        validation = validate_article_length(content, target_chars)

        if validation["is_valid"]:
            logger.info(f"Character count is valid: {current_chars}/{target_chars}")
            return content

        if validation["status"] == "too_short":
            logger.info(f"Content too short: {current_chars}/{target_chars}, expanding...")
            return await self._expand_content(input_data, content, sections,
                                            validation["adjustment_needed"])

        elif validation["status"] == "too_long":
            logger.info(f"Content too long: {current_chars}/{target_chars}, condensing...")
            return await self._condense_content(content, validation["adjustment_needed"])

        return content

    async def _expand_content(
        self,
        input_data: GenerateInput,
        content: str,
        sections: List[Dict[str, Any]],
        chars_needed: int
    ) -> str:
        """
        Expand content to reach target character count

        Args:
            input_data: Original input data
            content: Current content
            sections: Section structure
            chars_needed: Additional characters needed

        Returns:
            Expanded content
        """
        logger.info(f"Expanding content by approximately {chars_needed} characters")

        # Identify sections that can be expanded
        headings = extract_headings(content)
        if not headings:
            return content

        # Select sections to expand (prefer middle sections)
        sections_to_expand = min(3, len(sections))
        chars_per_expansion = chars_needed // sections_to_expand

        # For each selected section, generate additional content
        expanded_content = content

        for i in range(min(sections_to_expand, len(sections))):
            section = sections[i]

            try:
                additional_content = await self._generate_section_expansion(
                    input_data, section, chars_per_expansion
                )

                # Insert additional content after the section's last H3
                h2_title = section.get("h2", "")
                if h2_title:
                    expanded_content = self._insert_content_after_section(
                        expanded_content, h2_title, additional_content
                    )

            except Exception as e:
                logger.warning(f"Failed to expand section {i}: {str(e)}")
                continue

        return expanded_content

    async def _condense_content(self, content: str, chars_to_remove: int) -> str:
        """
        Condense content to reduce character count

        Args:
            content: Current content
            chars_to_remove: Characters to remove

        Returns:
            Condensed content
        """
        logger.info(f"Condensing content by approximately {chars_to_remove} characters")

        # Simple condensation strategies:
        # 1. Remove redundant paragraphs
        # 2. Shorten overly verbose explanations
        # 3. Remove excessive examples

        condensed = content

        # Remove empty paragraphs
        import re
        condensed = re.sub(r'<p>\s*</p>', '', condensed)

        # Remove very short paragraphs (likely redundant)
        condensed = re.sub(r'<p>[^<]{1,20}</p>', '', condensed)

        # Condense list items if lists are too long
        condensed = self._condense_long_lists(condensed)

        # If still too long, try more aggressive condensation
        current_chars = count_ja_chars_from_html(condensed)
        if current_chars > count_ja_chars_from_html(content) - chars_to_remove:
            condensed = self._aggressive_condense(condensed, chars_to_remove)

        return condensed

    async def _generate_section_expansion(
        self,
        input_data: GenerateInput,
        section: Dict[str, Any],
        target_chars: int
    ) -> str:
        """Generate additional content for a section"""
        h2_title = section.get("h2", "")

        # Create a focused prompt for expansion
        expansion_prompt = f"""以下のセクションについて、さらに詳細な情報を追加してください。

セクション: {h2_title}
記事コンテキスト: {input_data.summary}
目標追加文字数: 約{target_chars}文字

追加すべき内容:
- より具体的な例
- 詳細な解説
- 実践的なアドバイス
- 関連する補足情報

HTML形式（h3, p, ul, ol, li, strong, em タグを使用）で出力してください。"""

        try:
            response = await perplexity_client._call_api([
                {"role": "system", "content": perplexity_client._build_system_prompt()},
                {"role": "user", "content": expansion_prompt}
            ], max_tokens=2000)

            return sanitize_html(response.content)

        except Exception as e:
            logger.warning(f"Failed to generate expansion for section '{h2_title}': {str(e)}")
            return ""

    def _merge_sections(self, section_contents: List[str]) -> str:
        """
        Merge section contents into a single article

        Args:
            section_contents: List of section HTML contents

        Returns:
            Merged HTML content
        """
        # Simple concatenation with cleanup
        merged = "\n\n".join(section_contents)

        # Clean up duplicate headings or spacing issues
        merged = self._clean_merged_content(merged)

        return merged

    def _clean_merged_content(self, content: str) -> str:
        """Clean merged content for consistency"""
        import re

        # Remove excessive line breaks
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Ensure proper spacing around headings
        content = re.sub(r'</h[23]>\n*<p>', '</h2>\n<p>', content)
        content = re.sub(r'</h[23]>\n*<h[23]>', '</h2>\n<h3>', content)

        # Remove empty paragraphs
        content = re.sub(r'<p>\s*</p>', '', content)

        return content.strip()

    def _insert_content_after_section(self, content: str, h2_title: str, additional_content: str) -> str:
        """Insert additional content after a specific H2 section"""
        import re

        # Find the H2 section
        h2_pattern = rf'<h2[^>]*>{re.escape(h2_title)}</h2>'

        # Find the next H2 or end of content
        next_h2_pattern = r'<h2[^>]*>'

        match = re.search(h2_pattern, content, re.IGNORECASE)
        if not match:
            return content

        # Find where this section ends (next H2 or end of content)
        start_pos = match.end()
        next_match = re.search(next_h2_pattern, content[start_pos:], re.IGNORECASE)

        if next_match:
            insert_pos = start_pos + next_match.start()
            return (content[:insert_pos] +
                   f"\n\n{additional_content}\n\n" +
                   content[insert_pos:])
        else:
            # Insert at end
            return content + f"\n\n{additional_content}"

    def _condense_long_lists(self, content: str) -> str:
        """Condense overly long lists"""
        import re

        # Find lists with more than 7 items and reduce them
        def condense_list(match):
            list_content = match.group(1)
            items = re.findall(r'<li[^>]*>(.*?)</li>', list_content, re.DOTALL)

            if len(items) > 7:
                # Keep first 5 items and add "など" (etc.)
                condensed_items = items[:5]
                condensed_items.append("など")

                new_list = '\n'.join(f'<li>{item}</li>' for item in condensed_items)
                return f'<{match.group(0).split()[0][1:]}>\n{new_list}\n</{match.group(0).split()[0][1:].split(">")[0]}>'

            return match.group(0)

        # Apply to both ul and ol lists
        content = re.sub(r'<(ul[^>]*)>(.*?)</ul>', condense_list, content, flags=re.DOTALL)
        content = re.sub(r'<(ol[^>]*)>(.*?)</ol>', condense_list, content, flags=re.DOTALL)

        return content

    def _aggressive_condense(self, content: str, chars_to_remove: int) -> str:
        """More aggressive content condensation"""
        import re

        # Remove detailed examples that are too verbose
        content = re.sub(r'<p>例えば[^<]+</p>', '', content)

        # Shorten very long paragraphs
        def shorten_paragraph(match):
            p_content = match.group(1)
            if len(p_content) > 200:  # Very long paragraph
                # Keep first 150 characters and add conclusion
                shortened = p_content[:150] + "。"
                return f'<p>{shortened}</p>'
            return match.group(0)

        content = re.sub(r'<p>([^<]+)</p>', shorten_paragraph, content)

        return content


# Create service instance
generation_service = ArticleGenerationService()