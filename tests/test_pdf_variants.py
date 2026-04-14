from __future__ import annotations

import tempfile
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from python_sbb_polarion.extensions.pdf_exporter import DocumentType, PdfVariant

from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.verapdf_manager import VeraPDFManager


if TYPE_CHECKING:
    from collections.abc import Callable

    from python_sbb_polarion.types import JsonDict
    from requests import Response


# Module-level VeraPDF manager
_verapdf_manager = VeraPDFManager()

# Check if Docker is available for testcontainers
DOCKER_AVAILABLE = VeraPDFManager.is_docker_available()


class PdfExporterVariantsTest(PdfExporterTestCase):
    """Test PDF variants validation using VeraPDF"""

    PRODUCT_SPECIFICATION_LOCATION: str = "Specification/Product Specification"

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop VeraPDF container after all tests."""
        _verapdf_manager.stop_container()
        super().tearDownClass()

    # Supported PDF variants
    PDF_VARIANTS: ClassVar[list[PdfVariant]] = [
        PdfVariant.PDF_A_1A,
        PdfVariant.PDF_A_1B,
        # PdfVariant.PDF_A_2A,  # TODO: FontAwesome uses Unicode PUA characters without ActualText entries (ISO 32000-1:2008, 14.9.4)
        PdfVariant.PDF_A_2B,
        PdfVariant.PDF_A_2U,
        # PdfVariant.PDF_A_3A,  # TODO: FontAwesome uses Unicode PUA characters without ActualText entries (ISO 32000-1:2008, 14.9.4)
        PdfVariant.PDF_A_3B,
        PdfVariant.PDF_A_3U,
        PdfVariant.PDF_A_4E,
        # PdfVariant.PDF_A_4F,  # Tested in separate test case, see test_pdf_a_4f_variant() method
        PdfVariant.PDF_A_4U,
        # PdfVariant.PDF_UA_1,  # TODO: Requires alt text for images and correct list structure
        # PdfVariant.PDF_UA_2,  # TODO: Requires alt text for images and correct list structure
    ]

    # Map PDF variant to VeraPDF flavour codes
    VARIANT_FLAVOUR_MAP: ClassVar[dict[PdfVariant, str]] = {
        PdfVariant.PDF_A_1A: "1a",
        PdfVariant.PDF_A_1B: "1b",
        PdfVariant.PDF_A_2A: "2a",
        PdfVariant.PDF_A_2B: "2b",
        PdfVariant.PDF_A_2U: "2u",
        PdfVariant.PDF_A_3A: "3a",
        PdfVariant.PDF_A_3B: "3b",
        PdfVariant.PDF_A_3U: "3u",
        PdfVariant.PDF_A_4E: "4e",
        PdfVariant.PDF_A_4F: "4f",
        PdfVariant.PDF_A_4U: "4",
        PdfVariant.PDF_UA_1: "ua1",
        PdfVariant.PDF_UA_2: "ua2",
    }

    def _parse_verapdf_response(self, verapdf_result: JsonDict) -> tuple[bool, str]:
        """Parse VeraPDF REST API JSON response and extract validation result."""
        # Cast to Any for easier nested dict access without excessive type checks
        result: Any = verapdf_result
        report: Any = result.get("report", {})
        jobs: list[Any] = report.get("jobs", [])

        if not jobs:
            return False, "No validation jobs found in VeraPDF output"

        job: Any = jobs[0]
        # REST API returns validationResult as a LIST, not a single object
        validation_results: list[Any] = job.get("validationResult", [])

        if not validation_results:
            return False, "No validation result found in VeraPDF output"

        # Get first validation result from the list
        validation_result: Any = validation_results[0]

        is_compliant: bool = validation_result.get("compliant", False)
        profile_name: str = validation_result.get("profileName", "Unknown")

        if is_compliant:
            return True, f"PDF is compliant with {profile_name}"

        # Extract validation errors from ruleSummaries
        errors: list[str] = []
        details: Any = validation_result.get("details", {})
        rule_summaries: list[Any] = details.get("ruleSummaries", [])

        for rule_summary in rule_summaries:
            rule_id: Any = rule_summary.get("ruleId", {})
            specification: str = rule_id.get("specification", "Unknown")
            clause: str = rule_id.get("clause", "Unknown")
            description: str = rule_summary.get("description", "No description")
            failed_checks: int = rule_summary.get("checks", 0)
            errors.append(f"{specification} {clause}: {description} ({failed_checks} failed checks)")

        # Show first 5 errors
        error_msg: str = f"PDF is not compliant with {profile_name}. Errors:\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            error_msg += f"\n... and {len(errors) - 5} more errors"
        return False, error_msg

    def _verify_pdf_with_verapdf(self, pdf_content: bytes, expected_variant: PdfVariant) -> tuple[bool, str]:
        """
        Verify PDF compliance using VeraPDF REST API.

        Args:
            pdf_content: PDF file content as bytes
            expected_variant: Expected PDF variant (e.g., PdfVariant.PDF_A_1B)

        Returns:
            Tuple of (is_compliant, message)
        """
        # Create temporary file for PDF with automatic cleanup
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_pdf_path = Path(tmp_file.name)

        try:
            # Run VeraPDF validation using REST API
            flavour: str = self.VARIANT_FLAVOUR_MAP[expected_variant]
            success: bool
            verapdf_result: JsonDict | None
            error_msg: str
            success, verapdf_result, error_msg = _verapdf_manager.validate_pdf(tmp_pdf_path, flavour)

            if not success:
                return False, f"VeraPDF validation failed: {error_msg}"

            if verapdf_result is None:
                return False, "VeraPDF returned empty response"

            return self._parse_verapdf_response(verapdf_result)

        except Exception as e:
            return False, f"Unexpected error during VeraPDF validation: {e}"
        finally:
            # Clean up temporary file
            tmp_pdf_path.unlink(missing_ok=True)

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
        is_compliant, message = self._verify_pdf_with_verapdf(response.content, pdf_variant)
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
        is_compliant, message = self._verify_pdf_with_verapdf(response.content, pdf_variant)
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
