from http import HTTPStatus
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


from tests.pdf_exporter_test_case import PdfExporterTestCase


class PdfExporterUtilityTest(PdfExporterTestCase):
    """Tests for utility endpoints."""

    def test_get_webhooks_status(self) -> None:
        # Act
        response: Response = self.api().get_webhooks_status()

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        response_json: JsonDict = response.json()
        self.assertIsNotNone(response_json)
        self.assertIsInstance(response_json["enabled"], bool)

    def test_get_project_name(self) -> None:
        # Act
        response: Response = self.api().get_project_name(project_id=self.project_id)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertEqual("E-Library", response.text)

    def test_get_document_language(self) -> None:
        # Act
        response: Response = self.api().get_document_language(
            project_id=self.project_id,
            space_id="Specification",
            document_name="Administration Specification",
        )

        # Assert
        self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

    def test_get_link_role_names(self) -> None:
        # Act
        response: Response = self.api().get_link_role_names(scope=f"project/{self.project_id}/")

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        response_json: list[str] = response.json()
        self.assertIsNotNone(response_json)
        for json_entry in response_json:
            self.assertIsInstance(json_entry, str)
