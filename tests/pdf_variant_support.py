"""Validation of a PDF against the variant it was exported in, with veraPDF.

Shared by the variant tests of a single export and of a merge. Every module named ``test_pdf_variants*``
belongs to the group of PDF variant tests, which ``run.py`` runs only where ``RUN_PDF_VARIANT_TESTS`` is
set: they validate dozens of exports and take long, so a local run leaves them out and CI runs them.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from python_sbb_polarion.extensions.pdf_exporter import PdfVariant

from tests.verapdf_manager import VeraPDFManager


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict


# The prefix of the modules of the group, and the variable which runs it
GROUP_MODULE_PREFIX: str = "test_pdf_variants"
GROUP_VARIABLE: str = "RUN_PDF_VARIANT_TESTS"

# Module-level VeraPDF manager
_verapdf_manager = VeraPDFManager()

# Check if Docker is available for testcontainers
DOCKER_AVAILABLE: bool = VeraPDFManager.is_docker_available()

# Map PDF variant to VeraPDF flavour codes
VARIANT_FLAVOUR_MAP: dict[PdfVariant, str] = {
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


def group_requested() -> bool:
    """Whether this run asked for the group of PDF variant tests."""
    return os.environ.get(GROUP_VARIABLE, "").strip().lower() in {"1", "true", "yes"}


def stop_verapdf() -> None:
    """Stop the VeraPDF container; the next validation starts it again."""
    _verapdf_manager.stop_container()


def parse_verapdf_response(verapdf_result: JsonDict) -> tuple[bool, str]:
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


def verify_pdf_with_verapdf(pdf_content: bytes, expected_variant: PdfVariant) -> tuple[bool, str]:
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
        flavour: str = VARIANT_FLAVOUR_MAP[expected_variant]
        success: bool
        verapdf_result: JsonDict | None
        error_msg: str
        success, verapdf_result, error_msg = _verapdf_manager.validate_pdf(tmp_pdf_path, flavour)

        if not success:
            return False, f"VeraPDF validation failed: {error_msg}"

        if verapdf_result is None:
            return False, "VeraPDF returned empty response"

        return parse_verapdf_response(verapdf_result)

    # The validator reports failures as a result, it never raises at the caller.
    except Exception as e:  # noqa: BLE001
        return False, f"Unexpected error during VeraPDF validation: {e}"
    finally:
        # Clean up temporary file
        tmp_pdf_path.unlink(missing_ok=True)
