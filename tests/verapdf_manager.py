"""
VeraPDF Manager - Handles VeraPDF validation using REST API Docker container.

This module provides functionality to run VeraPDF validation using the official
verapdf/rest Docker image without requiring manual installation.
"""

from __future__ import annotations

import contextlib
import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import requests
from python_sbb_polarion.types import Header, MediaType
from testcontainers.core.container import DockerContainer
from testcontainers.core.docker_client import DockerClient
from testcontainers.core.waiting_utils import wait_for_logs


if TYPE_CHECKING:
    from pathlib import Path

    from python_sbb_polarion.types import JsonDict

logger = logging.getLogger(__name__)


class VeraPDFContainer(DockerContainer):  # type: ignore[misc,no-any-unimported]
    """VeraPDF REST API container."""

    VERAPDF_IMAGE = "verapdf/rest:latest"
    REST_PORT = 8080

    def __init__(self) -> None:
        super().__init__(self.VERAPDF_IMAGE)
        self.with_exposed_ports(self.REST_PORT)

    def get_base_url(self) -> str:
        """Get the base URL for the REST API."""
        host: str = self.get_container_host_ip()
        port: int = self.get_exposed_port(self.REST_PORT)
        return f"http://{host}:{port}"

    def start(self) -> VeraPDFContainer:
        """Start container and wait for REST API to be ready."""
        super().start()
        # Wait for the server to be ready (Jetty startup message)
        wait_for_logs(self, "Started", timeout=60)
        logger.info(f"VeraPDF REST API started at {self.get_base_url()}")
        return self


class VeraPDFManager:
    """Manages VeraPDF validation using REST API Docker container."""

    # Class-level container - shared across all instances
    _container: ClassVar[VeraPDFContainer | None] = None

    @staticmethod
    def is_docker_available() -> bool:
        """
        Check if Docker is available and working.

        Returns:
            True if Docker is available, False otherwise
        """
        try:
            client = DockerClient()
            client.client.ping()
            logger.info("Docker availability check: Docker is available and working")
            return True
        except Exception as e:
            logger.warning(f"Docker availability check: Docker is not available - {e}")
            return False

    def _ensure_container_running(self) -> VeraPDFContainer:
        """Ensure the VeraPDF container is running, starting it if necessary."""
        if VeraPDFManager._container is None:
            logger.info("Starting VeraPDF REST container...")
            VeraPDFManager._container = VeraPDFContainer()
            VeraPDFManager._container.start()
        return VeraPDFManager._container

    def stop_container(self) -> None:
        """Stop the VeraPDF container if running."""
        if VeraPDFManager._container is not None:
            with contextlib.suppress(Exception):
                VeraPDFManager._container.stop()
            VeraPDFManager._container = None
            logger.info("VeraPDF REST container stopped")

    def validate_pdf(self, pdf_path: Path, flavour: str) -> tuple[bool, JsonDict | None, str]:
        """
        Validate PDF file using VeraPDF REST API.

        Args:
            pdf_path: Path to PDF file to validate
            flavour: VeraPDF flavour code (e.g., "1b", "2b", "ua1")

        Returns:
            Tuple of (success, json_response, error_message)
        """
        logger.info(f"Validating PDF {pdf_path} with flavour {flavour} using REST API")

        try:
            container: VeraPDFContainer = self._ensure_container_running()
            base_url: str = container.get_base_url()
            validate_url: str = f"{base_url}/api/validate/{flavour}"

            # Read PDF file and send to REST API
            with pdf_path.open("rb") as pdf_file:
                files: dict[str, tuple[str, ...]] = {
                    "file": (pdf_path.name, pdf_file, MediaType.PDF),  # type: ignore[dict-item]
                }
                response: requests.Response = requests.post(
                    validate_url,
                    files=files,  # type: ignore[arg-type]
                    headers={Header.ACCEPT: MediaType.JSON},
                    timeout=120,
                )

            if response.status_code != HTTPStatus.OK:
                return False, None, f"VeraPDF REST API returned status {response.status_code}: {response.text}"

            json_response: JsonDict = response.json()
            logger.info("VeraPDF validation completed successfully")
            logger.debug(f"VeraPDF response: {json_response}")
            return True, json_response, ""

        except requests.RequestException as e:
            logger.exception("Error calling VeraPDF REST API")
            return False, None, f"Failed to call VeraPDF REST API: {e}"
        except Exception as e:
            logger.exception("Error during VeraPDF validation")
            return False, None, f"Failed to run VeraPDF validation: {e}"
