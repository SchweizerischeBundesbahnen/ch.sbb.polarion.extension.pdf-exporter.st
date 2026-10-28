from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from requests import Response


class PdfExporterFormulaTextTest(PdfExporterTestCase):
    """Tests that the LaTeX source of each formula lies over it in the PDF, so a reader can find, select and copy it.

    Polarion draws a formula as an SVG whose glyphs are paths. The exporter lays its source over it as invisible text, as an
    OCR layer lies over a scanned page, so the page looks as before: test_convert_live_doc_with_formula compares it.
    """

    LOCATION: str = "Testing/formula test"

    # The sources of the formulas of the document, in one line, as the exporter writes them
    SOURCES: ClassVar[list[str]] = [
        r"x=\frac{-b\pm\sqrt{\color{Red}{b^2-4ac}}}{2a}",
        (
            r"A = \pmatrix{ a_{11} & a_{12} & \ldots & a_{1n} \cr a_{21} & a_{22} & \ldots & a_{2n} \cr"
            r" \vdots & \vdots & \ddots & \vdots \cr a_{m1} & a_{m2} & \ldots & a_{mn} \cr }"
        ),
        "A = é à è",
    ]

    def test_convert_live_doc_lays_the_source_of_each_formula_over_it(self) -> None:
        response: Response = self._convert(project_id=self.project_id, location_path=self.LOCATION)
        self.assertEqual(HTTPStatus.OK, response.status_code)

        with fitz.open(stream=response.content, filetype="pdf") as document:
            text: str = " ".join(" ".join(page.get_text().split()) for page in document)
        for source in self.SOURCES:
            self.assertIn(source, text)
