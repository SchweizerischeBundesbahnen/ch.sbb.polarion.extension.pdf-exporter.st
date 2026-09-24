"""The external-resource policy, seen from outside the server.

Every case here names a resource the server must not load and asserts that the probe was never
asked for it. The probe is proven reachable from the Polarion container first, so silence means a
refusal rather than a broken network.

What the conversion service does counts as well: the refused url must not stay in the document, or
WeasyPrint would fetch it from its own network. The probe records that hop too, for every case which
names the probe under an address both containers reach. The two loopback cases are the exception:
`127.0.0.1` inside the conversion service names that service, not the probe, so there the probe
witnesses the first hop alone.

A refusal costs the document the resource and nothing else. The last section says so from both
sides: what a stylesheet keeps around an address it may not load, and what the answer of the
server reports about the addresses it refused.
"""

from __future__ import annotations

import base64
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar, NoReturn

import fitz

from tests.constants import PdfExporterFeature
from tests.pdf_exporter_test_case import PdfExporterTestCase
from tests.ssrf_probe import PROBE_BODY_MARKER, PROBE_IMAGE_HEIGHT, PROBE_IMAGE_WIDTH, PROBE_PNG, SsrfProbe
from tests.ssrf_support import (
    answers_on_loopback,
    containerized_run,
    polarion_base_url,
    reachable_probe_endpoint,
    release_docker,
    served_as,
    start_loopback_forwarder,
    stop_loopback_forwarder,
)


if TYPE_CHECKING:
    from requests import Response


BLOCKED_RESOURCES_COUNT: str = "Blocked-Resources-Count"
# what `#ff0000` and `#000000` are once a reader has drawn them
RED: int = 0xFF0000
BLACK: int = 0x000000
RED_DECLARATION: str = "#ff0000"
BLOCKED_RESOURCES: str = "Blocked-Resources"

TRANSPARENT_PIXEL: str = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
# a picture which paints, carried by the document itself: what a policy stripping everything loses
VISIBLE_PICTURE: str = "data:image/png;base64," + base64.b64encode(PROBE_PNG).decode()


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
        release_docker()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        if self.__class__.probe is None:
            self._unavailable("no probe reachable from the Polarion container")
        self._probe().reset()

    def _unavailable(self, reason: str) -> NoReturn:
        """A missing piece of the harness: a failure where the harness owns it, a skip where it does not.

        The GitHub Actions run is the required check on `main` and starts the container itself, so a
        probe nobody can reach is a broken run there and has to be red. The nightly run against a
        long-lived server has no docker to ask, and skips.
        """
        if containerized_run():
            self.fail(f"the external-resource cases cannot run: {reason}")
        self.skipTest(reason)

    def _probe(self) -> SsrfProbe:
        probe: SsrfProbe | None = self.__class__.probe
        if probe is None:
            self.fail("the probe is gone")
        return probe

    # ------------------------------------------------------------------ helpers

    def _document(self, body: str) -> str:
        return f"<html><head><meta charset='utf-8'/></head><body>{body}</body></html>"

    def _export_response(self, body: str) -> Response:
        response: Response = self._convert_html(self.api(), html=self._document(body))
        self.assertEqual(HTTPStatus.OK, response.status_code, "a refused resource must not break the export")
        return response

    def _export(self, body: str) -> bytes:
        return self._export_response(body).content

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
            # the forwarder ends by itself after its lifetime, so a slow run finds it gone rather
            # than broken: it is started once more before the loopback is called unreachable
            self.__class__.loopback_forwarded = start_loopback_forwarder(self._probe().port, self.__class__.endpoint.rsplit(":", 1)[0])
            if not self.__class__.loopback_forwarded or not answers_on_loopback(self._probe().port, family):
                self._unavailable(f"the probe does not answer on the {family} loopback of the container")
        self._probe().reset()

    def _text_of(self, pdf_bytes: bytes) -> str:
        """The text of every page, without its spacing.

        The raw bytes of a pdf carry no readable text - WeasyPrint compresses the content streams -
        so a case which looks for a body in the file has to read the file as a reader does. The
        spacing goes because a long word is broken across lines wherever it does not fit.
        """
        document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            return "".join("".join(document[index].get_text().split()) for index in range(len(document)))
        finally:
            document.close()

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
        # nothing answers at this address here, so the probe cannot witness this one. The case holds
        # the direction: it fails on the day the address answers and what it gives reaches the file
        self._refused("<p><img src='http://169.254.169.254/latest/meta-data/'/></p>")

    def test_a_network_path_reference_is_refused(self) -> None:
        # '//host/path' names no scheme and is loaded under both, so both have to be refused
        self._refused(f"<p><img src='//{self.endpoint}/probe/ok.png'/></p>")

    def test_a_file_url_is_refused(self) -> None:
        # no request leaves the machine for a 'file:' url either way, so the probe cannot witness it.
        # The exported document is the witness instead: the file it names must not stand in it
        pdf_bytes: bytes = self._export("<p><img src='file:///etc/passwd'/>text</p>")
        self._assert_probe_silent()
        self.assertNotIn("root:", self._text_of(pdf_bytes), "the content of a local file reached the exported document")
        self.assertEqual([], self._embedded_pictures(pdf_bytes), "only the placeholder may stand where the resource was refused")

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

    # ------------------------------------------------------------------ the reported issue

    def test_the_body_of_a_refused_resource_never_reaches_the_file(self) -> None:
        """The reported issue itself: the whole response written into the exported document.

        The report named `{image:https://httpbun.com/get}` in a document and exported it; the produced
        file carried the full json answer, headers and the address of the server among it. The url is
        never fetched now, and where it stood only the placeholder remains.
        """
        pdf_bytes: bytes = self._refused(f"<p><img src='http://{self.endpoint}/probe/report.json'/>text</p>")

        self.assertNotIn(PROBE_BODY_MARKER, self._text_of(pdf_bytes), "the body of the answer reached the exported document")
        self.assertEqual([], self._embedded_pictures(pdf_bytes), "only the placeholder may stand where the resource was refused")

    def test_a_body_which_is_not_a_picture_is_not_embedded(self) -> None:
        """The shape of the reported issue: a trusted origin answering with something else than a picture.

        The reporter named an external url whose body was json; the whole response was written into
        the exported file. The address gate does not decide this one - a document may always name the
        server it is exported from - so the content does, and this url answers with the login page
        under the name of a picture.
        """
        base: str | None = polarion_base_url()
        if base is None:
            self._unavailable("the base url of the server is unknown")
        url: str = f"{base}/polarion/wiki/skins/sidecar/msg.png"
        served: tuple[int, str] | None = served_as(url)
        if served is None:
            self._unavailable(f"what the server answers for {url} could not be read")
        status: int = served[0]
        content_type: str = served[1]
        self.assertEqual(HTTPStatus.OK, status, f"this case stands on {url} answering 200")
        self.assertNotIn("image/", content_type, f"this case stands on {url} answering with something which is not a picture")

        pdf_bytes: bytes = self._export(f"<p><img src='{url}'/>text</p>")

        self.assertEqual([], self._embedded_pictures(pdf_bytes), "only the placeholder may stand where the resource was refused")

    def test_a_picture_from_the_server_is_embedded(self) -> None:
        # the other half of the case above: a real picture on the same origin still reaches the document,
        # so the refusal above is about the content and not about the address
        base: str | None = polarion_base_url()
        if base is None:
            self._unavailable("the base url of the server is unknown")
        pdf_bytes: bytes = self._export(f"<p><img src='{base}/polarion/icons/default/enums/document_package.png'/>text</p>")

        self.assertTrue(self._embedded_pictures(pdf_bytes), "a picture from the server itself must still be embedded")

    def _embedded_pictures(self, pdf_bytes: bytes) -> list[tuple[int, int]]:
        """Every embedded picture larger than the 1x1 placeholder."""
        found: list[tuple[int, int]] = []
        document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            for page_index in range(len(document)):
                for image in document[page_index].get_images(full=True):
                    extracted: dict[str, int] = document.extract_image(image[0])
                    if extracted["width"] > 1 or extracted["height"] > 1:
                        found.append((extracted["width"], extracted["height"]))
        finally:
            document.close()
        return found

    # ------------------------------------------------------------------ what must keep working

    def test_a_relative_url_is_left_alone(self) -> None:
        # nothing answers under this name, so what is asserted is that the policy did not take the
        # paragraph apart around it: the text beside the picture still stands
        pdf_bytes: bytes = self._export("<p><img src='images/logo.png'/>relative-url-case</p>")
        self._assert_probe_silent()
        self.assertIn("relative-url-case", self._text_of(pdf_bytes), "the text beside a relative url was lost")

    def test_a_data_url_is_kept(self) -> None:
        # a data url carries its own picture, so the picture has to reach the document: a policy
        # which strips everything fails here
        pdf_bytes: bytes = self._export(f"<p><img src='{VISIBLE_PICTURE}'/>text</p>")
        self._assert_probe_silent()
        self.assertIn((PROBE_IMAGE_WIDTH, PROBE_IMAGE_HEIGHT), self._embedded_pictures(pdf_bytes), "the picture of a data url was dropped")

    # ------------------------------------------------------------------ the placeholder

    def test_the_placeholder_paints_nothing(self) -> None:
        # a refused picture is replaced by a placeholder, and a placeholder which paints marks the
        # document where the reader expects the picture
        refused: bytes = self._export(f"<p><img src='http://{self.endpoint}/probe/ok.png'/>text</p>")
        transparent: bytes = self._export(f"<p><img src='{TRANSPARENT_PIXEL}'/>text</p>")
        visible: bytes = self._export(f"<p><img src='{VISIBLE_PICTURE}'/>text</p>")

        self.assertEqual(self._rendered_pages(transparent), self._rendered_pages(refused))
        # and the comparison has to be able to tell two renders apart, or it holds for free
        self.assertNotEqual(self._rendered_pages(visible), self._rendered_pages(refused))

    def _rendered_pages(self, pdf_bytes: bytes) -> list[bytes]:
        document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            return [document[index].get_pixmap(dpi=150).tobytes("png") for index in range(len(document))]
        finally:
            document.close()

    # ------------------------------------------------------------------ what a refusal costs the stylesheet

    def _styled(self, declarations: str) -> str:
        return f"<style>p {{ {declarations} }}</style><p>text</p>"

    def _text_colors(self, pdf_bytes: bytes) -> set[int]:
        """Every color a glyph of the document is drawn in.

        A whole page compares badly - a stylesheet naming one declaration more produces a file of
        another size and the glyphs land on slightly other pixels - while the color of the text says
        exactly what the case asks: whether the declaration beside the refused address still applies.
        """
        document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        try:
            return {span["color"] for index in range(len(document)) for block in document[index].get_text("dict")["blocks"] for line in block.get("lines", []) for span in line["spans"]}
        finally:
            document.close()

    def _assert_the_stylesheet_survived(self, declarations: str) -> None:
        """Export a document styled red beside `declarations`, and read the color back out of it."""
        refused: bytes = self._export(self._styled(f"color: {RED_DECLARATION}; {declarations}"))
        self._assert_probe_silent()

        self.assertEqual({RED}, self._text_colors(refused), "the stylesheet lost more than the address it named")
        # and the color has to be read out of the file rather than assumed, or the case holds for free
        self.assertEqual({BLACK}, self._text_colors(self._export(self._styled("color: #000000;"))))

    def test_a_stylesheet_keeps_its_declarations_around_a_refused_address(self) -> None:
        """A refused address costs the stylesheet the address and nothing else.

        The reported case lost the whole file: a style package of 2.4 MB became 55 bytes and the
        exported document carried none of its styles. The stylesheet here may lose the picture it
        names - nothing fetches it - and may not lose the declaration standing beside it.
        """
        self._assert_the_stylesheet_survived(f"background-image: url(http://{self.endpoint}/probe/ok.png);")

    def test_an_address_the_parser_cannot_account_for_leaves_the_rest_of_the_stylesheet(self) -> None:
        """A bracket inside `url(...)`: the parser reads no address there, so the walk over the text does.

        This is the stylesheet the inlining cannot vouch for declaration by declaration, and the one
        which used to be dropped whole for it. Only the address is neutralized now.
        """
        self._assert_the_stylesheet_survived(f"background-image: url(http://{self.endpoint}/probe/ok.png?x=(a));")

    def test_a_colon_in_the_last_segment_does_not_abort_the_export(self) -> None:
        """A url is judged, not read as a path of the host.

        The extension of a url used to be read by `FilenameUtils.getExtension`, which throws on a ':'
        standing after the last separator: there it names an NTFS alternate data stream. A url may
        carry one anywhere, and the throw took the whole export with it rather than the one address.
        The export completes here, and the address is refused like any other.
        """
        response: Response = self._export_response(f"<p><img src='http://{self.endpoint}/probe/a:b.png'/>text</p>")
        self._assert_probe_silent()

        self.assertEqual("1", response.headers.get(BLOCKED_RESOURCES_COUNT), "the answer has to count the resource it refused")
        self.assertIn(self.endpoint, response.headers.get(BLOCKED_RESOURCES, ""), "the answer has to name the address it refused")

    # ------------------------------------------------------------------ what the answer reports

    def test_the_answer_names_the_resource_it_refused(self) -> None:
        """A refusal leaves no mark in the file, so the answer carries it: the export dialog reads these headers."""
        response: Response = self._export_response(f"<p><img src='http://{self.endpoint}/probe/ok.png'/>text</p>")
        self._assert_probe_silent()

        self.assertEqual("1", response.headers.get(BLOCKED_RESOURCES_COUNT), "the answer has to count the resource it refused")
        self.assertIn(self.endpoint, response.headers.get(BLOCKED_RESOURCES, ""), "the answer has to name the address it refused")

    def test_the_answer_reports_nothing_when_nothing_was_refused(self) -> None:
        # the other half: a document naming only what it carries itself is not degraded, and the answer
        # carries no header at all for it - which is what the export dialog reads as "nothing to report"
        response: Response = self._export_response(f"<p><img src='{VISIBLE_PICTURE}'/>text</p>")

        self.assertIsNone(response.headers.get(BLOCKED_RESOURCES_COUNT), "an export which refused nothing must report nothing")
        self.assertIsNone(response.headers.get(BLOCKED_RESOURCES), "an export which refused nothing must name nothing")

    # ------------------------------------------------------------------ the reported case, end to end

    def test_the_css_setting_of_a_document_export_keeps_its_declarations(self) -> None:
        """The reported case from the setting to the exported document.

        The reporter put `@page { background: url(...) }` into the CSS setting of a style package and the
        export lost every style of it. Here the document keeps the color the same setting gives it, the
        probe is never asked for the picture, and the answer names the address it refused.
        """
        name: str = "external-resource-case"
        self.addCleanup(self.api().delete_setting, feature=PdfExporterFeature.CSS, name=name, scope=self.scope)
        page: str = "@page { margin: 0; background: %s no-repeat center 100%%; background-size: contain; }"

        refused: Response = self._export_with_css(name, (page % f"url('http://{self.endpoint}/probe/ok.png')") + f"\n* {{ color: {RED_DECLARATION} !important; }}")
        self._assert_probe_silent()

        self.assertGreaterEqual(int(refused.headers.get(BLOCKED_RESOURCES_COUNT, "0")), 1, "the answer has to count the resource it refused")
        self.assertIn(self.endpoint, refused.headers.get(BLOCKED_RESOURCES, ""), "the answer has to name the address it refused")
        self.assertIn(RED, self._text_colors(refused.content), "the document lost the color its CSS setting gives it")

        # and the color has to come from the setting rather than from the document, or the case holds for free
        without_the_color: Response = self._export_with_css(name, page % "none")
        self.assertNotIn(RED, self._text_colors(without_the_color.content))

    def _export_with_css(self, name: str, css: str) -> Response:
        """Export the document of the suite under a CSS setting of this text."""
        self._probe().reset()
        saved: Response = self.api().save_setting(feature=PdfExporterFeature.CSS, name=name, scope=self.scope, data={"css": css, "disableDefaultCss": False})
        self.assertEqual(HTTPStatus.NO_CONTENT, saved.status_code)

        response: Response = self._convert(self.project_id, self.DOCUMENT_LOCATION, custom_export_params={"css": name})
        self.assertEqual(HTTPStatus.OK, response.status_code, "a refused resource must not break the export")
        return response
