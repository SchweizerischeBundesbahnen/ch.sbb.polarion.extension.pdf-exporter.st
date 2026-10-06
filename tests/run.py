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

The PDF variant tests, the modules named ``test_pdf_variants*``, run only where RUN_PDF_VARIANT_TESTS
is true. CI sets it; a local run leaves them out, as they take long:
        $ RUN_PDF_VARIANT_TESTS=true python tests/run.py --app_url https://<POLARION_URL> --app_token TOKEN
"""

import sys
import unittest

import xmlrunner
from python_sbb_polarion.testing.temp_project import TempProject
from python_sbb_polarion.testing.testcontainers_helper import TestContainersHelper
from python_sbb_polarion.util import abs_path, abs_path_str

from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.pdf_variant_support import GROUP_MODULE_PREFIX, GROUP_VARIABLE, group_requested


def without_group(tests: unittest.TestSuite) -> unittest.TestSuite:
    """The tests of a suite, those of the modules of the PDF variant group left out."""
    kept = unittest.TestSuite()
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            kept.addTest(without_group(test))
        elif not type(test).__module__.rpartition(".")[2].startswith(GROUP_MODULE_PREFIX):
            kept.addTest(test)
    return kept


# find and load tests
loader = unittest.TestLoader()
suite = loader.discover(abs_path_str("."))
if not group_requested():
    sys.stderr.write(f"The PDF variant tests are left out; set {GROUP_VARIABLE}=true to run them\n")
    suite = without_group(suite)

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
