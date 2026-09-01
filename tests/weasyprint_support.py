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
import shlex
import sys
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
# The documented default of a JDK truststore. It is not a credential of this project, and an
# installation which changed it names the new one here.
CACERTS_PASSWORD = os.environ.get("POLARION_TRUSTSTORE_PASSWORD", "changeit")
# the authority which signed the certificate of the service, where the environment names it itself
CA_ALIAS_OVERRIDE = os.environ.get("WEASYPRINT_CA_ALIAS", "")
SERVICE_READY_ATTEMPTS = 30
# what a recreated container can carry over: a named volume under its name, a bind under its path
RECREATABLE_MOUNT_TYPES = ("bind", "volume")
# where the authority waits while a case runs without it, so a killed run leaves it recoverable
CA_UNDER_TEST_PATH = "/tmp/ca-under-test.pem"  # a path inside the container


def _polarion_exec(command: list[str]) -> tuple[int, str] | None:
    """Run a command inside the Polarion container, or None where there is no container to ask."""
    container: Any = polarion_container()
    if container is None:
        return None
    try:
        answer: Any = container.exec_run(command)
    except Exception:  # noqa: BLE001 - an unreachable container is reported, not raised
        # the command itself is never logged: some of them carry the password of the truststore
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
            # both spellings: newer daemons report the names under DNSNames and leave Aliases behind
            if wanted_host in (settings.get("Aliases") or []) or wanted_host in (settings.get("DNSNames") or []):
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
        kind: str = mount.get("Type", "")
        if kind not in RECREATABLE_MOUNT_TYPES:
            # said rather than dropped: a tmpfs is not carried over, and a service which came back
            # without one would not be the service the other cases measured
            return f"the service carries a '{kind}' mount at '{mount.get('Destination')}', which this cannot reproduce"
        if kind == "bind" and source and not Path(source).exists():
            return f"the service was started from '{source}', which no longer exists on the host"
    return None


def _network_aliases(settings: dict[str, Any], container_name: str, container_id: str) -> list[str]:
    """Every name a network answers this container under, minus the two docker adds by itself.

    A newer daemon reports the names under `DNSNames` and leaves `Aliases` behind, and `DNSNames`
    also carries the name of the container and its short id. Those two come back on their own, and
    passing the short id of a container which no longer exists would be wrong.
    """
    names: list[str] = [*(settings.get("Aliases") or []), *(settings.get("DNSNames") or [])]
    given: set[str] = {container_name, container_id[:12]}
    return [name for name in dict.fromkeys(names) if name not in given]


def _service_spec(container: Any) -> dict[str, Any]:
    """Everything needed to put this container back, read once so a restore cannot use a stale view."""
    attributes: dict[str, Any] = container.attrs
    return {
        "name": attributes["Name"].lstrip("/"),
        "image": attributes["Config"]["Image"],
        "env": [value for value in attributes["Config"]["Env"] if not value.startswith("API_KEY=")],
        "api_keys": next((value.partition("=")[2] for value in attributes["Config"]["Env"] if value.startswith("API_KEY=")), None),
        # every binding of every port, the interface it was published on included: a service reachable
        # only on the loopback must not come back reachable from the network
        "ports": {port: [(binding.get("HostIp") or "", binding["HostPort"]) for binding in bindings] for port, bindings in (attributes["HostConfig"]["PortBindings"] or {}).items() if bindings},
        # a named volume is carried under its name, a bind mount under its path on the host
        "volumes": {
            mount.get("Name") or mount["Source"]: {"bind": mount["Destination"], "mode": "rw" if mount.get("RW", True) else "ro"}
            for mount in attributes.get("Mounts") or []
            if mount.get("Type") in RECREATABLE_MOUNT_TYPES and mount.get("Destination")
        },
        "networks": {name: _network_aliases(settings, attributes["Name"].lstrip("/"), attributes["Id"]) for name, settings in attributes["NetworkSettings"]["Networks"].items()},
    }


def _print_service_log(container: Any) -> None:
    """Put the log of a container into the output of the run, before it is taken away with it."""
    try:
        lines: str = container.logs().decode(errors="replace")
    except Exception:  # noqa: BLE001 - a log which cannot be read is not worth failing a case over
        return
    if lines.strip():
        sys.stdout.write(f"--- the WeasyPrint service, before it was replaced ---\n{lines}\n")


def _recreate(spec: dict[str, Any], api_keys: str | None) -> None:
    """Put the service back from a spec, with these keys and every name it answered under.

    The aliases are what the address in polarion.properties resolves through, and they are applied
    from the spec rather than from the container being replaced: a container recreated once carries
    no alias in its own attributes yet, and a restore reading those would drop the name.
    """
    client: Any = docker_client()
    environment: list[str] = list(spec["env"])
    if api_keys is not None:
        environment.append(f"API_KEY={api_keys}")

    try:
        existing: Any = client.containers.get(spec["name"])
    except Exception:  # noqa: BLE001 - nothing to replace is a fine starting point
        existing = None
    if existing is not None:
        # What the container said is read before it goes, since removing it takes its log along, and
        # the cases which replace it are the ones whose failures are read out of that log.
        _print_service_log(existing)
        existing.stop(timeout=10)
        existing.remove()

    networks: dict[str, list[str]] = spec["networks"]
    first: str = next(iter(networks), "")
    fresh: Any = client.containers.run(spec["image"], name=spec["name"], detach=True, environment=environment, ports=spec["ports"], volumes=spec["volumes"], network=first or None)
    # containers.run takes a network but no alias, and the alias is the name the address resolves
    # through, so every network is joined again carrying its own
    for network_name, aliases in networks.items():
        network: Any = client.networks.get(network_name)
        if network_name == first:
            network.disconnect(fresh)
        network.connect(fresh, aliases=aliases or None)


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
    spec: dict[str, Any] = _service_spec(original)

    try:
        # inside the block: a recreate which fails leaves no service, and the restore below is what
        # puts one back
        _recreate(spec, api_keys)
        yield _wait_until_answering()
    finally:
        _recreate(spec, spec["api_keys"])
        if not _wait_until_answering():
            logger.error("the WeasyPrint service did not answer after it was put back")


# ------------------------------------------------------------------ the truststore


def _certificate_issuer() -> str | None:
    """The authority which signed the certificate the service presents, as it names itself."""
    url: str | None = service_url()
    if url is None:
        return None
    host: str = urlparse(url).hostname or ""
    port: int = urlparse(url).port or 443
    quoted_host: str = shlex.quote(host)
    answer: tuple[int, str] | None = _polarion_exec(["sh", "-c", f"echo | openssl s_client -connect {quoted_host}:{port:d} -servername {quoted_host} 2>/dev/null | openssl x509 -noout -issuer"])
    if answer is None or answer[0] != 0:
        return None
    # 'issuer=CN = Name, O = Org' becomes 'Name': the common name is what the truststore prints too
    issuer: str = answer[1].strip().partition("=")[2]
    for part in issuer.split(","):
        pair: tuple[str, str, str] = part.partition("=")
        if pair[1] and pair[0].strip() == "CN":
            return pair[2].strip()
    return None


def trusted_ca_alias() -> str | None:
    """The alias under which the truststore holds the authority of the service, or None.

    An environment which names it itself is taken at its word. Otherwise the certificate is asked who
    signed it, and the truststore is asked which alias holds that name, so a case does not remove some
    other authority and conclude that trust does not matter.
    """
    if CA_ALIAS_OVERRIDE:
        return CA_ALIAS_OVERRIDE
    issuer: str | None = _certificate_issuer()
    if issuer is None:
        return None
    # the password is configurable and the issuer comes from a certificate, so neither is pasted into
    # the shell as it stands. The issuer is matched literally as well: a common name is not a pattern
    quoted_password: str = shlex.quote(CACERTS_PASSWORD)
    quoted_issuer: str = shlex.quote(issuer)
    answer: tuple[int, str] | None = _polarion_exec(["sh", "-c", f"keytool -list -v -keystore {CACERTS_PATH} -storepass {quoted_password} 2>/dev/null | grep -F -B8 -- {quoted_issuer} | grep 'Alias name' | head -1"])
    if answer is None or answer[0] != 0:
        return None
    alias: str = answer[1].strip().partition(":")[2].strip()
    return alias or None


def ca_in_truststore(alias: str | None) -> bool:
    """Whether the Polarion JVM trusts the authority under this alias."""
    if not alias:
        return False
    answer: tuple[int, str] | None = _polarion_exec(["keytool", "-list", "-alias", alias, "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD])
    return answer is not None and answer[0] == 0


@contextmanager
def ca_removed(alias: str) -> Generator[bool]:
    """Run the block with the authority out of the truststore, then put it back.

    The truststore is read per request, so this needs no restart, which is what makes a negative
    certificate case affordable at all.
    """
    exported: tuple[int, str] | None = _polarion_exec(["keytool", "-exportcert", "-alias", alias, "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD, "-rfc", "-file", CA_UNDER_TEST_PATH])
    if exported is None or exported[0] != 0:
        yield False
        return

    removed: tuple[int, str] | None = _polarion_exec(["keytool", "-delete", "-alias", alias, "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD])
    try:
        yield removed is not None and removed[0] == 0
    finally:
        restored: tuple[int, str] | None = _polarion_exec(["keytool", "-importcert", "-alias", alias, "-file", CA_UNDER_TEST_PATH, "-keystore", CACERTS_PATH, "-storepass", CACERTS_PASSWORD, "-noprompt"])
        if restored is None or restored[0] != 0:
            # said out loud, or the next case fails with a handshake error which reads like a defect
            # the alias is not named: it is read through a command carrying the password of the
            # truststore, and the path is what the reader needs anyway
            logger.error("the authority could not be put back into the truststore, it is still in %s", CA_UNDER_TEST_PATH)
        else:
            _polarion_exec(["rm", "-f", CA_UNDER_TEST_PATH])
