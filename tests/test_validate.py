from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from python_sbb_polarion.extensions.pdf_exporter import DocumentType

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterValidateTest(PdfExporterTestCase):
    """Tests for document validation functionality."""

    def test_validate_document_with_invalid_pages(self) -> None:
        # Act
        response: Response = self.__validate(
            project_id=self.project_id,
            location_path="Specification/Product Specification",
            fit_to_page=False,
        )

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)

        json_response: JsonDict = response.json()
        self.assertIsNotNone(json_response)
        self.assertEqual(1, len(json_response["invalidPages"]))  # type: ignore[arg-type]
        self.assertEqual(5, json_response["invalidPages"][0]["number"])  # type: ignore[index,call-overload]
        self.assertEqual(0, len(json_response["suspiciousWorkItems"]))  # type: ignore[arg-type]

    def test_validate_document_without_invalid_pages(self) -> None:
        # Act
        response: Response = self.__validate(
            project_id=self.project_id,
            location_path="Specification/Administration Specification",
        )

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)

        json_response: JsonDict = response.json()
        self.assertIsNotNone(json_response)
        self.assertEqual(0, len(json_response["invalidPages"]))  # type: ignore[arg-type]
        self.assertEqual(0, len(json_response["suspiciousWorkItems"]))  # type: ignore[arg-type]

    def test_validate_unknown_project(self) -> None:
        # Act
        response: Response = self.__validate(
            project_id="Missing Project",
            location_path="Specification/Administration Specification",
            print_error=False,
        )

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)

    def test_validate_unknown_document(self) -> None:
        # Act
        response: Response = self.__validate(
            project_id=self.project_id,
            location_path="Specification/Missing Document",
            print_error=False,
        )

        # Assert
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_code)

    def __validate(self, project_id: str, location_path: str, fit_to_page: bool = True, print_error: bool = True) -> Response:
        export_params: JsonDict = {
            "projectId": project_id,
            "locationPath": location_path,
            "documentType": DocumentType.LIVE_DOC,
            "fitToPage": fit_to_page,
        }

        self.api().polarion_connection.set_print_error(print_error)
        response: Response = self.api().validate(export_params=export_params)
        self.api().polarion_connection.set_print_error(True)
        return response
