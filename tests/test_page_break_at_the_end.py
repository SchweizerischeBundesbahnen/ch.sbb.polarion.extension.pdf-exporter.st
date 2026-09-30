from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterPageBreakAtTheEndTest(PdfExporterTestCase):
    """Tests that a page break the document ends with leaves no page behind."""

    def test_convert_live_doc_leaves_no_page_after_a_break_it_ends_with(self) -> None:
        """The editor sets the orientation of the page above a break, so a landscape document carries one at its end."""
        # A timestamp in the footer would differ on every run, so the pages are rendered without one
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="PageBreaks/Br LA at the end",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)

        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_page_break_at_the_end",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers, "The break the document ends with has nothing to put on a page of its own")
        self._compare_pdf_pages(
            custom_prefix="test_page_break_at_the_end",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )
