"""PDF document ingestion and section detection.

Handles parsing PDF files for strategic and action plans (separate or combined).
"""

from pathlib import Path
from typing import Optional

import pdfplumber


class DocumentIngestion:
    """Parses PDF documents and extracts text."""

    @staticmethod
    def extract_text_from_pdf(pdf_path: str | Path) -> str:
        """Extract all text from a single PDF file.

        Args:
            pdf_path: Path to the PDF file to parse

        Returns:
            Complete text content of the PDF

        Raises:
            FileNotFoundError: If PDF file does not exist
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        with pdfplumber.open(pdf_path) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts)

    @staticmethod
    def extract_from_separate_pdfs(
        strategic_pdf: str | Path,
        action_pdfs: list[str | Path],
    ) -> tuple[str, str]:
        """Extract text from separate strategic and action plan PDFs.

        Args:
            strategic_pdf: Path to strategic plan PDF
            action_pdfs: List of paths to action plan PDFs

        Returns:
            Tuple of (strategic_text, action_text)

        This is the recommended method when you have separate PDFs for
        strategic plans and action plans.
        """
        # Extract strategic plan text
        strategic_text = DocumentIngestion.extract_text_from_pdf(strategic_pdf)

        # Extract and combine all action plan texts
        action_texts = []
        for action_pdf in action_pdfs:
            action_text = DocumentIngestion.extract_text_from_pdf(action_pdf)
            action_texts.append(action_text)

        action_text = "\n\n--- ACTION PLAN DOCUMENT SEPARATOR ---\n\n".join(action_texts)

        return strategic_text, action_text

    @staticmethod
    def extract_from_combined_pdf(
        pdf_path: str | Path,
        strategic_start: Optional[int] = None,
        strategic_end: Optional[int] = None,
        action_start: Optional[int] = None,
        action_end: Optional[int] = None,
    ) -> tuple[str, str]:
        """Extract strategic and action sections from a combined PDF.

        Args:
            pdf_path: Path to the combined PDF file
            strategic_start: Starting page for strategic plan (1-indexed)
            strategic_end: Ending page for strategic plan (1-indexed)
            action_start: Starting page for action plan (1-indexed)
            action_end: Ending page for action plan (1-indexed)

        Returns:
            Tuple of (strategic_text, action_text)

        Use this method when both strategic and action plans are in the same PDF.
        If page ranges are not specified, defaults to a 50/50 split.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

            # Extract strategic plan section
            if strategic_start and strategic_end:
                strategic_pages = pdf.pages[strategic_start - 1 : strategic_end]
            elif strategic_start:
                strategic_pages = pdf.pages[
                    strategic_start - 1 : total_pages // 2
                ]
            else:
                strategic_pages = pdf.pages[: total_pages // 2]

            strategic_text = "\n\n".join(
                [p.extract_text() or "" for p in strategic_pages]
            )

            # Extract action plan section
            if action_start and action_end:
                action_pages = pdf.pages[action_start - 1 : action_end]
            elif action_start:
                action_pages = pdf.pages[action_start - 1 :]
            else:
                action_pages = pdf.pages[total_pages // 2 :]

            action_text = "\n\n".join(
                [p.extract_text() or "" for p in action_pages]
            )

            return strategic_text, action_text

    def detect_section_boundaries(self, text: str) -> dict[str, int]:
        """Attempt to detect strategic vs action plan boundaries using keywords.

        Args:
            text: Full PDF text

        Returns:
            Dictionary with detected boundary positions
        """
        lines = text.split("\n")
        boundaries = {}

        # Keywords that typically indicate section transitions
        strategic_keywords = [
            "strategic plan",
            "strategy",
            "vision",
            "mission",
            "objectives",
        ]
        action_keywords = [
            "action plan",
            "implementation",
            "roadmap",
            "timeline",
            "tasks",
            "deliverables",
        ]

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Check for strategic section start
            if not boundaries.get("strategic_start"):
                if any(kw in line_lower for kw in strategic_keywords):
                    boundaries["strategic_start"] = i

            # Check for action section start
            if not boundaries.get("action_start"):
                if any(kw in line_lower for kw in action_keywords):
                    boundaries["action_start"] = i

        return boundaries
