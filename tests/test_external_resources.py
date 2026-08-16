"""The external-resource policy, seen from outside the server.

Every case here names a resource the server must not load and asserts that the probe was never
asked for it. The probe is proven reachable from the Polarion container first, so silence means a
refusal rather than a broken network.

What the conversion service does counts as well: the refused url must not stay in the document, or
WeasyPrint would fetch it from its own network. The probe records that hop too.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import fitz

from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.ssrf_probe import PROBE_IMAGE_HEIGHT, PROBE_IMAGE_WIDTH, SsrfProbe
from tests.ssrf_support import answers_on_loopback, reachable_probe_endpoint, start_loopback_forwarder, stop_loopback_forwarder


if TYPE_CHECKING:
    from requests import Response


TRANSPARENT_PIXEL: str = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="


class PdfExporterExternalResourcesTest(PdfExporterTestCase):
    """Cases for the external-resource policy (SSRF)."""

    probe: ClassVar[SsrfProbe | None] = None
    endpoint: ClassVar[str] = ""
    loopback_forwarded: ClassVar[bool] = False

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        probe: SsrfProbe = SsrfProbe()
        probe.__enter__()
        endpoint: str | None = reachable_probe_endpoint(probe.port)
        if endpoint is None:
            probe.__exit__(None, None, None)
            return
        # the loopback of the container names nothing by itself, so the probe is carried there:
        # a case which asks for '127.0.0.1' has to fail on a server with no policy
        cls.loopback_forwarded = start_loopback_forwarder(probe.port, endpoint.rsplit(":", 1)[0])
        probe.reset()
        cls.probe = probe
        cls.endpoint = endpoint

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.loopback_forwarded:
            stop_loopback_forwarder()
            cls.loopback_forwarded = False
        if cls.probe is not None:
            cls.probe.__exit__(None, None, None)
            cls.probe = None
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        if self.__class__.probe is None:
            self.skipTest("no probe reachable from the Polarion container")
        self._probe().reset()

    def _probe(self) -> SsrfProbe:
        probe: SsrfProbe | None = self.__class__.probe
        if probe is None:
            self.fail("the probe is gone")
        return probe

    # ------------------------------------------------------------------ helpers

    def _document(self, body: str) -> str:
        return f"<html><head><meta charset='utf-8'/></head><body>{body}</body></html>"

    def _export(self, body: str) -> bytes:
        response: Response = self._convert_html(self.api(), html=self._document(body))
        self.assertEqual(HTTPStatus.OK, response.status_code, "a refused resource must not break the export")
        return response.content

    def _assert_probe_silent(self) -> None:
        recorded: list[str] = list(self._probe().requests)
        self.assertEqual([], recorded, f"the server loaded a resource it had to refuse: {recorded}")

    def _assert_probe_picture_absent(self, pdf_bytes: bytes) -> None:
        document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            for page_index in range(len(document)):
                for image in document[page_index].get_images(full=True):
                    extracted: dict[str, int] = document.extract_image(image[0])
                    if extracted["width"] == PROBE_IMAGE_WIDTH and extracted["height"] == PROBE_IMAGE_HEIGHT:
                        self.fail("the picture of the probe reached the exported document")
        finally:
            document.close()

    def _refused(self, body: str) -> bytes:
        pdf_bytes: bytes = self._export(body)
        self._assert_probe_silent()
        self._assert_probe_picture_absent(pdf_bytes)
        return pdf_bytes

    def _require_loopback(self, family: str) -> None:
        if not self.__class__.loopback_forwarded or not answers_on_loopback(self._probe().port, family):
            self.skipTest(f"the probe does not answer on the {family} loopback of the container")
        self._probe().reset()

    # ------------------------------------------------------------------ the address decides

    def test_an_image_from_a_private_address_is_refused(self) -> None:
        self._refused(f"<p><img src='http://{self.endpoint}/probe/ok.png'/></p>")

    def test_the_loopback_of_the_server_is_refused(self) -> None:
        # the probe answers on the loopback of the container, so a fetch would be recorded
        self._require_loopback("ipv4")
        self._refused(f"<p><img src='http://127.0.0.1:{self._probe().port}/probe/ok.png'/></p>")

    def test_the_ipv6_loopback_of_the_server_is_refused(self) -> None:
        # the pin has to answer for '[::1]' as the url spells it, brackets and all
        self._require_loopback("ipv6")
        self._refused(f"<p><img src='http://[::1]:{self._probe().port}/probe/ok.png'/></p>")

    def test_the_cloud_metadata_address_is_refused(self) -> None:
        self._refused("<p><img src='http://169.254.169.254/latest/meta-data/'/></p>")

    def test_a_network_path_reference_is_refused(self) -> None:
        # '//host/path' names no scheme and is loaded under both, so both have to be refused
        self._refused(f"<p><img src='//{self.endpoint}/probe/ok.png'/></p>")

    def test_a_file_url_is_refused(self) -> None:
        pdf_bytes: bytes = self._export("<p><img src='file:///etc/passwd'/></p>")
        self._assert_probe_silent()
        self.assertGreater(len(pdf_bytes), 0)

    # ------------------------------------------------------------------ every channel, not only img

    def test_a_stylesheet_link_is_refused(self) -> None:
        self._refused(f"<link rel='stylesheet' href='http://{self.endpoint}/probe/style.css'/><p>text</p>")

    def test_a_css_url_in_a_document_style_is_refused(self) -> None:
        style: str = f"<style>p {{ background-image: url(http://{self.endpoint}/probe/ok.png); }}</style>"
        self._refused(f"{style}<p>text</p>")

    def test_a_css_import_is_removed(self) -> None:
        # an at-rule is never inlined, so it is removed whatever it names: WeasyPrint would load it itself
        style: str = f"<style>@import url(http://{self.endpoint}/probe/style.css); p {{ color: black; }}</style>"
        self._refused(f"{style}<p>text</p>")

    def test_a_css_escape_does_not_hide_the_address(self) -> None:
        # '\68 ttp://host' names an address as much as 'http://host' does
        style: str = f"<style>p {{ background-image: url(\\68 ttp://{self.endpoint}/probe/ok.png); }}</style>"
        self._refused(f"{style}<p>text</p>")

    def test_an_iframe_is_refused(self) -> None:
        self._refused(f"<iframe src='http://{self.endpoint}/probe/ok.png'></iframe>")

    def test_an_object_and_an_embed_are_refused(self) -> None:
        self._refused(f"<object data='http://{self.endpoint}/probe/ok.png'></object><embed src='http://{self.endpoint}/probe/ok.png'/>")

    def test_an_svg_reference_is_refused(self) -> None:
        self._refused(f"<svg xmlns='http://www.w3.org/2000/svg'><image href='http://{self.endpoint}/probe/ok.png'/></svg>")

    # ------------------------------------------------------------------ what must keep working

    def test_a_relative_url_is_left_alone(self) -> None:
        pdf_bytes: bytes = self._export("<p><img src='images/logo.png'/>text</p>")
        self._assert_probe_silent()
        self.assertGreater(len(pdf_bytes), 0)

    def test_a_data_url_is_kept(self) -> None:
        pdf_bytes: bytes = self._export(f"<p><img src='{TRANSPARENT_PIXEL}'/>text</p>")
        self._assert_probe_silent()
        self.assertGreater(len(pdf_bytes), 0)

    # ------------------------------------------------------------------ the placeholder

    def test_the_placeholder_paints_nothing(self) -> None:
        # a refused picture is replaced by a placeholder, and a placeholder which paints marks the
        # document where the reader expects the picture
        refused: bytes = self._export(f"<p><img src='http://{self.endpoint}/probe/ok.png'/>text</p>")
        transparent: bytes = self._export(f"<p><img src='{TRANSPARENT_PIXEL}'/>text</p>")

        self.assertEqual(self._rendered_pages(transparent), self._rendered_pages(refused))

    def _rendered_pages(self, pdf_bytes: bytes) -> list[bytes]:
        document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            return [document[index].get_pixmap(dpi=150).tobytes("png") for index in range(len(document))]
        finally:
            document.close()
