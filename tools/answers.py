#!/usr/bin/env python3
"""The Project Details every render fixture in this repo starts from.

TODO §23.1: the same handful of values used to be literals in seven places --
`tests/test_recommended_path.py`, `tests/test_mcp_server.py`,
`tests/test_batch.py`, `test_example.py`'s `copy_project_recommended`
(the split moved it to `tests/support.py`), `tools/z3_witnesses.py` (whose
comment admitted it "mirrors tests/test_recommended_path.py:25-34"),
`example-answers.yml` and `batches/base.yml` (whose own comment made the same
promise). Nothing compared them, so tightening a validator (the e-mail, the
URLs derived from `github_org`) meant finding all seven by hand.

Why here and not in `tests/`: `tools/z3_witnesses.py` and `tools/batch.py` are
the repo's tools, and a tool cannot import a test module's fixture without
inverting the dependency; a test module importing another test module's fixture
couples modules that only share data. `tools/questionnaire.py` is the natural
owner of question *names* and defaults, but these values are the choices the
suite makes (a real-shaped e-mail, a real-looking org), not the questionnaire's.

`tests/test_questionnaire.py` checks every answer key any fixture uses against
the live questionnaire, and checks `batches/base.yml` against this dict, so a
rename in `copier.yml` or a hand-edited sample fails there instead of quietly
rendering a default.

The preset readers live here too: `tools/cli.py`, `tools/explain.py` and
`tools/suggest.py` each read `presets/*.yml` (the same mapping a render uses),
and each had its own copy of the listing, the leading-comment description and
the unknown-name error. The mapping reader raises `PresetError` carrying the
exact message; each caller re-raises it as its own error type (RequestError,
ExplainError) without rewording, so the CLI text is unchanged and there is
only one listing to drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.render_inputs import read_yaml_mapping

TOP = Path(__file__).resolve().parent.parent
"""The repository root (this module lives in tools/ directly under it)."""

PRESETS = TOP / "presets"
"""The ready-made answer files the preset readers serve (same directory renders use)."""

# The Project Details the suite pins on purpose. copier's own defaults are
# placeholders (`my_package`, `Your Name`, `you@example.com`), so a fixture that
# took them would exercise placeholders in the validators that read these fields
# (CITATION.cff, codemeta.json, the generated pyproject URLs). `repo_name` and
# `distribution_name` are deliberately absent: copier derives them from
# `package_name`, and pinning them here would mean every fixture that overrides
# `package_name` had to restate the derivation by hand.
BASE: dict[str, Any] = {
    "package_name": "smoke_example",
    "description": "An example project",
    "git_platform": "github.com",
    "github_org": "kasi-x",
    "author_name": "kasi-x",
    "author_email": "kashimiya.exe@gmail.com",
}


class PresetError(Exception):
    """No preset mapping can be served under this name."""


def preset_names(presets_dir: Path = PRESETS) -> list[str]:
    """The preset names: the answer files under `presets_dir`, sorted."""
    return sorted(path.stem for path in presets_dir.glob("*.yml"))


def preset_description(name: str, presets_dir: Path = PRESETS) -> str:
    """The preset file's leading comment (the family's one-line description)."""
    lines = (presets_dir / f"{name}.yml").read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if text:
                return text
    return "(no description)"


def read_preset(name: str, presets_dir: Path = PRESETS) -> dict[str, Any]:
    """The answers mapping of `<presets_dir>/<name>.yml`.

    Only the questions that define the family are in there; the rest of the
    questionnaire keeps the default copier would use for a non-interactive
    run. Raises `PresetError` for an unknown name or a non-mapping file; the
    message names the available presets, so each caller re-raises it as its
    own error type without rewording.
    """
    path = presets_dir / f"{name}.yml"
    if not path.is_file():
        known = ", ".join(preset_names(presets_dir)) or "(none)"
        msg = f"unknown preset {name!r}: no presets/{name}.yml. Available presets: {known}"
        raise PresetError(msg)
    try:
        return read_yaml_mapping(path)
    except (TypeError, ValueError) as error:
        msg = f"{path} is not an answers mapping"
        raise PresetError(msg) from error
