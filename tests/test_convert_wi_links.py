from __future__ import annotations

import io
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pypdf

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


# The labels of the cross-references of the document: EL-255 refers to EL-253 with its title, EL-256 to EL-251 by its ID
CROSS_REFERENCE_LABELS: frozenset[str] = frozenset({"EL-253 - wi 2", "EL-251"})

# The color of a link in Polarion, #007993, as the PDF sets it: RGB components from 0 to 1, to three decimals
LINK_COLOR: tuple[float, ...] = (0.0, 0.475, 0.576)


class PdfExporterWILinksConvertTest(PdfExporterTestCase):
    """Test cases for converting work item links to internal PDF links."""

    def test_convert_live_doc_draws_cross_references_as_polarion_does(self) -> None:
        """pdf-exporter#1268: a cross-reference is in the color of a link, as in Polarion, not black, with local URLs cut or not."""
        for cut_local_urls in (False, True):
            with self.subTest(cut_local_urls=cut_local_urls):
                response: Response = self._convert(
                    project_id=self.project_id,
                    location_path="Specification/convert_wi_links_to_internal",
                    custom_export_params={"cutLocalUrls": cut_local_urls},
                )

                self.assertEqual(HTTPStatus.OK, response.status_code)
                text_in_link_color: str = self._text_in_color(response.content, LINK_COLOR)
                for label in sorted(CROSS_REFERENCE_LABELS):
                    self.assertIn(label, text_in_link_color, f"The cross-reference '{label}' is in the color of a link")

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
        pdf_reader: pypdf.PdfReader = pypdf.PdfReader(stream)

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
            page: pypdf.PageObject = pdf_reader.pages[page_num]
            page_text: str = page.extract_text()

            if "/Annots" not in page:
                continue

            annotations: Any = page["/Annots"]
            if hasattr(annotations, "get_object"):
                annotations = annotations.get_object()

            for annot_ref in annotations:
                annot: Any = annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref

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

    def _text_in_color(self, pdf: bytes, color: tuple[float, ...]) -> str:
        """The text the PDF draws in a fill color, its pieces joined by a line break."""
        pieces: list[str] = []
        fill: list[tuple[float, ...] | None] = [None]

        def before(operator: bytes, operands: list[Any], _cm: Any, _tm: Any) -> None:
            if operator == b"rg":
                fill[0] = tuple(round(float(operand), 3) for operand in operands)

        def text(piece: str, _cm: Any, _tm: Any, _font: Any, _size: Any) -> None:
            if fill[0] == color:
                pieces.append(piece)

        for page in pypdf.PdfReader(io.BytesIO(pdf)).pages:
            page.extract_text(visitor_operand_before=before, visitor_text=text)
        return "\n".join(pieces)

    def _find_page_with_text(self, pdf_reader: pypdf.PdfReader, search_text: str) -> int | None:
        """Find the first page containing the specified text."""
        for page_num in range(len(pdf_reader.pages)):
            page_text: str = pdf_reader.pages[page_num].extract_text()
            if search_text in page_text:
                return page_num
        return None

    def _get_link_target_page(self, annot: Any, pdf_reader: pypdf.PdfReader) -> int | None:
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

    def _resolve_named_destination(self, dest_name: str, pdf_reader: pypdf.PdfReader) -> int | None:
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
        # Malformed or missing destination data means the link is unresolved.
        except KeyError, AttributeError, TypeError:
            return None

        return None
