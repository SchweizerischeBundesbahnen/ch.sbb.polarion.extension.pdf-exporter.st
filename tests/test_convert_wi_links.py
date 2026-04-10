from __future__ import annotations

import io
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import PyPDF2

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterWILinksConvertTest(PdfExporterTestCase):
    """Test cases for converting work item links to internal PDF links."""

    def test_convert_live_doc_with_wi_links_to_internal(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(project_id=self.project_id, location_path="Specification/convert_wi_links_to_internal")

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        stream: io.BytesIO = io.BytesIO(response.content)
        pdf_reader: PyPDF2.PdfReader = PyPDF2.PdfReader(stream)

        # Find target pages
        el_251_page: int | None = self._find_page_with_text(pdf_reader, "EL-251")
        el_253_page: int | None = self._find_page_with_text(pdf_reader, "EL-253")

        self.assertIsNotNone(el_251_page, "Could not find EL-251 in the PDF")
        self.assertIsNotNone(el_253_page, "Could not find EL-253 in the PDF")

        # Track verified links
        el_255_to_253_verified: bool = False
        el_256_to_251_verified: bool = False

        # Check all internal links in the PDF
        for page_num in range(len(pdf_reader.pages)):
            page: PyPDF2.PageObject = pdf_reader.pages[page_num]
            page_text: str = page.extract_text()

            if "/Annots" not in page:
                continue

            annotations: Any = page["/Annots"]
            if hasattr(annotations, "get_object"):
                annotations = annotations.get_object()

            for annot in annotations:
                if hasattr(annot, "get_object"):
                    annot = annot.get_object()

                if annot.get("/Subtype") != "/Link":
                    continue

                target_page: int | None = self._get_link_target_page(annot, pdf_reader)

                if target_page is None:
                    continue

                # Verify specific link relationships
                if "EL-256" in page_text and target_page == el_251_page:
                    el_256_to_251_verified = True

                if "EL-255" in page_text and target_page == el_253_page:
                    el_255_to_253_verified = True

        # Verify all required links were found
        self.assertTrue(el_256_to_251_verified, "EL-256 link to EL-251 was not found or verified")
        self.assertTrue(el_255_to_253_verified, "EL-255 link to EL-253 was not found or verified")

    def _find_page_with_text(self, pdf_reader: PyPDF2.PdfReader, search_text: str) -> int | None:
        """Find the first page containing the specified text."""
        for page_num in range(len(pdf_reader.pages)):
            page_text: str = pdf_reader.pages[page_num].extract_text()
            if search_text in page_text:
                return page_num
        return None

    def _get_link_target_page(self, annot: Any, pdf_reader: PyPDF2.PdfReader) -> int | None:
        """Extract the target page number from a link annotation."""
        # Check for /Dest
        if "/Dest" in annot:
            dest: Any = annot["/Dest"]

            # If dest is a string, it's a named destination - look it up
            if isinstance(dest, str):
                return self._resolve_named_destination(dest, pdf_reader)

            # Otherwise it's a direct destination array
            if isinstance(dest, list) and len(dest) > 0:
                target_page_ref: Any = dest[0]
                for idx, pdf_page in enumerate(pdf_reader.pages):
                    if hasattr(pdf_page, "indirect_reference") and pdf_page.indirect_reference == target_page_ref:
                        return idx

        # Check for /A (action)
        if "/A" in annot:
            action: Any = annot["/A"]
            if hasattr(action, "get_object"):
                action = action.get_object()

            if action.get("/S") == "/GoTo" and "/D" in action:
                dest_action: Any = action["/D"]

                if isinstance(dest_action, str):
                    return self._resolve_named_destination(dest_action, pdf_reader)

        return None

    def _resolve_named_destination(self, dest_name: str, pdf_reader: PyPDF2.PdfReader) -> int | None:
        """Resolve a named destination to a page number."""
        try:
            # Check named_destinations attribute
            if hasattr(pdf_reader, "named_destinations") and dest_name in pdf_reader.named_destinations:
                dest: Any = pdf_reader.named_destinations[dest_name]

                # Named destinations use /Page key pointing to the page object
                if isinstance(dest, dict) and "/Page" in dest:
                    target_page_ref: Any = dest["/Page"]

                    # Find which page number this IndirectObject refers to
                    for idx, pdf_page in enumerate(pdf_reader.pages):
                        # Compare indirect references
                        if hasattr(pdf_page, "indirect_reference") and pdf_page.indirect_reference == target_page_ref:
                            return idx
                        # Try direct comparison
                        if hasattr(target_page_ref, "get_object") and pdf_page == target_page_ref.get_object():
                            return idx
        except (KeyError, AttributeError, TypeError):
            pass

        return None
