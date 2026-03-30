import pathlib
import re
import tempfile
from http import HTTPStatus
from typing import TYPE_CHECKING

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterSettingsTest(PdfExporterTestCase):
    """Tests for settings management."""

    def test_settings_get_css(self) -> None:
        # Act
        response: Response = self.api().get_setting_content(feature="css", scope=self.scope)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        json_settings: JsonDict = response.json()
        self.assertIn("bundleTimestamp", json_settings)
        self.assertIn("css", json_settings)
        self.assertIsInstance(json_settings["bundleTimestamp"], str)
        self.assertIsInstance(json_settings["css"], str)
        self.assertIn("Arial", json_settings["css"])  # type: ignore[arg-type]
        self.assertIn("/polarion/ria/fonts/opensans/OpenSans-Regular.ttf", json_settings["css"])  # type: ignore[arg-type]

    def test_settings_post_css(self) -> None:
        # Act
        response_get: Response = self.api().get_setting_default_content(feature="css")
        response_save: Response = self.api().save_setting(feature="css", scope=self.scope, data=response_get.json())

        # Assert
        self.assertEqual(HTTPStatus.NO_CONTENT, response_save.status_code)

    def test_settings_get_localization(self) -> None:
        # Act
        response: Response = self.api().get_setting_content(feature="localization", scope=self.scope)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        json_settings: JsonDict = response.json()

        self.assertIn("bundleTimestamp", json_settings)
        self.assertIn("translations", json_settings)
        self.assertIsInstance(json_settings["bundleTimestamp"], str)
        self.assertIsInstance(json_settings["translations"]["Accepted"], list)  # type: ignore[index,call-overload]

        for json_entry in json_settings["translations"]["Accepted"]:  # type: ignore[index,call-overload,union-attr]
            self.assertIn("language", json_entry)  # type: ignore[arg-type]
            self.assertIn("value", json_entry)  # type: ignore[arg-type]
            self.assertIsInstance(json_entry["language"], str)  # type: ignore[index,call-overload]
            self.assertIsInstance(json_entry["value"], str)  # type: ignore[index,call-overload]

    def test_settings_post_localization(self) -> None:
        # Act
        response_get: Response = self.api().get_setting_default_content(feature="localization")
        json_data: JsonDict = response_get.json()
        new_entry: JsonDict = {
            "Test": [
                {"language": "de", "value": "Test de"},
                {"language": "fr", "value": "Test fr"},
                {"language": "it", "value": "Test it"},
            ]
        }
        json_data["translations"]["Test"] = new_entry["Test"]  # type: ignore[index,call-overload]
        response_save: Response = self.api().save_setting(feature="localization", scope=self.scope, data=json_data)

        # Assert
        self.assertEqual(HTTPStatus.NO_CONTENT, response_save.status_code)

        response: Response = self.api().get_setting_content(feature="localization", scope=self.scope)
        stored_settings: JsonDict = response.json()
        test_value: list[JsonDict] = stored_settings["translations"]["Test"]  # type: ignore[assignment,index,call-overload]
        self.assertIsNotNone(test_value)

        self.assertEqual("de", test_value[0]["language"])
        self.assertEqual("fr", test_value[1]["language"])
        self.assertEqual("it", test_value[2]["language"])
        self.assertEqual("Test de", test_value[0]["value"])
        self.assertEqual("Test fr", test_value[1]["value"])
        self.assertEqual("Test it", test_value[2]["value"])

    def test_settings_get_headerfooter(self) -> None:
        # Act
        response: Response = self.api().get_setting_content(feature="header-footer", scope=self.scope)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        json_settings: JsonDict = response.json()
        self.assertIn("bundleTimestamp", json_settings)
        self.assertIn("headerLeft", json_settings)
        self.assertIn("headerCenter", json_settings)
        self.assertIn("headerRight", json_settings)
        self.assertIn("footerLeft", json_settings)
        self.assertIn("footerCenter", json_settings)
        self.assertIn("footerRight", json_settings)

        self.assertIsInstance(json_settings["bundleTimestamp"], str)
        self.assertIsInstance(json_settings["headerLeft"], str)
        self.assertIsInstance(json_settings["headerCenter"], str)
        self.assertIsInstance(json_settings["headerRight"], str)
        self.assertIsInstance(json_settings["footerLeft"], str)
        self.assertIsInstance(json_settings["footerCenter"], str)
        self.assertIsInstance(json_settings["footerRight"], str)

    def test_settings_post_headerfooter(self) -> None:
        # Act
        response_get: Response = self.api().get_setting_default_content(feature="header-footer")
        original_settings: JsonDict = response_get.json()
        json_data: JsonDict = response_get.json()
        json_data["headerCenter"] = "header center value"
        response_save: Response = self.api().save_setting(feature="header-footer", scope=self.scope, data=json_data)

        # Assert
        self.assertEqual(HTTPStatus.NO_CONTENT, response_save.status_code)

        response: Response = self.api().get_setting_content(feature="header-footer", scope=self.scope)
        stored_settings: JsonDict = response.json()

        restore_settings_response: Response = self.api().save_setting(feature="header-footer", scope=self.scope, data=original_settings)
        self.assertEqual(HTTPStatus.NO_CONTENT, restore_settings_response.status_code)

        self.assertEqual("header center value", stored_settings["headerCenter"])

    def test_settings_headerfooter_revisions(self) -> None:
        # Act
        response: Response = self.api().get_setting_revisions(feature="header-footer", scope=self.scope)

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        json_data: list[JsonDict] = response.json()
        for json_entry in json_data:
            self.assertIn("name", json_entry)
            self.assertIn("date", json_entry)
            self.assertIn("author", json_entry)
            self.assertIn("description", json_entry)

            self.assertIsInstance(json_entry["name"], str)
            self.assertIsInstance(json_entry["date"], str)
            self.assertIsInstance(json_entry["author"], str)
            self.assertIsInstance(json_entry["description"], str)

            assert isinstance(json_entry["description"], str)
            self.assertTrue(re.match(r"^Polarion commit .* \[.*\]$", json_entry["description"]))

    def test_settings_download_upload_localization(self) -> None:
        # Act
        download_localization_response: Response = self.api().download_localization_settings(language="de", scope="")

        # Assert
        self.assertEqual(HTTPStatus.OK, download_localization_response.status_code)

        # Act
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(download_localization_response.text)
            temp_file_path: str = temp_file.name

        upload_localization_response: Response = self.api().upload_localization_settings(temp_file.name, "de", scope=self.scope)

        # Clean up
        pathlib.Path(temp_file_path).unlink()

        # Assert
        self.assertEqual(HTTPStatus.OK, upload_localization_response.status_code)
        json_data: list[str] = upload_localization_response.json()
        self.assertEqual(14, len(json_data))
