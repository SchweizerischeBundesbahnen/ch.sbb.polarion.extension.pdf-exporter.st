"""How Polarion is configured to reach the WeasyPrint service, and the two levers a case may pull.

Both the address of the service and the name of the secret holding its API key live in
``polarion.properties``, and Polarion reads that file once, at start. The value behind the secret name
is cached as well. So neither can separate two cases of one run, and both are read here only to decide
whether the authenticated cases apply at all.

What a case may move while Polarion runs -- the service, by recreating its container with a different
``API_KEY``, and the trust, by removing the certificate authority from the truststore -- is shared with
the bulk processing service and lives in ``tls_service_support``. This module names the WeasyPrint one.
"""

from __future__ import annotations

from tests.tls_service_support import TlsService


SERVICE_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.weasyprint.service"
API_KEY_SECRET_PROPERTY = "ch.sbb.polarion.extension.pdf-exporter.weasyprint.apiKeySecret"

WEASYPRINT: TlsService = TlsService(
    label="WeasyPrint service",
    service_property=SERVICE_PROPERTY,
    api_key_secret_property=API_KEY_SECRET_PROPERTY,
    container_env="WEASYPRINT_CONTAINER",
    # the authority which signed the certificate of the service, where the environment names it itself
    ca_alias_env="WEASYPRINT_CA_ALIAS",
)

service_url = WEASYPRINT.service_url
api_key_secret_name = WEASYPRINT.api_key_secret_name
authenticated_over_tls = WEASYPRINT.authenticated_over_tls
service_answers = WEASYPRINT.service_answers
service_container = WEASYPRINT.service_container
service_log_lines = WEASYPRINT.service_log_lines
service_restartable = WEASYPRINT.service_restartable
service_running_with = WEASYPRINT.service_running_with
trusted_ca_alias = WEASYPRINT.trusted_ca_alias
ca_in_truststore = WEASYPRINT.ca_in_truststore
ca_removed = WEASYPRINT.ca_removed
