"""PDF extraction utilities for annual reports and ESG documents."""

import asyncio
from pathlib import Path
from typing import List, Optional
from loguru import logger

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


class PDFExtractor:
    """Extract text from PDF files."""

    @staticmethod
    def extract_with_pypdf(pdf_path: str, max_pages: Optional[int] = None) -> str:
        """Extract text using pypdf library.

        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to extract (None = all)

        Returns:
            Extracted text
        """
        if not pypdf:
            logger.warning("pypdf not installed, skipping PDF extraction")
            return ""

        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                pages = reader.pages[: max_pages or len(reader.pages)]

                text = "\n".join(
                    page.extract_text() for page in pages if page.extract_text()
                )

            logger.info(f"Extracted {len(text)} chars from {Path(pdf_path).name} (pypdf)")
            return text

        except Exception as e:
            logger.error(f"PDF extraction failed with pypdf: {e}")
            return ""

    @staticmethod
    def extract_with_pdfplumber(
        pdf_path: str, max_pages: Optional[int] = None
    ) -> str:
        """Extract text using pdfplumber library (better for complex layouts).

        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to extract (None = all)

        Returns:
            Extracted text
        """
        if not pdfplumber:
            logger.warning("pdfplumber not installed, skipping PDF extraction")
            return ""

        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages = pdf.pages[: max_pages or len(pdf.pages)]

                text = "\n".join(
                    page.extract_text() or "" for page in pages
                )

            logger.info(
                f"Extracted {len(text)} chars from {Path(pdf_path).name} (pdfplumber)"
            )
            return text

        except Exception as e:
            logger.error(f"PDF extraction failed with pdfplumber: {e}")
            return ""

    @staticmethod
    def extract_text(
        pdf_path: str,
        max_pages: Optional[int] = 50,
        use_pdfplumber_first: bool = True,
    ) -> str:
        """Extract text from PDF with fallback options.

        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to extract
            use_pdfplumber_first: Try pdfplumber first (better quality)

        Returns:
            Extracted text
        """
        if not Path(pdf_path).exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return ""

        if use_pdfplumber_first:
            text = PDFExtractor.extract_with_pdfplumber(pdf_path, max_pages)
            if text:
                return text
            return PDFExtractor.extract_with_pypdf(pdf_path, max_pages)
        else:
            text = PDFExtractor.extract_with_pypdf(pdf_path, max_pages)
            if text:
                return text
            return PDFExtractor.extract_with_pdfplumber(pdf_path, max_pages)

    @staticmethod
    async def extract_multiple(
        pdf_paths: List[str], max_pages_per_file: int = 50
    ) -> dict:
        """Extract text from multiple PDFs concurrently.

        Args:
            pdf_paths: List of PDF file paths
            max_pages_per_file: Max pages per PDF

        Returns:
            Dictionary mapping file names to extracted text
        """
        loop = asyncio.get_event_loop()

        async def extract_async(path: str) -> tuple:
            text = await loop.run_in_executor(
                None, PDFExtractor.extract_text, path, max_pages_per_file
            )
            return Path(path).name, text

        results = await asyncio.gather(
            *[extract_async(path) for path in pdf_paths], return_exceptions=True
        )

        extracted = {}
        for result in results:
            if isinstance(result, tuple):
                name, text = result
                extracted[name] = text
            else:
                logger.error(f"PDF extraction error: {result}")

        return extracted
