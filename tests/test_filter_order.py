from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from python_sbb_polarion.types import Header, MediaType
from python_sbb_polarion.util.http import HttpConnection

from tests.constants import PdfExporterFeature
from tests.pdf_exporter_test_case import PdfExporterTestCase


if TYPE_CHECKING:
    from python_sbb_polarion.types import JsonDict
    from requests import Response


UNRESTRICTED: JsonDict = {"globalRoles": [], "projectRoles": []}
RESTRICTED: JsonDict = {"globalRoles": ["role_that_nobody_has"], "projectRoles": []}


class PdfExporterFilterOrderTest(PdfExporterTestCase):
    """Regression tests for the order of the REST request filters.

    The generic AuthenticationFilter must run before RolesRestrictedFilter. Jersey orders both by
    their @Priority rank, and when that rank is lost the authorization filter runs first, reads the
    roles setting with nobody authenticated and answers 500 instead of a clean 401. That happened for
    real: the ranks tied at Priorities.USER because the extension bundle resolved
    jakarta.annotation.Priority from a different OSGi bundle than Jersey did, and the order then
    followed HashSet iteration order - a different one on each JVM start.

    Both tests run with the roles restriction switched on. With the default empty role lists export is
    unrestricted, the authorization filter returns early and a wrong order stays invisible.
    """

    def setUp(self) -> None:
        super().setUp()
        # Registered before the setting is changed, so the restore runs even if that change fails.
        # Nothing else restores it: authorization is not one of SUPPORTED_FEATURES.
        self.addCleanup(self._save_authorization, UNRESTRICTED)
        self._save_authorization(RESTRICTED)

    def _save_authorization(self, data: JsonDict) -> None:
        response: Response = self.api().save_setting(feature=PdfExporterFeature.AUTHORIZATION, scope=self.scope, data=data)
        self.assertEqual(HTTPStatus.NO_CONTENT, response.status_code)

    def _post_convert(self, connection: HttpConnection) -> Response:
        url: str = f"/polarion/{self.api().extension_name}/rest/api/convert"
        data: JsonDict = {
            "projectId": self.project_id,
        }
        # The endpoint only produces PDF. Without this the request is rejected as Not Acceptable
        # before the filters run, and the test would never see which of them answered.
        headers: dict[Header, MediaType] = {
            Header.ACCEPT: MediaType.PDF,
        }
        return connection.api_request_post(url, data=data, headers=headers, print_error=False)

    def test_authentication_runs_before_authorization(self) -> None:
        # Arrange
        connection: HttpConnection = HttpConnection(url=self.api().polarion_connection.host, token="invalid token")

        # Act
        response: Response = self._post_convert(connection)

        # Assert
        self.assertEqual(HTTPStatus.UNAUTHORIZED, response.status_code)

    def test_authorization_rejects_an_authenticated_user_without_the_role(self) -> None:
        # Act
        response: Response = self._post_convert(self.api().polarion_connection)

        # Assert
        self.assertEqual(HTTPStatus.FORBIDDEN, response.status_code)
