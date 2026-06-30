from http import HTTPStatus
from typing import TYPE_CHECKING

from python_sbb_polarion.extensions.pdf_exporter import DocumentType

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.core import PolarionApiV1
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterCollectionTest(PdfExporterTestCase):
    """Tests for document collection operations."""

    def test_fetch_documents_from_collection(self) -> None:
        project_id: str = self.project_id
        collection_id: str = "1"

        # Act
        response: Response = self.api().get_documents_from_collection(project_id=project_id, collection_id=collection_id)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)
        json_response: list[JsonDict] = response.json()
        self.assertEqual("Administration Specification", json_response[0]["documentName"])
        self.assertEqual(self.project_id, json_response[0]["projectId"])

    def test_collection_with_report_from_non_default_space(self) -> None:
        project_id: str = self.project_id
        collection_id: str = "1"
        space_id: str = "Reports"
        report_name: str = "Items By Status"

        polarion_api: PolarionApiV1 = self.polarion_api()
        rich_page_relationship: JsonDict = {"data": [{"type": "pages", "id": f"{project_id}/{space_id}/{report_name}"}]}

        add_response: Response = polarion_api.create_collection_relationships(project_id, collection_id, "richPages", rich_page_relationship)
        self.assertEqual(HTTPStatus.NO_CONTENT, add_response.status_code)
        try:
            response: Response = self.api().get_documents_from_collection(project_id=project_id, collection_id=collection_id)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            documents: list[JsonDict] = response.json()
            reports: list[JsonDict] = [document for document in documents if document.get("documentType") == DocumentType.LIVE_REPORT]
            self.assertEqual(1, len(reports), f"Expected exactly one report in the collection, got: {documents}")

            report: JsonDict = reports[0]
            self.assertEqual(project_id, report["projectId"])
            self.assertEqual(space_id, report["spaceId"])
            self.assertEqual(report_name, report["documentName"])
        finally:
            polarion_api.delete_collection_relationships(project_id, collection_id, "richPages", rich_page_relationship)
