from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from requests import Response


class PdfExporterImageSizeTest(PdfExporterTestCase):
    """Tests that an image keeps the size the document gives it."""

    # A CSS pixel is 0.75 pt, the unit a PDF is laid out in.
    PT_PER_PX = 0.75

    def test_convert_live_doc_keeps_the_size_the_document_gives_a_diagram(self) -> None:
        """A Polarion diagram is an SVG, and its size used to be replaced by the size of that SVG."""
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Testing/Diagram Sizes",
        )

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)

        # Every image carries its own raster, so they are read in the order the page draws them
        drawn: list[tuple[float, float, int]] = []
        with fitz.open(stream=response.content, filetype="pdf") as document:
            for page in document:
                for xref in {image[0] for image in page.get_images(full=True)}:
                    drawn.extend((rect.y0, rect.x0, round(rect.width / self.PT_PER_PX)) for rect in page.get_image_rects(xref))

        # The diagram is 200x100 px: its own size where the document gives none, then half of it and twice it
        self.assertEqual([200, 100, 400], [width for _, _, width in sorted(drawn)])
