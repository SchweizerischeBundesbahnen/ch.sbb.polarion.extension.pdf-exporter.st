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
        default_response: Response = self.api().get_setting_default_content(feature="css")

        # Assert
        self.assertEqual(HTTPStatus.OK, response.status_code)
        json_settings: JsonDict = response.json()
        self.assertIn("bundleTimestamp", json_settings)
        self.assertIn("css", json_settings)
        self.assertIsInstance(json_settings["bundleTimestamp"], str)
        # The setup stores a copy of the default CSS, which is read as no custom CSS: the export applies the default CSS once.
        self.assertEqual("", json_settings["css"])
        self.assertFalse(json_settings["disableDefaultCss"])

        self.assertEqual(HTTPStatus.OK, default_response.status_code)
        default_css: str = default_response.json()["css"]
        self.assertIn("Arial", default_css)
        self.assertIn("/polarion/ria/fonts/opensans/OpenSans-Regular.ttf", default_css)

    def test_settings_created_without_content_start_empty(self) -> None:
        expected_contents: dict[str, JsonDict] = {
            "css": {"css": "", "disableDefaultCss": False},
            "cover-page": {"templateHtml": "", "templateCss": "", "useCustomValues": False},
        }
        for feature, expected in expected_contents.items():
            with self.subTest(feature=feature):
                # Act
                url: str = f"{self.api().rest_api_url}/settings/{feature}/names/Created without content/content"
                params: dict[str, str] = {
                    "scope": self.scope,
                }
                create_response: Response = self.api().polarion_connection.api_request_put(url, params=params)
                try:
                    content_response: Response = self.api().get_setting_content(feature=feature, name="Created without content", scope=self.scope)
                finally:
                    self.api().delete_setting(feature=feature, name="Created without content", scope=self.scope)

                # Assert
                self.assertEqual(HTTPStatus.NO_CONTENT, create_response.status_code)
                self.assertEqual(HTTPStatus.OK, content_response.status_code)
                content: JsonDict = content_response.json()
                for key, value in expected.items():
                    self.assertEqual(value, content[key], key)

    def test_settings_cover_page_template_content(self) -> None:
        # Act
        names_url: str = f"{self.api().rest_api_url}/settings/cover-page/templates"
        names_response: Response = self.api().polarion_connection.api_request_get(names_url)
        self.assertEqual(HTTPStatus.OK, names_response.status_code)
        template_names: list[str] = names_response.json()

        # Assert
        self.assertIn("English", template_names)
        for template_name in template_names:
            with self.subTest(template=template_name):
                content_url: str = f"{self.api().rest_api_url}/settings/cover-page/templates/{template_name}/content"
                content_response: Response = self.api().polarion_connection.api_request_get(content_url)
                self.assertEqual(HTTPStatus.OK, content_response.status_code)
                content: JsonDict = content_response.json()
                self.assertTrue(content["templateHtml"])
                self.assertRegex(str(content["defaultHash"]), r"^[0-9a-f]{64}$")

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
