from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import fitz
from python_sbb_polarion.extensions.pdf_exporter import PdfVariant

from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.pdf_variant_support import DOCKER_AVAILABLE, stop_verapdf, verify_pdf_with_verapdf
from tests.suites import VERAPDF


if TYPE_CHECKING:
    from requests import Response


class PdfExporterVariantsOfFormulasTest(PdfExporterTestCase):
    """Tests that a document with formulas exports to PDF/A, with the text of its formulas where the variant allows it.

    The source of a formula lies over it as transparent text. PDF/A-1 allows no transparency (ISO 19005-1, 6.4), so a
    PDF/A-1 export leaves the text out, and veraPDF passes both.
    """

    SUITE: ClassVar[str] = VERAPDF

    LOCATION: str = "Testing/formula test"
    SOURCE: str = r"x=\frac{-b\pm\sqrt{\color{Red}{b^2-4ac}}}{2a}"

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop the veraPDF container after all tests."""
        stop_verapdf()
        super().tearDownClass()

    def test_pdf_a_1b_leaves_the_text_of_the_formulas_out(self) -> None:
        text: str = self._export_and_verify(PdfVariant.PDF_A_1B)

        self.assertNotIn(self.SOURCE, text)

    def test_pdf_a_2b_lays_the_text_over_the_formulas(self) -> None:
        text: str = self._export_and_verify(PdfVariant.PDF_A_2B)

        self.assertIn(self.SOURCE, text)

    def _export_and_verify(self, pdf_variant: PdfVariant) -> str:
        """Exports the document in the variant, checks it with veraPDF and returns its text."""
        if not DOCKER_AVAILABLE:
            self.fail("Docker not available - VeraPDF tests require Docker")

        response: Response = self._convert(
            project_id=self.project_id,
            location_path=self.LOCATION,
            custom_export_params={"pdfVariant": str(pdf_variant.value)},
        )
        self.assertEqual(HTTPStatus.OK, response.status_code, f"Failed to export PDF with variant {pdf_variant}")

        is_compliant: bool
        message: str
        is_compliant, message = verify_pdf_with_verapdf(response.content, pdf_variant)
        self.assertTrue(is_compliant, f"PDF variant {pdf_variant} validation failed: {message}")

        with fitz.open(stream=response.content, filetype="pdf") as document:
            return " ".join(" ".join(page.get_text().split()) for page in document)
