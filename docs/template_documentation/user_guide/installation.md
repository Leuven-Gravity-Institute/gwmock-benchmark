# Installation

We recommend [uv](https://docs.astral.sh/uv/) to create environments and sync
dependencies for **python_package_template**.

## Requirements

- **Python 3.12 or newer** (`requires-python` in `pyproject.toml`)
- Linux, macOS, or Windows

## Install from a checkout (recommended)

```bash
git clone https://github.com/isaac-cf-wong/python-package-template.git
cd python-package-template

uv sync --extra dev --extra docs --extra test
```

Activate the virtualenv if you prefer not to prefix commands with `uv run`:

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Install git hooks:

```bash
uv run prek install
```

## Install from PyPI

The template repository is primarily meant to be copied; a PyPI name may still
point at placeholder metadata. If a published distribution exists for your use
case:

```bash
uv pip install python_package_template
```

Optional extras:

```bash
uv pip install "python_package_template[dev]"
uv pip install "python_package_template[docs]"
```

## Verify the CLI

```bash
uv run python_package_template --help
```

Or import the package:

```bash
uv run python -c "import python_package_template; print(python_package_template.__version__)"
```

## Core runtime dependency

- **Typer** — command-line interface

## Getting help

1. [Troubleshooting](../development/troubleshooting.md)
2. [Issues](https://github.com/isaac-cf-wong/python-package-template/issues)
