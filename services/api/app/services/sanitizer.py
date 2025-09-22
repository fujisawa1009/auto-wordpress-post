"""
HTML sanitization and text processing utilities
"""
import re
from typing import List, Dict, Any

import bleach


# Allowed HTML tags for article content
ALLOWED_TAGS = [
    'h2', 'h3', 'p', 'ul', 'ol', 'li',
    'blockquote', 'code', 'pre', 'strong', 'em', 'a'
]

# Allowed attributes for HTML tags
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'blockquote': ['cite'],
    'code': ['class'],
    'pre': ['class'],
}

# URL protocols allowed in links
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content for safe display

    Args:
        html_content: Raw HTML content

    Returns:
        Sanitized HTML content
    """
    if not html_content:
        return ""

    # Basic HTML sanitization
    clean_html = bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )

    # Additional cleaning
    clean_html = _clean_malformed_html(clean_html)
    clean_html = _normalize_whitespace(clean_html)

    return clean_html


def count_ja_chars_from_html(html_content: str) -> int:
    """
    Count Japanese characters from HTML content

    Args:
        html_content: HTML content string

    Returns:
        Number of Japanese characters (excluding whitespace)
    """
    if not html_content:
        return 0

    # Remove HTML tags
    text = bleach.clean(html_content, tags=[], strip=True)

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Count non-whitespace characters
    return sum(1 for ch in text if not ch.isspace())


def extract_text_from_html(html_content: str) -> str:
    """
    Extract plain text from HTML content

    Args:
        html_content: HTML content string

    Returns:
        Plain text without HTML tags
    """
    if not html_content:
        return ""

    # Remove HTML tags
    text = bleach.clean(html_content, tags=[], strip=True)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def validate_article_length(html_content: str, target_chars: int = 10000, tolerance: int = 1000) -> Dict[str, Any]:
    """
    Validate article length against target

    Args:
        html_content: HTML content to validate
        target_chars: Target character count
        tolerance: Acceptable deviation from target

    Returns:
        Validation result with status and metrics
    """
    char_count = count_ja_chars_from_html(html_content)
    min_chars = target_chars - tolerance
    max_chars = target_chars + tolerance

    is_valid = min_chars <= char_count <= max_chars

    if char_count < min_chars:
        status = "too_short"
        adjustment_needed = min_chars - char_count
    elif char_count > max_chars:
        status = "too_long"
        adjustment_needed = char_count - max_chars
    else:
        status = "valid"
        adjustment_needed = 0

    return {
        "is_valid": is_valid,
        "status": status,
        "char_count": char_count,
        "target_chars": target_chars,
        "min_chars": min_chars,
        "max_chars": max_chars,
        "adjustment_needed": adjustment_needed,
        "deviation_percent": abs(char_count - target_chars) / target_chars * 100
    }


def extract_headings(html_content: str) -> List[Dict[str, str]]:
    """
    Extract heading structure from HTML content

    Args:
        html_content: HTML content string

    Returns:
        List of headings with level and text
    """
    if not html_content:
        return []

    headings = []

    # Find all h2 and h3 tags
    h2_pattern = re.compile(r'<h2[^>]*>(.*?)</h2>', re.IGNORECASE | re.DOTALL)
    h3_pattern = re.compile(r'<h3[^>]*>(.*?)</h3>', re.IGNORECASE | re.DOTALL)

    for match in h2_pattern.finditer(html_content):
        text = bleach.clean(match.group(1), tags=[], strip=True).strip()
        if text:
            headings.append({
                "level": "h2",
                "text": text,
                "position": match.start()
            })

    for match in h3_pattern.finditer(html_content):
        text = bleach.clean(match.group(1), tags=[], strip=True).strip()
        if text:
            headings.append({
                "level": "h3",
                "text": text,
                "position": match.start()
            })

    # Sort by position in document
    headings.sort(key=lambda x: x["position"])

    # Remove position info
    for heading in headings:
        del heading["position"]

    return headings


def _clean_malformed_html(html_content: str) -> str:
    """Clean malformed HTML patterns"""
    # Remove empty tags
    html_content = re.sub(r'<(\w+)[^>]*>\s*</\1>', '', html_content)

    # Remove multiple consecutive br tags
    html_content = re.sub(r'(<br[^>]*>\s*){3,}', '<br><br>', html_content, flags=re.IGNORECASE)

    # Clean up malformed links
    html_content = re.sub(r'<a[^>]*href=["\']javascript:[^"\']*["\'][^>]*>', '', html_content, flags=re.IGNORECASE)

    return html_content


def _normalize_whitespace(html_content: str) -> str:
    """Normalize whitespace in HTML content"""
    # Normalize line breaks
    html_content = re.sub(r'\r\n', '\n', html_content)
    html_content = re.sub(r'\r', '\n', html_content)

    # Remove excessive whitespace between tags
    html_content = re.sub(r'>\s+<', '><', html_content)

    # Normalize spacing around block elements
    html_content = re.sub(r'\n\s*\n', '\n', html_content)

    return html_content.strip()


def generate_excerpt(html_content: str, max_length: int = 300) -> str:
    """
    Generate excerpt from HTML content

    Args:
        html_content: HTML content string
        max_length: Maximum length of excerpt

    Returns:
        Generated excerpt
    """
    if not html_content:
        return ""

    # Extract text
    text = extract_text_from_html(html_content)

    # Truncate to max length
    if len(text) <= max_length:
        return text

    # Find last complete sentence within limit
    excerpt = text[:max_length]
    last_period = excerpt.rfind('。')
    last_exclamation = excerpt.rfind('！')
    last_question = excerpt.rfind('？')

    # Use the latest sentence ending
    last_sentence_end = max(last_period, last_exclamation, last_question)

    if last_sentence_end > max_length * 0.7:  # If sentence end is reasonably close
        excerpt = excerpt[:last_sentence_end + 1]
    else:
        # No good sentence boundary, just add ellipsis
        excerpt = excerpt.rstrip() + "..."

    return excerpt


def analyze_content_structure(html_content: str) -> Dict[str, Any]:
    """
    Analyze HTML content structure

    Args:
        html_content: HTML content string

    Returns:
        Content structure analysis
    """
    if not html_content:
        return {
            "char_count": 0,
            "word_count": 0,
            "paragraph_count": 0,
            "heading_count": 0,
            "list_count": 0,
            "headings": []
        }

    text = extract_text_from_html(html_content)
    headings = extract_headings(html_content)

    # Count elements
    paragraph_count = len(re.findall(r'<p[^>]*>', html_content, re.IGNORECASE))
    list_count = len(re.findall(r'<(ul|ol)[^>]*>', html_content, re.IGNORECASE))

    # Estimate word count (approximate for Japanese text)
    word_count = len(re.findall(r'\S+', text))

    return {
        "char_count": count_ja_chars_from_html(html_content),
        "word_count": word_count,
        "paragraph_count": paragraph_count,
        "heading_count": len(headings),
        "list_count": list_count,
        "headings": headings,
        "has_good_structure": len(headings) >= 3 and paragraph_count >= 5
    }