from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from requests import Response


class PdfExporterVisioTest(PdfExporterTestCase):
    """Tests that a Visio drawing attached to a document arrives in the PDF as a drawing.

    weasyprint-service draws VSDX and VSD through weasyvsdx and libvisio as vector, so the text of a drawing is text in
    the PDF. A drawing the service cannot draw is left out, and with it its text. The drawings are test data of Apache
    POI, Apache License 2.0.
    """

    def test_convert_live_doc_draws_a_vsdx_drawing_as_vector(self) -> None:
        text: str = self._text_of_the_document()

        # A container with a header, two lines of text and a star
        self.assertIn("This is a test.", text)
        self.assertIn("Nothing fancy.", text)

    def test_convert_live_doc_draws_a_vsd_drawing_as_vector(self) -> None:
        """The exporter takes a VSD attachment instead of its thumbnail since vsd is a renderable image extension."""
        text: str = self._text_of_the_document()

        # A box with a title and a line of text, and a line of text on the page
        self.assertIn("I am a test view", text)
        self.assertIn("Some random text, on a page", text)

    def _text_of_the_document(self) -> str:
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Testing/Visio Drawings",
        )
        self.assertEqual(HTTPStatus.OK, response.status_code)
        with fitz.open(stream=response.content, filetype="pdf") as document:
            return " ".join(" ".join(page.get_text().split()) for page in document)
