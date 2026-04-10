from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict


class PdfExporterVersionTest(PdfExporterTestCase):
    """Tests for version endpoint."""

    def test_version_get(self) -> None:
        response: JsonDict = self.run_test_get_version()
        self.assertEqual("PDF Exporter Extension for Polarion ALM", response["bundleName"])

    def test_version_get_with_invalid_token(self) -> None:
        self.run_test_get_version_with_invalid_token()
