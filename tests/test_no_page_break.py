from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterNoPageBreakTest(PdfExporterTestCase):
    """Tests the No Page Break a work item presentation asks for.

    Both documents hold the same requirement after as much text as it takes for the end of the first page to fall
    inside it. Only one of them asks for No Page Break in the presentation of its requirements.
    """

    # The first and the last line of the requirement
    FIRST_LINE: str = "L1L"
    LAST_LINE: str = "L12L"

    def setUp(self) -> None:
        super().setUp()
        # The time of the export and the revision would differ on every run
        self.previous_header_footer: JsonDict
        self.previous_header_footer, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

    def tearDown(self) -> None:
        self._save_header_footer_settings(self.previous_header_footer)
        super().tearDown()

    def test_convert_keeps_a_work_item_with_no_page_break_on_one_page(self) -> None:
        response: Response = self._convert(project_id=self.project_id, location_path="Testing/No Page Break")

        self.assertEqual(HTTPStatus.OK, response.status_code)
        pages: list[str] = self._page_texts(response.content)
        self.assertEqual(2, len(pages))
        self.assertEqual(1, self._page_of(pages, self.FIRST_LINE), "The requirement moves whole to the second page")
        self.assertEqual(1, self._page_of(pages, self.LAST_LINE), "The requirement ends on the page it starts on")

        page_numbers: int = self._pdf_to_png(pdf_bytes=response.content, custom_prefix="test_no_page_break", output_folder=self._get_output_folder())
        self._compare_pdf_pages(
            custom_prefix="test_no_page_break",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_breaks_a_work_item_without_no_page_break_where_the_page_ends(self) -> None:
        response: Response = self._convert(project_id=self.project_id, location_path="Testing/No Page Break Off")

        self.assertEqual(HTTPStatus.OK, response.status_code)
        pages: list[str] = self._page_texts(response.content)
        self.assertEqual(0, self._page_of(pages, self.FIRST_LINE), "The requirement starts on the first page")
        self.assertEqual(1, self._page_of(pages, self.LAST_LINE), "The requirement ends on the second page")

    @staticmethod
    def _page_of(pages: list[str], text: str) -> int:
        return next((index for index, page in enumerate(pages) if text in page), -1)

    def _page_texts(self, pdf_bytes: bytes) -> list[str]:
        pdf_document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            return [page.get_text() for page in pdf_document]
        finally:
            pdf_document.close()
