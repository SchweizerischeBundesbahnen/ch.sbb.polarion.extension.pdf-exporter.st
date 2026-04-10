from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING

from python_sbb_polarion.extensions.pdf_exporter import DocumentType
from python_sbb_polarion.types import MediaType

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterFileNameTest(PdfExporterTestCase):
    """Tests for filename generation functionality."""

    def test_filename_live_report(self) -> None:
        # Act
        data: JsonDict = {
            "projectId": self.project_id,
            "locationPath": "Specification/Epic Statistics",
            "documentType": DocumentType.LIVE_REPORT,
        }
        response: Response = self.api().generate_document_export_filename(data=data)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)
        self.assertTrue(re.match(r"^E-Library Specification Epic Statistics .*\.pdf$", response.text))

    def test_filename_live_document(self) -> None:
        # Act
        data: JsonDict = {
            "projectId": self.project_id,
            "locationPath": "Specification/Administration Specification",
            "documentType": DocumentType.LIVE_DOC,
        }
        response: Response = self.api().generate_document_export_filename(data=data)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)
        self.assertEqual("E-Library Specification Administration Specification.pdf", response.text)

    def test_filename_wiki_page(self) -> None:
        project_id: str = self.project_id
        space_id: str = "Specification"
        name: str = "Test Wiki page"

        # Act
        data: JsonDict = {
            "projectId": project_id,
            "locationPath": f"{space_id}/{name}",
            "documentType": DocumentType.WIKI_PAGE,
        }
        response_filename: Response = self.api().generate_document_export_filename(data=data)

        # Assert
        self.assertEqual(HTTPStatus.OK, response_filename.status_code)
        self.assertIsNotNone(response_filename.content)
        self.assertTrue(re.match(r"^E-Library Specification Test Wiki page .*\.pdf$", response_filename.text))

    def test_filename_live_report_in_global_repo_and_default_space(self) -> None:
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
            data: JsonDict = {
                "locationPath": f"{space_id}/{name}",
                "documentType": DocumentType.LIVE_REPORT,
            }
            response_filename: Response = self.api().generate_document_export_filename(data=data)

            # Assert
            self.assertEqual(HTTPStatus.OK, response_filename.status_code)
            self.assertIsNotNone(response_filename.content)
            self.assertTrue(re.match(r"^Report in default space .*\.pdf$", response_filename.text))
        finally:
            response_delete: Response = self.admin_utility_api.delete_live_report_in_default_space(space_id=space_id, name=name)
            self.assertEqual(HTTPStatus.NO_CONTENT, response_delete.status_code)

    def test_filename_wiki_page_in_global_repo_and_default_space(self) -> None:
        space_id: str = "_default"
        name: str = "Wiki in default space"

        try:
            # Arrange
            response: Response = self.admin_utility_api.create_wiki_page_in_global_repo(space_id=space_id, name=name)
            self.assertEqual(HTTPStatus.CREATED, response.status_code)

            # Act
            data: JsonDict = {
                "locationPath": f"{space_id}/{name}",
                "documentType": DocumentType.WIKI_PAGE,
            }
            response_filename: Response = self.api().generate_document_export_filename(data=data)

            # Assert
            self.assertEqual(HTTPStatus.OK, response_filename.status_code)
            self.assertIsNotNone(response_filename.content)
            self.assertTrue(re.match(r"^\s*Wiki in default space .*\.pdf$", response_filename.text))
        finally:
            response_delete: Response = self.admin_utility_api.delete_wiki_page_in_global_repo(space_id=space_id, name=name)
            self.assertEqual(HTTPStatus.NO_CONTENT, response_delete.status_code)

    def test_filename_non_existing_live_report(self) -> None:
        # Act
        self.api().polarion_connection.set_print_error(False)
        data: JsonDict = {
            "projectId": self.project_id,
            "locationPath": "Specification/non existing live report",
            "documentType": DocumentType.LIVE_REPORT,
        }
        response: Response = self.api().generate_document_export_filename(data=data)

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.api().polarion_connection.set_print_error(True)

    def test_filename_non_existing_live_document(self) -> None:
        # Act
        self.api().polarion_connection.set_print_error(False)
        data: JsonDict = {
            "projectId": self.project_id,
            "locationPath": "Specification/non existing document",
            "documentType": DocumentType.LIVE_DOC,
        }
        response: Response = self.api().generate_document_export_filename(data=data)

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)
        self.api().polarion_connection.set_print_error(True)

    def test_filename_non_existing_wiki_page(self) -> None:
        project_id: str = self.project_id

        # Act
        self.api().polarion_connection.set_print_error(False)
        data: JsonDict = {
            "projectId": project_id,
            "locationPath": "Specification/non existing wiki page",
            "documentType": DocumentType.WIKI_PAGE,
        }
        response_filename: Response = self.api().generate_document_export_filename(data=data)

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response_filename.status_code)
        self.api().polarion_connection.set_print_error(True)
