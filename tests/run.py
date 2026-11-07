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

SYSTEM_TEST_SUITE names the suites to run, separated by commas, or ``all``, see tests/suites.py. Where it names none,
the run takes ``default``: no test of the bulk processing service, and none of the PDF variant tests, which take long:
        $ SYSTEM_TEST_SUITE=default,bulk python tests/run.py --app_url https://<POLARION_URL> --app_token TOKEN

SYSTEM_TEST_MODULES, a comma-separated list of module names, runs only those modules of the suite. A name which
matches no module of the suite fails the run, so a renamed module cannot leave it empty:
        $ SYSTEM_TEST_MODULES=test_convert,test_fit_to_page python tests/run.py --app_url https://<POLARION_URL> --app_token TOKEN
"""

import os
import sys
import unittest

import xmlrunner
from python_sbb_polarion.testing.temp_project import TempProject
from python_sbb_polarion.testing.testcontainers_helper import TestContainersHelper
from python_sbb_polarion.util import abs_path, abs_path_str

from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.suites import ALL, SUITE_VARIABLE, SUITES, of_no_suite, requested_suites, tests_of


def only_modules(tests: unittest.TestSuite, modules: set[str]) -> unittest.TestSuite:
    """The tests of a suite which belong to the given modules."""
    kept = unittest.TestSuite()
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            kept.addTest(only_modules(test, modules))
        elif type(test).__module__.rpartition(".")[2] in modules:
            kept.addTest(test)
    return kept


def modules_of(tests: unittest.TestSuite) -> set[str]:
    """The names of the modules the tests of a suite belong to."""
    names: set[str] = set()
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            names |= modules_of(test)
        else:
            names.add(type(test).__module__.rpartition(".")[2])
    return names


# find and load tests
loader = unittest.TestLoader()
suite = loader.discover(abs_path_str("."))
# A test of a suite of no other name would be left out of every run
lost_tests = of_no_suite(suite)
if lost_tests:
    sys.exit(f"Tests state a suite of no other name ({', '.join(SUITES)}): {', '.join(sorted(lost_tests))}")
requested = requested_suites()
unknown_suites = requested - set(SUITES)
if unknown_suites:
    sys.exit(f"{SUITE_VARIABLE} names no suite: {', '.join(sorted(unknown_suites))}; the suites are {', '.join((*SUITES, ALL))}")
suite = tests_of(suite, requested)
sys.stderr.write(f"Suites of this run: {', '.join(sorted(requested))}; {SUITE_VARIABLE} names them\n")
requested_modules = {name.strip() for name in os.environ.get("SYSTEM_TEST_MODULES", "").split(",") if name.strip()}
if requested_modules:
    suite = only_modules(suite, requested_modules)
    missing_modules = requested_modules - modules_of(suite)
    if missing_modules:
        sys.exit(f"SYSTEM_TEST_MODULES names modules with no tests in the suites {', '.join(sorted(requested))}: {', '.join(sorted(missing_modules))}")
    sys.stderr.write(f"Only the modules of SYSTEM_TEST_MODULES run: {', '.join(sorted(requested_modules))}\n")

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
