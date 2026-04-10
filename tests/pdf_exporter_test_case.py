from __future__ import annotations

import pathlib
from contextlib import contextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import cv2
import fitz
from python_sbb_polarion.extensions.pdf_exporter import DocumentType, Orientation, PaperSize, PolarionPdfExporterApi
from python_sbb_polarion.testing.generic_test_case import GenericTestCase
from python_sbb_polarion.util import abs_path, abs_path_str

from tests.constants import PDF_RENDER_DPI, SUPPORTED_FEATURES


if TYPE_CHECKING:
    from collections.abc import Generator

    import numpy as np
    from numpy.typing import NDArray
    from python_sbb_polarion.extensions.admin_utility import PolarionAdminUtilityApi
    from python_sbb_polarion.testing.temp_project import TempProject
    from python_sbb_polarion.types import JsonDict
    from requests import Response


class PdfExporterTestCase(GenericTestCase):
    """PDF Exporter Test Case."""

    extension_api: PolarionPdfExporterApi
    admin_utility_api: PolarionAdminUtilityApi
    elibrary: TempProject

    DOCUMENT_LOCATION: str = "Specification/Administration Specification"

    HEADER_FOOTER_WITHOUT_TIMESTAMP: ClassVar[JsonDict] = {
        "useCustomValues": True,
        "headerLeft": "{{ PROJECT_NAME }}",
        "headerCenter": "",
        "headerRight": "<a href='https://www.sbb.ch/'><img src='/polarion/icons/group/sbb-headerlogo.png' alt='Schweizerische Bundesbahnen' style='height: 20px'></a>",
        "footerLeft": "{{ DOCUMENT_TITLE }}",
        "footerCenter": "",
        "footerRight": "{{ PAGE_NUMBER }}/{{ PAGES_TOTAL_COUNT }}",
    }

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.extension_api = cls.create_extension_api("pdf-exporter")
        cls.admin_utility_api = cls.create_extension_api("admin-utility")

    @classmethod
    def set_elibrary(cls, elibrary: TempProject) -> None:
        cls.elibrary = elibrary

    def setUp(self) -> None:
        self.project_id: str = self.__class__.elibrary.temp_project_id
        self.scope: str = f"project/{self.project_id}/"
        self.reinit_all_settings(features=SUPPORTED_FEATURES, scope=self.scope)

    def reinit_all_settings(self, features: list[str], scope: str | None = None) -> None:
        """Bulk reinitialize multiple feature settings."""
        for feature in features:
            self._init_settings(feature=feature, scope=scope)

    def _init_settings(self, feature: str, scope: str | None = None) -> None:
        """Initialize settings with default values to prevent clashes with default Repository settings."""
        default_settings: Response = self.api().get_setting_default_content(feature=feature)
        save_response: Response = self.api().save_setting(feature=feature, scope=scope, data=default_settings.json())
        self.assertEqual(HTTPStatus.NO_CONTENT, save_response.status_code)

    @contextmanager
    def suppress_api_errors(self) -> Generator[None]:
        """Context manager to suppress API error logging."""
        self.api().polarion_connection.set_print_error(False)
        try:
            yield
        finally:
            self.api().polarion_connection.set_print_error(True)

    def api(self) -> PolarionPdfExporterApi:
        return self.extension_api

    def _get_expected_folder(self) -> str:
        return abs_path_str("../test-data/expected")

    def _get_output_folder(self) -> str:
        return abs_path_str("../test-data/output")

    def _load_test_data(self, filename: str) -> str:
        filepath: pathlib.Path = abs_path(f"../test-data/{filename}")
        with filepath.open(encoding="utf-8") as test_file:
            content: str = test_file.read()
            return content

    def _pdf_to_png(self, pdf_bytes: bytes, custom_prefix: str, output_folder: str) -> int:
        pdf_document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]

        page_numbers: int = 0
        for page_index in range(len(pdf_document)):
            page_number: int = page_index + 1
            page: fitz.Page = pdf_document[page_index]  # type: ignore[no-any-unimported]
            pix: fitz.Pixmap = page.get_pixmap(dpi=PDF_RENDER_DPI)  # type: ignore[no-any-unimported]
            output_file: str = f"{output_folder}/{custom_prefix}_page_{page_number}.png"
            pix.save(output_file)
            page_numbers += 1

        pdf_document.close()
        return page_numbers

    def _create_ignore_mask(self, ignore_regions: list[tuple[int, int, int, int]], height: int, width: int) -> NDArray[np.uint8]:
        """Create a mask for regions to ignore during image comparison.

        Args:
            ignore_regions: List of rectangles as (left, top, right, bottom)
            height: Image height
            width: Image width

        Returns:
            Mask with ignored regions marked as 255
        """
        import numpy as np

        ignore_mask_raw: NDArray[np.uint8] | None = cv2.zeros((height, width), dtype="uint8") if hasattr(cv2, "zeros") else None
        if ignore_mask_raw is None:
            ignore_mask_raw = np.zeros((height, width), dtype=np.uint8)

        for rect in ignore_regions:
            if len(rect) != 4:
                raise AssertionError("Ignore region must be a 4-tuple (left, top, right, bottom)")
            left: int
            top: int
            right: int
            bottom: int
            left, top, right, bottom = rect
            # Clamp to image bounds
            left = max(0, min(int(left), width))
            top = max(0, min(int(top), height))
            right = max(0, min(int(right), width))
            bottom = max(0, min(int(bottom), height))
            if right <= left or bottom <= top:
                raise AssertionError("Invalid ignore region: right must be > left and bottom must be > top")
            cv2.rectangle(
                ignore_mask_raw,
                (left, top),
                (right - 1, bottom - 1),
                color=255,
                thickness=-1,
            )

        # Ensure proper type
        ignore_mask: NDArray[np.uint8] = np.asarray(ignore_mask_raw, dtype=np.uint8)
        return ignore_mask

    def _apply_ignore_mask(self, mask: NDArray[np.uint8], diff: NDArray[np.uint8], ignore_mask: NDArray[np.uint8]) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
        """Apply ignore mask to difference mask and diff image.

        Args:
            mask: Binary difference mask
            diff: Difference image
            ignore_mask: Regions to ignore

        Returns:
            Tuple of (updated mask, updated diff)
        """
        import numpy as np

        updated_mask: NDArray[np.uint8] = np.asarray(cv2.bitwise_and(mask, cv2.bitwise_not(ignore_mask)), dtype=np.uint8)
        # Also zero out color diff in ignored areas (for diff visualization)
        inv: NDArray[np.uint8] = cv2.bitwise_not(ignore_mask)  # type: ignore[assignment]
        if diff.ndim == 3:
            updated_diff: NDArray[np.uint8] = np.asarray(cv2.bitwise_and(diff, diff, mask=inv), dtype=np.uint8)
        else:
            updated_diff = np.asarray(cv2.bitwise_and(diff, inv), dtype=np.uint8)
        return updated_mask, updated_diff

    def _compare_images(self, image1_path: str, image2_path: str, ignore_regions: list[tuple[int, int, int, int]] | None = None) -> tuple[int | float, NDArray[np.uint8] | None]:
        """Compare two images and return number of different pixels and the raw diff image.

        Args:
            image1_path: Path to first image
            image2_path: Path to second image
            ignore_regions: Optional list of rectangles to ignore during comparison.
                Each rectangle MUST be provided as (left, top, right, bottom).
                Coordinates are in pixels with origin at top-left. Out-of-bounds values will be clamped.

        Returns:
            Tuple of (number of different pixels, diff image array)
        """
        img1: NDArray[np.uint8] = cv2.imread(image1_path)  # type: ignore[assignment]
        img2: NDArray[np.uint8] = cv2.imread(image2_path)  # type: ignore[assignment]

        if img1 is None or img2 is None:
            raise AssertionError(f"Failed to read images: '{image1_path}' or '{image2_path}'")

        if img1.shape != img2.shape:
            # Different sizes -> not comparable
            return float("inf"), None

        import numpy as np

        diff_raw: NDArray[np.uint8] = cv2.absdiff(img1, img2)  # type: ignore[assignment]

        # Convert to grayscale for thresholding
        gray_diff: NDArray[np.uint8] = cv2.cvtColor(diff_raw, cv2.COLOR_BGR2GRAY) if len(diff_raw.shape) == 3 else diff_raw  # type: ignore[assignment]

        tolerance: int = 10
        _: float
        mask_raw: NDArray[np.uint8]
        _, mask_raw = cv2.threshold(gray_diff, tolerance, 255, cv2.THRESH_BINARY)  # type: ignore[assignment]

        # Ensure proper types
        mask: NDArray[np.uint8] = np.asarray(mask_raw, dtype=np.uint8)
        diff: NDArray[np.uint8] = np.asarray(diff_raw, dtype=np.uint8)

        # Apply ignore mask if regions provided
        if ignore_regions:
            h: int
            w: int
            h, w = gray_diff.shape[:2]
            ignore_mask: NDArray[np.uint8] = self._create_ignore_mask(ignore_regions, h, w)
            mask, diff = self._apply_ignore_mask(mask, diff, ignore_mask)

        num_diff_pixels: int = cv2.countNonZero(mask)
        return num_diff_pixels, diff

    def _compare_pdf_pages(
        self,
        custom_prefix: str,
        page_numbers: int,
        expected_folder: str,
        output_folder: str,
        ignore_regions_per_page: dict[int, list[tuple[int, int, int, int]]] | list[tuple[int, int, int, int]] | None = None,
    ) -> None:
        """Compare rendered PNG pages with expected PNGs.

        Args:
            custom_prefix: Prefix for image filenames
            page_numbers: Number of pages to compare
            expected_folder: Path to folder with expected images
            output_folder: Path to folder with generated images
            ignore_regions_per_page: Regions to ignore during comparison.
                - Pass a dict[int, list[tuple]] mapping page_number (1-based) to a list of rectangles.
                - Or pass a list[tuple] to apply the same rectangles to all pages.
                Rectangle format per entry: (left, top, right, bottom)
                Example: ignore only on page 2 -> {2: [(100, 200, 300, 260)]}
        """
        failed_pages: list[str] = []

        for page_index in range(page_numbers):
            page_number: int = page_index + 1
            expected_page: str = f"{expected_folder}/{custom_prefix}_page_{page_number}.png"
            generated_page: str = f"{output_folder}/{custom_prefix}_page_{page_number}.png"
            regions: list[tuple[int, int, int, int]] | None = None
            if ignore_regions_per_page and isinstance(ignore_regions_per_page, dict):
                regions = ignore_regions_per_page.get(page_number)
            elif ignore_regions_per_page and isinstance(ignore_regions_per_page, list):
                # Same regions for all pages
                regions = ignore_regions_per_page
            num_diff_pixels: int | float
            difference: NDArray[np.uint8] | None
            num_diff_pixels, difference = self._compare_images(expected_page, generated_page, ignore_regions=regions)
            if num_diff_pixels > 0:
                self._highlight_differences(
                    difference,
                    custom_prefix,
                    output_folder,
                    page_number,
                )
                failed_pages.append(f"Page {page_number} is NOT identical to '{expected_page}'")

        # Report all failed pages at once, after checking all pages
        if failed_pages:
            failure_message: str = "\n".join(failed_pages)
            self.fail(f"PDF comparison failed:\n{failure_message}")

    def _highlight_differences(
        self,
        difference: NDArray[np.uint8] | None,
        custom_prefix: str,
        output_folder: str,
        page_number: int,
    ) -> None:
        if difference is None:
            return
        import numpy as np

        difference_page: str = f"{output_folder}/{custom_prefix}_page_{page_number}_diff.png"
        # Create a blue mask where differences are present
        blue_mask: NDArray[np.uint8] = difference.copy()
        # If grayscale, convert to BGR
        if len(blue_mask.shape) == 2:
            blue_mask = np.asarray(cv2.cvtColor(blue_mask, cv2.COLOR_GRAY2BGR), dtype=np.uint8)
        # Set all nonzero pixels to blue (BGR: 255,0,0)
        blue_mask[(blue_mask != 0).any(axis=2)] = [255, 0, 0]
        cv2.imwrite(difference_page, blue_mask)

    def _save_header_footer_settings(self, header_footer_settings: JsonDict) -> tuple[JsonDict, JsonDict]:
        # Get original header footer settings
        response_previous: Response = self.api().get_setting_content(feature="header-footer", scope=f"project/{self.project_id}/")
        self.assertEqual(HTTPStatus.OK, response_previous.status_code)
        previous_header_footer_settings: JsonDict = response_previous.json()

        # Save new header footer settings
        response_saved: Response = self.api().save_setting(
            feature="header-footer",
            scope=f"project/{self.project_id}/",
            data=header_footer_settings,
        )
        self.assertEqual(HTTPStatus.NO_CONTENT, response_saved.status_code)

        return previous_header_footer_settings, previous_header_footer_settings

    def _convert(self, project_id: str | None, location_path: str, custom_export_params: JsonDict | None = None, print_error: bool = True) -> Response:
        export_params: JsonDict = {
            "projectId": project_id,
            "locationPath": location_path,
            "documentType": DocumentType.LIVE_DOC,
        }
        if custom_export_params:
            export_params.update(custom_export_params)

        self.api().polarion_connection.set_print_error(print_error)
        response: Response = self.api().convert(export_params=export_params)
        self.api().polarion_connection.set_print_error(True)
        return response

    def _convert_html(
        self,
        api: PolarionPdfExporterApi,
        html: str,
        orientation: Orientation = Orientation.PORTRAIT,
        paper_size: PaperSize = PaperSize.A4,
        filename: str = "diff.pdf",
        print_error: bool = True,
        fit_to_page: bool = False,
    ) -> Response:
        api.polarion_connection.set_print_error(print_error)
        response: Response = api.convert_html(
            html=html,
            orientation=orientation,
            paper_size=paper_size,
            fit_to_page=fit_to_page,
            filename=filename,
        )
        api.polarion_connection.set_print_error(True)
        return response

    def _is_rightmost_column_white(self, file_name: str) -> bool:
        file_path: pathlib.Path = pathlib.Path(self._get_output_folder()) / file_name
        img: NDArray[np.uint8] = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)  # type: ignore[assignment]
        return img is not None and all(img[:, -1] == 255)

    def convert_pdf_to_png_first_page(self, pdf_bytes: bytes, file_name: str) -> None:
        output_file: pathlib.Path = pathlib.Path(self._get_output_folder()) / file_name
        pdf_document: fitz.Document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-any-unimported]
        pdf_document[0].get_pixmap(dpi=PDF_RENDER_DPI).save(str(output_file))
        pdf_document.close()
