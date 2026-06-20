# Customize and clean up

After you fork the template, walk through these steps so the repository matches
your package and publishing setup.

## Rename the Python package

1. Rename the directory `src/python_package_template/` to
   `src/your_package_name/`.
2. Replace imports and string references to `python_package_template` across
   `src/`, `tests/`, and `docs/`.
3. In `pyproject.toml`, update `[project] name`, `[project.scripts]`, and any
   URLs under `[project.urls]`.
4. In `zensical.toml`, set `site_name`, `site_description`, and optionally
   `site_url` for GitHub Pages.
5. Regenerate or edit hand-written API pages under `docs/api/` if you keep them,
   and adjust the **API** section of `nav` in `zensical.toml`.

## Point git-cliff at your repository

In `cliff.toml`, replace the template’s GitHub URL with your own so changelog
links resolve correctly.

## PyPI and GitHub environments

Publishing workflows expect GitHub environments named `pypi` and/or `testpypi`.
The scheduled release workflow uses `continue-on-error: true` on the publish
step so the template does not fail if those environments are missing. For a real
package, remove that flag and configure
[trusted publishing](https://docs.pypi.org/trusted-publishers/) on PyPI.

## Remove template-only documentation

When you are done with onboarding copy:

1. Delete the directory **`docs/template_documentation/`**.
2. Remove the **`Template documentation`** entry from `nav` in `zensical.toml`.

Optional: replace the root **`docs/index.md`** with copy aimed at end users of
your package only.

## Optional: drop tooling you do not need

- **Git hooks**: delete `.pre-commit-config.yaml` and remove `prek` from the
  `dev` dependency group in `pyproject.toml` if you do not want hooks.
- **Documentation**: remove or replace the docs stack (for example drop Zensical
  and the `docs` extra) if you use something else.
- **CLI**: remove `src/.../cli/`, Typer from dependencies, and
  `[project.scripts]` if you do not ship a command-line entry point.
