from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from collections.abc import Sequence

    from requests import Response


class PdfExporterStatusIconTest(PdfExporterTestCase):
    """Tests that the icon of a status stays on the line of its label after a wide image.

    A work item lists its fields after its description, in brackets: ``[<icon>Draft]``. After an image almost as wide as
    the column, the line had room for the bracket and the icon alone, and the label went to the next line. pdf-exporter
    13.12.0 broke them so from an image of 574 px on. The document holds a work item for each of these widths:

    * 560 px, which leaves the status room on the line of the image.
    * 572 px, the widest image after which 13.12.0 kept the status whole.
    * 574 px, the narrowest after which it broke it.
    * 584 px, in the middle of the widths it broke it after.
    * 600 px, wider than the page, which the exporter narrows to it.

    Each description gives its image in its source, so the document needs no attachments.
    """

    LOCATION: str = "Testing/Status After A Wide Image"
    WORK_ITEMS: int = 5

    # An icon is 12 pt wide, the images before the fields are far wider
    MAX_ICON_WIDTH_PT: float = 20
    # How far the middle of an icon may be from the middle of its label: the icon is drawn by whole pixels
    TOLERANCE_PT: float = 3

    def test_convert_live_doc_keeps_the_icon_of_a_status_on_the_line_of_its_label(self) -> None:
        response: Response = self._convert(project_id=self.project_id, location_path=self.LOCATION)
        self.assertEqual(HTTPStatus.OK, response.status_code)

        statuses: int = 0
        with fitz.open(stream=response.content, filetype="pdf") as document:
            for page in document:
                icons: list[Box] = sorted(
                    (box for box in (_box(info["bbox"]) for info in page.get_image_info()) if box[2] - box[0] < self.MAX_ICON_WIDTH_PT),
                    key=_reading_order,
                )
                labels: list[Box] = sorted(
                    (_box(span["bbox"]) for block in page.get_text("dict")["blocks"] for line in block.get("lines", []) for span in line["spans"] if span["text"].startswith("Draft")),
                    key=_reading_order,
                )
                self.assertEqual(len(labels), len(icons), f"Each label on page {page.number + 1} has its icon")
                for icon, label in zip(icons, labels, strict=True):
                    self.assertAlmostEqual(_middle(label), _middle(icon), delta=self.TOLERANCE_PT, msg=f"The icon at {icon} is on the line of its label at {label}")
                    self.assertGreater(label[0], icon[0], f"The label at {label} follows its icon at {icon}")
                statuses += len(labels)
        self.assertEqual(self.WORK_ITEMS, statuses)

    def test_convert_live_doc_draws_the_statuses_after_wide_images(self) -> None:
        self._assert_convert_matches_snapshot(
            location_path=self.LOCATION,
            custom_prefix="test_convert_live_doc_status_after_a_wide_image",
            expected_page_count=1,
        )


Box = tuple[float, float, float, float]
"""The left, top, right and bottom of a box on a page, in points."""


def _box(bbox: Sequence[float]) -> Box:
    return float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])


def _reading_order(box: Box) -> tuple[float, float]:
    """Top to bottom, then left to right."""
    return box[1], box[0]


def _middle(box: Box) -> float:
    """The vertical middle of the box."""
    return (box[1] + box[3]) / 2
