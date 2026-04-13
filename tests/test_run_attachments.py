from __future__ import annotations

import io
import json
import pathlib
from http import HTTPStatus
from typing import TYPE_CHECKING

import pypdf
from python_sbb_polarion.extensions.pdf_exporter import DocumentType
from python_sbb_polarion.util import abs_path_str

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.core import PolarionApiV1
    from python_sbb_polarion.types import FilesDict, JsonDict
    from requests import Response


class TestRunAttachmentTest(PdfExporterTestCase):
    """Tests for test run attachment operations."""

    def _build_testrun_attachment_files(self, file_path: str, attributes: JsonDict) -> FilesDict:
        """Build FilesDict for testrun attachment creation."""
        resource: JsonDict = {
            "data": [
                {
                    "type": "testrun_attachments",
                    "attributes": attributes,
                },
            ]
        }
        file_path_obj: pathlib.Path = pathlib.Path(file_path)
        content: bytes = file_path_obj.read_bytes()
        files: FilesDict = {
            "resource": json.dumps(resource),
            "files": (file_path_obj.name, content),
        }
        return files

    def _build_test_step_result_attachment_files(self, file_path: str, attributes: JsonDict) -> FilesDict:
        """Build FilesDict for test step result attachment creation."""
        resource: JsonDict = {
            "data": [
                {
                    "type": "teststepresult_attachments",
                    "attributes": attributes,
                },
            ],
        }
        file_path_obj: pathlib.Path = pathlib.Path(file_path)
        content: bytes = file_path_obj.read_bytes()
        files: FilesDict = {
            "resource": json.dumps(resource),
            "files": (file_path_obj.name, content),
        }
        return files

    def _build_test_record_attachment_files(self, file_path: str, attributes: JsonDict) -> FilesDict:
        """Build FilesDict for test record attachment creation."""
        resource: JsonDict = {"data": [{"type": "testrecord_attachments", "attributes": attributes}]}
        file_path_obj: pathlib.Path = pathlib.Path(file_path)
        content: bytes = file_path_obj.read_bytes()
        files: FilesDict = {
            "resource": json.dumps(resource),
            "files": (file_path_obj.name, content),
        }
        return files

    def test_fetch_test_run_attachment_from_test_run(self) -> None:
        polarion_api: PolarionApiV1 = self.polarion_api()
        assert polarion_api is not None
        project_id: str = self.project_id
        testrun_id: str = "0_9b FMST"
        attachment_file_name: str = "test_attachment_file_name"
        title: str = "Test attachment title"
        filepath: str = abs_path_str("../test-data/test-attachment.txt")
        test_case_id: str = "EL-1"

        try:
            # Attachment to the test run itself
            files: FilesDict = self._build_testrun_attachment_files(
                file_path=filepath,
                attributes={"fileName": attachment_file_name, "title": title},
            )
            response: Response = polarion_api.create_testrun_attachments(
                project_id=project_id,
                testrun_id=testrun_id,
                files=files,
            )
            self.assertEqual(HTTPStatus.CREATED, response.status_code)
            json_response_1: JsonDict = response.json()
            assert isinstance(json_response_1, dict)
            assert isinstance(json_response_1["data"], list)
            assert isinstance(json_response_1["data"][0], dict)
            assert isinstance(json_response_1["data"][0]["id"], str)
            test_run_attachment_id: str = json_response_1["data"][0]["id"].split("/")[-1]

            # Attachment to the first step of the test case 1
            step_files: FilesDict = self._build_test_step_result_attachment_files(
                file_path=filepath,
                attributes={"fileName": attachment_file_name, "title": title},
            )
            response_step: Response = polarion_api.create_test_step_result_attachments(
                project_id=project_id,
                testrun_id=testrun_id,
                test_case_project_id=project_id,
                test_case_id=test_case_id,
                iteration=0,
                test_step_index=1,
                files=step_files,
            )
            self.assertEqual(HTTPStatus.CREATED, response_step.status_code)
            json_response_2: JsonDict = response_step.json()
            assert isinstance(json_response_2, dict)
            assert isinstance(json_response_2["data"], list)
            assert isinstance(json_response_2["data"][0], dict)
            assert isinstance(json_response_2["data"][0]["id"], str)
            test_step_attachment_id: str = json_response_2["data"][0]["id"].split("/")[-1]

            # Attachment to the test case 1 record (summary)
            record_files: FilesDict = self._build_test_record_attachment_files(
                file_path=filepath,
                attributes={"fileName": attachment_file_name, "title": title},
            )
            response_record: Response = polarion_api.create_test_record_attachments(
                project_id=project_id,
                testrun_id=testrun_id,
                test_case_project_id=project_id,
                test_case_id=test_case_id,
                iteration=0,
                files=record_files,
            )
            self.assertEqual(HTTPStatus.CREATED, response_record.status_code)
            json_response_3: JsonDict = response_record.json()
            assert isinstance(json_response_3, dict)
            assert isinstance(json_response_3["data"], list)
            assert isinstance(json_response_3["data"][0], dict)
            assert isinstance(json_response_3["data"][0]["id"], str)
            test_record_attachment_id: str = json_response_3["data"][0]["id"].split("/")[-1]

            # Now get all attachments using our method
            response_attachments: Response = self.api().get_test_run_attachments(project_id=project_id, test_run_id=testrun_id)

            # Assert that result contains all 3 types of attachments
            self.assertEqual(HTTPStatus.OK, response_attachments.status_code)
            self.assertIsNotNone(response_attachments.content)

            attachments_response: list[JsonDict] = response_attachments.json()
            assert isinstance(attachments_response, list)
            self.assertIsNotNone(attachments_response)
            self.assertGreater(len(attachments_response), 2)

            test_run_attachment: JsonDict | None = next(
                (item for item in attachments_response if isinstance(item, dict) and item.get("id") == test_run_attachment_id),
                None,
            )
            self.assertIsNotNone(test_run_attachment)
            test_step_attachment: JsonDict | None = next(
                (item for item in attachments_response if isinstance(item, dict) and item.get("id") == test_step_attachment_id),
                None,
            )
            self.assertIsNotNone(test_step_attachment)
            test_record_attachment: JsonDict | None = next(
                (item for item in attachments_response if isinstance(item, dict) and item.get("id") == test_record_attachment_id),
                None,
            )
            self.assertIsNotNone(test_record_attachment)

        finally:
            # Clean up
            response = polarion_api.delete_testrun_attachment(
                project_id=project_id,
                testrun_id=testrun_id,
                attachment_id=attachment_file_name,
            )
            self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

            response = polarion_api.delete_test_step_result_attachment(
                project_id=project_id,
                testrun_id=testrun_id,
                test_case_project_id=project_id,
                test_case_id=test_case_id,
                iteration=0,
                test_step_index=1,
                attachment_id=test_step_attachment_id,
            )
            self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

            response = polarion_api.delete_test_record_attachment(
                project_id=project_id,
                testrun_id=testrun_id,
                test_case_project_id=project_id,
                test_case_id=test_case_id,
                iteration=0,
                attachment_id=test_record_attachment_id,
            )
            self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

    def test_export_test_run_with_embedded_attachment(self) -> None:
        polarion_api: PolarionApiV1 = self.polarion_api()
        assert polarion_api is not None
        project_id: str = self.project_id
        testrun_id: str = "0_9b FMST"
        attachment_file_name: str = "test_attachment_file_name"
        title: str = "Test attachment title"
        filepath: str = abs_path_str("../test-data/test-attachment.pdf")

        try:
            # Attachment to the test run itself
            files: FilesDict = self._build_testrun_attachment_files(
                file_path=filepath,
                attributes={"fileName": attachment_file_name, "title": title},
            )
            response: Response = polarion_api.create_testrun_attachments(
                project_id=project_id,
                testrun_id=testrun_id,
                files=files,
            )
            self.assertEqual(HTTPStatus.CREATED, response.status_code)

            # Now get all attachments using our method
            response_get: Response = self.api().get_test_run_attachments(project_id=project_id, test_run_id=testrun_id)

            # Assert that result contains attachments
            self.assertEqual(HTTPStatus.OK, response_get.status_code)

            response_convert: Response = self.__convert(project_id=project_id, testrun_id=testrun_id)

            # Verify PDF content
            stream: io.BytesIO = io.BytesIO(response_convert.content)
            pdf_reader: pypdf.PdfReader = pypdf.PdfReader(stream)

            total_pages: int = len(pdf_reader.pages)
            self.assertEqual(2, total_pages)

            embedded_files: object = pdf_reader.trailer["/Root"].get("/Names", {}).get("/EmbeddedFiles")  # type: ignore[attr-defined]
            self.assertIsNotNone(embedded_files)

            embedded_files_obj: object = embedded_files.get_object()  # type: ignore[attr-defined]
            names: list[object] = embedded_files_obj.get("/Names", [])  # type: ignore[attr-defined]
            file_names: list[object] = [names[i] for i in range(0, len(names), 2)]
            assert "test_attachment_file_name" in file_names[0]  # type: ignore[operator]
        finally:
            # Clean up
            response = polarion_api.delete_testrun_attachment(
                project_id=project_id,
                testrun_id=testrun_id,
                attachment_id=attachment_file_name,
            )
            self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

    def __convert(self, project_id: str, testrun_id: str, custom_export_params: JsonDict | None = None, print_error: bool = True) -> Response:
        export_params: JsonDict = {
            "projectId": project_id,
            "urlQueryParameters": {"id": testrun_id},
            "embedAttachments": True,
            "documentType": DocumentType.TEST_RUN,
        }
        if custom_export_params:
            export_params.update(custom_export_params)

        self.api().polarion_connection.set_print_error(print_error)
        response: Response = self.api().convert(export_params=export_params)
        self.api().polarion_connection.set_print_error(True)
        return response
