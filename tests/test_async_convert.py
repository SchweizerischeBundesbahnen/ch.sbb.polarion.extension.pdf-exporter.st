import time
from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterAsyncConvertTest(PdfExporterTestCase):
    """Tests for asynchronous PDF conversion functionality."""

    def test_async_convert(self) -> None:
        self.api().polarion_connection.set_print_error(False)
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        export_params: JsonDict = {
            "projectId": self.project_id,
            "locationPath": "Specification/Administration Specification",
        }
        # Act
        response: Response = self.api().start_pdf_conversion_job(export_params)

        # Assert
        self.assertEqual(HTTPStatus.ACCEPTED, response.status_code)

        location: str | None = response.headers.get("Location")
        self.assertIsNotNone(location)
        assert location is not None

        job_id: str = location.rsplit("/", 1)[1]
        self.assertIsNotNone(job_id)

        start: float = time.time()
        # Timeout value for polling (seconds, not HTTP status code)
        max_wait_time: int = 50 + 50
        while time.time() - start < max_wait_time:
            response = self.api().get_pdf_converter_job_status(job_id=job_id)
            if response.status_code == HTTPStatus.ACCEPTED:
                time.sleep(1)
                continue
            break

        self.assertEqual(HTTPStatus.SEE_OTHER, response.status_code)

        # Act
        response = self.api().get_pdf_converter_job_result(job_id=job_id)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_async_convert",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_async_convert",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        self.api().polarion_connection.set_print_error(True)

    def test_async_convert_get_all_pdf_converter_jobs(self) -> None:
        self.api().polarion_connection.set_print_error(False)
        export_params: JsonDict = {
            "projectId": self.project_id,
            "locationPath": "Specification/Administration Specification",
        }
        # Act
        response: Response = self.api().start_pdf_conversion_job(export_params)
        # Assert
        self.assertEqual(HTTPStatus.ACCEPTED, response.status_code)

        # Act
        response = self.api().get_all_pdf_converter_jobs()

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)

        json_data: list[JsonDict] = response.json()
        self.assertTrue(len(json_data) > 0)

        self.api().polarion_connection.set_print_error(True)

    def test_async_convert_get_pdf_converter_job_status_with_wrong_job_id(self) -> None:
        self.api().polarion_connection.set_print_error(False)
        # Act
        response: Response = self.api().get_pdf_converter_job_status(job_id="wrong job id")

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.api().polarion_connection.set_print_error(True)

    def test_async_convert_get_pdf_converter_job_result_with_wrong_job_id(self) -> None:
        self.api().polarion_connection.set_print_error(False)
        # Act
        response: Response = self.api().get_pdf_converter_job_result(job_id="wrong job id")

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.api().polarion_connection.set_print_error(True)
