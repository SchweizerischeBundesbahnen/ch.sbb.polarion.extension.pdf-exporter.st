"""The bulk processing service, seen from a running Polarion.

The extension calls the bulk processing service to merge several exported documents into a single PDF.
The unit tests of the extension settle the connector's branches with mocks. What they cannot show is
that a real Polarion, configured with a real service, reaches it. That is this case: the address named
in ``polarion.properties`` answers Polarion on its open ``/version`` endpoint.

The service is optional -- the "Merge all documents into a single PDF" feature is hidden where none is
named -- so a Polarion which names none skips rather than fails.
"""

from __future__ import annotations

from tests.bulk_processing_support import configured, service_answers, service_url
from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.ssrf_support import release_docker


class PdfExporterBulkProcessingTest(PdfExporterTestCase):
    """Cases for the bulk processing service the extension merges documents through."""

    @classmethod
    def tearDownClass(cls) -> None:
        # the docker client this class opened through the container lookup is given back
        release_docker()
        super().tearDownClass()

    def setUp(self) -> None:
        # asked before the base settings are reinitialised: a Polarion which names no bulk processing
        # service should not pay for that first
        if not configured():
            self.skipTest("this Polarion does not name a bulk processing service")
        super().setUp()

    def test_the_named_bulk_processing_service_answers_polarion(self) -> None:
        url: str | None = service_url()
        self.assertTrue(service_answers(), f"the bulk processing service at {url} does not answer Polarion on /version")
