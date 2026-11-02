from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from requests import Response


class PdfExporterCrossReferencesTest(PdfExporterTestCase):
    """pdf-exporter#1268: a cross-reference looks as it does in Polarion, in the color of a link with a dashed gray line below.

    The document follows the report of the issue: Object 3 refers to Object 1 by its outline number and title,
    "1 - Object 1", and Object 4 refers to Object 3 by its ID and title. The report cut local URLs, and so does the
    snapshot.
    """

    LOCATION: str = "Testing/Cross References"

    # The labels Polarion writes for the cross-references of the document
    LABELS: tuple[str, ...] = ("1 - Object 1", "EL-14494 - Object 3 Cross-Reference")

    # The color of a link in Polarion, #007993, as the PDF sets it: RGB components from 0 to 1, to three decimals
    LINK_COLOR: tuple[float, ...] = (0.0, 0.475, 0.576)

    def test_convert_live_doc_draws_cross_references_as_polarion_does(self) -> None:
        self._assert_convert_matches_snapshot(
            location_path=self.LOCATION,
            custom_prefix="test_convert_live_doc_cross_references",
            expected_page_count=1,
            custom_export_params={"cutLocalUrls": True},
        )

    def test_convert_live_doc_draws_cross_references_in_the_color_of_a_link(self) -> None:
        for cut_local_urls in (False, True):
            with self.subTest(cut_local_urls=cut_local_urls):
                response: Response = self._convert(project_id=self.project_id, location_path=self.LOCATION, custom_export_params={"cutLocalUrls": cut_local_urls})

                self.assertEqual(HTTPStatus.OK, response.status_code)
                text_in_link_color: str = self._text_in_color(response.content, self.LINK_COLOR)
                for label in self.LABELS:
                    self.assertIn(label, text_in_link_color, f"The cross-reference '{label}' is in the color of a link")
