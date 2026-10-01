from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterFirstPageHeaderFooterTest(PdfExporterTestCase):
    """Tests the header and footer a style package names for the first page.

    The text of each page says which header and footer it got, and the snapshots say where they are drawn.
    """

    # Two portrait pages, a page break between them
    DOCUMENT: str = "Testing/First Page Header Footer"

    # The name of the header and footer of the first page, next to "Default" for the other pages
    FIRST_PAGE: str = "First page title"

    # Text only: a timestamp differs on every run, and an image would be an external resource
    RUNNING: ClassVar[JsonDict] = {
        "useCustomValues": True,
        "headerLeft": "Running {{ PROJECT_NAME }}",
        "headerCenter": "Running center",
        "headerRight": "Running right",
        "footerLeft": "Running {{ DOCUMENT_TITLE }}",
        "footerCenter": "Running foot center",
        "footerRight": "Running page {{ PAGE_NUMBER }}/{{ PAGES_TOTAL_COUNT }}",
    }

    TITLE: ClassVar[JsonDict] = {
        "useCustomValues": True,
        "headerLeft": "Title left",
        "headerCenter": "<b>Title {{ DOCUMENT_TITLE }}</b>",
        "headerRight": "",
        "footerLeft": "",
        "footerCenter": "Title foot center",
        "footerRight": "Title page {{ PAGE_NUMBER }}/{{ PAGES_TOTAL_COUNT }}",
    }

    def setUp(self) -> None:
        super().setUp()
        self.previous_header_footer: JsonDict
        self.previous_header_footer, _ = self._save_header_footer_settings(self.RUNNING)
        response: Response = self.api().save_setting(feature="header-footer", data=self.TITLE, name=self.FIRST_PAGE, scope=self.scope)
        self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

    def tearDown(self) -> None:
        self.api().delete_setting(feature="header-footer", name=self.FIRST_PAGE, scope=self.scope)
        self._save_header_footer_settings(self.previous_header_footer)
        super().tearDown()

    def test_settings_store_the_first_page_header_footer_of_a_style_package(self) -> None:
        name: str = "With a first page"
        style_package: JsonDict = {**self.api().get_setting_default_content(feature="style-package").json(), "firstPageHeaderFooter": self.FIRST_PAGE}
        saved: Response = self.api().save_setting(feature="style-package", data=style_package, name=name, scope=self.scope)
        self.assertEqual(HTTPStatus.NO_CONTENT, saved.status_code)
        try:
            response: Response = self.api().get_setting_content(feature="style-package", name=name, scope=self.scope)
        finally:
            self.api().delete_setting(feature="style-package", name=name, scope=self.scope)

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertEqual(self.FIRST_PAGE, response.json()["firstPageHeaderFooter"])

    def test_settings_of_a_style_package_name_no_first_page_header_footer_by_default(self) -> None:
        response: Response = self.api().get_setting_default_content(feature="style-package")

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNone(response.json().get("firstPageHeaderFooter"))

    def test_convert_prints_the_first_page_header_footer_on_the_first_page(self) -> None:
        pages: list[str] = self._convert_and_compare(
            custom_prefix="test_first_page_header_footer",
            expected_page_count=2,
            custom_export_params={"firstPageHeaderFooter": self.FIRST_PAGE},
        )

        self._assert_first_page_parts(pages[0], page_number=1, pages_total=2)
        self._assert_running_parts(pages[1], page_number=2, pages_total=2)

    def test_convert_prints_the_first_page_header_footer_on_the_page_after_the_cover_page(self) -> None:
        pages: list[str] = self._convert_and_compare(
            custom_prefix="test_first_page_header_footer_with_cover_page",
            expected_page_count=3,
            custom_export_params={"firstPageHeaderFooter": self.FIRST_PAGE, "coverPage": "Default"},
        )

        self.assertNotIn("Running", pages[0], "The cover page has no header and footer")
        self.assertNotIn("Title left", pages[0], "The cover page has no header and footer")
        self._assert_first_page_parts(pages[1], page_number=2, pages_total=3)
        self._assert_running_parts(pages[2], page_number=3, pages_total=3)

    def test_convert_prints_the_other_header_footer_on_the_first_page_without_one_of_its_own(self) -> None:
        response: Response = self._convert(project_id=self.project_id, location_path=self.DOCUMENT)

        self.assertEqual(HTTPStatus.OK, response.status_code)
        pages: list[str] = self._page_texts(response.content)
        self.assertEqual(2, len(pages))
        for page_number, page in enumerate(pages, start=1):
            self._assert_running_parts(page, page_number=page_number, pages_total=2)

    # The page counters carry a margin each, so the text reads "1 / 2"
    def _assert_first_page_parts(self, page: str, page_number: int, pages_total: int) -> None:
        for part in ("Title left", "Title First Page Header Footer", "Title foot center", f"Title page {page_number} / {pages_total}"):
            self.assertIn(part, page)
        self.assertNotIn("Running", page, "The header and footer of the first page replaces the other one")

    def _assert_running_parts(self, page: str, page_number: int, pages_total: int) -> None:
        for part in ("Running center", "Running right", "Running foot center", f"Running page {page_number} / {pages_total}"):
            self.assertIn(part, page)
        self.assertNotIn("Title", page, "Only the first page gets the header and footer of the first page")

    def _convert_and_compare(self, *, custom_prefix: str, expected_page_count: int, custom_export_params: JsonDict) -> list[str]:
        response: Response = self._convert(project_id=self.project_id, location_path=self.DOCUMENT, custom_export_params=custom_export_params)

        self.assertEqual(HTTPStatus.OK, response.status_code)
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix=custom_prefix,
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(expected_page_count, page_numbers)
        self._compare_pdf_pages(
            custom_prefix=custom_prefix,
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )
        return self._page_texts(response.content)

    def _page_texts(self, pdf_bytes: bytes) -> list[str]:
        pdf_document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            return [page.get_text() for page in pdf_document]
        finally:
            pdf_document.close()
