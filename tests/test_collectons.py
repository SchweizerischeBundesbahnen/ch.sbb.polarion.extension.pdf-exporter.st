from http import HTTPStatus
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from requests import Response
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict


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
