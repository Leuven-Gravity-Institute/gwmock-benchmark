# CI/CD and releases

This guide describes the GitHub Actions setup for this repository: testing,
security analysis, releases, documentation, and optional PyPI publishing.

## Overview

- **CI** — `pytest` on Linux, macOS, and Windows for Python 3.12, 3.13, and 3.14
  (`ci.yml`)
- **CodeQL** — scheduled and on pushes to `main` (`codeql.yml`; also invoked
  from the scheduled release pipeline)
- **Pull request titles** — Conventional Commit style
  (`semantic_pull_request.yml`)
- **Scheduled release** — weekly tag bump, GitHub release, and optional PyPI
  publish (`scheduled_release.yml`)
- **Draft release** — moving changelog preview on every push to `main`
  (`draft_release.yml`)
- **Documentation** — Zensical build and GitHub Pages deploy
  (`documentation.yml`)
- **Manual publish** — `publish.yml` and `publish_testpypi.yml` with
  `workflow_dispatch`

Linting and formatting are enforced locally via **prek** using
`.pre-commit-config.yaml`, and on pull requests via **pre-commit.ci**, not via a
separate job in `ci.yml`. Add a workflow job if you want Ruff in CI as well.

## Workflows

### `ci.yml` (CI)

**Triggers:** `push` and `pull_request` to `main`, plus `workflow_dispatch` and
`workflow_call`.

**Steps:** checkout → `uv` → `uv sync --extra test,ci --frozen` →
`uv run pytest` → Codecov upload.

**Branch protection:** require the matrix jobs you care about, for example
`test (ubuntu-latest, 3.12)` (exact names appear in the Actions UI).

### `codeql.yml` (CodeQL Advanced)

**Triggers:** `push` / `pull_request` to `main`, weekly schedule,
`workflow_call`.

Runs the GitHub CodeQL autobuild + analyze steps for Python.

### `semantic_pull_request.yml` (Lint PR)

**Triggers:** `pull_request_target` when a PR is opened or updated.

Validates the PR title with
[action-semantic-pull-request](https://github.com/amannn/action-semantic-pull-request).

### `scheduled_release.yml` (Scheduled Release)

**Triggers:** `cron: '0 0 * * 2'` (Tuesday 00:00 UTC) and `workflow_dispatch`.

When there are new commits since the latest tag:

1. Calls `ci.yml` and `codeql.yml`
2. Bumps the next semantic tag with `git-cliff` / `uv run git-cliff`
3. Calls `release.yml` with that tag
4. Builds wheels, runs smoke tests, and attempts `uv publish` against the
   **`pypi`** environment (with `continue-on-error: true` so missing setup does
   not fail the template)

### `release.yml` (Release)

**Triggers:** `workflow_call` (from scheduled release) or `workflow_dispatch`
with a `tag_name` input.

Uses **git-cliff-action** to render release notes, removes the `next-release`
draft if present, and creates a GitHub Release with
**softprops/action-gh-release**.

### `draft_release.yml` (Draft Release)

**Triggers:** every push to `main`.

Refreshes a **Next Release (Draft)** GitHub release whose body is the unreleased
changelog from git-cliff.

### `documentation.yml` (Documentation)

**Triggers:** `push` to `main` and `workflow_dispatch`.

Runs `uv sync --extra docs --frozen` and `uv run zensical build`, then uploads
the `site/` directory to GitHub Pages.

### `publish.yml` / `publish_testpypi.yml`

**Triggers:** `workflow_dispatch` with a tag and environment selection.

Build with `uv build`, smoke-test artifacts, then `uv publish`. These workflows
also use `continue-on-error: true` on the publish step so the template stays
green until you configure PyPI trusted publishing and GitHub environments.

## Release process

### Repository URL in `cliff.toml`

Replace the `<REPO>` substitution in `cliff.toml` (the `postprocessors` entry
that points at `https://github.com/isaac-cf-wong/python-package-template`) with
your own GitHub URL so changelog links resolve.

### Conventional commits

git-cliff reads history in Conventional Commits form, for example:

```bash
feat: add new feature          # Minor bump
fix: fix a bug                 # Patch bump
feat!: breaking change         # Major bump
docs: update documentation     # Changelog section, may not bump
```

[Conventional Commits](https://www.conventionalcommits.org/)

### Automatic weekly release

On the cron schedule, **Scheduled Release** runs the sequence above. No UI
action is required if commits warrant a new version.

### Manual runs

- **Scheduled Release** — Actions → **Scheduled Release** → **Run workflow** to
  mimic the weekly job immediately (still subject to “new commits since last
  tag” logic).
- **Release** — supply an existing tag to regenerate release notes for that tag.
- **Publish** / **Publish TestPyPI** — build and upload a chosen tag.

## Publishing

### GitHub environments

Create environments named **`pypi`** and/or **`testpypi`** with the protection
rules you want, then configure
[trusted publishing](https://docs.pypi.org/trusted-publishers/) on PyPI to trust
this repository’s **`scheduled_release.yml`** and **`publish.yml`** (or the
TestPyPI workflow) together with the matching environment name.

### Remove `continue-on-error` for real packages

The template tolerates missing PyPI configuration. For production, remove
`continue-on-error: true` from the publish steps (for example in
`scheduled_release.yml` near the `uv publish` step, and in `publish.yml` /
`publish_testpypi.yml`) so failed uploads fail the workflow.

## Customization

### Change the release cadence

Edit the `schedule` block in `scheduled_release.yml`.

### Change Python versions for tests

Edit the `matrix.python-version` list in `ci.yml` and align `requires-python`
and classifiers in `pyproject.toml`.

### Skip CodeQL in the scheduled pipeline

Remove or gate the `codeql` job in `scheduled_release.yml` instead of editing
`ci.yml` (CodeQL is not part of `ci.yml`).

## Troubleshooting

### CI fails

- Reproduce with `uv sync --extra test,ci --frozen` then `uv run pytest`
- Inspect the failing OS / Python cell in the matrix

### Scheduled release does nothing

- Confirm there are commits after the latest tag (the workflow skips otherwise)
- Inspect the `check_new_commits` job output

### PyPI publish is skipped or succeeds silently

- Check for `continue-on-error: true` on publish steps
- Verify the `pypi` environment and trusted publisher mapping

## Resources

- [GitHub Actions](https://docs.github.com/en/actions)
- [git-cliff](https://git-cliff.org/)
- [Zensical](https://zensical.org/)
- [uv](https://docs.astral.sh/uv/)
