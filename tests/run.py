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

import sys
import unittest

import xmlrunner
from python_sbb_polarion.testing.temp_project import TempProject
from python_sbb_polarion.testing.testcontainers_helper import TestContainersHelper
from python_sbb_polarion.util import abs_path, abs_path_str

from tests.pdf_exporter_test_case import PdfExporterTestCase


# find and load tests
loader = unittest.TestLoader()
suite = loader.discover(abs_path_str("."))

testcontainers_helper = TestContainersHelper()
testcontainers_helper.create_test_container_if_required("pdf-exporter")

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
