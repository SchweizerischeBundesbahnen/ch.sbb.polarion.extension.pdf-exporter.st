from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterCommentFromDeletedUserTest(PdfExporterTestCase):
    """Tests converting LiveDoc with comment inserted by user who was later deleted. Conversion shouldn't fail"""

    def test_comment_from_deleted_user(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(project_id=self.project_id, location_path="Testing/Comment from deleted user test")

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)
