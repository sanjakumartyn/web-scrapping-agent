"""Text processing utilities for cleaning and chunking enterprise content."""

import re
from typing import List
from loguru import logger


class TextProcessor:
    """Process and clean text for LLM consumption."""

    # Boilerplate patterns to remove
    BOILERPLATE_PATTERNS = [
        r"(?i)cookie|privacy|terms of service|sitemap|contact us",
        r"(?i)copyright|all rights reserved|©",
        r"(?i)follow us|connect with us|social media",
        r"(?i)powered by|developed by|built with",
    ]

    # HTML tags and entities to clean
    HTML_PATTERNS = [
        (r"<script[^>]*>.*?</script>", " ", re.DOTALL | re.IGNORECASE),
        (r"<style[^>]*>.*?</style>", " ", re.DOTALL | re.IGNORECASE),
        (r"<noscript[^>]*>.*?</noscript>", " ", re.DOTALL | re.IGNORECASE),
        (r"<[^>]+>", " "),  # HTML tags
        (r"&nbsp;", " "),
        (r"&quot;", '"'),
        (r"&apos;", "'"),
        (r"&amp;", "&"),
        (r"&#?\w+;", " "),  # HTML entities
    ]

    @staticmethod
    def clean_html(text: str) -> str:
        """Remove HTML tags and clean HTML entities.

        Args:
            text: Raw HTML text

        Returns:
            Cleaned text
        """
        for pattern, replacement, *flags in TextProcessor.HTML_PATTERNS:
            flag = flags[0] if flags else 0
            text = re.sub(pattern, replacement, text, flags=flag)

        return text

    @staticmethod
    def remove_boilerplate(text: str) -> str:
        """Remove common website boilerplate text.

        Args:
            text: Text to clean

        Returns:
            Text with boilerplate removed
        """
        for pattern in TextProcessor.BOILERPLATE_PATTERNS:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace and remove extra blank lines.

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        # Replace multiple spaces with single space
        text = re.sub(r"\s+", " ", text)
        # Replace multiple newlines with single newline
        text = re.sub(r"\n\n+", "\n", text)
        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """Extract sentences from text.

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

        return sentences

    @staticmethod
    def clean_text(text: str) -> str:
        """Complete text cleaning pipeline.

        Args:
            text: Raw text to clean

        Returns:
            Fully cleaned text
        """
        if not text:
            return ""

        text = TextProcessor.clean_html(text)
        text = TextProcessor.remove_boilerplate(text)
        text = TextProcessor.normalize_whitespace(text)

        return text

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
        min_chunk_size: int = 100,
    ) -> List[str]:
        """Split text into overlapping chunks for LLM processing.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks
            min_chunk_size: Minimum chunk size to include

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text] if len(text) >= min_chunk_size else []

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind(".", start, end)
                if last_period > start + chunk_size // 2:
                    end = last_period + 1

            chunk = text[start:end].strip()

            if len(chunk) >= min_chunk_size:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - overlap if end < len(text) else len(text)

        return chunks

    @staticmethod
    def remove_duplicates(texts: List[str]) -> List[str]:
        """Remove duplicate or near-duplicate texts.

        Args:
            texts: List of texts to deduplicate

        Returns:
            Deduplicated list
        """
        seen = set()
        result = []

        for text in texts:
            normalized = TextProcessor.normalize_whitespace(text.lower())

            if normalized not in seen and len(normalized) > 10:
                seen.add(normalized)
                result.append(text)

        return result

    @staticmethod
    def extract_key_phrases(text: str, min_length: int = 3) -> List[str]:
        """Extract key phrases from text (basic noun-phrase extraction).

        Args:
            text: Input text
            min_length: Minimum phrase length

        Returns:
            List of key phrases
        """
        # Simple pattern for capitalized phrases
        pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        phrases = re.findall(pattern, text)

        # Filter out single words and short phrases
        phrases = [p for p in phrases if len(p.split()) >= min_length or len(p) > 10]

        return list(set(phrases))
