# Troubleshooting

This guide covers common issues you might encounter when using this template and
how to resolve them.

## Setup Issues

### Git hook installation fails (prek)

**Problem:** `uv run prek install` returns an error or hooks don't run on
commit.

**Solutions:**

<!-- prettier-ignore-start -->

1. Ensure you're in the project root directory
2. Sync dev dependencies so **prek** is installed:

    ```bash
    uv sync --extra dev --extra docs --extra test
    ```

3. Reinstall hook shims:

    ```bash
    uv run prek uninstall
    uv run prek install
    ```

4. Check if `.git` directory exists (must be a git repository)
5. Try running manually: `uv run prek run --all-files`

<!-- prettier-ignore-end -->

### Pull request title check failed

**Problem:** The **Lint PR** workflow reports that your pull request title does
not follow Conventional Commits.

**Solutions:**

1. Rename the PR to use an allowed type and a short description, for example
   `feat: add batch export` or `fix(cli): handle missing config`.
2. Read the workflow log for the exact regular expression the action uses.
3. Remember: this template does **not** run commitlint on local `git commit`;
   only the PR title is enforced in GitHub Actions.

### Virtual Environment Issues

**Problem:** Packages can't be found or dependencies conflict.

**Solutions:**

<!-- prettier-ignore-start -->

1. Create a fresh virtual environment:

    ```bash
    rm -rf .venv
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

2. Upgrade pip:

    ```bash
    python -m pip install --upgrade pip
    ```

3. Install dependencies:

    ```bash
    uv sync --extra dev --extra docs --extra test
    ```

4. Verify installation:

    ```bash
    python -c "import your_package; print(your_package.__version__)"
    ```

<!-- prettier-ignore-end -->

### Python Version Mismatch

**Problem:** `python -m venv .venv` fails or tests don't run with wrong Python
version.

**Solutions:**

<!-- prettier-ignore-start -->

1. Check your Python version:

    ```bash
    python --version
    ```

2. Ensure Python **3.12 or newer** is installed (`requires-python` in
   `pyproject.toml`)
3. Use a specific interpreter when creating a venv:

    ```bash
    python3.12 -m venv .venv
    ```

4. Or use uv for version management:

    ```bash
    uv venv --python 3.12
    source .venv/bin/activate
    ```

<!-- prettier-ignore-end -->

## Testing Issues

### Pytest Fails to Collect Tests

**Problem:** `pytest` returns "no tests collected" or import errors.

**Solutions:**

<!-- prettier-ignore-start -->

1. Verify test file naming: Must be `test_*.py` or `*_test.py`
2. Verify test function naming: Must start with `test_`
3. Check `__init__.py` exists in test directory: `touch tests/__init__.py`
4. Run pytest with verbose output:

    ```bash
    pytest -vv
    ```

5. Check test discovery:

    ```bash
    pytest --collect-only
    ```

<!-- prettier-ignore-end -->

### Import Errors in Tests

**Problem:** Tests can't import your package modules.

**Solutions:**

<!-- prettier-ignore-start -->

1. Install package in development mode:

    ```bash
    uv sync --extra dev --extra test
    ```

2. Verify package structure (should have `src/your_package/`)
3. Check `pyproject.toml` has correct `packages` configuration
4. Run from project root directory
5. Verify `__init__.py` exists in package directory

<!-- prettier-ignore-end -->

### Coverage Report Issues

**Problem:** Coverage report shows 0% or missing files.

**Solutions:**

<!-- prettier-ignore-start -->

1. Run pytest with coverage:

    ```bash
    pytest --cov=src/your_package --cov-report=html
    ```

2. Check `.coveragerc` or `pyproject.toml` coverage settings
3. Ensure source files have proper imports
4. Verify test files import from `src/` layout correctly

<!-- prettier-ignore-end -->

## Git hook issues (prek)

### Hooks Running Too Slowly

**Problem:** Hooks take a very long time or times out.

**Solutions:**

<!-- prettier-ignore-start -->

1. Check which hooks are slow:

    ```bash
    uv run prek run --all-files --verbose
    ```

2. Consider excluding large files:

    ```yaml
    exclude: |
      (?x)^(
        large_data_file.csv|
        node_modules/
      )$
    ```

3. Run specific hooks:

    ```bash
    uv run prek run ruff --all-files  # Just ruff
    ```

<!-- prettier-ignore-end -->

### Formatting Changes After Commit

**Problem:** Hooks auto-fix files, but you didn't expect it.

**Solutions:**

<!-- prettier-ignore-start -->

1. This is normal behavior - review the changes
2. Stage the new changes:

    ```bash
    git add .
    git commit -m "your message"  # Try again
    ```

3. Modify tool settings if behavior is unwanted (in `pyproject.toml`)
4. Disable specific hooks temporarily:

    ```bash
    uv run prek run --all-files --skip ruff
    ```

<!-- prettier-ignore-end -->

### "Unstaged Changes" After Running Hooks

**Problem:** Hooks modified files but they're not staged.

**Solutions:**

<!-- prettier-ignore-start -->

1. This is expected - review changes:

    ```bash
    git diff
    ```

2. Stage the changes:

    ```bash
    git add .
    ```

3. Try committing again
4. Or use `git add -A` to stage all changes before commit

<!-- prettier-ignore-end -->

## CI/CD Issues

### CI Workflow Fails on Push

**Problem:** GitHub Actions workflow fails unexpectedly.

**Solutions:**

<!-- prettier-ignore-start -->

1. Check the Actions tab in GitHub for error details
2. Run tests locally first:

    ```bash
    pytest
    uv run prek run --all-files
    ```

3. Common causes:

    - Dependency installation failed: Check `uv sync --extra dev --extra docs --extra test`
    - Python version mismatch: Verify Python versions in workflow matrix
    - Missing dependencies: Add to `pyproject.toml`
    - Hook or pre-commit.ci failures: Fix locally with `uv run prek run --all-files` first

4. Re-run failed jobs from GitHub Actions UI

<!-- prettier-ignore-end -->

### CodeQL Analysis Takes Too Long

**Problem:** CI is slow due to CodeQL analysis.

**Solutions:**

1. This is normal (~2-3 minutes per run)
2. To disable CodeQL in automation, remove or skip the `codeql` job from
   `.github/workflows/scheduled_release.yml` (and/or disable `codeql.yml`), and
   keep security-oriented hooks (for example **Bandit** or **gitleaks**) in
   `.pre-commit-config.yaml` for basic review
3. Or check if it's necessary for your project
4. CodeQL provides value for security-critical projects

### Release Workflow Fails

**Problem:** Release or publish workflow doesn't work.

**Solutions:**

1. Verify tag format matches pattern: `v[0-9]+.[0-9]+.[0-9]+*`
    - Good: `v1.0.0`, `v1.2.3-alpha`
    - Bad: `1.0.0`, `release-1.0.0`
2. Check CI workflow passed first (required by release workflow)
3. Verify git-cliff configuration in `cliff.toml`
4. For publishing:
    - Check trusted publishers are configured in PyPI
    - Or verify API tokens are set as secrets
    - See [CI/CD guide — Publishing](../user_guide/ci_cd.md#publishing)

## Documentation Issues

### Zensical Site Won't Build

**Problem:** `zensical serve` or `zensical build` fails.

**Solutions:**

<!-- prettier-ignore-start -->

1. Verify Zensical is installed:

    ```bash
    uv sync --extra docs
    ```

2. Check `zensical.toml` syntax (must be valid TOML)
3. Verify markdown files exist and paths are correct
4. Check for circular includes or missing includes
5. Run with verbose output:

    ```bash
    zensical build --verbose
    ```

<!-- prettier-ignore-end -->

### Documentation Not Updating on GitHub Pages

**Problem:** You pushed changes but the docs aren't updated online.

**Solutions:**

1. Verify GitHub Pages is enabled:
    - Go to repository Settings → Pages
    - Under "Build and deployment", select "GitHub Actions" as the source
    - This allows the documentation workflow to deploy directly
2. Check documentation workflow ran successfully:
    - Go to Actions tab
    - Look for "Deploy Zensical documentation to Pages" workflow
3. Verify changes were pushed to the correct branch
4. Wait 1-2 minutes for Pages to build
5. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
6. Check browser cache isn't serving old version

### API Documentation Not Generating

**Problem:** API reference pages are empty or show errors.

**Solutions:**

<!-- prettier-ignore-start -->

1. Verify docstrings are present in your code:

    ```python
    def my_function():
        """This is a docstring."""
        pass
    ```

2. Ensure documentation extras are installed (they pull in `mkdocstrings-python`):

    ```bash
    uv sync --extra docs
    ```

3. Verify navigation in `zensical.toml` includes API section
4. Check `gen_ref_pages.py` script ran successfully:

    ```bash
    python docs/gen_ref_pages.py
    ```

5. Ensure modules are properly imported in `__init__.py`

<!-- prettier-ignore-end -->

## Dependencies & Package Issues

### "ModuleNotFoundError" When Running CLI

**Problem:** Running `your-package --help` fails with module not found.

**Solutions:**

<!-- prettier-ignore-start -->

1. Install package in development mode:

    ```bash
    uv sync
    ```

2. Verify entry points in `pyproject.toml`:

    ```toml
    [project.scripts]
    your-package = "your_package.cli.main:app"
    ```

3. Check the specified function exists and is callable
4. Verify package name doesn't use hyphens in the module name:

    - Package: `your-package` (in `pyproject.toml`)
    - Module: `your_package` (directory name)

<!-- prettier-ignore-end -->

### Dependency Conflicts

**Problem:** `pip install` fails with conflict messages.

**Solutions:**

<!-- prettier-ignore-start -->

1. Check Python version:

    ```bash
    python --version
    ```

2. Create fresh virtual environment:

    ```bash
    rm -rf .venv && python -m venv .venv
    source .venv/bin/activate
    ```

3. Upgrade pip:

    ```bash
    python -m pip install --upgrade pip
    ```

4. Install with verbose output to see conflict:

    ```bash
    uv sync --extra dev --extra docs --extra test -vv
    ```

5. Check `pyproject.toml` for overly restrictive version constraints

<!-- prettier-ignore-end -->

### Newer Version of Tool Breaks Things

**Problem:** Hooks or tools updated and now fail.

**Solutions:**

<!-- prettier-ignore-start -->

1. Check what changed:

    ```bash
    uv run prek auto-update --dry-run
    ```

2. Update individual tool:

    ```bash
    uv run prek auto-update --repo https://github.com/tool-repo
    ```

3. Test changes:

    ```bash
    uv run prek run --all-files
    ```

4. Pin to known-good version in `.pre-commit-config.yaml`:

    ```yaml
    rev: v1.0.0 # Specific version instead of latest
    ```

<!-- prettier-ignore-end -->

## Getting Help

If you encounter issues not listed here:

<!-- prettier-ignore-start -->

1. **Check existing issues**: Search GitHub Issues for your problem
2. **Review logs carefully**: Error messages usually point to the root cause
3. **Search documentation**: Many issues are covered in specific tool docs
4. **Try minimal reproduction**: Isolate the problem to a single file/command
5. **Ask for help**: Open an [issue](https://github.com/isaac-cf-wong/python-package-template/issues/new/choose) with:
    - Your environment (Python version, OS)
    - Steps to reproduce
    - Full error message/logs
    - What you've already tried

<!-- prettier-ignore-end -->
