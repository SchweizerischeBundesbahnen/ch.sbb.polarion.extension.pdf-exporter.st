"""Test runner for system tests.

This module discovers and runs all system tests.
It supports both external Polarion server mode and Docker test container mode.

Test Modes:
    - External Server: Requires APP_URL and APP_TOKEN environment variables
    - Docker Container: Requires TC_POLARION_IMAGE_NAME environment variable

Example:
    Run against external Polarion server:
        $ python tests/run.py --app_url https://<POLARION_URL> --app_token TOKEN

    Run with Docker test container:
        $ python tests/run.py --tc_polarion_image_name polarion:POLARION_VERSION
"""

import os
import sys
import unittest
from http import HTTPStatus
from typing import TYPE_CHECKING

import xmlrunner
from python_sbb_polarion.testing.temp_project import TempProject
from python_sbb_polarion.testing.testcontainers_helper import TestContainersHelper
from python_sbb_polarion.util import abs_path, abs_path_str

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.extensions.admin_utility import PolarionAdminUtilityApi
    from requests import Response


# find and load tests
loader = unittest.TestLoader()
suite = loader.discover(abs_path_str("."))

testcontainers_helper = TestContainersHelper()
testcontainers_helper.create_test_container_if_required("pdf-exporter")

# The WeasyPrint service is reached with an API key where the run configures one. Polarion holds the
# key in a secret, and reads it once, so the record is written before the first export.
weasyprint_api_key: str | None = os.environ.get("WEASYPRINT_API_KEY")
if weasyprint_api_key:
    record_name: str = os.environ.get("WEASYPRINT_API_KEY_SECRET", "weasyprint.api.key")
    admin_utility: PolarionAdminUtilityApi = PdfExporterTestCase.create_extension_api("admin-utility")
    stored: Response = admin_utility.create_vault_record(record_name, "weasyprint", weasyprint_api_key)
    # A run whose key never reached the secret fails every export it has, on a message about the
    # secret rather than about the run. It is said here instead, once, where the reason is known.
    # Neither the name nor the key is printed: the name comes from the environment and the key is
    # masked by the job which minted it.
    if stored.status_code not in (HTTPStatus.OK, HTTPStatus.CREATED, HTTPStatus.NO_CONTENT):
        message: str = f"The API key of the WeasyPrint service could not be stored in its Polarion secret: HTTP {stored.status_code}, {stored.text[:400]}"
        raise SystemExit(message)
    read_back: Response = admin_utility.get_vault_record(record_name)
    if read_back.status_code != HTTPStatus.OK or not read_back.json().get("password"):
        raise SystemExit(f"The Polarion secret of the WeasyPrint service is empty after it was written: HTTP {read_back.status_code}")
    sys.stdout.write("The API key of the WeasyPrint service is stored in its Polarion secret\n")

elibrary = TempProject("elibrary", "E-Library", "pdf_exporter_elibrary_st", abs_path("../test-data/project-template/pdf_exporter_elibrary_st"))
PdfExporterTestCase.set_elibrary(elibrary)

try:
    # run tests
    result = xmlrunner.XMLTestRunner(verbosity=2).run(suite)
    # Exit with non-zero status if tests failed or had errors
    if not result.wasSuccessful():
        sys.exit(1)
finally:
    elibrary.tear_down()
    testcontainers_helper.tear_down()
