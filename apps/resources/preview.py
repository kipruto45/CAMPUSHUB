"""
File preview service for CampusHub.
Provides preview generation for various file types.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class FilePreviewService:
    """
    Service for generating file previews.
    """

    # Supported preview types
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
    PDF_EXTENSION = ".pdf"
    DOCUMENT_EXTENSIONS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt"}

    # Thumbnail settings
    THUMBNAIL_SIZE = (300, 300)
    PREVIEW_SIZE = (800, 800)

    @staticmethod
    def get_file_type(file_path: str) -> str:
        """
        Determine the file type from extension.

        Args:
            file_path: Path to the file

        Returns:
            File type string (image, pdf, document, unknown)
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext in FilePreviewService.IMAGE_EXTENSIONS:
            return "image"
        elif ext == FilePreviewService.PDF_EXTENSION:
            return "pdf"
        elif ext in FilePreviewService.DOCUMENT_EXTENSIONS:
            return "document"
        else:
            return "unknown"

    @staticmethod
    def is_preview_supported(file_path: str) -> bool:
        """
        Check if preview is supported for this file type.

        Args:
            file_path: Path to the file

        Returns:
            True if preview is supported
        """
        return FilePreviewService.get_file_type(file_path) != "unknown"

    @staticmethod
    def get_mime_type(file_path: str) -> str:
        """
        Get MIME type based on file extension.

        Args:
            file_path: Path to the file

        Returns:
            MIME type string
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        mime_types = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".svg": "image/svg+xml",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
        }

        return mime_types.get(ext, "application/octet-stream")

    @staticmethod
    def generate_image_thumbnail(
        image_path: str, output_path: str = None
    ) -> Optional[str]:
        """
        Generate thumbnail for an image.

        Args:
            image_path: Path to the image file
            output_path: Output path for thumbnail (optional)

        Returns:
            Path to generated thumbnail or None
        """
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Create thumbnail
                img.thumbnail(
                    FilePreviewService.THUMBNAIL_SIZE, Image.Resampling.LANCZOS
                )

                # Save thumbnail
                if output_path is None:
                    name, ext = os.path.splitext(image_path)
                    output_path = f"{name}_thumb.jpg"

                img.save(output_path, "JPEG", quality=85)

            return output_path

        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            return None

    @staticmethod
    def generate_image_preview(
        image_path: str, output_path: str = None
    ) -> Optional[str]:
        """
        Generate preview for an image.

        Args:
            image_path: Path to the image file
            output_path: Output path for preview (optional)

        Returns:
            Path to generated preview or None
        """
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Resize for preview
                img.thumbnail(FilePreviewService.PREVIEW_SIZE, Image.Resampling.LANCZOS)

                # Save preview
                if output_path is None:
                    name, ext = os.path.splitext(image_path)
                    output_path = f"{name}_preview.jpg"

                img.save(output_path, "JPEG", quality=90)

            return output_path

        except Exception as e:
            logger.error(f"Failed to generate preview: {e}")
            return None

    @staticmethod
    def get_pdf_page_count(pdf_path: str) -> Optional[int]:
        """
        Get number of pages in PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages or None
        """
        try:
            from pypdf import PdfReader

            reader = PdfReader(pdf_path)
            return len(reader.pages)

        except Exception as e:
            logger.error(f"Failed to get PDF page count: {e}")
            return None

    @staticmethod
    def generate_pdf_thumbnail(
        pdf_path: str, output_path: str = None, page_number: int = 0
    ) -> Optional[str]:
        """
        Generate thumbnail for first page of PDF.

        Args:
            pdf_path: Path to PDF file
            output_path: Output path for thumbnail
            page_number: Page number to render (0-indexed)

        Returns:
            Path to generated thumbnail or None
        """
        try:
            from PIL import Image, ImageDraw
            from pypdf import PdfReader

            reader = PdfReader(pdf_path)
            if page_number >= len(reader.pages):
                return None

            if output_path is None:
                name, _ = os.path.splitext(pdf_path)
                output_path = f"{name}_thumb.jpg"

            # Preferred path: render first page via pdf2image if available.
            try:
                from pdf2image import convert_from_path

                rendered = convert_from_path(
                    pdf_path,
                    first_page=page_number + 1,
                    last_page=page_number + 1,
                    fmt="jpeg",
                    single_file=True,
                )
                if rendered:
                    image = rendered[0]
                    resample = getattr(Image, "Resampling", Image).LANCZOS
                    image.thumbnail(FilePreviewService.THUMBNAIL_SIZE, resample)
                    image.save(output_path, "JPEG", quality=85)
                    return output_path
            except Exception as render_error:
                logger.debug(
                    "PDF rasterization unavailable for %s (%s). Falling back to generic thumbnail.",
                    pdf_path,
                    render_error,
                )

            # Fallback path: create a deterministic generic thumbnail.
            placeholder = Image.new(
                "RGB", FilePreviewService.THUMBNAIL_SIZE, color=(245, 245, 245)
            )
            draw = ImageDraw.Draw(placeholder)
            draw.rectangle(
                (
                    12,
                    12,
                    FilePreviewService.THUMBNAIL_SIZE[0] - 12,
                    FilePreviewService.THUMBNAIL_SIZE[1] - 12,
                ),
                outline=(220, 220, 220),
                width=2,
            )
            draw.text((24, 24), "PDF", fill=(200, 40, 40))
            draw.text((24, 56), f"Pages: {len(reader.pages)}", fill=(70, 70, 70))
            draw.text((24, 82), f"Page: {page_number + 1}", fill=(70, 70, 70))
            placeholder.save(output_path, "JPEG", quality=85)
            return output_path
        except Exception as e:
            logger.error(f"Failed to generate PDF thumbnail: {e}")
            return None

    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """
        Get comprehensive file information.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file information
        """
        info = {
            "type": "unknown",
            "mime_type": "application/octet-stream",
            "supported": False,
            "size": 0,
            "extension": "",
        }

        try:
            # Get file stats
            stat = os.stat(file_path)
            info["size"] = stat.st_size

            # Get extension
            _, ext = os.path.splitext(file_path)
            info["extension"] = ext.lower()

            # Get type info
            file_type = FilePreviewService.get_file_type(file_path)
            info["type"] = file_type
            info["mime_type"] = FilePreviewService.get_mime_type(file_path)
            info["supported"] = FilePreviewService.is_preview_supported(file_path)

            # Get PDF-specific info
            if file_type == "pdf":
                page_count = FilePreviewService.get_pdf_page_count(file_path)
                if page_count:
                    info["page_count"] = page_count

            # Get image dimensions
            if file_type == "image":
                try:
                    from PIL import Image

                    with Image.open(file_path) as img:
                        info["width"] = img.width
                        info["height"] = img.height
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to get file info: {e}")

        return info

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted size string
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"


class DocumentPreviewService:
    """
    Service for handling document previews.
    """

    @staticmethod
    def can_preview(file_extension: str) -> bool:
        """
        Check if document type can be previewed.

        Args:
            file_extension: File extension including dot

        Returns:
            True if preview is supported
        """
        return file_extension.lower() in {
            ".pdf",
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
        }

    @staticmethod
    def get_preview_limitations(file_extension: str) -> str:
        """
        Get limitations info for document preview.

        Args:
            file_extension: File extension

        Returns:
            Limitation message
        """
        limitations = {
            ".doc": "Best viewed in Microsoft Word or converted to PDF",
            ".docx": "Best viewed in Microsoft Word or converted to PDF",
            ".ppt": "Best viewed in Microsoft PowerPoint",
            ".pptx": "Best viewed in Microsoft PowerPoint",
            ".xls": "Best viewed in Microsoft Excel",
            ".xlsx": "Best viewed in Microsoft Excel",
        }

        return limitations.get(
            file_extension.lower(), "Preview not available. Please download the file."
        )


class PreviewResponse:
    """
    Response object for preview requests.
    """

    def __init__(
        self,
        success: bool,
        file_path: str = None,
        preview_url: str = None,
        thumbnail_url: str = None,
        file_info: dict = None,
        error: str = None,
    ):
        self.success = success
        self.file_path = file_path
        self.preview_url = preview_url
        self.thumbnail_url = thumbnail_url
        self.file_info = file_info or {}
        self.error = error

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "file_path": self.file_path,
            "preview_url": self.preview_url,
            "thumbnail_url": self.thumbnail_url,
            "file_info": self.file_info,
            "error": self.error,
        }

    @classmethod
    def from_file(cls, file_path: str) -> "PreviewResponse":
        """
        Create preview response from file path.

        Args:
            file_path: Path to file

        Returns:
            PreviewResponse instance
        """
        if not os.path.exists(file_path):
            return cls(success=False, error="File not found")

        file_type = FilePreviewService.get_file_type(file_path)

        if file_type == "unknown":
            return cls(success=False, error="Preview not supported for this file type")

        file_info = FilePreviewService.get_file_info(file_path)

        # For images, generate preview URLs (in real implementation, these would be media URLs)
        preview_url = None
        thumbnail_url = None

        if file_type == "image":
            name, _ = os.path.splitext(file_path)
            preview_url = f"{name}_preview.jpg"
            thumbnail_url = f"{name}_thumb.jpg"

        return cls(
            success=True,
            file_path=file_path,
            preview_url=preview_url,
            thumbnail_url=thumbnail_url,
            file_info=file_info,
        )
