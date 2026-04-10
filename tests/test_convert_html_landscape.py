from http import HTTPStatus
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from requests import Response


from python_sbb_polarion.extensions.pdf_exporter import Orientation, PaperSize

from tests.pdf_exporter_test_case import PdfExporterTestCase


class PdfExporterConvertHtmlLandscapeTest(PdfExporterTestCase):
    """Tests for HTML to PDF conversion in landscape orientation."""

    def test_convert_html_landscape_A3(self) -> None:
        # Arrange
        html: str = self._load_test_data(filename="test-specification.html")

        # Act
        response: Response = self._convert_html(self.api(), html=html, orientation=Orientation.LANDSCAPE, paper_size=PaperSize.A3)

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_html_landscape_A3",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(3, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_html_landscape_A3",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_with_fit_to_page(self) -> None:
        # Arrange
        html: str = self._load_test_data(filename="test-fit-to-page.html")
        response: Response = self._convert_html(
            self.api(),
            html,
            orientation=Orientation.LANDSCAPE,
            filename="fitToPage.pdf",
            fit_to_page=True,
        )

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)
        self.convert_pdf_to_png_first_page(response.content, "test.png")

        self.assertTrue(self._is_rightmost_column_white("test.png"))

    def test_convert_without_fit_to_page(self) -> None:
        # Arrange
        html: str = self._load_test_data(filename="test-fit-to-page.html")
        response: Response = self._convert_html(
            self.api(),
            html,
            filename="fitToPage.pdf",
            orientation=Orientation.LANDSCAPE,
            fit_to_page=False,
        )

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        self.convert_pdf_to_png_first_page(response.content, "test.png")

        self.assertFalse(self._is_rightmost_column_white("test.png"))
