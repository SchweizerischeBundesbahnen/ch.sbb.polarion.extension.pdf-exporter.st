"""Where the probe stands, seen from Polarion.

Polarion runs in a container, the probe runs on the test host, and how the container reaches that
host depends on the engine: Docker Desktop answers under ``host.docker.internal``, a plain Linux
daemon under the gateway of the container network. So the candidates are tried in turn and the first
one which answers is used.

Every candidate is private, which is what the negative cases need. Reachability is proven by asking
Polarion itself to fetch from the probe: a probe nobody can reach would make every negative case
pass for the wrong reason.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any
from urllib.parse import ParseResult, urlparse

import docker  # type: ignore[import-untyped]


logger = logging.getLogger(__name__)

PROBE_PATH = "/probe/ok.png"
DEFAULT_PORT_OF_SCHEME = {"http": 80, "https": 443}

_UNRESOLVED: Any = object()

_client: Any = None
_container: Any = _UNRESOLVED


def _wanted_port() -> str:
    """The port the tests talk to, named or implied by the scheme."""
    app_url: str = os.environ.get("APP_URL", "http://localhost")
    parts: ParseResult = urlparse(app_url)
    return str(parts.port or DEFAULT_PORT_OF_SCHEME.get(parts.scheme, 80))


def _find_polarion_container() -> Any:
    """The running Polarion container: the one named, or the one publishing the port of APP_URL."""
    global _client  # noqa: PLW0603 - one client for the run, closed by release_docker()

    try:
        _client = docker.from_env()
        containers: list[Any] = _client.containers.list()
    except Exception:  # noqa: BLE001 - no docker, no cases; the reason is logged
        logger.info("docker is not reachable, the external-resource cases are skipped")
        return None

    named: str | None = os.environ.get("POLARION_CONTAINER")
    if named:
        # an explicit name is an answer, not a hint: it may not lose to a container which happens
        # to publish the same port
        for container in containers:
            if container.name == named:
                return container
        logger.info("no container is named %s, the external-resource cases are skipped", named)
        return None

    wanted_port: str = _wanted_port()
    for container in containers:
        ports: dict[str, list[dict[str, str]] | None] = container.attrs["NetworkSettings"]["Ports"] or {}
        for bindings in ports.values():
            for binding in bindings or []:
                if binding.get("HostPort") == wanted_port:
                    return container
    return None


def _polarion_container() -> Any:
    """The container, looked for once: every case in the run talks to the same one.

    The lookup answers None as well, and that answer is kept: the sentinel tells the two apart.
    """
    global _container  # noqa: PLW0603 - the lookup is the state

    if _container is _UNRESOLVED:
        _container = _find_polarion_container()
    return _container


def polarion_container() -> Any:
    """The Polarion container the tests talk to, for the cases which need to ask it something."""
    return _polarion_container()


def docker_client() -> Any:
    """The client which found the container, so a caller can look for another one."""
    _polarion_container()
    return _client


def release_docker() -> None:
    """Give the connection of the docker client back, at the end of the run."""
    global _client, _container  # noqa: PLW0603 - the lookup is the state

    if _client is not None:
        _client.close()
    _client = None
    _container = _UNRESOLVED


def _candidate_hosts(container: Any) -> list[str]:
    """Every name under which the container may reach the test host, best guess first."""
    named: str | None = os.environ.get("SSRF_PROBE_HOST")
    hosts: list[str] = [named] if named else []
    hosts.append("host.docker.internal")
    networks: dict[str, dict[str, str]] = container.attrs["NetworkSettings"]["Networks"]
    hosts.extend(settings["Gateway"] for settings in networks.values() if settings.get("Gateway"))
    return hosts


def _answers(container: Any, host: str, port: int) -> bool:
    command: list[str] = ["curl", "-s", "-m", "3", "-o", "/dev/null", "-w", "%{http_code}", f"http://{host}:{port}{PROBE_PATH}"]
    try:
        answer: Any = container.exec_run(command)
    except Exception:  # noqa: BLE001 - an unreachable probe is reported, not raised
        return False
    exit_code: int = answer[0]
    output: bytes = answer[1]
    return bool(exit_code == 0 and output.decode().strip() == "200")


def served_as(url: str) -> tuple[int, str] | None:
    """The status and the content type Polarion itself gets for a url, asked from inside the container.

    A case which says "this url answers with something which is not a picture" states a premise about
    the server. Asked this way, the premise is checked instead of assumed.
    """
    container: Any = _polarion_container()
    if container is None:
        return None
    command: list[str] = ["curl", "-s", "-m", "5", "-o", "/dev/null", "-w", "%{http_code} %{content_type}", url]
    try:
        answer: Any = container.exec_run(command)
    except Exception:  # noqa: BLE001 - an unreadable answer is reported, not raised
        return None
    if answer[0] != 0:
        return None
    parts: list[str] = answer[1].decode().strip().split(" ", 1)
    status: str = parts[0]
    if not status.isdigit():
        return None
    content_type: str = parts[1].strip() if len(parts) > 1 else ""
    return int(status), content_type


def containerized_run() -> bool:
    """Whether the suite drives a container it started itself - the GitHub Actions merge gate.

    There the probe is part of the harness, so a probe which cannot be reached is a broken run. The
    nightly run against a long-lived server has no docker to ask, and skips instead.
    """
    return bool(os.environ.get("TC_POLARION_IMAGE_NAME"))


def reachable_probe_endpoint(port: int) -> str | None:
    """The ``host:port`` the Polarion container really reaches, or None when there is none."""
    container: Any = _polarion_container()
    if container is None:
        return None
    for host in _candidate_hosts(container):
        if _answers(container, host, port):
            logger.info("the probe is reached under %s", host)
            return f"{host}:{port}"
    logger.info("no candidate address reaches the probe, the external-resource cases are skipped")
    return None


def polarion_base_url() -> str | None:
    """The url the server knows itself under - the one origin the policy trusts without an allowlist.

    A document may always name the server it is exported from, so a resource there passes the address
    gate and is decided on its content alone. That is the shape of the reported issue: a url which
    answers with something which is not a picture.
    """
    container: Any = _polarion_container()
    if container is None:
        return None
    try:
        answer: Any = container.exec_run(["grep", "-m1", "-E", "^base.url", "/opt/polarion/etc/polarion.properties"])
    except Exception:  # noqa: BLE001 - without the base url the cases are skipped
        logger.info("the base url of the server could not be read")
        return None
    if answer[0] != 0:
        return None
    line: str = answer[1].decode().strip()
    value: str = line.partition("=")[2]
    return value.strip().rstrip("/") or None


FORWARDER_MARKER = "ssrf-loopback-forwarder"

# Carries the probe from the loopback of the Polarion container to the test host. Without it
# '127.0.0.1' names nothing inside that container, and a case which asks for it would pass on a
# server with no policy at all. The forwarder ends by itself, so a killed test leaves no process.
_FORWARDER_SOURCE = """
import socket, sys, threading

port = int(sys.argv[1])
upstream = (sys.argv[2], port)
threading.Timer(int(sys.argv[3]), lambda: __import__("os")._exit(0)).start()


def pipe(source, target):
    try:
        while True:
            chunk = source.recv(65536)
            if not chunk:
                break
            target.sendall(chunk)
    except OSError:
        pass
    finally:
        source.close()
        target.close()


def serve(family, address):
    listener = socket.socket(family, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(address)
    listener.listen(50)
    while True:
        client, _ = listener.accept()
        try:
            server = socket.create_connection(upstream)
        except OSError:
            client.close()
            continue
        threading.Thread(target=pipe, args=(client, server), daemon=True).start()
        threading.Thread(target=pipe, args=(server, client), daemon=True).start()


threading.Thread(target=serve, args=(socket.AF_INET, ("127.0.0.1", port)), daemon=True).start()
try:
    serve(socket.AF_INET6, ("::1", port, 0, 0))
except OSError:
    threading.Event().wait()
"""


def start_loopback_forwarder(port: int, upstream_host: str, lifetime_seconds: int = 900) -> bool:
    """Make the probe answer on the loopback of the Polarion container, both under IPv4 and IPv6."""
    container: Any = _polarion_container()
    if container is None:
        return False
    source: str = base64.b64encode(_FORWARDER_SOURCE.encode()).decode()
    command: list[str] = [
        "python3",
        "-c",
        f"import base64;exec(base64.b64decode('{source}'))",
        str(port),
        upstream_host,
        str(lifetime_seconds),
        FORWARDER_MARKER,
    ]
    try:
        container.exec_run(command, detach=True)
    except Exception:  # noqa: BLE001 - without the forwarder the loopback cases are skipped
        logger.info("the loopback forwarder could not be started")
        return False
    for _ in range(20):
        if _answers(container, "127.0.0.1", port):
            return True
        time.sleep(0.2)
    logger.info("the loopback forwarder did not answer, the loopback cases are skipped")
    stop_loopback_forwarder()
    return False


def stop_loopback_forwarder() -> None:
    container: Any = _polarion_container()
    if container is None:
        return
    try:
        container.exec_run(["pkill", "-f", FORWARDER_MARKER])
    except Exception:  # noqa: BLE001 - the forwarder ends by itself as well
        logger.info("the loopback forwarder could not be stopped, it ends by itself")


def answers_on_loopback(port: int, family: str = "ipv4") -> bool:
    """Whether the forwarded probe answers inside the container, under the named family."""
    container: Any = _polarion_container()
    if container is None:
        return False
    return _answers(container, "127.0.0.1" if family == "ipv4" else "[::1]", port)
