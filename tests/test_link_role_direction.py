from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterLinkRoleDirectionTest(PdfExporterTestCase):
    """Tests for 'Fit To Page' logic during PDF conversion."""

    def test_direct_link_role_direction(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {"linkedWorkitemRoles": ["relates to"], "linkRoleDirection": "DIRECT"}

        # Act
        response: Response = self._convert(project_id=self.project_id, location_path="Testing/Link Role Direction Test", custom_export_params=custom_export_params)

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_direct_link_role_direction",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_direct_link_role_direction",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_reverse_link_role_direction(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {"linkedWorkitemRoles": ["relates to"], "linkRoleDirection": "REVERSE"}

        # Act
        response: Response = self._convert(project_id=self.project_id, location_path="Testing/Link Role Direction Test", custom_export_params=custom_export_params)

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_reverse_link_role_direction",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_reverse_link_role_direction",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_both_link_role_direction(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {"linkedWorkitemRoles": ["relates to"], "linkRoleDirection": "BOTH"}

        # Act
        response: Response = self._convert(project_id=self.project_id, location_path="Testing/Link Role Direction Test", custom_export_params=custom_export_params)

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_both_link_role_direction",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_both_link_role_direction",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )
