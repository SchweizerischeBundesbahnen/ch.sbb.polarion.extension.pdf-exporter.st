from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from python_sbb_polarion.extensions.pdf_exporter import DocumentType, PdfVariant

from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.pdf_variant_support import DOCKER_AVAILABLE, stop_verapdf, verify_pdf_with_verapdf


if TYPE_CHECKING:
    from collections.abc import Callable

    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterVariantsTest(PdfExporterTestCase):
    """Test PDF variants validation using VeraPDF"""

    PRODUCT_SPECIFICATION_LOCATION: str = "Specification/Product Specification"

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop VeraPDF container after all tests."""
        stop_verapdf()
        super().tearDownClass()

    # PDF variants this test covers
    PDF_VARIANTS: ClassVar[list[PdfVariant]] = [
        PdfVariant.PDF_A_1A,
        PdfVariant.PDF_A_1B,
        PdfVariant.PDF_A_2A,
        PdfVariant.PDF_A_2B,
        PdfVariant.PDF_A_2U,
        PdfVariant.PDF_A_3A,
        PdfVariant.PDF_A_3B,
        PdfVariant.PDF_A_3U,
        PdfVariant.PDF_A_4E,
        PdfVariant.PDF_A_4U,
    ]

    # PDF variants this test does not cover, and why
    EXCLUDED_VARIANTS: ClassVar[dict[PdfVariant, str]] = {
        PdfVariant.PDF_A_4F: "covered by test_pdf_a_4f_variant()",
        PdfVariant.PDF_UA_1: "a cover page loses the headers of its table cells, so a TH needs a Scope (PDF/UA-1, 7.5), pdf-exporter#1170",
        PdfVariant.PDF_UA_2: "a link pseudo element makes a Link inside a Link (ISO 32005, Table 5), pdf-exporter#1171",
    }

    def _run_pdf_variant(self, pdf_variant: PdfVariant, cover_page: str | None) -> None:
        """Test PDF variant compliance using VeraPDF validation"""
        # Fail if Docker is not available
        if not DOCKER_AVAILABLE:
            self.fail("Docker not available - VeraPDF tests require Docker")

        # Arrange
        export_params: JsonDict = {
            "pdfVariant": str(pdf_variant.value),
        }
        if cover_page:
            export_params["coverPage"] = cover_page

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path=self.PRODUCT_SPECIFICATION_LOCATION,
            custom_export_params=export_params,
        )

        # Assert HTTP response
        cover_info: str = "with cover page" if cover_page else "without cover page"
        self.assertEqual(
            HTTPStatus.OK,
            response.status_code,
            f"Failed to export PDF with variant {pdf_variant} {cover_info}",
        )
        self.assertIsNotNone(response.content)
        self.assertGreater(len(response.content), 0, "PDF content is empty")

        # Verify PDF compliance with VeraPDF
        is_compliant: bool
        message: str
        is_compliant, message = verify_pdf_with_verapdf(response.content, pdf_variant)
        self.assertTrue(
            is_compliant,
            f"PDF variant {pdf_variant} {cover_info} validation failed: {message}",
        )

    def test_pdf_a_4f_variant(self) -> None:
        """Test pdf/a-4f variant compliance using VeraPDF validation. Special handling as there should be embeddings into PDF"""
        # Arrange
        pdf_variant: PdfVariant = PdfVariant.PDF_A_4F

        export_params: JsonDict = {"projectId": self.project_id, "documentType": DocumentType.TEST_RUN, "pdfVariant": str(pdf_variant.value), "embedAttachments": True, "urlQueryParameters": {"id": "Test"}}

        # Act
        response: Response = self.api().convert(export_params=export_params)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)
        self.assertGreater(len(response.content), 0, "PDF content is empty")

        is_compliant: bool
        message: str
        is_compliant, message = verify_pdf_with_verapdf(response.content, pdf_variant)
        self.assertTrue(
            is_compliant,
            f"PDF variant {pdf_variant} validation failed: {message}",
        )


_variant_test_params = [(variant, None) for variant in PdfExporterVariantsTest.PDF_VARIANTS] + [(variant, "Default") for variant in PdfExporterVariantsTest.PDF_VARIANTS]

for _idx, (_pdf_variant, _cover_page) in enumerate(_variant_test_params):
    _test_name = f"test_pdf_variant_{_idx:02d}_{_pdf_variant.name}"

    def _make_test(_pv: PdfVariant = _pdf_variant, _cp: str | None = _cover_page) -> Callable[..., None]:
        def test_method(self: PdfExporterVariantsTest) -> None:
            self._run_pdf_variant(_pv, _cp)

        test_method.__doc__ = f"Test PDF variant compliance using VeraPDF validation [with pdf_variant={_pv!r}, cover_page={_cp!r}]"
        return test_method

    setattr(PdfExporterVariantsTest, _test_name, _make_test())
