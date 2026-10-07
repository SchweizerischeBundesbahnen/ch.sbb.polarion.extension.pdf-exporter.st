"""The tokens of Polarion, which tell the bulk processing service who a merge is made for, seen from a running Polarion.

Every call the extension makes for a merge carries a short-lived token Polarion itself issues for the signed-in
user (``X-Polarion-Token``). A service started with ``POLARION_JWKS_URL`` fetches the keys Polarion publishes,
checks the signature of each token, and lets a job be used only by the user it was started for, with a token made
for that very job.

The unit tests of the extension and of the service settle each half with a key of their own. What neither can show is
the two together, and that is what these cases are for: a token a real Polarion signed, accepted by a real service
which read the key set a real Polarion published (which carries a private member as ``null``, something no clean test
key set does), and the refusals the service owes everything else.

What a run cannot do is sign a token of Polarion's outside Polarion, so these cases cover what they can reach from
outside: the merge Polarion signs for itself, and the calls which present no token, a garbage one, or one signed by
somebody else. A token of another user, or for another job, and one which has expired, need the key of Polarion and
stay with the unit tests of the service.

A service which already checks tokens is used as it is. One which does not is recreated with the setting for the
cases which need it, and put back as it was, where the run owns the containers: so the other bulk processing cases keep
running against a service which does not check tokens, since the ones which drive the service by hand from inside
Polarion present a key and no token, and a service which checks tokens would refuse them.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, NoReturn

from python_sbb_polarion.extensions.pdf_exporter import DocumentType

from tests.bulk_processing_support import (
    BULK,
    FORGED_TOKEN_LOGGED,
    INVALID_TOKEN_ANSWER,
    JWKS_HOST_SETTING,
    KEY_SET_UNREACHABLE_ANSWER,
    MISSING_TOKEN_ANSWER,
    UNKNOWN_JOB_ID,
    forged_token,
    job_id_of,
    jwt_required_by_the_run,
    merge_through_extension,
    polarion_jwks_host,
    polarion_jwks_url,
    polarion_key_id,
    service_log_lines,
    service_restartable,
    service_running_with,
    stored_jobs,
    token_answer,
    tokens_enforced,
)
from tests.bulk_processing_test_case import BulkProcessingTestCase
from tests.ssrf_support import containerized_run


if TYPE_CHECKING:
    from collections.abc import Generator

    from python_sbb_polarion.types import JsonList

    from tests.bulk_processing_support import MergeJobOutcome


# two live documents: the extension hands a job to the service only when it merges more than one
MERGED_DOCUMENTS: list[str] = [
    "Specification/Administration Specification",
    "Specification/Product Specification",
]
# what the service logs for a merge it finished, so a case can tell a merge the service made from one which never reached it
FINISH_LOGGED: str = '/finish HTTP/1.1" 200'
MERGE_JOB_TIMEOUT_IN_SEC: int = 100
# an address which resolves nowhere, for the service which cannot fetch the key set
UNREACHABLE_JWKS_URL: str = "http://key-set.invalid/polarion/.well-known/jwks.json"
SETTING: str = "POLARION_JWKS_URL"
SHA256_HEX: re.Pattern[str] = re.compile(r"[0-9a-f]{64}")


class PdfExporterBulkProcessingJwtTest(BulkProcessingTestCase):
    """Cases for a bulk processing service which checks the tokens of Polarion."""

    def _cannot_check(self, reason: str) -> NoReturn:
        """What a case cannot check here: a skip, or a failure where the run says its service checks Polarion tokens.

        A skip leaves the required check green over a run which covered nothing, so a run which says its service checks
        tokens must not be allowed to skip.
        """
        if jwt_required_by_the_run():
            self.fail(f"the Polarion token cases cannot check anything: {reason}")
        self.skipTest(reason)

    def _require_recreatable_service(self) -> str:
        """What a service which does not check tokens yet needs to be made to: the address of the key set to give it.

        Only a run which owns the containers can recreate the service. A run against a long-lived server cannot, and
        recreating a service it did not start would not put it back as it was.
        """
        if not containerized_run():
            self._cannot_check("the service does not check tokens, and a run against a long-lived server cannot recreate it with the setting")
        reason: str | None = service_restartable()
        if reason is not None:
            self._unavailable(f"the bulk processing service cannot be recreated: {reason}")
        jwks_url: str | None = polarion_jwks_url()
        if jwks_url is None:
            self._unavailable("the address of the key set of Polarion is unknown: the container of Polarion was not found and none is named")
        return str(jwks_url)

    @contextmanager
    def _service_checking_tokens(self, jwks_url: str | None = None) -> Generator[None]:
        """Run the block with the service checking tokens, then put the service back as it was.

        A service which already checks them is used as it is: nothing is recreated, which is what a run against a
        long-lived server with such a service needs. One which does not is recreated with the setting, where the run owns
        the containers. A service which predates the tokens ignores the setting, and the block then has nothing to check:
        a skip, or a failure where the run says its image checks them. That is decided before the block runs, whatever
        address the service was given.

        Given an address, the service is always recreated with that one: the case asks what a service does which cannot
        fetch the key set, and only a service recreated with a bad address can be asked.
        """
        if jwks_url is None and tokens_enforced():
            yield
            return
        address: str = jwks_url or self._require_recreatable_service()
        if jwks_url is not None:
            self._require_recreatable_service()
        with service_running_with(BULK.service_api_keys(), {SETTING: address, JWKS_HOST_SETTING: polarion_jwks_host()}) as answering:
            self.assertTrue(answering, "the service did not come back with the setting for the Polarion tokens")
            # a call without a token is refused before the key set is asked for, so this holds for an unreachable one too
            if not tokens_enforced():
                self._service_predates_tokens()
            yield

    def _service_predates_tokens(self) -> NoReturn:
        """The service ignored the setting: a skip, or a failure where the run says its image checks tokens."""
        reason: str = "the bulk processing service does not check Polarion tokens: its image predates them"
        self._cannot_check(reason)

    def _key_id(self) -> str:
        """The id of the key Polarion publishes: a token naming any other would be refused for its key id, not its signature."""
        key_id: str | None = polarion_key_id()
        if key_id is None:
            self._unavailable("the key set of Polarion could not be read from inside Polarion")
        return str(key_id)

    def _merge(self) -> MergeJobOutcome:
        merge_params: JsonList = [{"projectId": self.project_id, "locationPath": location_path, "documentType": DocumentType.LIVE_DOC} for location_path in MERGED_DOCUMENTS]
        # the job answers 303 once it is ready and 409 where it failed, and both are outcomes a case asserts on
        with self.suppress_api_errors():
            return merge_through_extension(self.api(), merge_params, MERGE_JOB_TIMEOUT_IN_SEC)

    def _assert_status_and_answer(self, answer: tuple[int, str] | None, status: int, text: str) -> None:
        self.assertIsNotNone(answer, "the service could not be asked from inside Polarion")
        assert answer is not None  # asserted above
        self.assertEqual(status, answer[0], f"the service answered {answer[0]}: {answer[1]}")
        self.assertIn(text, answer[1], f"the refusal does not say why: {answer[1]}")

    # ------------------------------------------------------------------ a merge the service checks

    def test_a_merge_succeeds_while_the_service_checks_tokens(self) -> None:
        # the token is signed by this Polarion, with the key it publishes, and the service read that key set:
        # a pdf alone is no evidence, so the merge is also looked for in the log of the service
        with self._service_checking_tokens():
            finished_before: int = service_log_lines(FINISH_LOGGED)
            outcome: MergeJobOutcome = self._merge()
            finished_after: int = service_log_lines(FINISH_LOGGED)

        self.assertEqual(HTTPStatus.OK, outcome.status, f"the merge did not succeed: {outcome.error_message}")
        assert outcome.pdf is not None  # an OK outcome carries the pdf
        self.assertTrue(outcome.pdf.startswith(b"%PDF"), "the merge did not return a pdf")
        self.assertGreater(finished_after, finished_before, "the merge was not made by the bulk processing service")

    def test_the_service_keeps_a_digest_of_the_initiator_of_a_job(self) -> None:
        with self._service_checking_tokens():
            before: list[dict[str, Any]] | None = stored_jobs()
            outcome: MergeJobOutcome = self._merge()
            after: list[dict[str, Any]] | None = stored_jobs()

        self.assertEqual(HTTPStatus.OK, outcome.status, f"the merge did not succeed: {outcome.error_message}")
        if before is None or after is None:
            self._unavailable("the jobs the service holds could not be read from its container")
        known: set[Any] = {job.get("job_id") for job in before or []}
        # a job which was already there says nothing about this merge, so only one it started is looked at
        started: list[dict[str, Any]] = [job for job in after or [] if job.get("job_id") not in known]
        self.assertTrue(started, "the service holds no job this merge started")
        initiators: list[Any] = [job.get("initiator_hash") for job in started]
        self.assertTrue(all(isinstance(value, str) and SHA256_HEX.fullmatch(value) for value in initiators), f"a job of this merge holds no digest of its initiator: {initiators}")

    # ------------------------------------------------------------------ the calls which present no token

    def test_the_service_refuses_every_call_without_a_token(self) -> None:
        calls: list[tuple[str, str]] = [
            ("POST", "/api/convert/start"),
            ("POST", f"/api/convert/{UNKNOWN_JOB_ID}/add"),
            ("POST", f"/api/convert/{UNKNOWN_JOB_ID}/finish"),
            ("DELETE", f"/api/convert/{UNKNOWN_JOB_ID}"),
        ]
        with self._service_checking_tokens():
            answers: list[tuple[str, tuple[int, str] | None]] = [(f"{method} {path}", token_answer(method, path)) for method, path in calls]

        for name, answer in answers:
            with self.subTest(call=name):
                self._assert_status_and_answer(answer, HTTPStatus.UNAUTHORIZED, MISSING_TOKEN_ANSWER)

    def test_the_service_refuses_a_garbage_token(self) -> None:
        with self._service_checking_tokens():
            answer: tuple[int, str] | None = token_answer("POST", "/api/convert/start", token="a.b.c", json_body={})

        self._assert_status_and_answer(answer, HTTPStatus.UNAUTHORIZED, INVALID_TOKEN_ANSWER)

    def test_the_service_refuses_a_token_which_polarion_did_not_sign(self) -> None:
        # it names the key Polarion really publishes and carries every claim the service asks for, so the
        # signature is the only thing wrong with it
        with self._service_checking_tokens():
            key_id: str = self._key_id()
            refused_before: int = service_log_lines(FORGED_TOKEN_LOGGED)
            answer: tuple[int, str] | None = token_answer("POST", "/api/convert/start", token=forged_token(key_id), json_body={})
            refused_after: int = service_log_lines(FORGED_TOKEN_LOGGED)

        self._assert_status_and_answer(answer, HTTPStatus.UNAUTHORIZED, INVALID_TOKEN_ANSWER)
        # it is the signature which was refused, not a key id the service does not know
        self.assertGreater(refused_after, refused_before, "the service did not log that it refused the signature of the token")

    def test_a_forged_token_does_not_open_a_job_by_naming_it(self) -> None:
        # the claims are the ones a job asks for, the signature is not: naming the job opens nothing
        with self._service_checking_tokens():
            token: str = forged_token(self._key_id(), job_id=UNKNOWN_JOB_ID)
            answers: list[tuple[int, str] | None] = [
                token_answer("POST", f"/api/convert/{UNKNOWN_JOB_ID}/finish", token=token),
                token_answer("DELETE", f"/api/convert/{UNKNOWN_JOB_ID}", token=token),
            ]

        for answer in answers:
            self._assert_status_and_answer(answer, HTTPStatus.UNAUTHORIZED, INVALID_TOKEN_ANSWER)

    # ------------------------------------------------------------------ a key set which cannot be fetched

    def test_a_service_which_cannot_fetch_the_key_set_fails_the_merge_and_says_so(self) -> None:
        # nothing can be verified, so nothing is let through, and the reason reaches the person who exports
        with self._service_checking_tokens(UNREACHABLE_JWKS_URL):
            outcome: MergeJobOutcome = self._merge()

        self.assertEqual(HTTPStatus.CONFLICT, outcome.status, "a merge which cannot be verified must not report success")
        self.assertIn(KEY_SET_UNREACHABLE_ANSWER, outcome.error_message, f"the merge did not say why it failed: {outcome.error_message}")

    # ------------------------------------------------------------------ a service which does not check

    def test_a_service_without_a_key_set_takes_the_tokens_without_checking_them(self) -> None:
        # the service as the run started it: the extension sends a token with every call and the service does not look at it
        if tokens_enforced():
            self.skipTest("the bulk processing service of this run already checks tokens, so there is no unchecked one to look at")

        answer: tuple[int, str] | None = token_answer("POST", "/api/convert/start", token="a.b.c", json_body={})

        self.assertIsNotNone(answer, "the service could not be asked from inside Polarion")
        assert answer is not None  # asserted above
        try:
            self.assertEqual(HTTPStatus.CREATED, answer[0], f"the service refused a call although it checks no tokens: {answer[1]}")
        finally:
            # the job this case started is not left for the cleanup of the service
            job_id: str | None = job_id_of(answer[1])
            if job_id is not None:
                token_answer("DELETE", f"/api/convert/{job_id}")
