from __future__ import annotations

import json
import time
from http import HTTPStatus
from typing import TYPE_CHECKING

from python_sbb_polarion.extensions.pdf_exporter import DocumentType

from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


COLLECTION_ID = "1"

# Dedicated LIVE_DOC stored as part of the project template under
# `test-data/project-template/pdf_exporter_elibrary_st/modules/Specification/Work Items Query Test Spec/`.
# The document is laid out so that every chapter contains only work items
# (no prose between headings), which makes cutEmptyChapters observable and
# forces snapshot-level divergence between filter outcomes. The initial
# content was produced via the test-data extension's
# POST /internal/projects/{projectId}/spaces/Specification/work-items-query-fixture
# endpoint (WorkItemsQueryFixtureService) and then exported into the template.
FIXTURE_DOC = "Specification/Work Items Query Test Spec"


class PdfExporterWorkItemsQueryTest(PdfExporterTestCase):
    """System tests for the Work Items Query filter feature.

    Each PDF-producing test:
      1. Pins the header/footer to HEADER_FOOTER_WITHOUT_TIMESTAMP so the PDF
         is byte-deterministic across runs.
      2. Converts the resulting PDF to PNG via `_pdf_to_png`.
      3. Compares the PNG(s) page-by-page with `_compare_pdf_pages` against
         golden snapshots in `test-data/expected/`.

    On first run the expected PNGs are absent and the comparison will fail —
    copy `test-data/output/test_work_items_query_*_page_*.png` to
    `test-data/expected/` after manual review, then re-run.
    """

    def setUp(self) -> None:
        super().setUp()
        # Per-test bookkeeping for style packages so a failing test before
        # tearDown can't leak names into the next one.
        self._style_packages_to_cleanup: list[str] = []

    def tearDown(self) -> None:
        for name in self._style_packages_to_cleanup:
            self.api().delete_style_package(name, scope=self.scope)
        self._style_packages_to_cleanup.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _convert_fixture(self, custom_export_params: JsonDict | None = None, print_error: bool = True) -> Response:
        return self._convert(
            project_id=self.project_id,
            location_path=FIXTURE_DOC,
            custom_export_params=custom_export_params,
            print_error=print_error,
        )

    def _assert_pdf_matches_snapshot(self, pdf_bytes: bytes, custom_prefix: str) -> int:
        page_numbers: int = self._pdf_to_png(
            pdf_bytes=pdf_bytes,
            custom_prefix=custom_prefix,
            output_folder=self._get_output_folder(),
        )
        self.assertGreater(page_numbers, 0, "Resulting PDF must have at least one page")
        self._compare_pdf_pages(
            custom_prefix=custom_prefix,
            page_numbers=page_numbers,
            expected_folder=self._get_expected_folder(),
            output_folder=self._get_output_folder(),
        )
        return page_numbers

    def _create_style_package_with_query(
        self,
        work_items_query: str | None,
        matching_query: str = "",
        weight: float = 90.0,
    ) -> str:
        """Create a Style Package in test scope with the given workItemsQuery and high weight.

        High weight ensures it wins over the default Repository Style Package when
        the backend auto-selects the most suitable one.
        """
        new_name: str = f"WIQuery_ST_{time.time_ns()}"
        data: JsonDict = {
            "matchingQuery": matching_query,
            "weight": weight,
            "exposeSettings": True,
            "workItemsQuery": work_items_query,
        }
        response: Response = self.api().save_style_package(new_name, data, self.scope)
        self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)
        self._style_packages_to_cleanup.append(new_name)
        return new_name

    # ------------------------------------------------------------------
    # 1-4: convert with / without / no-match / unicode query
    # ------------------------------------------------------------------

    def test_convert_live_doc_with_work_items_query_filter(self) -> None:
        """Query `type:heading` keeps only the 4 chapter headings — snapshot-verified."""
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {"urlQueryParameters": {"query": "type:heading"}}
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self.assertIsNotNone(response.content)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_live_doc_with_query_heading")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_convert_live_doc_without_query_keeps_all_workitems(self) -> None:
        """Baseline export without any query — full document snapshot (multi-page)."""
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            response: Response = self._convert_fixture()

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_live_doc_without_query")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_convert_live_doc_with_query_no_match(self) -> None:
        """A query that matches no body work items still renders chapter headings.

        Polarion's renderer treats heading work items as part of the document
        outline, so a `title:zzz_no_match_xyz` query — which matches zero WIs by
        title — produces a PDF showing just the 4 chapter headings (no body
        rows). That makes this snapshot intentionally identical to
        `test_convert_live_doc_with_work_items_query_filter` (`type:heading`):
        both end up rendering only the chapter outline. The two scenarios
        exercise different filter branches in the backend even though their
        rendered output is the same.
        """
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {"urlQueryParameters": {"query": "title:zzz_no_match_xyz"}}
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_live_doc_with_query_no_match")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_convert_with_unicode_query(self) -> None:
        """Unicode in the query must be accepted and actually match.

        The fixture has two WIs whose title starts with `Übersicht`:
        the chapter heading `Übersicht der Filter` and the requirement
        `Übersicht der Lucene-Validierung` under it. A successful UTF-8 round
        trip through the export pipeline means `title:Übersicht` returns 200
        and the snapshot pins both items (chapter heading + its requirement) —
        which is what distinguishes this snapshot from `with_query_no_match`.
        """
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {"urlQueryParameters": {"query": "title:Übersicht"}}
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(
                HTTPStatus.OK,
                response.status_code,
                f"Unicode query must be accepted, got {response.status_code}: {response.text[:200]}",
            )
            self._assert_pdf_matches_snapshot(response.content, "test_convert_unicode_query")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    # ------------------------------------------------------------------
    # 5-6: backend validation of work items query
    # ------------------------------------------------------------------

    def test_convert_with_invalid_query_returns_bad_request(self) -> None:
        """Syntactically invalid Lucene query is rejected with 400."""
        custom_export_params: JsonDict = {"urlQueryParameters": {"query": "type:(((unclosed_paren"}}
        response: Response = self._convert_fixture(
            custom_export_params=custom_export_params,
            print_error=False,
        )

        self.assertEqual(HTTPStatus.BAD_REQUEST, response.status_code)
        self.assertIn("Invalid work items query", response.text)

    def test_convert_with_empty_query_is_accepted(self) -> None:
        """Empty query string is treated as 'no filter' — same snapshot as baseline."""
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {"urlQueryParameters": {"query": ""}}
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            # The PDF should be identical to the no-query baseline.
            self._assert_pdf_matches_snapshot(response.content, "test_convert_live_doc_without_query")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    # ------------------------------------------------------------------
    # 7-8: StylePackage save/load round-trip for workItemsQuery
    # ------------------------------------------------------------------

    def test_style_package_save_and_load_work_items_query(self) -> None:
        """Saving a StylePackage with workItemsQuery and reading it back returns the same value."""
        name: str = self._create_style_package_with_query(work_items_query="type:requirement")

        response: Response = self.api().get_style_package(name, scope=self.scope)
        self.assertEqual(HTTPStatus.OK, response.status_code)
        loaded: JsonDict = json.loads(response.content)
        self.assertEqual("type:requirement", loaded.get("workItemsQuery"))

    def test_style_package_save_with_null_work_items_query(self) -> None:
        """Saving a StylePackage with workItemsQuery=null leaves it absent in the JSON response (NON_NULL)."""
        name: str = self._create_style_package_with_query(work_items_query=None)

        response: Response = self.api().get_style_package(name, scope=self.scope)
        self.assertEqual(HTTPStatus.OK, response.status_code)
        loaded: JsonDict = json.loads(response.content)
        self.assertNotIn(
            "workItemsQuery",
            loaded,
            "workItemsQuery should be omitted from JSON when null (Jackson @JsonInclude(NON_NULL))",
        )

    # ------------------------------------------------------------------
    # 9-10: StylePackage default workItemsQuery fallback at convert time
    # ------------------------------------------------------------------

    def test_style_package_work_items_query_applied_as_default(self) -> None:
        """autoSelectStylePackage=true + StylePackage.workItemsQuery applies as default filter — verified via snapshot."""
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            self._create_style_package_with_query(work_items_query="type:heading")

            custom_export_params: JsonDict = {"autoSelectStylePackage": True}
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            # Expected to match the same snapshot as explicit type:heading query.
            self._assert_pdf_matches_snapshot(response.content, "test_convert_live_doc_with_query_heading")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_explicit_query_overrides_style_package_default(self) -> None:
        """Explicit urlQueryParameters.query wins over StylePackage.workItemsQuery — verified via snapshot.

        If the StylePackage default `type:heading` had won, the PDF would be the
        same as in `test_style_package_work_items_query_applied_as_default`.
        Because the explicit `type:epic` wins, the PDF contains the 2 epics
        in addition to the 4 chapter headings — a distinct snapshot.
        """
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            self._create_style_package_with_query(work_items_query="type:heading")

            custom_export_params: JsonDict = {
                "autoSelectStylePackage": True,
                "urlQueryParameters": {"query": "type:epic"},
            }
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_explicit_query_overrides_style_package")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    # ------------------------------------------------------------------
    # 11-12: collection bulk export — query is propagated to each document
    # ------------------------------------------------------------------

    def test_collection_export_propagates_query_to_each_document(self) -> None:
        """Emulate bulk-collection front-end: convert every LIVE_DOC in the collection
        with the same query and assert each resulting PDF matches its snapshot.

        Snapshots for all documents are generated up-front so that the first run
        produces every `_page_*.png` in the output folder, regardless of whether
        an individual comparison fails. Comparison failures are aggregated and
        reported at the end.
        """
        documents_response: Response = self.api().get_documents_from_collection(
            project_id=self.project_id,
            collection_id=COLLECTION_ID,
        )
        self.assertEqual(HTTPStatus.OK, documents_response.status_code)
        documents: list[JsonDict] = documents_response.json()
        self.assertGreater(len(documents), 0, "Collection must contain at least one document")

        live_docs: list[JsonDict] = [d for d in documents if d.get("documentType") == DocumentType.LIVE_DOC]
        self.assertGreater(len(live_docs), 0, "Collection must contain at least one LIVE_DOC")

        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {"urlQueryParameters": {"query": "type:heading"}}

            # Stage 1: convert every document and render PDF → PNG up-front, so even
            # if comparison fails later, all output PNGs are available for review.
            generated: list[tuple[str, int]] = []
            for doc in live_docs:
                project_id: str = str(doc["projectId"])
                space_id: str = str(doc["spaceId"])
                document_name: str = str(doc["documentName"])
                location_path: str = f"{space_id}/{document_name}"
                response: Response = self._convert(
                    project_id=project_id,
                    location_path=location_path,
                    custom_export_params=custom_export_params,
                )
                self.assertEqual(
                    HTTPStatus.OK,
                    response.status_code,
                    f"Convert failed for collection document '{location_path}'",
                )
                safe_space: str = space_id.replace(" ", "_").replace("/", "_")
                safe_name: str = document_name.replace(" ", "_").replace("/", "_")
                custom_prefix: str = f"test_collection_export_query_{safe_space}_{safe_name}"
                page_numbers: int = self._pdf_to_png(
                    pdf_bytes=response.content,
                    custom_prefix=custom_prefix,
                    output_folder=self._get_output_folder(),
                )
                self.assertGreater(page_numbers, 0, f"PDF for '{location_path}' has no pages")
                generated.append((custom_prefix, page_numbers))

            # Stage 2: compare all snapshots, collect failures, fail at the end.
            failures: list[str] = []
            for prefix, page_count in generated:
                try:
                    self._compare_pdf_pages(
                        custom_prefix=prefix,
                        page_numbers=page_count,
                        expected_folder=self._get_expected_folder(),
                        output_folder=self._get_output_folder(),
                    )
                except AssertionError as e:
                    failures.append(f"[{prefix}] {e}")
            if failures:
                self.fail("Collection snapshot comparison failed for one or more documents:\n" + "\n\n".join(failures))
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    # The LIVE_REPORT-in-collection scenario is not automated because the test
    # harness re-uploads the project template at each run, but test-data's
    # ProjectTemplateService/BaselineService can't restore a baseline collection
    # that contains a rich page (the upload silently drops the collection,
    # so any test depending on it would fail with 404). The behaviour
    # "LiveReportAdapter ignores urlQueryParameters.query when applied to a
    # rich page during a collection-bulk export" must therefore be exercised
    # manually against a real Polarion instance — recipe:
    #   1. Add a rich page to baseline collection 1 via the Polarion UI.
    #   2. POST /pdf-exporter/rest/internal/convert with body:
    #        { "documentType": "LIVE_REPORT",
    #          "projectId": "<your_project>",
    #          "locationPath": "<space>/<RichPageName>",
    #          "urlQueryParameters": { "query": "type:heading" } }
    #   3. Expect 200 OK (the query parameter must be silently ignored by
    #      LiveReportAdapter, not rejected with 400).

    # ------------------------------------------------------------------
    # A: Lucene syntax edge cases
    # ------------------------------------------------------------------

    def test_convert_with_compound_query_AND(self) -> None:
        """Compound query with AND must be accepted and applied — snapshot-verified."""
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            # Fixture has exactly one requirement titled "Filter by id" — AND-narrowed
            # to a single WI lets the snapshot pin which row remains in chapter 1.
            custom_export_params: JsonDict = {
                "urlQueryParameters": {"query": 'type:requirement AND title:"Filter by id"'},
            }
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_compound_query_AND")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_convert_with_quoted_query(self) -> None:
        """A quoted phrase must round-trip through query parsing and produce the expected match.

        The fixture has two WIs containing the adjacent tokens `Quoted Phrase`
        in their title: the chapter heading `Quoted Phrase Compatibility` and
        the requirement `Quoted Phrase acceptance` under it. The snapshot pins
        both — that's how this scenario distinguishes itself from
        `with_query_no_match`.
        """
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {"urlQueryParameters": {"query": 'title:"Quoted Phrase"'}}
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_quoted_query")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_convert_with_id_query(self) -> None:
        """Filtering by a single title keeps just that one work item — snapshot-verified.

        Generated WI ids are unstable across project provisioning, so we pin the
        single-WI result by a deterministic title set up by the fixture service.
        """
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {"urlQueryParameters": {"query": 'title:"Filter by id"'}}
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_title_query")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_convert_with_very_long_query(self) -> None:
        """A long disjunction must be transported, parsed and applied without errors."""
        long_query: str = " OR ".join(f'title:"Filter by id {i}"' for i in range(1, 201))  # ~ 4 KB
        custom_export_params: JsonDict = {"urlQueryParameters": {"query": long_query}}
        response: Response = self._convert_fixture(custom_export_params=custom_export_params)

        self.assertEqual(
            HTTPStatus.OK,
            response.status_code,
            f"Long query should be accepted with 200, got {response.status_code}: {response.text[:200]}",
        )

    # ------------------------------------------------------------------
    # B: StylePackage lifecycle for workItemsQuery
    # ------------------------------------------------------------------

    def test_style_package_update_adds_work_items_query(self) -> None:
        """Update existing StylePackage to add workItemsQuery — persisted and readable."""
        name: str = self._create_style_package_with_query(work_items_query=None)

        # Read current data, mutate, save back.
        current: JsonDict = json.loads(self.api().get_style_package(name, scope=self.scope).content)
        current["workItemsQuery"] = "type:requirement"
        save_response: Response = self.api().save_style_package(name, current, self.scope)
        self.assertEqual(HTTPStatus.NO_CONTENT, save_response.status_code)

        updated: JsonDict = json.loads(self.api().get_style_package(name, scope=self.scope).content)
        self.assertEqual("type:requirement", updated.get("workItemsQuery"))

    def test_style_package_update_clears_work_items_query(self) -> None:
        """Clearing workItemsQuery (set to null) on update removes it from the persisted JSON."""
        name: str = self._create_style_package_with_query(work_items_query="type:requirement")

        # Sanity: it is there.
        initial: JsonDict = json.loads(self.api().get_style_package(name, scope=self.scope).content)
        self.assertEqual("type:requirement", initial.get("workItemsQuery"))

        # Clear it.
        initial["workItemsQuery"] = None
        save_response: Response = self.api().save_style_package(name, initial, self.scope)
        self.assertEqual(HTTPStatus.NO_CONTENT, save_response.status_code)

        updated: JsonDict = json.loads(self.api().get_style_package(name, scope=self.scope).content)
        self.assertNotIn("workItemsQuery", updated)

    # ------------------------------------------------------------------
    # C: Integration with other export options
    # ------------------------------------------------------------------

    def test_convert_with_query_and_cut_empty_chapters(self) -> None:
        """Filter WIs by a narrow query + drop chapters left empty by the filter.

        `title:"Filter by id"` keeps a single requirement in chapter 1. The
        fixture has no prose between headings, so chapters 2/3/4 contain only
        non-matching WIs and become empty under the filter. With
        `cutEmptyChapters=true`, those three chapters must be dropped — the
        resulting PDF differs from the un-cut version and from the no-query
        baseline.
        """
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {
                "urlQueryParameters": {"query": 'title:"Filter by id"'},
                "cutEmptyChapters": True,
            }
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_query_and_cut_empty_chapters")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    def test_convert_with_query_and_mark_referenced_workitems(self) -> None:
        """Mark-referenced-workitems styling applies on top of the filter — snapshot-verified."""
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            custom_export_params: JsonDict = {
                "urlQueryParameters": {"query": "type:requirement"},
                "markReferencedWorkitems": True,
            }
            response: Response = self._convert_fixture(custom_export_params=custom_export_params)

            self.assertEqual(HTTPStatus.OK, response.status_code)
            self._assert_pdf_matches_snapshot(response.content, "test_convert_query_and_mark_referenced_workitems")
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)

    # `chapters` selector requires Polarion outline numbering on the source document
    # (cutNotNeededChapters identifies chapters via the <span><span>NUMBER</span></span>
    # markup that Polarion only emits when outline numbering is enabled). The
    # Work Items Query Test Spec fixture intentionally does not use outline numbering,
    # so combining `chapters: [...]` with this fixture removes every chapter — not a
    # useful scenario to snapshot-verify. Not testing.

    # ------------------------------------------------------------------
    # D: Multi-page documents — filter strictly reduces page count
    # ------------------------------------------------------------------

    def test_convert_multi_page_doc_with_query_reduces_pages(self) -> None:
        """Applying a tight filter to a multi-page document strictly reduces pages.

        The new dedicated fixture is short on purpose (it must collapse
        cleanly under different filters), so this test uses the much larger
        Product Specification — which spans many pages and contains both
        requirements and user stories — to actually exercise the multi-page
        reduction path. We don't snapshot here: the assertion is purely
        on the page count.
        """
        previous_header_footer_settings: JsonDict
        previous_header_footer_settings, _ = self._save_header_footer_settings(self.HEADER_FOOTER_WITHOUT_TIMESTAMP)
        try:
            multi_page_doc: str = "Specification/Product Specification"

            baseline_response: Response = self._convert(
                project_id=self.project_id,
                location_path=multi_page_doc,
            )
            self.assertEqual(HTTPStatus.OK, baseline_response.status_code)
            baseline_pages: int = self._pdf_to_png(
                pdf_bytes=baseline_response.content,
                custom_prefix="test_multi_page_baseline",
                output_folder=self._get_output_folder(),
            )

            filtered_response: Response = self._convert(
                project_id=self.project_id,
                location_path=multi_page_doc,
                custom_export_params={
                    "urlQueryParameters": {"query": "type:heading"},
                    "cutEmptyChapters": True,
                },
            )
            self.assertEqual(HTTPStatus.OK, filtered_response.status_code)
            filtered_pages: int = self._pdf_to_png(
                pdf_bytes=filtered_response.content,
                custom_prefix="test_multi_page_filtered",
                output_folder=self._get_output_folder(),
            )

            self.assertGreater(baseline_pages, 1, "Baseline PDF must span multiple pages")
            self.assertLess(
                filtered_pages,
                baseline_pages,
                f"Filtered PDF must have fewer pages than baseline (filtered={filtered_pages}, baseline={baseline_pages})",
            )
        finally:
            self._save_header_footer_settings(previous_header_footer_settings)
