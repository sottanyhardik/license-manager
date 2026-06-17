"""
Base exporter class and enums for all export functionality.
"""

from abc import ABC, abstractmethod
from enum import Enum
from io import BytesIO
from typing import Any


class ExportFormat(Enum):
    """Supported export formats."""
    PDF = 'pdf'
    EXCEL = 'excel'
    CSV = 'csv'


class BaseExporter(ABC):
    """
    Base class for all exporters.
    
    Provides common functionality for exporting data to various formats.
    """

    def __init__(self, title: str = "", **config):
        """
        Initialize exporter.
        
        Args:
            title: Document title
            **config: Additional configuration options
        """
        self.title = title
        self.config = config
        self.buffer = BytesIO()

    @abstractmethod
    def generate(self, data: Any) -> BytesIO:
        """
        Generate export document.
        
        Args:
            data: Data to export
            
        Returns:
            BytesIO buffer with generated document
        """
        pass

    @abstractmethod
    def get_content_type(self) -> str:
        """
        Get MIME type for the export format.
        
        Returns:
            Content type string
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get file extension for the export format.
        
        Returns:
            File extension (without dot)
        """
        pass

    def get_filename(self, base_name: str = "export") -> str:
        """
        Generate filename for export.
        
        Args:
            base_name: Base name for file
            
        Returns:
            Full filename with extension
        """
        extension = self.get_file_extension()
        return f"{base_name}.{extension}"

    def reset_buffer(self) -> None:
        """Reset the internal buffer."""
        self.buffer = BytesIO()

    def get_buffer_value(self) -> bytes:
        """
        Get current buffer value.
        
        Returns:
            Buffer contents as bytes
        """
        self.buffer.seek(0)
        return self.buffer.getvalue()
