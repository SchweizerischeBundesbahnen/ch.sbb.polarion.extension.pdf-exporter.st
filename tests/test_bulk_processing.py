"""The bulk processing service, seen from a running Polarion.

The extension calls the bulk processing service to merge several exported documents into a single PDF.
The unit tests of the extension settle the connector's branches with mocks. What they cannot show is
that a real Polarion, configured with a real service, reaches it and drives its merge lifecycle: a job
is started, documents are added, and the job is finished into one PDF, the API key on every call the
service protects.

Two layers are exercised. The lifecycle cases drive the service directly, with documents made here, so
a defect in the service is told apart from a defect in the extension. The end-to-end case drives the
extension instead: real live documents of the elibrary are merged by the merge job the way the "Merge
all documents into a single PDF" feature does, so the whole path -- export, hand-off, merge -- is
crossed at once.

The service is optional -- the "Merge all documents into a single PDF" feature is hidden where none is
named -- so a Polarion which names none skips rather than fails. A run which starts the service itself
is configured for these cases and is the only thing which measures them, so there a missing piece is a
failure rather than a skip, the way the WeasyPrint authenticated cases decide it.
"""

from __future__ import annotations

import io
import json
from http import HTTPStatus
from typing import TYPE_CHECKING, NoReturn

import pypdf
from python_sbb_polarion.extensions.pdf_exporter import DocumentType

from tests.bulk_processing_support import (
    UNKNOWN_JOB_ID,
    add_document,
    configured,
    delete_job,
    finish_job,
    merge_through_extension,
    request,
    service_answers,
    service_api_key,
    service_enforces_key,
    service_ready,
    service_url,
    start_job,
)
from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.ssrf_support import containerized_run, release_docker


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonList
    from requests import Response

    from tests.bulk_processing_support import FinishOutcome, MergeJobOutcome


WRONG_KEY: str = "a-key-the-service-was-not-started-with"

# real live documents of the elibrary, merged end to end through the extension. Two are enough to show
# a merge combines rather than replaces; each is the location path the export path takes
REAL_DOCUMENTS: list[str] = [
    "Specification/Administration Specification",
    "Specification/Product Specification",
]
# a merge job renders every document through WeasyPrint before combining them, so it is given the same
# room the asynchronous single-document export is
MERGE_JOB_TIMEOUT_IN_SEC: int = 100


def _document(title: str) -> str:
    """A small, self-contained HTML document WeasyPrint turns into a single page."""
    return f"<html><head><meta charset='utf-8'/></head><body><h1>{title}</h1><p>merged by the system tests</p></body></html>"


def _pdf_page_count(pdf_bytes: bytes) -> int:
    """The number of pages in a PDF, read from its bytes."""
    return len(pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)


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

    # ------------------------------------------------------------------ reachability and contract

    def test_the_named_bulk_processing_service_answers_polarion(self) -> None:
        url: str | None = service_url()
        self.assertTrue(service_answers(), f"the bulk processing service at {url} does not answer Polarion on /version")

    def test_version_reports_the_service_contract(self) -> None:
        self._require_answering()

        answer: tuple[int, str] | None = request("GET", "/version")
        if answer is None:
            self._unavailable("the version of the bulk processing service could not be read")
        status: int
        body: str
        status, body = answer
        self.assertEqual(HTTPStatus.OK, status)

        contract: dict[str, object] = json.loads(body)
        for field in ("apiVersion", "python", "bulkProcessingService", "timestamp"):
            self.assertIn(field, contract, f"the version endpoint did not name '{field}': {contract}")
        self.assertIsInstance(contract["apiVersion"], int, "the api version is not a number")
        self.assertTrue(str(contract["bulkProcessingService"]).strip(), "the service names no version of itself")

    # ------------------------------------------------------------------ the merge lifecycle

    def test_a_merge_of_two_documents_returns_one_pdf(self) -> None:
        self._require_ready()
        key: str | None = service_api_key()

        job_id: str | None = start_job(key, "merged-by-the-system-tests.pdf")
        if job_id is None:
            self._unavailable("the bulk processing service did not start a merge job")

        try:
            self.assertEqual(HTTPStatus.ACCEPTED, add_document(job_id, _document("First"), key), "the first document was not accepted")
            self.assertEqual(HTTPStatus.ACCEPTED, add_document(job_id, _document("Second"), key), "the second document was not accepted")

            outcome: FinishOutcome | None = finish_job(job_id, key)
            self.assertIsNotNone(outcome, "the merge job could not be finished")
            assert outcome is not None  # narrows the type after the assertion above
            self.assertEqual(HTTPStatus.OK, outcome.status, "finishing the merge did not succeed")
            self.assertTrue(outcome.is_pdf, "the merge did not return a pdf")
            self.assertEqual(2, outcome.documents_merged, "the merge did not report both documents")
        finally:
            # the job is deleted whichever way the case ends, so a run leaves nothing behind for the
            # TTL cleanup to reach later
            delete_job(job_id, key)

    def test_an_unknown_job_is_not_found(self) -> None:
        self._require_answering()
        key: str | None = service_api_key()

        status: int | None = delete_job(UNKNOWN_JOB_ID, key)
        self.assertEqual(HTTPStatus.NOT_FOUND, status, "an unknown job was not reported as not found")

    # ------------------------------------------------------------------ the merge through the extension

    def test_a_merge_of_real_documents_exports_one_combined_pdf(self) -> None:
        """The extension merges real live documents into one PDF through the bulk processing service.

        The lifecycle cases drive the service with documents made here. This one drives the extension
        end to end: two live documents of the elibrary are exported and combined by the merge job the
        "Merge all documents into a single PDF" feature starts, and the one PDF it returns carries at
        least the pages the two documents produce on their own. The count is read from the documents
        rather than fixed, so a changed template moves the baseline with the output instead of failing.
        """
        self._require_ready()

        expected_pages: int = sum(self._exported_page_count(location_path) for location_path in REAL_DOCUMENTS)

        merge_params: JsonList = [{"projectId": self.project_id, "locationPath": location_path, "documentType": DocumentType.LIVE_DOC} for location_path in REAL_DOCUMENTS]
        merged_pdf: bytes = self._run_merge_job(merge_params)

        self.assertTrue(merged_pdf.startswith(b"%PDF"), "the merge job did not return a pdf")
        merged_pages: int = _pdf_page_count(merged_pdf)
        self.assertGreaterEqual(
            merged_pages,
            expected_pages,
            f"the merged pdf has fewer pages ({merged_pages}) than the documents merged into it ({expected_pages})",
        )

    def _exported_page_count(self, location_path: str) -> int:
        """The pages a single live document produces on its own, exported the way the merge exports it."""
        response: Response = self._convert(self.project_id, location_path)
        self.assertEqual(HTTPStatus.OK, response.status_code, f"the document '{location_path}' could not be exported on its own")
        return _pdf_page_count(response.content)

    def _run_merge_job(self, merge_params: JsonList) -> bytes:
        """Start a merge job, wait for it, and return the merged PDF, the way the async export is driven.

        The status endpoint answers 303 once the merge is ready, so the expected non-2xx replies are
        kept out of the error log the way the other job-driven cases keep theirs.
        """
        with self.suppress_api_errors():
            outcome: MergeJobOutcome = merge_through_extension(self.api(), merge_params, MERGE_JOB_TIMEOUT_IN_SEC)
        self.assertEqual(HTTPStatus.OK, outcome.status, f"the merge job did not return the merged pdf: {outcome.error_message}")
        assert outcome.pdf is not None  # an OK outcome carries the pdf
        return outcome.pdf

    # ------------------------------------------------------------------ the key the endpoints require

    def test_the_merge_endpoints_require_the_api_key(self) -> None:
        # the merge endpoints carry document content, so they are guarded by the key; the open version
        # and probe endpoints are not. This is what makes a missing or wrong key a rejection
        self._require_answering()
        # whether the service enforces a key is a deployment choice, not something a run guarantees: a
        # keyless service rejects nothing, so there is nothing to assert and the case is skipped, in a
        # containerized run as well
        if not service_enforces_key():
            self.skipTest("the bulk processing service was started without a key, so it rejects none")
        self._require_key()

        missing: tuple[int, str] | None = request("POST", "/api/convert/start", api_key=None, json_body={})
        self.assertIsNotNone(missing, "the service did not answer a keyless request")
        assert missing is not None
        self.assertEqual(HTTPStatus.UNAUTHORIZED, missing[0], "a request without a key was not rejected")

        wrong: tuple[int, str] | None = request("POST", "/api/convert/start", api_key=WRONG_KEY, json_body={})
        self.assertIsNotNone(wrong, "the service did not answer a wrongly-keyed request")
        assert wrong is not None
        self.assertEqual(HTTPStatus.UNAUTHORIZED, wrong[0], "a request with a wrong key was not rejected")
