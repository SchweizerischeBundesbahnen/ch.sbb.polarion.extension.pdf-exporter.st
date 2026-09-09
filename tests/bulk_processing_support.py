"""How Polarion is configured to reach the bulk processing service, read from a running instance.

The bulk processing service is what the extension calls to merge several exported documents into one
PDF. Its address lives in ``polarion.properties`` under ``...bulk.processing.service``, and the name of
the secret holding its API key under ``...bulk.processing.apiKeySecret``. Polarion reads that file once,
at start, so both are read here only to decide whether the bulk-processing cases apply at all, and to
ask -- from inside the Polarion container -- whether the named service actually answers.
"""

from __future__ import annotations

import logging
from typing import Any

from tests.ssrf_support import polarion_container


logger = logging.getLogger(__name__)

PROPERTIES_PATH = "/opt/polarion/etc/polarion.properties"
SERVICE_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.bulk.processing.service"
API_KEY_SECRET_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.bulk.processing.apiKeySecret"


def _polarion_exec(command: list[str]) -> tuple[int, str] | None:
    """Run a command inside the Polarion container, or None where there is no container to ask."""
    container: Any = polarion_container()
    if container is None:
        return None
    try:
        answer: Any = container.exec_run(command)
    except Exception:  # noqa: BLE001 - an unreachable container is reported, not raised
        logger.info("a command could not be run in the Polarion container")
        return None
    return int(answer[0]), answer[1].decode(errors="replace")


def configured_property(name: str) -> str | None:
    """The value of a property of the running Polarion, read from the file it was started with."""
    answer: tuple[int, str] | None = _polarion_exec(["grep", "-m1", f"^{name}=", PROPERTIES_PATH])
    if answer is None or answer[0] != 0:
        return None
    return answer[1].strip().partition("=")[2].strip() or None


def service_url() -> str | None:
    """The address Polarion names for the bulk processing service, or None where none is named."""
    return configured_property(SERVICE_PROPERTY)


def api_key_secret_name() -> str | None:
    """The name of the Polarion secret holding the API key, or None where no key is configured."""
    return configured_property(API_KEY_SECRET_PROPERTY)


def configured() -> bool:
    """Whether this Polarion names a bulk processing service at all."""
    return service_url() is not None


def service_answers() -> bool:
    """Whether the named service answers Polarion on its open ``/version`` endpoint, the certificate aside.

    Asked from inside the Polarion container with ``-k`` on purpose: a privately signed certificate must
    not turn "the service is up" into "the truststore is wrong". The certificate is the concern of the
    authenticated cases, not of a reachability check, and ``/version`` needs no API key.
    """
    url: str | None = service_url()
    if url is None:
        return False
    answer: tuple[int, str] | None = _polarion_exec(["curl", "-sk", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", f"{url}/version"])
    return answer is not None and answer[0] == 0 and answer[1].strip() == "200"
