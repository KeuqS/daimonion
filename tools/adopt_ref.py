"""Which revision to expand, and which answers to expand it with.

`tools/adopt.py` renders a revision of this template, not just the working
tree: `copier copy` without `--vcs-ref` resolves the newest tag, and a
fork's inherited tags can point at a long-abandoned ancestor with a
different questionnaire. `resolve_ref` judges the latest tag by whether it
carries this questionnaire and falls back to the branch when it does not;
`_plan_data` layers the caller's answers over what `tools/detect.py`
derived for the target.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
reads the template's git history through `tools/batch.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import batch  # noqa: E402
from tools import detect  # noqa: E402
from tools import questionnaire  # noqa: E402
from tools.adopt_models import CONFIG_FILES  # noqa: E402
from tools.adopt_models import top  # noqa: E402


def _ref_questions(ref: str) -> set[str]:
    """Question names declared at `ref`, read out of git without a checkout."""
    names: set[str] = set()
    paths = [*CONFIG_FILES, *(p for p in _ref_question_files(ref))]
    for path in paths:
        shown = batch.git(top(), "show", f"{ref}:{path}")
        if shown.returncode != 0:
            continue
        names.update(questionnaire.QUESTION_LINE.findall(shown.stdout))
    return names


def _ref_question_files(ref: str) -> list[str]:
    listing = batch.git(top(), "ls-tree", "-r", "--name-only", ref, "--", "questions")
    if listing.returncode != 0:
        return []
    return [line for line in listing.stdout.splitlines() if line.endswith((".yml", ".yaml"))]


def resolve_ref(requested: str | None = None) -> tuple[str, str]:
    """Choose the revision to expand: the latest tag only if it is this questionnaire.

    `copier copy` without `--vcs-ref` resolves the repository's newest tag.
    This fork tags its own releases, so that tag normally is the right
    questionnaire. It is still used only when it declares the same questions
    as this checkout -- a tag left over from before the fork detach points at
    a different template -- and otherwise the default branch is used, with the
    reason reported. `--ref` names a revision explicitly; `--ref HEAD` expands
    the working tree for local iteration.
    """
    if requested:
        return requested, "requested explicitly"
    latest = batch.git(top(), "describe", "--tags", "--abbrev=0")
    branch = batch.git(top(), "rev-parse", "--abbrev-ref", "HEAD")
    branch_name = branch.stdout.strip() if branch.returncode == 0 else ""
    tag = latest.stdout.strip() if latest.returncode == 0 else ""
    if not tag or not branch_name or branch_name == "HEAD":
        return "HEAD", "no usable tag or branch; rendering the working tree"
    worktree = _ref_questions("HEAD")
    tagged = _ref_questions(tag)
    missing = sorted(worktree - tagged)
    if missing:
        reason = (
            f"latest tag {tag} does not carry this questionnaire "
            f"(missing {len(missing)} question(s), e.g. {', '.join(missing[:3])}); using {branch_name}"
        )
        return branch_name, reason
    return tag, f"latest tag {tag} carries this questionnaire"


def _plan_data(detection: detect.Detection, answers: dict[str, Any]) -> dict[str, Any]:
    """The answers for this target: what detect derived, overridden by the caller."""
    data = dict(detection.suggested_answers)
    if detection.mode == "fresh":
        data["existing_project"] = False
    data.update(answers)
    return data
