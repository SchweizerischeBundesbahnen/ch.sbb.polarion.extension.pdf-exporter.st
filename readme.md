[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=bugs)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=coverage)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=ncloc)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_ch-sbb-polarion-extension-pdf-exporter-st)

# System Tests for Polarion PDF Exporter extension

## CI

This project uses dual CI:

- **GitHub Actions**
  - `ci.yml` — linting, type checking, and SonarCloud analysis.
  - `system-tests.yml` — system tests against a Polarion instance running in a Docker container. This is the pull request merge gate (the `system-tests` check is required on `main`), so merging no longer depends on the availability of a long-lived Polarion instance.
- **Jenkins** (`Jenkinsfile`) — the same system tests run on a nightly schedule against a long-lived Polarion instance behind a firewall, on the `main` branch only. Jenkins is no longer part of the per-pull-request merge path.

## 1. Run tests against prepared Polarion server (local or remote)
In this mode, the tests will be executed against running Polarion server specified by app_url parameter and using app_token credentials.

| Parameter | Default value | Mandatory for external Polarion | Description                          |
|-----------|---------------|---------------------------------|--------------------------------------|
| app_url   | -             | yes                             | Base URL of external Polarion server |
| app_token | -             | yes                             | Authentication token                 |

### IntelliJ
- install Python plugin
- import project
- add and configure Python SDK in project settings
- run as normal unit test

### Command line example
```
uv run python tests/run.py --app_url BASE_POLARION_URL --app_token AUTH_TOKEN
```
## 2. Run tests against local Polarion Test Container
In this mode Polarion and Weasyprint containers will be created on the fly from the Docker image and tests will be executed against it.
Both containers will be bound to common network and Weasyprint service endpoint set dynamically as environment variable in Polarion container
### Prerequisites
- Docker runtime must be available on machine
- Polarion Docker image with specified name should exist either locally or in remote registry
- Weasyprint Docker image with specified name should exist either locally or in remote registry
### Command line example
```
uv run python tests/run.py --tc_polarion_image_name=polarion:2512 --tc_weasyprint_service_image_name=weasyprint-service:68.1.0
```
### Parameters
| Parameter                        | Default value | Mandatory for test containers | Description                                                                                                                                    |
|----------------------------------|---------------|-------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| tc_polarion_image_name           | -             | yes                           | Polarion Docker image name. Parameter triggers test containers mode                                                                            |
| tc_weasyprint_service_image_name | -             | no                            | Weasyprint service Docker image name. Parameter triggers creation of Weasyprint service container and bounds both containers to common network |
| tc_extension_version             | latest        | no                            | Version of testing extension. By default, the latest version from local maven repo will be taken                                               |
| tc_additional_bundles            | -             | no                            | Comma separated list of additional bundles to be installed with testing extension in form group_id:artifact_id:version                         |
| tc_admin_utility_version         | 1.8.0         | no                            | Version of admin-utility extension used to initialize polarion instance and prepare test data                                                  |

All parameters can be specified as environment variables.

## 3. PDF Variants Testing with VeraPDF

The test suite includes validation of PDF variants (PDF/A and PDF/UA) using VeraPDF. The test `test_pdf_variants.py` validates that generated PDFs comply with their specified variants.

### Docker-based VeraPDF Validation

The test suite uses the official VeraPDF Docker image:

- Uses Docker container `ghcr.io/verapdf/cli:latest` for validation
- On first run, Docker will automatically pull the image (~50MB)
- No manual installation or system dependencies needed
- Perfect for CI/CD environments
- Works consistently across Linux, macOS, and Windows
- **Automatic Docker detection**: Tests automatically detect if Docker is available and skip gracefully if not

### Prerequisites

The only requirement is Docker:

- **Docker Desktop** (for macOS/Windows)
- **Docker Engine** (for Linux)

Verify Docker is installed and running:
```bash
docker --version
docker ps
```

**Note**: If Docker is not available, the PDF variant tests will be automatically skipped with a clear message.

### Supported PDF Variants
The following PDF variants are tested:
- PDF/A-1b
- PDF/A-2b
- PDF/A-3b
- PDF/A-4b
- PDF/A-2u
- PDF/A-3u
- PDF/A-4u

**Note:** PDF/UA-1 validation is currently disabled as it requires additional accessibility features (alt text for images and proper list structure) to be implemented in the PDF exporter.
