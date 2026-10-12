# How to update to the latest template structure

## Overview

To track changes to the upstream template, run

```
uvx copier update --trust
```

!!! note
    One-time migration: if your project's recorded template version predates
    the Jinja-extension removal, run the first update with
    `uvx --with copier-template-extensions copier update --trust` — after
    that single update, plain `uvx copier update --trust` works again.

This will fetch the latest tagged release of the template, and apply any changes to your working copy. It will prompt for answers again, giving your previous answers as the defaults.

It will stage all the changes for commit, but there may be merge conflicts that need fixing first, find them with

```
git diff --check
```

Once they are all fixed, make a commit.

## Recommended Workflow

The following steps are recommended to update your project, especially for infrequently updated projects:

- first make sure all the tools are updated to latest versions
    - for devcontainers
        - `ctrl+shift+p` -> `Remote-Containers: Rebuild Without Cache and Reopen in Container`
    - for local development
        - `uv sync`
- validate your project against the latest tools
    - `task check`
- fix issues found by the above
- commit the changes
- update the template
    - `uvx copier update --trust`
- fix any merge conflicts
- validate that the project still works
    - `task check`
- fix any issues found by the above
- commit the changes

## Check what changed: the composition contract

Every generated project carries `.daimonion-manifest.yml`: the composition
contract — the template ref it was generated from, the answers file it
describes, and the ethics sections the render distributed. It never carries
answer values (those live in `.copier-answers.yml`), so it is safe to keep
and compare.

Before updating, record what you have; after updating, ask what moved:

```
daimonion verify /path/to/project
daimonion verify /path/to/project --against /path/to/older-copy
```

The report checks the manifest's schema version, holds the manifest's ref
against the answers file's `_commit`, and — with `--against` — lists which
ref, answers, and distributed sections changed. A tampered manifest fails
verification instead of reporting a clean bill.
