from tests.pdf_exporter_test_case import PdfExporterTestCase


class PdfExporterContextTest(PdfExporterTestCase):
    """Tests for context endpoint."""

    def test_context_get(self) -> None:
        self.run_test_get_context()
