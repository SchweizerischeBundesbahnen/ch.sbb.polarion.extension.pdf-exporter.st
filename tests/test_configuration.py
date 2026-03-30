from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterConfigurationTest(PdfExporterTestCase):
    """Tests for PDF exporter configuration endpoints."""

    def test_check_default_settings(self) -> None:
        response: Response = self.api().check_default_settings()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        json_settings: JsonDict = response.json()
        self.assertIn("name", json_settings)
        self.assertEqual("Default Settings", json_settings["name"])

    def test_check_document_properties_pane_config(self) -> None:
        response: Response = self.api().check_document_properties_pane_config()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        json_settings: JsonDict = response.json()
        self.assertIn("name", json_settings)
        self.assertEqual("Document Properties Pane", json_settings["name"])

    def test_check_dle_toolbar_config(self) -> None:
        response: Response = self.api().check_dle_toolbar_config()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        json_settings: JsonDict = response.json()
        self.assertIn("name", json_settings)
        self.assertEqual("DLE Toolbar", json_settings["name"])

    def test_check_live_report_config(self) -> None:
        response: Response = self.api().check_live_report_config()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        json_settings: JsonDict = response.json()
        self.assertIn("name", json_settings)
        self.assertEqual("LiveReport Button", json_settings["name"])

    def test_check_cors_config(self) -> None:
        response: Response = self.api().check_cors_config()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        json_settings: JsonDict = response.json()
        self.assertIn("name", json_settings)
        self.assertEqual("CORS (Cross-Origin Resource Sharing)", json_settings["name"])

    def test_check_weasyprint(self) -> None:
        response: Response = self.api().check_weasyprint()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        json_settings: list[JsonDict] = response.json()
        self.assertIn("name", json_settings[0])
        self.assertEqual("WeasyPrint Service", json_settings[0]["name"])
