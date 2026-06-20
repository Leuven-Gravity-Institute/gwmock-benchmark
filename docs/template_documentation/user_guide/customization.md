# Customization

This page covers **ongoing** changes to dependencies, tools, and workflows after
your repository already has a name and import path.

If you are still adopting the GitHub template (rename package, remove template
docs), use [Customize and clean up](../onboarding/customize_repository.md)
first.

## Dependencies

Runtime and optional groups live in `pyproject.toml`:

```toml
[project]
dependencies = [...]

[project.optional-dependencies]
test = [...]
dev = [...]
docs = [...]
```

After editing dependencies, refresh the lockfile:

```bash
uv lock
uv sync --extra dev
```

## Ruff

Rules and formatting live under `[tool.ruff]` and `[tool.ruff.lint]` in
`pyproject.toml`. Prefer editing there and re-running:

```bash
uv run ruff check --fix src tests
uv run ruff format src tests
```

## Git hooks (prek)

Hooks are listed in `.pre-commit-config.yaml`. Add or remove repos there, then:

```bash
uv run prek auto-update
uv run prek run --all-files
```

## Documentation site

Navigation and theme options are in `zensical.toml`. Add a page under `docs/`,
then add it to the `nav` array so it appears in the sidebar.

## CI workflows

Workflows live in `.github/workflows/`. Typical edits are Python version
matrices in `ci.yml`, release cadence in `scheduled_release.yml`, and Pages
settings described in [CI/CD and releases](ci_cd.md).

## Spell checking

Typos are checked with [typos](https://github.com/crate-ci/typos) via the hook
in `.pre-commit-config.yaml` (run locally with **prek**). Project-specific
overrides go in `.typos.toml` at the repository root.
