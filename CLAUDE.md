# CLAUDE.md

- Use `uv` for all Python tooling (`uv run tox`, `uv run pytest`, `uv sync`, `uv build`) — never `pip`, `python -m pip`, or bare tool invocations.
- GitHub Actions workflows from `SchweizerischeBundesbahnen/*` are intentionally pinned to `@main`, not hash-pinned. This is enforced by `zizmor.yml`. Do not change these to hash pins.
- CI uses `uv sync --frozen` (not `--locked`) — `--locked` fails after release-please bumps the version in `pyproject.toml`. Do not change back to `--locked`.
- `==` pins in `pyproject.toml` are for Renovate — `ruff`, `mypy`, `types-requests`, `pypdf` use exact pins so Renovate creates PRs that go through CI. Do not relax these to ranges. Range-pinned deps are upgraded by `uv lock --upgrade`.
- **Python version is hardcoded in multiple places** — `.tool-versions` is the source of truth, but `pyproject.toml` (`requires-python`, ruff `target-version`, mypy `python_version`) and `sonar-project.properties` must be updated manually. Only `ci.yml` reads from `.tool-versions` automatically.
- **mypy `python_version = "3.14"` is intentional** — forward-compatibility checking even though runtime is 3.13. Do not "fix" this to match `requires-python`.
