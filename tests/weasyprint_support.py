"""How Polarion is configured to reach the WeasyPrint service, and the two levers a case may pull.

Both the address of the service and the name of the secret holding its API key live in
``polarion.properties``, and Polarion reads that file once, at start. The value behind the secret name
is cached as well. So neither can separate two cases of one run, and both are read here only to decide
whether the authenticated cases apply at all.

What a case may move while Polarion runs:

- **the service**, by recreating its container with a different ``API_KEY``, which takes seconds;
- **the trust**, by removing the certificate authority from the truststore of the Polarion JVM, which
  the next request already sees.

Recreating the service is only offered where its files are still on the host. A container which was
started from material since deleted keeps running, but would come back without TLS.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from tests.ssrf_support import docker_client, polarion_container


if TYPE_CHECKING:
    from collections.abc import Generator


logger = logging.getLogger(__name__)

PROPERTIES_PATH = "/opt/polarion/etc/polarion.properties"
SERVICE_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.weasyprint.service"
API_KEY_SECRET_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.weasyprint.apiKeySecret"
CACERTS_PATH = "/opt/java/openjdk/lib/security/cacerts"
# the documented default of a JDK truststore, not a credential of this project
CACERTS_PASSWORD = "changeit"
# the authority which signed the certificate of the service, named as the environment stores it
CA_ALIAS = os.environ.get("WEASYPRINT_CA_ALIAS", "pebble-root")
SERVICE_READY_ATTEMPTS = 30


def _polarion_exec(command: list[str]) -> tuple[int, str] | None:
    """Run a command inside the Polarion container, or None where there is no container to ask."""
    container: Any = polarion_container()
    if container is None:
        return None
    try:
        answer: Any = container.exec_run(command)
    except Exception:  # noqa: BLE001 - an unreachable container is reported, not raised
        logger.info("the Polarion container did not run %s", command[0])
        return None
    return int(answer[0]), answer[1].decode(errors="replace")


def configured_property(name: str) -> str | None:
    """The value of a property of the running Polarion, read from the file it was started with."""
    answer: tuple[int, str] | None = _polarion_exec(["grep", "-m1", f"^{name}=", PROPERTIES_PATH])
    if answer is None or answer[0] != 0:
        return None
    return answer[1].strip().partition("=")[2].strip() or None


def service_url() -> str | None:
    """The address Polarion names for the WeasyPrint service."""
    return configured_property(SERVICE_PROPERTY)


def api_key_secret_name() -> str | None:
    """The name of the Polarion secret holding the API key, or None where no key is configured."""
    return configured_property(API_KEY_SECRET_PROPERTY)


def authenticated_over_tls() -> bool:
    """Whether this Polarion talks to the service over https with a key, which the auth cases need."""
    url: str | None = service_url()
    return bool(url and url.lower().startswith("https://") and api_key_secret_name())


def service_answers() -> bool:
    """Whether the service answers Polarion at all, certificate aside."""
    url: str | None = service_url()
    if url is None:
        return False
    answer: tuple[int, str] | None = _polarion_exec(["curl", "-sk", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", f"{url}/version"])
    return answer is not None and answer[0] == 0 and answer[1].strip() == "200"


# ------------------------------------------------------------------ the service container


def service_container() -> Any:
    """The container serving the address Polarion names, found by the name it answers under."""
    url: str | None = service_url()
    if url is None:
        return None
    named: str | None = os.environ.get("WEASYPRINT_CONTAINER")
    wanted_host: str = urlparse(url).hostname or ""
    client: Any = docker_client()
    if client is None:
        return None

    for container in client.containers.list():
        if named and container.name == named:
            return container
        if named:
            continue
        networks: dict[str, dict[str, Any]] = container.attrs["NetworkSettings"]["Networks"]
        for settings in networks.values():
            if wanted_host in (settings.get("Aliases") or []):
                return container
    if named:
        logger.info("no container is named %s", named)
    return None


def service_log_lines(text: str) -> int:
    """How often the service has logged a line holding this text, since it started."""
    container: Any = service_container()
    if container is None:
        return 0
    try:
        logs: bytes = container.logs()
    except Exception:  # noqa: BLE001 - unreadable logs are reported, not raised
        return 0
    return logs.decode(errors="replace").count(text)


def service_restartable() -> str | None:
    """The reason the service must not be recreated, or None where recreating it is safe.

    A container started from files which are no longer on the host keeps running, but would come back
    without the material it read at start. Recreating that one takes TLS away from the environment
    rather than testing it.
    """
    container: Any = service_container()
    if container is None:
        return "the container of the WeasyPrint service was not found"
    for mount in container.attrs.get("Mounts") or []:
        source: str = mount.get("Source", "")
        if mount.get("Type") == "bind" and source and not Path(source).exists():
            return f"the service was started from '{source}', which no longer exists on the host"
    return None


def _recreate(container: Any, api_keys: str | None) -> Any:
    """Put the service back with a different key, keeping everything else as it was."""
    client: Any = docker_client()
    attributes: dict[str, Any] = container.attrs
    name: str = attributes["Name"].lstrip("/")
    image: str = attributes["Config"]["Image"]
    environment: list[str] = [value for value in attributes["Config"]["Env"] if not value.startswith("API_KEY=")]
    if api_keys is not None:
        environment.append(f"API_KEY={api_keys}")
    ports: dict[str, Any] = {port: bindings[0]["HostPort"] for port, bindings in (attributes["HostConfig"]["PortBindings"] or {}).items() if bindings}
    volumes: dict[str, dict[str, str]] = {mount["Source"]: {"bind": mount["Destination"], "mode": "ro" if not mount.get("RW", True) else "rw"} for mount in attributes.get("Mounts") or [] if mount.get("Type") == "bind"}
    networks: dict[str, dict[str, Any]] = attributes["NetworkSettings"]["Networks"]
    first_network: str = next(iter(networks), "")

    container.stop(timeout=10)
    container.remove()
    fresh: Any = client.containers.run(image, name=name, detach=True, environment=environment, ports=ports, volumes=volumes, network=first_network or None)
    for network_name, settings in networks.items():
        if network_name == first_network:
            continue
        client.networks.get(network_name).connect(fresh, aliases=settings.get("Aliases"))
    if first_network and networks[first_network].get("Aliases"):
        # the alias of the first network is not part of containers.run, so it is reconnected with it
        client.networks.get(first_network).disconnect(fresh)
        client.networks.get(first_network).connect(fresh, aliases=networks[first_network]["Aliases"])
    return fresh


def _wait_until_answering() -> bool:
    """Wait for the service to answer Polarion again, so a case does not race its start."""
    for _ in range(SERVICE_READY_ATTEMPTS):
        if service_answers():
            return True
        time.sleep(1)
    return False


@contextmanager
def service_running_with(api_keys: str | None) -> Generator[bool]:
    """Run the block with the service holding these keys, then put the original service back.

    Yields whether the service answered, so a case can report a service which did not come up rather
    than assert against silence.
    """
    original: Any = service_container()
    if original is None:
        yield False
        return
    attributes: dict[str, Any] = dict(original.attrs)
    original_keys: str | None = next((value.partition("=")[2] for value in attributes["Config"]["Env"] if value.startswith("API_KEY=")), None)

    changed: Any = _recreate(original, api_keys)
    try:
        yield _wait_until_answering()
    finally:
        _recreate(changed, original_keys)
        _wait_until_answering()


# ------------------------------------------------------------------ the truststore


def ca_in_truststore(alias: str = CA_ALIAS) -> bool:
    """Whether the Polarion JVM trusts the authority which signed the certificate of the service."""
    answer: tuple[int, str] | None = _polarion_exec(["keytool", "-list", "-alias", alias, "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD])
    return answer is not None and answer[0] == 0


@contextmanager
def ca_removed(alias: str = CA_ALIAS) -> Generator[bool]:
    """Run the block with the authority out of the truststore, then put it back.

    The truststore is read per request, so this needs no restart, which is what makes a negative
    certificate case affordable at all.
    """
    exported: tuple[int, str] | None = _polarion_exec(["keytool", "-exportcert", "-alias", alias, "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD, "-rfc", "-file", "/tmp/ca-under-test.pem"])
    if exported is None or exported[0] != 0:
        yield False
        return

    removed: tuple[int, str] | None = _polarion_exec(["keytool", "-delete", "-alias", alias, "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD])
    try:
        yield removed is not None and removed[0] == 0
    finally:
        _polarion_exec(["keytool", "-importcert", "-alias", alias, "-file", "/tmp/ca-under-test.pem", "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD, "-noprompt"])
        _polarion_exec(["rm", "-f", "/tmp/ca-under-test.pem"])
