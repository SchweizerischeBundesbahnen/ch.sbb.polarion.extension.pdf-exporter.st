from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterOrphanHeaderTest(PdfExporterTestCase):
    """Tests that a table header is not left alone at the bottom of a page."""

    HEADER_CELL = "Diagram"

    # A logo is drawn on every page, so the diagram is told from it by the height it is drawn at.
    DIAGRAM_HEIGHT_PT = 200

    def _draws_the_diagram(self, document: fitz.Document, page: fitz.Page) -> bool:  # type: ignore[no-any-unimported]
        return any(rect.height > self.DIAGRAM_HEIGHT_PT for xref in {image[0] for image in page.get_images(full=True)} for rect in page.get_image_rects(xref))

    def test_convert_live_doc_keeps_a_table_header_with_its_row(self) -> None:
        """The row holds a diagram taller than a page, which fit to page shortens to a page of its own."""
        # A timestamp in the footer would differ on every run, so the pages are rendered without one
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Testing/Orphan Header",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)

        with fitz.open(stream=response.content, filetype="pdf") as document:
            header_pages: list[int] = [page.number for page in document if self.HEADER_CELL in page.get_text()]
            diagram_pages: list[int] = [page.number for page in document if self._draws_the_diagram(document, page)]
            page_numbers: int = document.page_count

        orphans: list[int] = [page for page in header_pages if page not in diagram_pages]
        self.assertEqual([], orphans, f"A header without the row it heads says nothing, and pages {orphans} carry one")

        self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_orphan_header",
            output_folder=self._get_output_folder(),
        )
        self._compare_pdf_pages(
            custom_prefix="test_orphan_header",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )
