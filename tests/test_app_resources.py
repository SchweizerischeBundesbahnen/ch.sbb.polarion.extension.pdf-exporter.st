"""The app modules the server's own surfaces name by a fixed URL.

`bulk-widget.js`, `export-popup.js` and `side-panel.js` keep their names through the build, because
what loads them cannot know the hashed names Vite gives the rest of the bundle: a Java widget
renderer, the fragment of the Document Properties pane, and the toolbar injectors. The same paths
are read on the server as well - `BundleCacheKey` hashes each module to build the cache key of its
URL - and nothing in the build ties the two together.

So a module renamed or moved costs the feature quietly: the import fails in the browser, and the
cache key falls back to the version alone, which is the stale-module bug it was written against.

The toolbar injectors are not covered here. They are served from the extension's own web context,
which answers a token-authenticated request with Polarion's login page rather than the script; only
a browser session reaches them.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from python_sbb_polarion.types import Header

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from requests import Response


APP_ASSETS: str = "/polarion/pdf-exporter-app/ui/app/assets"


class PdfExporterAppResourcesTest(PdfExporterTestCase):
    """The fixed-name modules of the app, as the browser asks for them."""

    def _assert_module_is_served(self, name: str, exported_symbol: str) -> None:
        url: str = f"{APP_ASSETS}/{name}"
        response: Response = self.api().polarion_connection.api_request_get(url)

        self.assertEqual(HTTPStatus.OK, response.status_code, f"{name} is not served")
        self.assertIn("javascript", response.headers.get(Header.CONTENT_TYPE, ""), f"{name} is not served as javascript")
        # the name its importer calls, which is what `preserveEntrySignatures: 'strict'` keeps
        self.assertIn(exported_symbol, response.text, f"{name} does not export {exported_symbol}")

    def test_the_bulk_export_widget_module_is_served(self) -> None:
        # BulkPdfExportWidgetRenderer imports it and calls its default export with the shim's id
        self._assert_module_is_served("bulk-widget.js", "as default")

    def test_the_export_dialog_module_is_served(self) -> None:
        # the three toolbar injectors and ExportToPdfButtonRenderer import it on click
        self._assert_module_is_served("export-popup.js", "openExportPopup")

    def test_the_side_panel_module_is_served(self) -> None:
        # the fragment PdfExporterFormExtension renders into the Document Properties pane imports it
        self._assert_module_is_served("side-panel.js", "mountSidePanel")
