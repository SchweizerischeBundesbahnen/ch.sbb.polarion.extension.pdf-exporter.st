"""The PDF variants of a merge through the bulk processing service, validated with veraPDF.

A merge does not return what WeasyPrint wrote: the service combines the documents and their cover pages
into one file, and a variant holds only if the combined file keeps what each document carried for it,
the catalog and, for a tagged variant, the structure. So each variant a single export is validated in
is validated here after a merge too, without and with a cover page.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from python_sbb_polarion.extensions.pdf_exporter import DocumentType, PdfVariant

from tests.bulk_processing_support import merge_through_extension
from tests.bulk_processing_test_case import BulkProcessingTestCase
from tests.pdf_variant_support import DOCKER_AVAILABLE, stop_verapdf, verify_pdf_with_verapdf


if TYPE_CHECKING:
    from collections.abc import Callable

    from python_sbb_polarion.types import JsonDict, JsonList

    from tests.bulk_processing_support import MergeJobOutcome


# Two live documents of the elibrary, both with the icons of Font Awesome Polarion puts before a plan
MERGED_DOCUMENTS: list[str] = [
    "Specification/Product Specification",
    "Specification/Catalog Specification",
]
# A merge job renders every document through WeasyPrint before combining them
MERGE_JOB_TIMEOUT_IN_SEC: int = 100


class PdfExporterMergeVariantsTest(BulkProcessingTestCase):
    """Each PDF variant of a merge of two documents validated with veraPDF."""

    # PDF variants this test covers, those of a single export
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
        PdfVariant.PDF_A_4F: "requires embedded files, which a merge does not carry (pdf-exporter#1166)",
        PdfVariant.PDF_UA_1: "a cover page loses the headers of its table cells, so a TH needs a Scope (PDF/UA-1, 7.5), pdf-exporter#1170",
        PdfVariant.PDF_UA_2: "a link pseudo element makes a Link inside a Link (ISO 32005, Table 5), pdf-exporter#1171",
    }

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop VeraPDF container after all tests."""
        stop_verapdf()
        super().tearDownClass()

    def _run_pdf_variant(self, pdf_variant: PdfVariant, cover_page: str | None) -> None:
        """Merge the documents in a PDF variant and validate the merged PDF with VeraPDF."""
        if not DOCKER_AVAILABLE:
            self.fail("Docker not available - VeraPDF tests require Docker")
        self._require_ready()

        # Arrange
        merge_params: JsonList = []
        for location_path in MERGED_DOCUMENTS:
            params: JsonDict = {
                "projectId": self.project_id,
                "locationPath": location_path,
                "documentType": DocumentType.LIVE_DOC,
                "pdfVariant": str(pdf_variant.value),
            }
            if cover_page:
                params["coverPage"] = cover_page
            merge_params.append(params)

        # Act
        with self.suppress_api_errors():
            outcome: MergeJobOutcome = merge_through_extension(self.api(), merge_params, MERGE_JOB_TIMEOUT_IN_SEC)

        # Assert
        cover_info: str = "with cover pages" if cover_page else "without cover pages"
        self.assertEqual(HTTPStatus.OK, outcome.status, f"The merge in {pdf_variant} {cover_info} failed: {outcome.error_message}")
        assert outcome.pdf is not None  # an OK outcome carries the pdf

        is_compliant: bool
        message: str
        is_compliant, message = verify_pdf_with_verapdf(outcome.pdf, pdf_variant)
        self.assertTrue(is_compliant, f"The merge in {pdf_variant} {cover_info} validation failed: {message}")


_variant_test_params = [(variant, None) for variant in PdfExporterMergeVariantsTest.PDF_VARIANTS] + [(variant, "Default") for variant in PdfExporterMergeVariantsTest.PDF_VARIANTS]

for _idx, (_pdf_variant, _cover_page) in enumerate(_variant_test_params):
    _test_name = f"test_merge_pdf_variant_{_idx:02d}_{_pdf_variant.name}"

    def _make_test(_pv: PdfVariant = _pdf_variant, _cp: str | None = _cover_page) -> Callable[..., None]:
        def test_method(self: PdfExporterMergeVariantsTest) -> None:
            self._run_pdf_variant(_pv, _cp)

        test_method.__doc__ = f"Merge compliance with the PDF variant, validated with VeraPDF [with pdf_variant={_pv!r}, cover_page={_cp!r}]"
        return test_method

    setattr(PdfExporterMergeVariantsTest, _test_name, _make_test())
