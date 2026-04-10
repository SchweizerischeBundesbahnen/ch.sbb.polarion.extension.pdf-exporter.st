from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import fitz
from parameterized import parameterized
from python_sbb_polarion.extensions.pdf_exporter import Orientation

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterPageBreaksTest(PdfExporterTestCase):
    """Tests for PDF page breaks functionality."""

    PAGE_BREAKS_TEST_DATA: ClassVar[list[tuple[str, list[bool], JsonDict | None]]] = [
        ("PageBreaks/Br", [False, False], None),
        ("PageBreaks/Br", [True, True], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/Br LA", [False, True, False], None),
        ("PageBreaks/Br LA", [True, True, True], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/c1 R c2e Res c3 LA c4 R c5e", [False], {"chapters": ["1"]}),
        ("PageBreaks/c1 R c2e Res c3 LA c4 R c5e", [False, True], {"chapters": ["3"]}),
        ("PageBreaks/c1 R c2e Res c3 LA c4 R c5e", [True, True], {"chapters": ["4"], "orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/c1 R c2e Res c3 LA c4 R c5e", [False, True, False], {"cutEmptyChapters": True}),
        ("PageBreaks/LA Br", [True, False, False], None),
        ("PageBreaks/LA Br", [True, True, True], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/LA R", [True, False, True], None),
        ("PageBreaks/LA R", [True, True, False], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R Br", [False, True, True], None),
        ("PageBreaks/R Br", [True, False, False], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R Br LA R Br", [False, True, True, False, True, True], None),
        ("PageBreaks/R Br LA R Br", [True, False, True, True, False, False], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R LA R", [False, True, False, True], None),
        ("PageBreaks/R LA R", [True, True, True, False], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R R R", [False, True, True, True], None),
        ("PageBreaks/R R R", [True, False, False, False], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R R Res Res", [False, True, True, False, False], None),
        ("PageBreaks/R R Res Res", [True, False, False, True, True], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R Res", [False, True, False], None),
        ("PageBreaks/R Res", [True, False, True], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R Res LA R", [False, True, True, False, True], None),
        ("PageBreaks/R Res LA R", [True, False, True, True, False], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R Res PA R", [False, True, False, False, True], None),
        ("PageBreaks/R Res PA R", [True, False, False, True, False], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R Res R Res", [False, True, False, True, False], None),
        ("PageBreaks/R Res R Res", [True, False, True, False, True], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/R Res Res", [False, True, False, False], None),
        ("PageBreaks/R Res Res", [True, False, True, True], {"orientation": Orientation.LANDSCAPE}),
        ("PageBreaks/Res", [False, False], None),
        ("PageBreaks/Res", [True, True], {"orientation": Orientation.LANDSCAPE}),
    ]

    @parameterized.expand(PAGE_BREAKS_TEST_DATA)
    def test_convert_live_doc(self, file_path: str, expected_orientations: list[bool], custom_export_params: JsonDict | None) -> None:
        response: Response = self._convert(
            project_id=self.project_id,
            custom_export_params=custom_export_params,
            location_path=file_path,
        )
        self.assertEqual(HTTPStatus.OK, response.status_code)

        pdf_bytes: bytes = response.content

        page_orientations: list[bool] = self._pdf_pages_orientation(pdf_bytes)
        self.assertEqual(expected_orientations, page_orientations)

    def _pdf_pages_orientation(self, pdf_bytes: bytes) -> list[bool]:
        """Get orientations of all PDF pages (True for landscape, False for portrait)."""
        pdf_document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        page_count: int = pdf_document.page_count
        result: list[bool] = []

        for i in range(page_count):
            rect: fitz.Rect = pdf_document[i].rect  # type: ignore[no-any-unimported]
            result.append(rect.width > rect.height)

        pdf_document.close()
        return result
