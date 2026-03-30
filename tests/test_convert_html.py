from http import HTTPStatus
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from requests import Response


from tests.pdf_exporter_test_case import PdfExporterTestCase


class PdfExporterConvertHtmlTest(PdfExporterTestCase):
    """Tests for HTML to PDF conversion."""

    def test_convert_html(self) -> None:
        # Arrange
        html: str = self._load_test_data(filename="test-specification.html")

        # Act
        response: Response = self._convert_html(self.api(), html=html)

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_html",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(4, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_html",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_with_fit_to_page(self) -> None:
        output_image: str = "test.png"

        # Arrange
        html: str = self._load_test_data(filename="test-fit-to-page.html")
        response: Response = self._convert_html(self.api(), html, filename="fitToPage.pdf", fit_to_page=True)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)
        self.convert_pdf_to_png_first_page(response.content, output_image)

        self.assertTrue(self._is_rightmost_column_white(output_image))

    def test_convert_without_fit_to_page(self) -> None:
        output_image: str = "test.png"

        # Arrange
        html: str = self._load_test_data(filename="test-fit-to-page.html")
        response: Response = self._convert_html(self.api(), html, filename="fitToPage.pdf", fit_to_page=False)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        self.convert_pdf_to_png_first_page(response.content, output_image)

        self.assertFalse(self._is_rightmost_column_white(output_image))

    def test_convert_malformed_html(self) -> None:
        # Act
        response: Response = self._convert_html(self.api(), html="something wrong", print_error=False)

        # Assert
        self.assertEqual(HTTPStatus.BAD_REQUEST, response.status_code)
        self.assertIn("Input html is malformed, expected html and body tags", response.text)
