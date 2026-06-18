# CLAUDE.md

- Use `uv` for all Python tooling (`uv run tox`, `uv run pytest`, `uv sync`, `uv build`) — never `pip`, `python -m pip`, or bare tool invocations.
- GitHub Actions workflows from `SchweizerischeBundesbahnen/*` are intentionally pinned to `@main`, not hash-pinned. This is enforced by `zizmor.yml`. Do not change these to hash pins.
- CI uses `uv sync --frozen` (not `--locked`). Do not change back to `--locked`.
- `==` pins in `pyproject.toml` are for Renovate — `ruff`, `mypy`, `types-requests`, `pypdf` use exact pins so Renovate creates PRs that go through CI. Do not relax these to ranges. Range-pinned deps are upgraded by `uv lock --upgrade`.
- **Python version is hardcoded in multiple places** — `.tool-versions` is the source of truth, but `pyproject.toml` (`requires-python`, ruff `target-version`, mypy `python_version`) and `sonar-project.properties` must be updated manually. Only `ci.yml` reads from `.tool-versions` automatically.
- **mypy `python_version = "3.14"` is intentional** — forward-compatibility checking even though runtime is 3.13. Do not "fix" this to match `requires-python`.
- **System tests run in two places.** GitHub Actions (`system-tests.yml`) is the PR merge gate and runs against a containerized Polarion. The `Jenkinsfile` runs the same suite nightly against a long-lived Polarion environment. Keep these two paths in sync when changing test invocation or dependencies.
- **The Jenkins job is a multibranch pipeline.** Scheduled/manual stages in the `Jenkinsfile` MUST be guarded with `when { branch 'main' }` (combined with the `triggeredBy` checks) — otherwise the suite runs on every feature and PR branch. Do not assume a non-multibranch job; a missing branch guard means the tests fan out across all branches, not that they are skipped.
- **The nightly `Jenkinsfile` cron is intentionally time-based, not an upstream trigger.** The environment it tests is refreshed by a separate, externally scheduled process that Jenkins cannot observe via an upstream-job dependency, so the cron is timed to start after that refresh completes. Do not "improve" it into an `upstream(...)` trigger.
