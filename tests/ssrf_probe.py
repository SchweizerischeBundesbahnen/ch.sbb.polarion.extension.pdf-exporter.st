"""A witness for the external-resource tests.

The extension refuses to load a resource from an address it does not trust. A test can only see that
decision from outside the server, so this module runs a small HTTP server and records every request
which reaches it. A case which expects a refusal asserts that the probe stayed silent; that is the
only assertion which proves no request left Polarion.

The probe listens on every interface of the test host and is reached from the Polarion container
through the gateway of its docker network, so its address is private and refused under
``BLOCK_INTERNAL`` - which is what the negative cases need.
"""

from __future__ import annotations

import logging
import struct
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Self

from python_sbb_polarion.types import Header


if TYPE_CHECKING:
    from types import TracebackType


logger = logging.getLogger(__name__)

PROBE_IMAGE_WIDTH = 200
PROBE_IMAGE_HEIGHT = 100


def _png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Build a PNG of one solid color, without an image library."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body: bytes = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header: bytes = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row: bytes = b"\x00" + bytes(rgb) * width
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(row * height, 9)) + chunk(b"IEND", b"")


PROBE_PNG: bytes = _png(PROBE_IMAGE_WIDTH, PROBE_IMAGE_HEIGHT, (255, 0, 0))
PROBE_CSS: bytes = b"body { background-image: url(/probe/ok.png); }"
# one word of the body, which survives the text extraction of a pdf: a case looks for it there
PROBE_BODY_MARKER = "ssrf-probe-body-reached-the-document"
# what the reported issue used: a url which answers with a body that is not a picture at all
PROBE_JSON: bytes = b'{"method": "GET", "headers": {"Host": "probe"}, "origin": "' + PROBE_BODY_MARKER.encode() + b'"}'


class _Handler(BaseHTTPRequestHandler):
    probe: SsrfProbe

    def do_GET(self) -> None:
        self.probe.record(self.path)
        if self.path.startswith("/probe/report.json"):
            self._answer(b"application/json", PROBE_JSON)
        elif self.path.startswith("/probe/style.css"):
            self._answer(b"text/css", PROBE_CSS)
        else:
            self._answer(b"image/png", PROBE_PNG)

    def do_HEAD(self) -> None:
        self.probe.record(self.path)
        self._answer(b"image/png", b"")

    def _answer(self, content_type: bytes, body: bytes) -> None:
        self.send_response(200)
        self.send_header(Header.CONTENT_TYPE, content_type.decode())
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the name is fixed by the base class
        logger.debug("probe %s", format % args)


class SsrfProbe:
    """An HTTP server which remembers what asked it for something."""

    def __init__(self) -> None:
        handler: type[_Handler] = type("BoundHandler", (_Handler,), {"probe": self})
        # an empty host is every interface: the container has to reach the probe
        self._server: ThreadingHTTPServer = ThreadingHTTPServer(("", 0), handler)
        self._thread: threading.Thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._lock: threading.Lock = threading.Lock()
        self.requests: list[str] = []

    def __enter__(self) -> Self:
        """Start answering."""
        self._thread.start()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        """Stop answering."""
        self._server.shutdown()
        self._server.server_close()

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def record(self, path: str) -> None:
        with self._lock:
            self.requests.append(path)

    def reset(self) -> None:
        with self._lock:
            self.requests.clear()
