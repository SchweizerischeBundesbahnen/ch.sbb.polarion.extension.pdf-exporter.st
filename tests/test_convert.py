from __future__ import annotations

import io
from http import HTTPStatus
from typing import TYPE_CHECKING

import pypdf
from python_sbb_polarion.extensions.pdf_exporter import DocumentType
from python_sbb_polarion.types import MediaType

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterConvertTest(PdfExporterTestCase):
    """Tests for PDF conversion functionality."""

    def test_convert_live_doc(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path=self.DOCUMENT_LOCATION,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_toc(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_ToC",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_ToC",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(3, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_ToC",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_tof(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_ToF",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_ToF",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(4, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_ToF",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_tot(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_ToT",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_ToT",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_ToT",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_title_page(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        custom_export_params: JsonDict = {"coverPage": "Default"}
        response: Response = self._convert(
            project_id=self.project_id,
            location_path=self.DOCUMENT_LOCATION,
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_title_page",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(2, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_title_page",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_unknown_project(self) -> None:
        # Act
        response: Response = self._convert(
            project_id="Missing Project",
            location_path=self.DOCUMENT_LOCATION,
            print_error=False,
        )

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)

    def test_convert_unknown_document(self) -> None:
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/Missing Document",
            print_error=False,
        )

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)

    def test_convert_live_report(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        custom_export_params: JsonDict = {"documentType": DocumentType.LIVE_REPORT}
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Reports/Items By Status",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_report",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(2, page_numbers)
        # Pixel coordinates for ignoring "Reported by {user}" and timestamp region on page 1
        ignore_region_coords: list[tuple[int, int, int, int]] = [(1575, 450, 2300, 575)]
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_report",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
            ignore_regions_per_page={1: ignore_region_coords},
        )

    def test_convert_live_report_with_title_page(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        custom_export_params: JsonDict = {
            "coverPage": "Default",
            "documentType": DocumentType.LIVE_REPORT,
        }
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Reports/Items By Status",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_report_with_title_page",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(3, page_numbers)
        # Pixel coordinates for ignoring "Reported by {user}" and timestamp region on page 2
        ignore_region_coords_page2: list[tuple[int, int, int, int]] = [(1575, 450, 2300, 575)]
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_report_with_title_page",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
            ignore_regions_per_page={2: ignore_region_coords_page2},
        )

    def test_convert_live_report_in_global_repo_default_space(self) -> None:
        space_id: str = "_default"
        name: str = "Report in default space"

        try:
            # Arrange
            response: Response = self.admin_utility_api.create_live_report_in_default_space(
                space_id=space_id,
                name=name,
                content_type=MediaType.PLAIN,
                content="Default content",
            )
            self.assertEqual(HTTPStatus.CREATED, response.status_code)

            # Act
            custom_export_params: JsonDict = {"documentType": DocumentType.LIVE_REPORT}
            response = self._convert(
                project_id=None,
                location_path="_default/Report in default space",
                custom_export_params=custom_export_params,
            )

            # Assert
            self.assertEqual(HTTPStatus.OK, response.status_code)
            self.assertIsNotNone(response.content)

            # Verify PDF content
            stream: io.BytesIO = io.BytesIO(response.content)
            pdf_reader: pypdf.PdfReader = pypdf.PdfReader(stream)
            total_pages: int = len(pdf_reader.pages)
            self.assertEqual(1, total_pages)

            first_page: str = pdf_reader.pages[0].extract_text()
            self.assertTrue("Default" in first_page)
        finally:
            response = self.admin_utility_api.delete_live_report_in_default_space(space_id=space_id, name=name)
            self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

    def test_convert_wiki_page(self) -> None:
        project_id: str = self.project_id
        space_id: str = "Specification"
        name: str = "Test Wiki page"

        # Act
        custom_export_params: JsonDict = {"documentType": DocumentType.WIKI_PAGE}
        response: Response = self._convert(
            project_id=self.project_id,
            location_path=f"{space_id}/{name}",
            custom_export_params=custom_export_params,
        )

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        stream: io.BytesIO = io.BytesIO(response.content)
        pdf_reader: pypdf.PdfReader = pypdf.PdfReader(stream)
        total_pages: int = len(pdf_reader.pages)
        self.assertEqual(1, total_pages)

        first_page: str = pdf_reader.pages[0].extract_text()
        self.assertTrue("THIS PAGE HAS NO CONTENT YET" in first_page)

    def test_convert_wiki_page_with_title_page(self) -> None:
        project_id: str = self.project_id
        space_id: str = "Specification"
        name: str = "Test Wiki page"

        # Act
        custom_export_params: JsonDict = {
            "coverPage": "Default",
            "documentType": DocumentType.WIKI_PAGE,
        }
        response: Response = self._convert(
            project_id=project_id,
            location_path=f"{space_id}/{name}",
            custom_export_params=custom_export_params,
        )

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        stream: io.BytesIO = io.BytesIO(response.content)
        pdf_reader: pypdf.PdfReader = pypdf.PdfReader(stream)
        total_pages: int = len(pdf_reader.pages)
        self.assertEqual(2, total_pages)

        first_page: str = pdf_reader.pages[0].extract_text()
        self.assertTrue("Test Wiki page" in first_page)
        self.assertTrue("Author" in first_page)
        self.assertTrue("Status" in first_page)
        self.assertTrue("This document is protected by copyright." in first_page)

        second_page: str = pdf_reader.pages[1].extract_text()
        self.assertTrue("THIS PAGE HAS NO CONTENT YET" in second_page)

    def test_convert_wiki_page_in_global_repo_default_space(self) -> None:
        space_id: str = "_default"
        name: str = "Wiki in default space"

        try:
            # Arrange
            response: Response = self.admin_utility_api.create_wiki_page_in_global_repo(space_id=space_id, name=name)
            self.assertEqual(HTTPStatus.CREATED, response.status_code)

            # Act
            custom_export_params: JsonDict = {
                "coverPage": "Default",
                "documentType": DocumentType.WIKI_PAGE,
            }
            response = self._convert(
                project_id=None,
                location_path="_default/Wiki in default space",
                custom_export_params=custom_export_params,
            )

            # Assert
            self.assertEqual(HTTPStatus.OK, response.status_code)
            self.assertIsNotNone(response.content)

            # Verify PDF content
            stream: io.BytesIO = io.BytesIO(response.content)
            pdf_reader: pypdf.PdfReader = pypdf.PdfReader(stream)
            total_pages: int = len(pdf_reader.pages)
            self.assertEqual(2, total_pages)

            first_page: str = pdf_reader.pages[0].extract_text()
            self.assertTrue("Wiki in default space" in first_page)
        finally:
            response = self.admin_utility_api.delete_wiki_page_in_global_repo(space_id=space_id, name=name)
            self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

    def test_prepared_html_content(self) -> None:
        export_params: JsonDict = {
            "projectId": self.project_id,
            "locationPath": self.DOCUMENT_LOCATION,
            "documentType": DocumentType.LIVE_DOC,
        }

        response: Response = self.api().receive_prepared_html_content(export_params=export_params)
        self.assertEqual(HTTPStatus.OK, response.status_code)
        response_text: str = response.text
        self.assertIsNotNone(response_text)
        self.assertTrue('<body class="">' in response_text)

    def test_convert_live_doc_with_metadate(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {"metadataFields": ["version"]}
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path=self.DOCUMENT_LOCATION,
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        stream: io.BytesIO = io.BytesIO(response.content)
        pdf_reader: pypdf.PdfReader = pypdf.PdfReader(stream)
        metadata: pypdf.DocumentInformation | None = pdf_reader.metadata

        # Check the "version" field in metadata
        if metadata is not None:
            version: str | None = metadata.get("/version")
            self.assertEqual("1.0", version)

    def test_convert_live_doc_with_velocity(self) -> None:
        # Set header footer settings with velocity rendering code
        header_footer_settings: JsonDict = {
            "useCustomValues": True,
            "headerLeft": "HL",
            "headerCenter": "#set ($doc = $transaction.documents.getBy.oldApiObject($document) ) $doc.fields.status.render",
            "headerRight": "HR",
            "footerLeft": "FL",
            "footerCenter": "#set ($doc = $transaction.documents.getBy.oldApiObject($document) ) $doc.fields.type.render",
            "footerRight": "FR",
        }
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(header_footer_settings)

        # Act
        response: Response = self._convert(project_id=self.project_id, location_path=self.DOCUMENT_LOCATION)

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_velocity",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_velocity",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_all_comments(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {"renderComments": "ALL"}
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_comments",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_all_comments",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)

        ignore_region_coords_page1: list[tuple[int, int, int, int]] = [(550, 600, 860, 2000)]
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_all_comments",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
            ignore_regions_per_page={1: ignore_region_coords_page1},
        )

    def test_convert_live_doc_with_open_comments(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {"renderComments": "OPEN"}
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_comments",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_open_comments",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)

        ignore_region_coords_page1: list[tuple[int, int, int, int]] = [(550, 550, 860, 1600)]
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_open_comments",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
            ignore_regions_per_page={1: ignore_region_coords_page1},
        )

    def test_convert_live_doc_with_open_unreferenced_comments(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {
            "renderComments": "OPEN",
            "includeUnreferencedComments": "true",
        }
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_comments",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_open_unref_comments",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_open_unref_comments",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_all_unreferenced_comments(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {
            "renderComments": "ALL",
            "includeUnreferencedComments": "true",
        }
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_comments",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_all_unref_comments",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_all_unref_comments",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_open_native_comments(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {
            "renderComments": "OPEN",
            "renderNativeComments": "true",
        }
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_comments",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_open_native_comments",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_open_native_comments",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_all_native_comments(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        custom_export_params: JsonDict = {
            "renderComments": "ALL",
            "renderNativeComments": "true",
        }
        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_comments",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_all_native_comments",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_all_native_comments",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_without_comments_rendering(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/live_doc_with_comments",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_without_comments_rendering",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_without_comments_rendering",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_filter(self) -> None:
        # Test LiveDoc export with workitem filter using urlQueryParameters.

        # This test exports Product Specification document twice:
        # 1. Without filter - should have 7 pages (all 54 workitems)
        # 2. With filter severity:must_have - should have 5 pages (only 8 workitems)

        # Hidden workitems (46 total): EL-138, EL-137, EL-134, EL-130, EL-131, EL-132,
        # EL-141, EL-142, EL-140, EL-143, EL-136, EL-191, EL-125, EL-135, EL-11, EL-70,
        # EL-13, EL-12, EL-15, EL-10, EL-69, EL-7, EL-6, EL-9, EL-8, EL-5, EL-112, EL-113,
        # EL-111, EL-110, EL-109, EL-127, EL-128, EL-123, EL-124, EL-122, EL-120, EL-121,
        # EL-114, EL-117, EL-202, EL-200, EL-201, EL-199, EL-198, EL-139

        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Step 1: Export WITHOUT filter - should have 7 pages
        response_no_filter: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/Product Specification",
        )
        self.assertEqual(HTTPStatus.OK, response_no_filter.status_code)
        page_numbers_no_filter: int = self._pdf_to_png(
            pdf_bytes=response_no_filter.content,
            custom_prefix="test_convert_live_doc_no_filter",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(7, page_numbers_no_filter)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_no_filter",
            page_numbers=page_numbers_no_filter,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

        # Step 2: Export WITH filter severity:must_have - should have 5 pages
        custom_export_params: JsonDict = {
            "urlQueryParameters": {
                "query": "severity:must_have",
            },
        }
        response_with_filter: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/Product Specification",
            custom_export_params=custom_export_params,
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert filter works - page count should be reduced
        self.assertEqual(HTTPStatus.OK, response_with_filter.status_code)
        self.assertIsNotNone(response_with_filter.content)

        page_numbers_with_filter: int = self._pdf_to_png(
            pdf_bytes=response_with_filter.content,
            custom_prefix="test_convert_live_doc_with_filter",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(5, page_numbers_with_filter)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_filter",
            page_numbers=page_numbers_with_filter,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

        # Verify filter actually reduced page count
        self.assertLess(page_numbers_with_filter, page_numbers_no_filter, "Filter should reduce page count")

    def test_convert_live_doc_indentation_format(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Testing/Indent Test",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_indent",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(9, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_indent",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_no_split_table_rows_between_pages(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Specification/No_Split_Table",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_no_split_table_rows_between_pages",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(5, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_no_split_table_rows_between_pages",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_split_single_row_table_test(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Testing/split_table_test",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_split_single_row_table",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(2, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_split_single_row_table",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )

    def test_convert_live_doc_with_formula(self) -> None:
        # Set header footer settings without timestamp
        previous_header_footer_settings: JsonDict
        _current_header_footer_settings: JsonDict
        previous_header_footer_settings, _current_header_footer_settings = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)

        # Act
        response: Response = self._convert(
            project_id=self.project_id,
            location_path="Testing/formula test",
        )

        # Restore original header footer settings
        self._save_header_footer_settings(previous_header_footer_settings)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

        # Verify PDF content
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=response.content,
            custom_prefix="test_convert_live_doc_with_formula",
            output_folder=self._get_output_folder(),
        )
        self.assertEqual(1, page_numbers)
        self._compare_pdf_pages(
            custom_prefix="test_convert_live_doc_with_formula",
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )
