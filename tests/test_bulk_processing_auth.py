"""The API key and the certificates of the bulk processing service, seen from a running Polarion.

A merge crosses two TLS connections, and each is verified by a different party:

- **Polarion to the bulk processing service**, verified by the truststore of the Polarion JVM, with the
  key of ``...bulk.processing.apiKeySecret`` in the header;
- **the bulk processing service to WeasyPrint**, verified by the service itself, through the authority
  ``SSL_CERT_FILE`` names, with the key of ``WEASYPRINT_API_KEY``.

The unit tests of the extension settle the connector with mocks: the header is set or not set, a 401 is
reported as one of two causes, a key is refused over plain http. What they cannot show is the other
half, and that is what these cases are for: a real header, on a real TLS connection, accepted or
refused by the real service, and a service which does or does not trust the WeasyPrint behind it.

The levers are the ones of the WeasyPrint cases (``test_weasyprint_auth``): the service is recreated
with another key, another certificate or no trust of its own, and the authority of its certificate is
taken out of the truststore. The authority is one of its own, not the one of WeasyPrint, so taking it
out breaks the first connection only. That a key is not sent over plain http needs a Polarion started
with an http address, which a run cannot switch to; the unit tests of the connector hold that branch.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any, NoReturn

from python_sbb_polarion.extensions.pdf_exporter import DocumentType

from tests.bulk_processing_support import (
    BULK,
    api_key_secret_name,
    authenticated_over_tls,
    ca_in_truststore,
    ca_removed,
    configured,
    merge_through_extension,
    readiness,
    service_answers,
    service_has_file,
    service_log_lines,
    service_restartable,
    service_running_with,
    service_url,
    trusted_ca_alias,
)
from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.ssrf_support import containerized_run, release_docker


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonList
    from requests import Response

    from tests.bulk_processing_support import MergeJobOutcome


REJECTION_LOGGED: str = "Rejected unauthenticated request"
OTHER_KEY: str = "a-key-the-service-was-not-started-with"
SERVICE_STATUS_NAME: str = "Bulk Processing Service"
# two live documents: the extension hands a job to the service only when it merges more than one, and
# exports a single document itself, so one would cross neither connection under test
MERGED_DOCUMENTS: list[str] = [
    "Specification/Administration Specification",
    "Specification/Product Specification",
]
# what the service logs for a merge it finished, so a case can tell a merge the service made from one
# which never reached it
FINISH_LOGGED: str = '/finish HTTP/1.1" 200'
MERGE_JOB_TIMEOUT_IN_SEC: int = 100
# a certificate signed by the same authority for a name the service is not reached under, provisioned
# beside the real one by the environment (see system-tests.yml); a path inside the service container
OTHER_NAME_CERT: str = "/tls/bulk-other-name.pem"
OTHER_NAME_KEY: str = "/tls/bulk-other-name.key"


class PdfExporterBulkProcessingAuthTest(PdfExporterTestCase):
    """Cases for the API key and the certificates the bulk processing service is reached with."""

    @classmethod
    def tearDownClass(cls) -> None:
        # the client this class opened through the container lookup is given back
        release_docker()
        super().tearDownClass()

    def setUp(self) -> None:
        # asked before the settings of the base class are reinitialised: a run which cannot reach an
        # authenticated service should not pay for that first. The service is optional, so a Polarion
        # naming none skips, the way the other bulk processing cases decide it
        if not configured():
            self.skipTest("this Polarion does not name a bulk processing service")
        if not authenticated_over_tls():
            self._unavailable("this Polarion does not name the bulk processing service over https with a configured key")
        super().setUp()

    def _unavailable(self, reason: str) -> NoReturn:
        """A missing piece of the harness: a failure where the run owns it, a skip where it does not.

        A run which starts the containers itself is configured for the authenticated path, and this
        class is the only thing which measures it. Skipping there would leave the required check green
        over a run which covered none of what it exists to cover. A run against a long-lived server
        configures none of this and has no docker to ask, so it skips.
        """
        if containerized_run():
            self.fail(f"the authenticated bulk processing cases cannot run: {reason}")
        self.skipTest(reason)

    def _require_trusted_authority(self) -> str:
        """The alias holding the authority of the service, or a skip naming what could not be found."""
        alias: str | None = trusted_ca_alias()
        if not ca_in_truststore(alias):
            self._unavailable("the truststore does not hold the authority which signed the certificate of the bulk processing service")
        return str(alias)

    def _require_restartable_service(self) -> None:
        reason: str | None = service_restartable()
        if reason is not None:
            self._unavailable(f"the bulk processing service cannot be recreated: {reason}")

    def _merge(self) -> MergeJobOutcome:
        merge_params: JsonList = [{"projectId": self.project_id, "locationPath": location_path, "documentType": DocumentType.LIVE_DOC} for location_path in MERGED_DOCUMENTS]
        # the job answers 303 once it is ready and 409 where it failed, and both are outcomes a case
        # asserts on, not errors of the run
        with self.suppress_api_errors():
            return merge_through_extension(self.api(), merge_params, MERGE_JOB_TIMEOUT_IN_SEC)

    def _assert_merged_by_the_service(self) -> None:
        """Merge, and assert the pdf came back and the service is what made it.

        A pdf alone is no evidence: an export which never reached the service would return one too, and
        a case standing on it would pass without crossing the connection it names.
        """
        finished_before: int = service_log_lines(FINISH_LOGGED)
        outcome: MergeJobOutcome = self._merge()

        self.assertEqual(HTTPStatus.OK, outcome.status, f"the merge did not succeed: {outcome.error_message}")
        assert outcome.pdf is not None  # an OK outcome carries the pdf
        self.assertTrue(outcome.pdf.startswith(b"%PDF"), "the merge did not return a pdf")
        self.assertGreater(service_log_lines(FINISH_LOGGED), finished_before, "the merge was not made by the bulk processing service")

    def _failed_merge_message(self) -> str:
        outcome: MergeJobOutcome = self._merge()
        self.assertEqual(HTTPStatus.CONFLICT, outcome.status, "a merge which cannot reach the service must not report success")
        return outcome.error_message

    def _service_status(self) -> list[dict[str, str]]:
        response: Response = self.api().check_bulk_processing()
        self.assertEqual(HTTPStatus.OK, response.status_code)
        return [entry for entry in response.json() if entry["name"] == SERVICE_STATUS_NAME]

    def _stored_key_placeholder(self) -> str:
        """The key Polarion sends, taken from the service it currently authenticates against.

        The value is never read out of Polarion: the secret is not readable through the API, and the
        service it talks to today is the one holding the matching key.
        """
        keys: str | None = BULK.service_api_keys()
        if not keys:
            self._unavailable("the key the bulk processing service runs with could not be read")
        return keys

    # ------------------------------------------------------------------ the configuration itself

    def test_the_environment_is_the_authenticated_one(self) -> None:
        # the guard the other cases lean on: an address which is https and a secret which is named
        self.assertTrue((service_url() or "").lower().startswith("https://"), "the bulk processing service is not named over https")
        self.assertTrue(api_key_secret_name(), "no secret is named as the API key of the bulk processing service")
        self.assertTrue(service_answers(), "the bulk processing service does not answer Polarion")

    def test_a_merge_succeeds_over_the_authenticated_transport(self) -> None:
        self._assert_merged_by_the_service()

    def test_the_status_names_the_service_over_the_authenticated_transport(self) -> None:
        # the status is asked through the same client the merge uses, so an OK here is a handshake the
        # truststore accepted, not a curl which skipped the certificate
        entries: list[dict[str, str]] = self._service_status()

        self.assertTrue(entries, "the status says nothing about the bulk processing service")
        self.assertNotEqual("ERROR", entries[0]["status"], f"the status reports the service unreachable: {entries[0]['details']}")

    # ------------------------------------------------------------------ the key the service holds

    def test_a_key_the_service_does_not_hold_is_reported_as_rejected(self) -> None:
        self._require_restartable_service()

        with service_running_with(OTHER_KEY) as answering:
            self.assertTrue(answering, "the service did not come back with the other key")
            message: str = self._failed_merge_message()

        self.assertIn("rejected the configured API key", message, f"the merge did not name the rejected key: {message}")

    def test_the_service_says_nothing_about_the_key_it_refused(self) -> None:
        # the credential at risk is the one which arrives in the header, which is the key Polarion
        # holds. It is read before the service is given another one, since afterwards the container
        # carries the other key and the value under test would be gone
        self._require_restartable_service()
        refused_key: str = self._stored_key_placeholder()

        with service_running_with(OTHER_KEY) as answering:
            self.assertTrue(answering, "the service did not come back with the other key")
            self._failed_merge_message()
            rejections: int = service_log_lines(REJECTION_LOGGED)
            # the service may hold several keys, and only one of them travels in a header, so each
            # one is looked for on its own: the joined list would never appear in a log
            leaked: int = sum(service_log_lines(key) for key in (part.strip() for part in refused_key.split(",")) if key)

        self.assertGreater(rejections, 0, "the service did not log the refusal")
        self.assertEqual(0, leaked, "the service wrote the key it refused into its log")

    def test_the_status_page_stays_green_while_the_key_is_refused(self) -> None:
        # the version endpoint carries no key, so it cannot see the refusal, which is why a green
        # status here is not evidence that a merge would work
        self._require_restartable_service()

        with service_running_with(OTHER_KEY) as answering:
            self.assertTrue(answering, "the service did not come back with the other key")
            entries: list[dict[str, str]] = self._service_status()

        self.assertTrue(entries, "the status says nothing about the bulk processing service")
        self.assertNotEqual("ERROR", entries[0]["status"], "this case stands on the status not seeing a refused key")

    def test_a_key_which_is_one_of_several_is_accepted(self) -> None:
        # what a rotation looks like: the service holds the next key and the current one, so the
        # stored key keeps working while it is replaced
        self._require_restartable_service()

        with service_running_with(f"{OTHER_KEY},{self._stored_key_placeholder()}") as answering:
            self.assertTrue(answering, "the service did not come back with two keys")
            # asked inside the block: the log is the one of the service holding both keys
            self._assert_merged_by_the_service()

    def test_a_service_without_a_key_ignores_the_one_it_is_sent(self) -> None:
        # a deployment which turns authentication off must not break the merges of a Polarion which
        # still sends a key
        self._require_restartable_service()

        with service_running_with(None) as answering:
            self.assertTrue(answering, "the service did not come back without a key")
            self._assert_merged_by_the_service()

    # ------------------------------------------------------------------ the certificate of the service

    def test_an_untrusted_certificate_is_reported_by_the_status(self) -> None:
        # the truststore is read per request, so this case needs no restart. The merge itself says only
        # that it failed, the reason reaches the status page
        alias: str = self._require_trusted_authority()

        with ca_removed(alias) as removed:
            self.assertTrue(removed, "the authority could not be taken out of the truststore")
            self._failed_merge_message()
            entries: list[dict[str, str]] = self._service_status()

        self.assertTrue(entries, "the status says nothing about the bulk processing service")
        self.assertEqual("ERROR", entries[0]["status"], "the status did not report the untrusted certificate")
        self.assertIn("SSLHandshakeException", entries[0]["details"], f"the status did not name the handshake: {entries[0]['details']}")

    def test_the_trust_comes_back_with_the_authority(self) -> None:
        # the other half of the case above: the removal is what failed the merge, not the run itself
        self._require_trusted_authority()

        self._assert_merged_by_the_service()
        self.assertNotEqual("ERROR", self._service_status()[0]["status"])

    def test_a_certificate_for_another_name_is_refused(self) -> None:
        # a certificate the truststore would accept, for a name the service is not reached under: a
        # client which checked the chain and not the name would take it
        self._require_restartable_service()
        if not (service_has_file(OTHER_NAME_CERT) and service_has_file(OTHER_NAME_KEY)):
            self._unavailable(f"the environment provisioned no certificate for another name at {OTHER_NAME_CERT}")

        with service_running_with(BULK.service_api_keys(), {"TLS_CERT_FILE": OTHER_NAME_CERT, "TLS_KEY_FILE": OTHER_NAME_KEY}) as answering:
            self.assertTrue(answering, "the service did not come back with the certificate for another name")
            self._failed_merge_message()
            entries: list[dict[str, str]] = self._service_status()

        self.assertTrue(entries, "the status says nothing about the bulk processing service")
        self.assertEqual("ERROR", entries[0]["status"], "the status did not report the certificate for another name")
        self.assertIn("SSLHandshakeException", entries[0]["details"], f"the status did not name the handshake: {entries[0]['details']}")

    # ------------------------------------------------------------------ the service's trust of WeasyPrint

    def test_the_service_trusts_the_certificate_of_weasyprint(self) -> None:
        # the second connection is verified by the service, not by Polarion, and with stricter rules
        # than the JVM applies: an authority without keyUsage passes the truststore and fails here, so
        # a service which reads WeasyPrint as unavailable is named rather than left to fail the merges
        answer: tuple[int, dict[str, Any]] | None = readiness()

        self.assertIsNotNone(answer, "the readiness of the bulk processing service could not be read")
        assert answer is not None
        self.assertEqual("available", answer[1].get("weasyprint"), f"the bulk processing service cannot reach WeasyPrint over TLS: {answer[1]}")
        self.assertEqual(HTTPStatus.OK, answer[0], f"the bulk processing service is not ready: {answer[1]}")

    def test_a_service_which_does_not_trust_weasyprint_fails_the_merge(self) -> None:
        # the service trusts WeasyPrint only through SSL_CERT_FILE; without it the second connection is
        # refused, and a merge must fail with a reason rather than hang or return an empty document
        self._require_restartable_service()

        with service_running_with(BULK.service_api_keys(), {"SSL_CERT_FILE": None}) as answering:
            self.assertTrue(answering, "the service did not come back without the authority of WeasyPrint")
            answer: tuple[int, dict[str, Any]] | None = readiness()
            message: str = self._failed_merge_message()

        self.assertIsNotNone(answer, "the readiness of the bulk processing service could not be read")
        assert answer is not None
        self.assertEqual(HTTPStatus.SERVICE_UNAVAILABLE, answer[0], f"a service which cannot verify WeasyPrint reported itself ready: {answer[1]}")
        self.assertEqual("unavailable", answer[1].get("weasyprint"), f"the readiness did not name WeasyPrint: {answer[1]}")
        self.assertTrue(message, "the failed merge gave no reason")
