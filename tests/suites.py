"""The suites of the system tests: which tests a run takes.

A test class states its suite in ``SUITE``, a class which states none belongs to ``default``:

* ``default``: the tests which need Polarion and the WeasyPrint service alone.
* ``bulk``: the tests which need the bulk processing service too.
* ``verapdf``: the PDF variant tests, which validate dozens of exports with veraPDF and take long.

A run names its suites in ``SYSTEM_TEST_SUITE``, separated by commas, or ``all`` for every test. Where it names none,
it runs ``default``, so a local run needs no bulk processing service and leaves out the long PDF variant tests. CI runs
``default,bulk`` and ``verapdf`` apart, the nightly run ``all``.

A test which states a suite of no other name fails the run before it starts, so no run leaves it out unnoticed.
"""

from __future__ import annotations

import os
import unittest
from typing import Final


SUITE_VARIABLE: Final = "SYSTEM_TEST_SUITE"

DEFAULT: Final = "default"
BULK: Final = "bulk"
VERAPDF: Final = "verapdf"
SUITES: Final = (DEFAULT, BULK, VERAPDF)

# Every suite, as a run names them together
ALL: Final = "all"


def requested_suites() -> set[str]:
    """The suites this run asks for: every one for ``all``, ``default`` where it names none."""
    names: set[str] = {name.strip().lower() for name in os.environ.get(SUITE_VARIABLE, "").split(",") if name.strip()}
    if ALL in names:
        return set(SUITES)
    return names or {DEFAULT}


def suite_of(test: unittest.TestCase) -> str:
    """The suite the class of the test states, ``default`` where it states none."""
    suite: object = getattr(type(test), "SUITE", DEFAULT)
    return suite if isinstance(suite, str) else DEFAULT


def tests_of(tests: unittest.TestSuite, suites: set[str]) -> unittest.TestSuite:
    """The tests of a test suite which belong to the given suites."""
    kept = unittest.TestSuite()
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            kept.addTest(tests_of(test, suites))
        elif suite_of(test) in suites:
            kept.addTest(test)
    return kept


def of_no_suite(tests: unittest.TestSuite) -> set[str]:
    """The test classes, by module, which state a suite of no other name, so that no run would take them."""
    names: set[str] = set()
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            names |= of_no_suite(test)
        elif suite_of(test) not in SUITES:
            names.add(f"{type(test).__module__}.{type(test).__name__} ({suite_of(test)})")
    return names
