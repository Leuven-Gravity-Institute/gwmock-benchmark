# Template quick start

Use this page once, right after you create a new repository with **Use this
template** on GitHub.

## 1. Clone your new repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

## 2. Install dependencies with uv

This template targets **Python 3.12+** (see `requires-python` in
`pyproject.toml`). Install [uv](https://docs.astral.sh/uv/) if needed, then from
the repo root:

```bash
uv sync --extra dev --extra docs --extra test
```

That installs the package in editable mode with development, documentation, and
test extras.

## 3. Install Git hooks (prek)

```bash
uv run prek install
```

Run all hooks once to confirm the tree is clean:

```bash
uv run prek run --all-files
```

## 4. Run tests

```bash
uv run pytest
```

## 5. Preview documentation

```bash
uv run zensical serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) (or the URL printed in the
terminal).

## 6. Next steps

Follow [Customize and clean up](customize_repository.md) to rename
`python_package_template`, update metadata, and remove
**`docs/template_documentation/`** when you no longer need the template guides.

Commit messages and **pull request titles** should follow
[Conventional Commits](https://www.conventionalcommits.org/) so
[git-cliff](https://git-cliff.org/) can build release notes. Pull request titles
are checked in CI by the **Lint PR** workflow
(`.github/workflows/semantic_pull_request.yml`).
