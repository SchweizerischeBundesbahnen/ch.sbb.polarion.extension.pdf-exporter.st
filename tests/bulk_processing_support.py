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

import json
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from tests.tls_service_support import TlsService, polarion_exec


if TYPE_CHECKING:
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


def request(method: str, path: str, api_key: str | None = None, json_body: dict[str, Any] | None = None) -> tuple[int, str] | None:
    """A request to the service from inside the Polarion container, returning ``(status, body)``.

    None where there is no container to ask, or where curl itself could not run. The call travels the
    path Polarion uses: the same network, the same address, the key in the header the service reads.
    The body is passed as one argument, so its quotes reach the service rather than a shell.
    """
    url: str | None = service_url()
    if url is None:
        return None
    command: list[str] = ["curl", "-sk", "-m", "30", "-X", method, "-w", "\n%{http_code}"]
    if api_key:
        command += ["-H", f"X-API-Key: {api_key}"]
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
