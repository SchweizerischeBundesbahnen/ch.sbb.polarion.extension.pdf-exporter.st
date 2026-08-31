"""The API key and the certificate of the WeasyPrint service, seen from a running Polarion.

The unit tests of the extension settle every branch of the decision with mocks: the header is set or
not set, a 401 is reported as one of two causes, a key is refused over plain http. What they cannot
show is the other half, and that is what these cases are for: a real header, on a real TLS connection,
accepted or refused by the real service.

The export with attachments needs no case of its own. Both endpoints attach the key in one place,
``sendConvertingRequest``, and ``test_run_attachments`` exercises the multipart endpoint in the same
run, so it already crosses the authenticated path.

Two levers move while Polarion runs, since neither the properties nor the secret can: the service is
recreated with a different key, and the authority is taken out of the truststore. Everything else
would cost a Polarion, so it belongs to a run configured for it.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.ssrf_support import release_docker
from tests.weasyprint_support import (
    api_key_secret_name,
    authenticated_over_tls,
    ca_in_truststore,
    ca_removed,
    service_answers,
    service_container,
    service_log_lines,
    service_restartable,
    service_running_with,
    service_url,
    trusted_ca_alias,
)


if TYPE_CHECKING:
    from requests import Response


DOCUMENT: str = "<html><head><meta charset='utf-8'/></head><body><p>authenticated export</p></body></html>"
REJECTION_LOGGED: str = "Rejected unauthenticated request"
OTHER_KEY: str = "a-key-the-service-was-not-started-with"


class PdfExporterWeasyPrintAuthTest(PdfExporterTestCase):
    """Cases for the API key and the certificate of the WeasyPrint service."""

    @classmethod
    def tearDownClass(cls) -> None:
        # the client this class opened through the container lookup is given back
        release_docker()
        super().tearDownClass()

    def setUp(self) -> None:
        # asked before the settings of the base class are reinitialised: a run which cannot reach an
        # authenticated service should not pay for that first
        if not authenticated_over_tls():
            self.skipTest("this Polarion does not name the WeasyPrint service over https with a configured key")
        super().setUp()

    def _require_trusted_authority(self) -> str:
        """The alias holding the authority of the service, or a skip naming what could not be found."""
        alias: str | None = trusted_ca_alias()
        if not ca_in_truststore(alias):
            self.skipTest("the truststore does not hold the authority which signed the certificate of the service")
        return str(alias)

    def _require_restartable_service(self) -> None:
        reason: str | None = service_restartable()
        if reason is not None:
            self.skipTest(f"the service cannot be recreated: {reason}")

    def _export(self, print_error: bool = True) -> Response:
        # the printing is decided here rather than by a wrapper: _convert_html sets it from this
        # argument and puts it back to True, so a surrounding suppression would never be seen
        return self._convert_html(self.api(), html=DOCUMENT, print_error=print_error)

    def _failed_export_message(self) -> str:
        response: Response = self._export(print_error=False)
        self.assertEqual(HTTPStatus.INTERNAL_SERVER_ERROR, response.status_code, "an export which cannot authenticate must not report success")
        return str(response.json().get("message", ""))

    def _weasyprint_status(self) -> list[dict[str, str]]:
        response: Response = self.api().check_weasyprint()
        self.assertEqual(HTTPStatus.OK, response.status_code)
        return [entry for entry in response.json() if entry["name"] == "WeasyPrint Service"]

    # ------------------------------------------------------------------ the configuration itself

    def test_the_environment_is_the_authenticated_one(self) -> None:
        # the guard the other cases lean on: an address which is https and a secret which is named
        self.assertTrue((service_url() or "").lower().startswith("https://"), "the service is not named over https")
        self.assertTrue(api_key_secret_name(), "no secret is named as the API key of the service")
        self.assertTrue(service_answers(), "the service does not answer Polarion")

    def test_an_export_succeeds_over_the_authenticated_transport(self) -> None:
        response: Response = self._export()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertTrue(response.content.startswith(b"%PDF"), "the export did not return a pdf")

    # ------------------------------------------------------------------ the key the service holds

    def test_a_key_the_service_does_not_hold_is_reported_as_rejected(self) -> None:
        self._require_restartable_service()

        with service_running_with(OTHER_KEY) as answering:
            self.assertTrue(answering, "the service did not come back with the other key")
            message: str = self._failed_export_message()

        self.assertIn("rejected the configured API key", message, f"the export did not name the rejected key: {message}")

    def test_the_service_says_nothing_about_the_key_it_refused(self) -> None:
        # the credential at risk is the one which arrives in the header, which is the key Polarion
        # holds. It is read before the service is given another one, since afterwards the container
        # carries the other key and the value under test would be gone
        self._require_restartable_service()
        refused_key: str = self._stored_key_placeholder()

        with service_running_with(OTHER_KEY) as answering:
            self.assertTrue(answering, "the service did not come back with the other key")
            self._failed_export_message()
            rejections: int = service_log_lines(REJECTION_LOGGED)
            # the service may hold several keys, and only one of them travels in a header, so each
            # one is looked for on its own: the joined list would never appear in a log
            leaked: int = sum(service_log_lines(key) for key in (part.strip() for part in refused_key.split(",")) if key)

        self.assertGreater(rejections, 0, "the service did not log the refusal")
        self.assertEqual(0, leaked, "the service wrote the key it refused into its log")

    def test_the_status_page_stays_green_while_the_key_is_refused(self) -> None:
        # the version endpoint carries no key, so it cannot see the refusal. That is why the
        # configuration status has its own check for a key over plain http, and why a green status
        # here is not evidence that an export would work
        self._require_restartable_service()

        with service_running_with(OTHER_KEY) as answering:
            self.assertTrue(answering, "the service did not come back with the other key")
            entries: list[dict[str, str]] = self._weasyprint_status()

        self.assertTrue(entries, "the status says nothing about the WeasyPrint service")
        self.assertEqual("OK", entries[0]["status"], "this case stands on the status not seeing a refused key")

    def test_a_key_which_is_one_of_several_is_accepted(self) -> None:
        # what a rotation looks like: the service holds the next key and the current one, so the
        # stored key keeps working while it is replaced
        self._require_restartable_service()

        with service_running_with(f"{OTHER_KEY},{self._stored_key_placeholder()}") as answering:
            self.assertTrue(answering, "the service did not come back with two keys")
            response: Response = self._export()

        self.assertEqual(HTTPStatus.OK, response.status_code, "a key listed beside another one was refused")

    def test_a_service_without_a_key_ignores_the_one_it_is_sent(self) -> None:
        # a deployment which turns authentication off must not break the exports of a Polarion which
        # still sends a key
        self._require_restartable_service()

        with service_running_with(None) as answering:
            self.assertTrue(answering, "the service did not come back without a key")
            response: Response = self._export()

        self.assertEqual(HTTPStatus.OK, response.status_code, "an unexpected header broke the export")

    def _stored_key_placeholder(self) -> str:
        """The key Polarion sends, taken from the service it currently authenticates against.

        The value is never read out of Polarion: the secret is not readable through the API, and the
        service it talks to today is the one holding the matching key.
        """
        container_keys: str | None = self._current_service_keys()
        if not container_keys:
            self.skipTest("the key the service runs with could not be read")
        return container_keys

    def _current_service_keys(self) -> str | None:
        container: Any = service_container()
        if container is None:
            return None
        return next((value.partition("=")[2] for value in container.attrs["Config"]["Env"] if value.startswith("API_KEY=")), None)

    # ------------------------------------------------------------------ the certificate

    def test_an_untrusted_certificate_is_reported_by_the_status(self) -> None:
        # the truststore is read per request, so this case needs no restart. The export itself says
        # only that something failed, the reason reaches the status page
        alias: str = self._require_trusted_authority()

        with ca_removed(alias) as removed:
            self.assertTrue(removed, "the authority could not be taken out of the truststore")
            response: Response = self._export(print_error=False)
            entries: list[dict[str, str]] = self._weasyprint_status()

        self.assertEqual(HTTPStatus.INTERNAL_SERVER_ERROR, response.status_code, "an export over an untrusted certificate must not report success")
        self.assertTrue(entries, "the status says nothing about the WeasyPrint service")
        self.assertEqual("ERROR", entries[0]["status"], "the status did not report the untrusted certificate")
        self.assertIn("SSLHandshakeException", entries[0]["details"], f"the status did not name the handshake: {entries[0]['details']}")

    def test_the_trust_comes_back_with_the_authority(self) -> None:
        # the other half of the case above: the removal is what failed the export, not the run itself
        self._require_trusted_authority()

        response: Response = self._export()

        self.assertEqual(HTTPStatus.OK, response.status_code)
        self.assertEqual("OK", self._weasyprint_status()[0]["status"])
