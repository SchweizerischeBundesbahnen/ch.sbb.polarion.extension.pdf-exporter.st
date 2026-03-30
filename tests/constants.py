"""Constants and enums for PDF Exporter tests."""

from enum import StrEnum


class PdfExporterFeature(StrEnum):
    """PDF Exporter feature names for settings management."""

    COVER_PAGE = "cover-page"
    CSS = "css"
    FILENAME_TEMPLATE = "filename-template"
    HEADER_FOOTER = "header-footer"
    LOCALIZATION = "localization"
    STYLE_PACKAGE = "style-package"
    WEBHOOKS = "webhooks"


# PDF rendering settings
PDF_RENDER_DPI: int = 300  # Higher DPI for accurate visual comparison
EXPORT_TIMEOUT_SECONDS: int = 100  # Timeout for PDF export jobs
POLL_INTERVAL_SECONDS: float = 1.0  # Polling interval for async jobs

# Image comparison settings
COMPARISON_THRESHOLD: float = 0.95  # Similarity threshold for image comparison

# Features that need to be reinitialized in setUp
SUPPORTED_FEATURES: list[str] = [
    PdfExporterFeature.COVER_PAGE,
    PdfExporterFeature.CSS,
    PdfExporterFeature.FILENAME_TEMPLATE,
    PdfExporterFeature.HEADER_FOOTER,
    PdfExporterFeature.LOCALIZATION,
    PdfExporterFeature.STYLE_PACKAGE,
]
