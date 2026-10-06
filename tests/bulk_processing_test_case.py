"""The base of the cases which need the bulk processing service, and how they skip or fail without it.

The service is optional -- the "Merge all documents into a single PDF" feature is hidden where none is
named -- so a Polarion which names none skips rather than fails. A run which starts the service itself
is configured for these cases and is the only thing which measures them, so there a missing piece is a
failure rather than a skip, the way the WeasyPrint authenticated cases decide it.
"""

from __future__ import annotations

from typing import NoReturn

from tests.bulk_processing_support import configured, requested_by_the_run, service_answers, service_api_key, service_ready
from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.ssrf_support import containerized_run, release_docker


class BulkProcessingTestCase(PdfExporterTestCase):
    """Cases which reach the bulk processing service Polarion names."""

    @classmethod
    def tearDownClass(cls) -> None:
        # the docker client this class opened through the container lookup is given back
        release_docker()
        super().tearDownClass()

    def setUp(self) -> None:
        # asked before the base settings are reinitialised: a Polarion which names no bulk processing
        # service should not pay for that first
        if not configured():
            # the run asked for the service, so a Polarion naming none is a broken run: the property
            # did not reach polarion.properties, and a skip would leave the required check green
            if requested_by_the_run():
                self.fail("the run handed the harness a bulk processing service, but this Polarion does not name it")
            self.skipTest("this Polarion does not name a bulk processing service")
        super().setUp()

    def _unavailable(self, reason: str) -> NoReturn:
        """A missing piece of the harness: a failure where the run owns it, a skip where it does not.

        A run which starts the service itself is configured for these cases and is the only thing which
        measures them, so a skip there would leave a required check green over a run that covered none
        of what it exists to cover. A run against a long-lived server configures none of this and has
        no docker to ask, so it skips.
        """
        if containerized_run():
            self.fail(f"the bulk processing cases cannot run: {reason}")
        self.skipTest(reason)

    def _require_answering(self) -> None:
        if not service_answers():
            self._unavailable("the named bulk processing service does not answer Polarion")

    def _require_ready(self) -> None:
        # a merge converts each document through WeasyPrint, so a service which is not ready would fail
        # every document for a reason which is not the merge
        self._require_answering()
        if not service_ready():
            self._unavailable("the bulk processing service is not ready, it cannot reach WeasyPrint behind it")

    def _require_key(self) -> str:
        key: str | None = service_api_key()
        if key is None:
            self._unavailable("the key the bulk processing service runs with could not be read")
        return key
