"""How Polarion is configured to reach the bulk processing service, read from a running instance.

The bulk processing service is what the extension calls to merge several exported documents into one
PDF. Its address lives in ``polarion.properties`` under ``...bulk.processing.service``, and the name of
the secret holding its API key under ``...bulk.processing.apiKeySecret``. Polarion reads that file once,
at start, so both are read here only to decide whether the bulk-processing cases apply at all, and to
ask -- from inside the Polarion container -- whether the named service actually answers.

What the cases beyond reachability need is the merge lifecycle itself: a job is started, documents are
added to it, and the job is finished into one PDF. That lifecycle is driven from inside the Polarion
container, over the same network and the same address Polarion uses, with the key in the header the
service reads. The key is never read out of Polarion -- the secret is not readable through the API --
but the service it authenticates against is the one holding the matching key, so the key is read from
that container instead, the way the WeasyPrint cases read theirs.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from tests.ssrf_support import polarion_container
from tests.tls_service_support import TlsService, polarion_exec


if TYPE_CHECKING:
    from collections.abc import Mapping

    from python_sbb_polarion.types import JsonList


SERVICE_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.bulk.processing.service"
API_KEY_SECRET_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.bulk.processing.apiKeySecret"

# a job id the service was never given, for the case which asks what an unknown job answers
UNKNOWN_JOB_ID = "no-such-job-00000000000000000000"
# where a merged PDF and its headers wait inside the container while a finish is read, kept unique so
# two cases in one run do not read each other's file, and removed as soon as the answer is in hand. A
# path inside the Polarion container, not on the host.
_DOWNLOAD_DIR = "/tmp"

# The service is found, recreated and trusted the way the WeasyPrint one is (tls_service_support); this
# names the bulk processing one.
BULK: TlsService = TlsService(
    label="bulk processing service",
    service_property=SERVICE_PROPERTY,
    api_key_secret_property=API_KEY_SECRET_PROPERTY,
    container_env="BULK_PROCESSING_CONTAINER",
    # the authority which signed the certificate of the service, where the environment names it itself
    ca_alias_env="BULK_PROCESSING_CA_ALIAS",
)

service_url = BULK.service_url
api_key_secret_name = BULK.api_key_secret_name
authenticated_over_tls = BULK.authenticated_over_tls
service_answers = BULK.service_answers
service_container = BULK.service_container
service_has_file = BULK.service_has_file
service_log_lines = BULK.service_log_lines
service_restartable = BULK.service_restartable
service_running_with = BULK.service_running_with
trusted_ca_alias = BULK.trusted_ca_alias
ca_in_truststore = BULK.ca_in_truststore
ca_removed = BULK.ca_removed


def configured() -> bool:
    """Whether this Polarion names a bulk processing service at all."""
    return service_url() is not None


# what hands the harness a bulk processing service: the address of one started beside it, or the image
# of one it starts itself. Either way the run asked for the service, and Polarion is to name it
HARNESS_SERVICE_VARIABLES = ("TC_BULK_PROCESSING_SERVICE_URL", "TC_BULK_PROCESSING_SERVICE_IMAGE_NAME")


def requested_by_the_run() -> bool:
    """Whether this run handed the harness a bulk processing service, so a Polarion naming none is broken.

    Asked of the environment of the run rather than of whether it is containerized: a containerized run
    which starts no bulk processing service is one which leaves the feature out, and it skips.
    """
    return any(os.environ.get(name, "").strip() for name in HARNESS_SERVICE_VARIABLES)


def service_api_key() -> str | None:
    """One key the service accepts, read from its container, or None where it holds none.

    The service may be started with several comma-separated keys for rotation, and it accepts any of
    them, so the first is enough to authenticate a request.
    """
    configured_keys: str | None = BULK.service_api_keys()
    if not configured_keys:
        return None
    first: str = configured_keys.split(",")[0].strip()
    return first or None


def service_enforces_key() -> bool:
    """Whether the service was started with a key, so the protected endpoints reject an unkeyed call."""
    return service_api_key() is not None


# ------------------------------------------------------------------ the merge lifecycle


def request(method: str, path: str, api_key: str | None = None, json_body: dict[str, Any] | None = None, headers: Mapping[str, str] | None = None) -> tuple[int, str] | None:
    """A request to the service from inside the Polarion container, returning ``(status, body)``.

    None where there is no container to ask, or where curl itself could not run. The call travels the
    path Polarion uses: the same network, the same address, the key in the header the service reads.
    The body is passed as one argument, so its quotes reach the service rather than a shell. ``headers``
    are sent as they are, which is how a case presents a token of Polarion, or a forged one.
    """
    url: str | None = service_url()
    if url is None:
        return None
    command: list[str] = ["curl", "-sk", "-m", "30", "-X", method, "-w", "\n%{http_code}"]
    if api_key:
        command += ["-H", f"X-API-Key: {api_key}"]
    for header_name, header_value in (headers or {}).items():
        command += ["-H", f"{header_name}: {header_value}"]
    if json_body is not None:
        command += ["-H", "Content-Type: application/json", "--data", json.dumps(json_body)]
    command.append(f"{url}{path}")

    answer: tuple[int, str] | None = polarion_exec(command)
    if answer is None or answer[0] != 0:
        return None
    body: str
    status: str
    body, _, status = answer[1].rpartition("\n")
    if not status.strip().isdigit():
        return None
    return int(status.strip()), body


def service_ready() -> bool:
    """Whether the service reports itself ready, which includes reaching WeasyPrint behind it.

    A merge adds documents by converting them through WeasyPrint, so a service which cannot reach it
    would fail every document for a reason that is not the merge. This separates that from a defect.
    """
    answer: tuple[int, str] | None = request("GET", "/ready")
    return answer is not None and answer[0] == 200


def readiness() -> tuple[int, dict[str, Any]] | None:
    """What ``/ready`` answers, with the body read, or None where it could not be asked.

    The body names each dependency, so a case can tell a service which cannot reach WeasyPrint apart
    from one whose storage is full, and say which it was.
    """
    answer: tuple[int, str] | None = request("GET", "/ready")
    if answer is None:
        return None
    try:
        body: Any = json.loads(answer[1])
    except json.JSONDecodeError:
        body = {}
    return answer[0], body if isinstance(body, dict) else {}


@dataclass
class MergeJobOutcome:
    """How a merge job the extension ran ended: its last status, why it failed, and the merged PDF."""

    status: int
    error_message: str
    pdf: bytes | None


def merge_through_extension(api: Any, merge_params: JsonList, timeout_in_sec: int) -> MergeJobOutcome:
    """Start a merge job in the extension, wait for it, and return how it ended.

    The status endpoint answers 202 while the job runs, 303 once the merge is ready and 409 where it
    failed, the reason in ``errorMessage``. A caller expecting a failure keeps those out of the error
    log itself, since only it knows which of them it expects.
    """
    response: Any = api.start_pdf_merge_job(merge_params)
    if response.status_code != HTTPStatus.ACCEPTED:
        return MergeJobOutcome(status=response.status_code, error_message=response.text, pdf=None)
    job_id: str = str(response.headers.get("Location", "")).rsplit("/", 1)[-1]

    start: float = time.time()
    while time.time() - start < timeout_in_sec:
        response = api.get_pdf_converter_job_status(job_id=job_id)
        if response.status_code != HTTPStatus.ACCEPTED:
            break
        time.sleep(1)
    if response.status_code != HTTPStatus.SEE_OTHER:
        error_message: str = ""
        try:
            error_message = str(response.json().get("errorMessage") or "")
        except ValueError:
            error_message = response.text
        return MergeJobOutcome(status=response.status_code, error_message=error_message, pdf=None)

    response = api.get_pdf_converter_job_result(job_id=job_id)
    return MergeJobOutcome(status=response.status_code, error_message="", pdf=response.content if response.status_code == HTTPStatus.OK else None)


def start_job(api_key: str | None, file_name: str) -> str | None:
    """Start a merge job, returning its id, or None where the service did not name one."""
    answer: tuple[int, str] | None = request("POST", "/api/convert/start", api_key=api_key, json_body={"fileName": file_name})
    if answer is None or answer[0] != 201:
        return None
    try:
        job_id: Any = json.loads(answer[1]).get("jobId")
    except json.JSONDecodeError:
        return None
    return str(job_id) if job_id else None


def add_document(job_id: str, html: str, api_key: str | None) -> int | None:
    """Add one HTML document to a job, returning the status the service answered with."""
    answer: tuple[int, str] | None = request("POST", f"/api/convert/{job_id}/add", api_key=api_key, json_body={"html": html})
    return answer[0] if answer is not None else None


def delete_job(job_id: str, api_key: str | None) -> int | None:
    """Delete a job, returning the status the service answered with."""
    answer: tuple[int, str] | None = request("DELETE", f"/api/convert/{job_id}", api_key=api_key)
    return answer[0] if answer is not None else None


@dataclass
class FinishOutcome:
    """What a finished merge tells the caller: the status, the count it merged, and that it is a PDF."""

    status: int
    documents_merged: int | None
    is_pdf: bool


def finish_job(job_id: str, api_key: str | None) -> FinishOutcome | None:
    """Finish a job into one PDF, read from inside the container, or None where it could not be asked.

    The merged PDF is binary, so it is written to a file inside the container rather than carried back
    through a decoded string, and the file is removed once its first bytes and the merge count are in
    hand. ``X-Documents-Merged`` is the service's own count of what it merged.
    """
    url: str | None = service_url()
    if url is None:
        return None
    token: str = uuid.uuid4().hex
    pdf_path: str = f"{_DOWNLOAD_DIR}/bulk-merge-{token}.pdf"
    headers_path: str = f"{_DOWNLOAD_DIR}/bulk-merge-{token}.headers"

    command: list[str] = ["curl", "-sk", "-m", "60", "-X", "POST", "-D", headers_path, "-o", pdf_path, "-w", "%{http_code}"]
    if api_key:
        command += ["-H", f"X-API-Key: {api_key}"]
    command.append(f"{url}/api/convert/{job_id}/finish")

    answer: tuple[int, str] | None = polarion_exec(command)
    if answer is None or answer[0] != 0 or not answer[1].strip().isdigit():
        polarion_exec(["rm", "-f", pdf_path, headers_path])
        return None
    status: int = int(answer[1].strip())

    headers: tuple[int, str] | None = polarion_exec(["cat", headers_path])
    documents_merged: int | None = _header_count(headers[1], "X-Documents-Merged") if headers is not None and headers[0] == 0 else None

    magic: tuple[int, str] | None = polarion_exec(["head", "-c", "5", pdf_path])
    is_pdf: bool = magic is not None and magic[0] == 0 and magic[1].startswith("%PDF-")

    polarion_exec(["rm", "-f", pdf_path, headers_path])
    return FinishOutcome(status=status, documents_merged=documents_merged, is_pdf=is_pdf)


def _header_count(headers: str, name: str) -> int | None:
    """The integer value of a header, matched by name without regard to case, or None where absent."""
    for line in headers.splitlines():
        field: str
        separator: str
        value: str
        field, separator, value = line.partition(":")
        if separator and field.strip().lower() == name.lower():
            trimmed: str = value.strip()
            return int(trimmed) if trimmed.isdigit() else None
    return None


# ------------------------------------------------------------------ the tokens of Polarion

# Where the service fetches the keys Polarion signs its tokens with. The run names it itself where the
# default does not fit: Polarion answers a request only under the host name it knows itself by, so the
# address a service reaches it under may have to be spelled out.
JWKS_URL_ENV = "BULK_PROCESSING_JWKS_URL"
# The host name Polarion is asked for its keys under. Polarion answers only under the host name of its own base URL
# and refuses any other with a 400, so a service which reaches it by the name of its container has to say whose key
# set it wants. Its base URL is localhost in the images the runs use; a run whose Polarion knows itself by another name says so here.
JWKS_HOST_ENV = "BULK_PROCESSING_JWKS_HOST"
DEFAULT_JWKS_HOST = "localhost"
JWKS_HOST_SETTING = "POLARION_JWKS_HOST"
# set where the image of the service is known to check Polarion tokens: a service which does not is then
# a failure of the run, not a skip which would leave the required check green over a run which covered none
REQUIRE_JWT_ENV = "BULK_PROCESSING_REQUIRE_JWT"
POLARION_TOKEN_HEADER = "X-Polarion-Token"
JWKS_PATH = "/polarion/.well-known/jwks.json"
SERVICE_NAME = "bulk-processing-service"
# what the service answers a call without a token and a call with one it does not accept, so a case can tell the
# refusal of the token from the refusal of the API key, which is a 401 as well
MISSING_TOKEN_ANSWER = "Missing Polarion token"
INVALID_TOKEN_ANSWER = "Invalid Polarion token"
TOKEN_REFUSAL_LOGGED = "Polarion token refused"
# the service got as far as the signature, and that is what it refused
FORGED_TOKEN_LOGGED = "Polarion token refused (InvalidSignatureError)"
KEY_SET_UNREACHABLE_ANSWER = "key set is unreachable"
# where the service keeps its jobs; the default of the image
JOB_STORAGE_DIR = "/data/jobs"


def polarion_jwks_url() -> str | None:
    """The address the service is to fetch the key set of Polarion from, or None where there is none to name.

    The run's own answer wins. Otherwise Polarion is named the way the network the run created answers it,
    by its container name, which is how the service reaches it at all.
    """
    named: str = os.environ.get(JWKS_URL_ENV, "").strip()
    if named:
        return named
    container: Any = polarion_container()
    if container is None:
        return None
    return f"http://{container.name}{JWKS_PATH}"


def polarion_jwks_host() -> str:
    """The host name the service is to ask Polarion for its keys under."""
    return os.environ.get(JWKS_HOST_ENV, "").strip() or DEFAULT_JWKS_HOST


def jwt_required_by_the_run() -> bool:
    """Whether the run says its service checks Polarion tokens, so one which does not is a broken run."""
    return os.environ.get(REQUIRE_JWT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def token_answer(method: str, path: str, token: str | None = None, json_body: dict[str, Any] | None = None) -> tuple[int, str] | None:
    """A request to the service which presents this token, with the API key the service holds beside it.

    The key is sent where there is one, so a 401 is the refusal of the token and not of the key. A body is
    given where the call needs one: a service which checks no tokens validates it first, and answers 422 to a
    ``start`` without one, which says nothing about tokens.
    """
    headers: dict[str, str] = {POLARION_TOKEN_HEADER: token} if token is not None else {}
    return request(method, path, api_key=service_api_key(), json_body=json_body, headers=headers)


def tokens_enforced() -> bool:
    """Whether the service refuses a call which carries no token of Polarion.

    A service which predates the tokens ignores the setting which switches them on, and starts a job
    for anyone: that is how a case tells it has nothing to check.
    """
    answer: tuple[int, str] | None = token_answer("POST", "/api/convert/start", json_body={})
    if answer is not None and answer[0] == HTTPStatus.CREATED:
        # the service started a job for nobody: not one to leave behind for its cleanup
        job_id: str | None = job_id_of(answer[1])
        if job_id is not None:
            token_answer("DELETE", f"/api/convert/{job_id}")
    return answer is not None and answer[0] == HTTPStatus.UNAUTHORIZED and MISSING_TOKEN_ANSWER in answer[1]


def job_id_of(body: str) -> str | None:
    """The id of the job a ``start`` answered with, or None where the answer holds none."""
    try:
        job_id: Any = json.loads(body).get("jobId")
    except json.JSONDecodeError, AttributeError:
        return None
    return str(job_id) if job_id else None


def polarion_key_id() -> str | None:
    """The id of the key Polarion publishes, read from inside Polarion, which answers under its own name there.

    None where it cannot be read: a token naming a guessed key would be refused for its unknown key id and not for its
    signature, which is what the cases which use it are about.
    """
    answer: tuple[int, str] | None = polarion_exec(["curl", "-s", "-m", "5", f"http://localhost{JWKS_PATH}"])
    if answer is None or answer[0] != 0:
        return None
    try:
        keys: Any = json.loads(answer[1]).get("keys") or []
    except json.JSONDecodeError, AttributeError:
        return None
    key_id: Any = keys[0].get("kid") if keys and isinstance(keys[0], dict) else None
    return str(key_id) if key_id else None


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def forged_token(key_id: str, job_id: str | None = None) -> str:
    """A token which looks like one of Polarion's but was not signed by it.

    Its header names the key Polarion really publishes and its claims are the ones the service asks for, so
    the service gets as far as checking the signature, which is random bytes. Nothing else of the token is
    wrong, so a refusal can only be for the signature.
    """
    now: int = int(time.time())
    claims: dict[str, Any] = {"sub": "forger", "iat": now, "exp": now + 300, "svc": SERVICE_NAME}
    if job_id is not None:
        claims["job"] = job_id
    header: dict[str, str] = {"alg": "RS256", "typ": "JWT", "kid": key_id}
    return ".".join([_base64url(json.dumps(header).encode()), _base64url(json.dumps(claims).encode()), _base64url(secrets.token_bytes(256))])


def stored_jobs() -> list[dict[str, Any]] | None:
    """The metadata of every job the service holds, read from its container, or None where it cannot be read (an empty list is no job)."""
    container: Any = service_container()
    if container is None:
        return None
    try:
        answer: Any = container.exec_run(["sh", "-c", f'for f in {JOB_STORAGE_DIR}/*/metadata.json; do cat "$f"; echo; done 2>/dev/null'])
    except Exception:  # noqa: BLE001 - a container which cannot be asked holds nothing a case can read
        return None
    if int(answer[0]) != 0:
        return None
    jobs: list[dict[str, Any]] = []
    for line in answer[1].decode(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            parsed: Any = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            jobs.append(parsed)
    return jobs
