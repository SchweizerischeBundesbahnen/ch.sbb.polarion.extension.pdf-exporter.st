from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.drawn_pictures import drawn_pictures
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

        # A diagram is a raster with Chromium and a vector form with weasysvg, so they are read where the page draws them
        drawn: list[tuple[int, float, float, int]] = [(picture.page, picture.y0, picture.x0, round(picture.width / self.PT_PER_PX)) for picture in drawn_pictures(response.content)]

        # The diagram is 200x100 px: its own size where the document gives none, then half of it and twice it
        self.assertEqual([200, 100, 400], [width for _, _, _, width in sorted(drawn)])
