from __future__ import annotations

import json
import time
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict, JsonList
    from requests import Response


PRODUCT_SPECIFICATION = "Product Specification"
CATALOG_SPECIFICATION = "Catalog Specification"


class PdfExporterStylePackageTest(PdfExporterTestCase):
    """Tests for style package management."""

    _style_package_names_global_to_cleanup: ClassVar[list[str]] = []
    _style_package_names_test_scope_to_cleanup: ClassVar[list[str]] = []

    def test_get_style_packages_names(self) -> None:
        test_scope_package_name: str = self.create_style_package(self.scope)
        global_scope_package_name: str = self.create_style_package()

        response: Response = self.api().get_style_packages_names()
        self.assertEqual(HTTPStatus.OK, response.status_code)
        global_packages_set: set[str] = {(entry["name"]) for entry in json.loads(response.content)}
        self.assertTrue(global_scope_package_name in global_packages_set)

        self.assertTrue("" in {(entry["scope"]) for entry in json.loads(response.content)})

        response_test_scope: Response = self.api().get_style_packages_names(self.scope)
        self.assertEqual(HTTPStatus.OK, response_test_scope.status_code)
        test_scope_packages_set: set[str] = {(entry["name"]) for entry in json.loads(response_test_scope.content)}
        self.assertTrue(test_scope_package_name in test_scope_packages_set)

        # check that test scope contains all global entries
        self.assertTrue(global_packages_set.issubset(test_scope_packages_set))

    def test_get_suitable_style_package_names_order(self) -> None:
        # remember initially available styled packages for our document
        data: JsonList = [
            {
                "projectId": self.project_id,
                "spaceId": "Specification",
                "documentName": PRODUCT_SPECIFICATION,
            }
        ]
        response: Response = self.api().find_suitable_style_package_names(data=data)
        self.assertEqual(HTTPStatus.OK, response.status_code)
        initial_suitable_packages: list[str | JsonDict] = [entry["name"] for entry in json.loads(response.content)]

        # create several new styled packages in global & test scope
        global_scope_package_names: list[str] = [
            self.create_style_package(name_prefix="abc"),
            self.create_style_package(name_prefix="Vbn"),
            self.create_style_package(name_prefix="jas"),
        ]
        test_scope_package_names: list[str] = [
            self.create_style_package(self.scope, name_prefix="xyz"),
            self.create_style_package(self.scope, name_prefix="rty"),
            self.create_style_package(self.scope, name_prefix="Cvb"),
        ]

        # check that all those items are now available for our document
        response_updated: Response = self.api().find_suitable_style_package_names(data=data)
        updated_suitable_packages: list[str | JsonDict] = [entry["name"] for entry in json.loads(response_updated.content)]
        self.assertEqual(len(initial_suitable_packages) + 6, len(updated_suitable_packages))

        # extract just those items which were created in scope of this test
        just_created_packages: list[str | JsonDict] = [item for item in updated_suitable_packages if item in test_scope_package_names + global_scope_package_names]
        # and check whether they are sorted alphabetically, because by default they must have the same weight (50.0)
        self.assertTrue(just_created_packages == sorted(just_created_packages, key=lambda x: x.lower()))  # type: ignore[union-attr]

        # modify weights for our items
        self.api().save_style_package_weights(
            data=[
                {"name": global_scope_package_names[0], "scope": "", "weight": 1},
                {"name": global_scope_package_names[1], "scope": "", "weight": 2},
                {"name": global_scope_package_names[2], "scope": "", "weight": 3},
                {
                    "name": test_scope_package_names[0],
                    "scope": self.scope,
                    "weight": 4,
                },
                {
                    "name": test_scope_package_names[1],
                    "scope": self.scope,
                    "weight": 5,
                },
                {
                    "name": test_scope_package_names[2],
                    "scope": self.scope,
                    "weight": 6,
                },
            ]
        )

        # re-read packages
        response_modified: Response = self.api().find_suitable_style_package_names(data=data)
        modified_weight_suitable_packages: list[str | JsonDict] = [entry["name"] for entry in json.loads(response_modified.content)]

        # check that packages count haven't changed
        self.assertEqual(len(updated_suitable_packages), len(modified_weight_suitable_packages))

        # check new items order according to new weight values
        just_modified_weight_packages: list[str | JsonDict] = [item for item in modified_weight_suitable_packages if item in test_scope_package_names + global_scope_package_names]
        self.assertEqual(
            [
                test_scope_package_names[2],
                test_scope_package_names[1],
                test_scope_package_names[0],
                global_scope_package_names[2],
                global_scope_package_names[1],
                global_scope_package_names[0],
            ],
            just_modified_weight_packages,
        )

    def test_filter_suitable_style_package_names(self) -> None:
        # create a new styled package
        test_package_name: str = self.create_style_package(self.scope)
        # it must be available for all documents by default

        product_specification_data: JsonList = [
            {
                "projectId": self.project_id,
                "spaceId": "Specification",
                "documentName": PRODUCT_SPECIFICATION,
            }
        ]
        doc_1_suitable_packages: list[str | JsonDict] = json.loads(self.api().find_suitable_style_package_names(data=product_specification_data).content)

        catalog_specification_data: JsonList = [
            {
                "projectId": self.project_id,
                "spaceId": "Specification",
                "documentName": CATALOG_SPECIFICATION,
            }
        ]
        doc_2_suitable_packages: list[str | JsonDict] = json.loads(self.api().find_suitable_style_package_names(data=catalog_specification_data).content)

        self.assertIsNotNone(
            next(
                (entry for entry in doc_1_suitable_packages if entry["name"] == test_package_name),  # type: ignore[index]
                None,
            )
        )
        self.assertIsNotNone(
            next(
                (entry for entry in doc_2_suitable_packages if entry["name"] == test_package_name),  # type: ignore[index]
                None,
            )
        )

        # now set specific matching query
        package_data: JsonDict = json.loads(self.api().get_style_package(test_package_name, scope=self.scope).content)
        package_data["matchingQuery"] = "title:Catalog*"
        self.api().save_style_package(test_package_name, package_data, self.scope)

        # now it available only for matched documents
        doc_1_suitable_packages_updated: list[str | JsonDict] = json.loads(self.api().find_suitable_style_package_names(data=product_specification_data).content)
        doc_2_suitable_packages_updated: list[str | JsonDict] = json.loads(self.api().find_suitable_style_package_names(data=catalog_specification_data).content)
        self.assertIsNone(
            next(
                (entry for entry in doc_1_suitable_packages_updated if entry["name"] == test_package_name),  # type: ignore[index]
                None,
            )
        )
        self.assertIsNotNone(
            next(
                (entry for entry in doc_2_suitable_packages_updated if entry["name"] == test_package_name),  # type: ignore[index]
                None,
            )
        )

    def test_get_weights(self) -> None:
        response: Response = self.api().get_style_package_weights(scope=self.scope)
        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertIsNotNone(response.content)

    def test_update_weights(self) -> None:
        # create a new styled package
        package_name: str = self.create_style_package(self.scope)

        # check that by default weight was set to 50.0
        weight_infos: JsonList = json.loads(self.api().get_style_package_weights(scope=self.scope).content)
        weight_info: JsonDict | None = next((entry for entry in weight_infos if isinstance(entry, dict) and entry.get("name") == package_name), None)
        assert weight_info is not None
        assert isinstance(weight_info, dict)
        self.assertEqual(50.0, weight_info["weight"])

        # update weight
        new_weights_data: JsonList = [{"name": weight_info["name"], "scope": self.scope, "weight": 17.9}]
        response: Response = self.api().save_style_package_weights(data=new_weights_data)
        self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

        # check new value persisted
        updated_weight_infos: JsonList = json.loads(self.api().get_style_package_weights(scope=self.scope).content)
        updated_weight_info: JsonDict | None = next(
            (entry for entry in updated_weight_infos if isinstance(entry, dict) and entry.get("name") == package_name),
            None,
        )
        assert updated_weight_info is not None
        assert isinstance(updated_weight_info, dict)
        self.assertEqual(17.9, updated_weight_info["weight"])

    def create_style_package(self, scope: str = "", name_prefix: str = "ST_package") -> str:
        new_name: str = f"{name_prefix}_{time.time_ns()}"
        data: JsonDict = {}
        response: Response = self.api().save_style_package(new_name, data, scope)
        self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)
        if not scope:
            self._style_package_names_global_to_cleanup.append(new_name)
        else:
            self._style_package_names_test_scope_to_cleanup.append(new_name)
        return new_name

    def tearDown(self) -> None:
        for name in self._style_package_names_global_to_cleanup:
            self.api().delete_style_package(name, scope="")
        for name in self._style_package_names_test_scope_to_cleanup:
            self.api().delete_style_package(name, scope=self.scope)

        # tearDown called after each test method so we have to clear lists here
        # to avoid double deletion attempts
        self._style_package_names_global_to_cleanup.clear()
        self._style_package_names_test_scope_to_cleanup.clear()
