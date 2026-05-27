"""
Base PDF exporter class with common PDF generation functionality.
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Tuple, Any

from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph, PageBreak

from ..base import BaseExporter


@dataclass
class PDFConfig:
    """Configuration for PDF generation."""
    page_size: Tuple[float, float] = A4
    orientation: str = 'portrait'  # 'portrait' or 'landscape'
    margin_left: float = 30
    margin_right: float = 30
    margin_top: float = 30
    margin_bottom: float = 30
    title: str = ""
    author: str = ""
    subject: str = ""


class BasePDFExporter(BaseExporter):
    """
    Base class for PDF exporters using ReportLab.
    
    Provides common functionality for creating PDF documents.
    """

    def __init__(self, config: Optional[PDFConfig] = None, **kwargs):
        """
        Initialize PDF exporter.
        
        Args:
            config: PDF configuration
            **kwargs: Additional configuration passed to BaseExporter
        """
        super().__init__(**kwargs)
        self.config = config or PDFConfig()
        self.elements = []
        self.doc = None

    def get_content_type(self) -> str:
        """Get PDF MIME type."""
        return 'application/pdf'

    def get_file_extension(self) -> str:
        """Get PDF file extension."""
        return 'pdf'

    def _create_document(self) -> SimpleDocTemplate:
        """
        Create PDF document with configured settings.
        
        Returns:
            SimpleDocTemplate instance
        """
        # Determine page size based on orientation
        if self.config.orientation == 'landscape':
            page_size = landscape(self.config.page_size)
        else:
            page_size = portrait(self.config.page_size)

        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=page_size,
            leftMargin=self.config.margin_left,
            rightMargin=self.config.margin_right,
            topMargin=self.config.margin_top,
            bottomMargin=self.config.margin_bottom,
            title=self.config.title,
            author=self.config.author,
            subject=self.config.subject,
        )

        return doc

    def add_title(self, title: str, style: Any) -> None:
        """
        Add title to document.
        
        Args:
            title: Title text
            style: ReportLab ParagraphStyle
        """
        title_para = Paragraph(title, style)
        self.elements.append(title_para)

    def add_spacer(self, height: float = 0.2) -> None:
        """
        Add vertical space.
        
        Args:
            height: Height in inches
        """
        self.elements.append(Spacer(1, height * inch))

    def add_paragraph(self, text: str, style: Any) -> None:
        """
        Add paragraph to document.
        
        Args:
            text: Paragraph text (can include HTML tags)
            style: ReportLab ParagraphStyle
        """
        para = Paragraph(text, style)
        self.elements.append(para)

    def add_table(self, table: Any) -> None:
        """
        Add table to document.
        
        Args:
            table: ReportLab Table instance
        """
        self.elements.append(table)

    def add_page_break(self) -> None:
        """Add page break."""
        self.elements.append(PageBreak())

    def add_element(self, element: Any) -> None:
        """
        Add any flowable element to document.
        
        Args:
            element: ReportLab Flowable instance
        """
        self.elements.append(element)

    def build_document(self) -> None:
        """Build the PDF document from elements."""
        if not self.doc:
            self.doc = self._create_document()

        self.doc.build(self.elements)

    def generate(self, data: Any) -> BytesIO:
        """
        Generate PDF document.
        
        This method should be overridden by subclasses to implement
        specific document generation logic.
        
        Args:
            data: Data to export
            
        Returns:
            BytesIO buffer with PDF
        """
        self.reset_buffer()
        self.elements = []

        # Create document
        self.doc = self._create_document()

        # Subclasses should override this to add content
        self._add_content(data)

        # Build document
        self.build_document()

        return self.buffer

    def _add_content(self, data: Any) -> None:
        """
        Add content to document.
        
        This method should be overridden by subclasses.
        
        Args:
            data: Data to add to document
        """
        raise NotImplementedError("Subclasses must implement _add_content()")

    def get_available_width(self) -> float:
        """
        Get available width for content.
        
        Returns:
            Width in points
        """
        if self.config.orientation == 'landscape':
            page_width = self.config.page_size[1]
        else:
            page_width = self.config.page_size[0]

        return page_width - self.config.margin_left - self.config.margin_right

    def get_available_height(self) -> float:
        """
        Get available height for content.
        
        Returns:
            Height in points
        """
        if self.config.orientation == 'landscape':
            page_height = self.config.page_size[0]
        else:
            page_height = self.config.page_size[1]

        return page_height - self.config.margin_top - self.config.margin_bottom
