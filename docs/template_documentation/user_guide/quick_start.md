# Quick start

This page is for working on **this repository** after you have cloned it
(including if you created your repo from the GitHub template). If you only want
the one-time fork steps, use
[Template quick start](../onboarding/quick_start.md) instead.

## Environment

From the repository root, with [uv](https://docs.astral.sh/uv/) installed:

```bash
uv sync --extra dev --extra docs --extra test
```

That installs the package in editable mode with tooling for tests, docs, and
**prek** (local Git hooks).

## Commands you will use often

```bash
# Unit tests and coverage (same as CI, without optional markers)
uv run pytest

# All Git hooks on the full tree (prek)
uv run prek run --all-files

# Documentation site locally
uv run zensical serve
```

## Example CLI

The template exposes a Typer application:

```bash
uv run python_package_template --help
```

You can also run the package as a module:

```bash
uv run python -m python_package_template
```

## Layout reminder

Application code lives under `src/python_package_template/`. Tests live in
`tests/`. Markdown sources for this site live in `docs/`, and the site
configuration is in `zensical.toml`.

## Going further

- [Project structure](project_structure.md) — how directories map to packaging
  and tests
- [Development tools](development_tools.md) — Ruff, Bandit, typos, prek
- [CI/CD and releases](ci_cd.md) — what runs in GitHub Actions
