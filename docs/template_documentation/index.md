# Template documentation

Everything under **`docs/template_documentation/`** explains what this GitHub
template gives you: onboarding after **Use this template**, how the repository
is laid out, and how CI, packaging, docs, tests, and quality tools are wired.

It is **separate** from the pages you will keep for your real package at the
root of `docs/` (for example the home page, **API**, **Contributing**, and
**Security**). Those are placeholders you evolve while you ship your library.

## When you can remove this directory

Once you no longer need the walkthroughs:

1. Delete **`docs/template_documentation/`** entirely.
2. In **`zensical.toml`**, remove the **`Template documentation`** entry from
   the `nav` list (the whole nested block).

Your published site will then only show the durable docs you maintain for your
package.

## Contents

### Onboarding

For the first hours after creating a repo from the template:

- [Using this GitHub template — overview](onboarding/index.md)
- [Template quick start](onboarding/quick_start.md)
- [Customize and clean up](onboarding/customize_repository.md)

### User guide

How this repository is set up and how to work with it:

- [Installation](user_guide/installation.md)
- [Quick start](user_guide/quick_start.md)
- [Project structure](user_guide/project_structure.md)
- [Development tools](user_guide/development_tools.md)
- [Testing](user_guide/testing.md)
- [Documentation (Zensical)](user_guide/documentation.md)
- [CI/CD and releases](user_guide/ci_cd.md)
- [Packaging](user_guide/packaging.md)
- [Customization](user_guide/customization.md)

### Development notes

Deeper detail on quality and releases:

- [Code quality](development/code_quality.md)
- [Changelog (git-cliff)](development/changelog.md)
- [Troubleshooting](development/troubleshooting.md)
