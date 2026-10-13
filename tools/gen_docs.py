#!/usr/bin/env python3
"""Generate the questionnaire-derived documentation, and check it for drift.

The questionnaire (`copier.yml` plus the `questions/*.yml` fragments) is the
single source of truth for this template's option set; `tools/questionnaire.py`
exposes it as data. This script renders every part of the docs that only
repeats that data, so none of it can silently drift again:

- `docs/reference/questionnaire.md`: the project-type list, the area-gate
  table with each area's recommended defaults, the detailed questions a gate
  reveals, and the trailing project-details questions.
- `docs/reference/features.md`: the per-area recommended settings table, the
  ask-order mermaid graph (each gate's Yes/No branch) and the task-runner
  bullet of the feature catalogue.
- `docs/reference/features.md`: a compact support summary (one row per declared
  combination), generated from `support.yml`.
- `docs/reference/support.md`: the full support matrix, prose included, also
  generated from `support.yml`.
- `docs/explanations/verification.md`: the cost-ledger table (selector, tests,
  budget, measured), generated from `tests/matrix/tiers.json` (§28.6-D4).

The support blocks are only generated when `support.yml` exists (W4 owns
that file; no `support.yml`, no block).

Every generated region sits between an explicit marker pair::

    <!-- BEGIN GENERATED: <name> (tools/gen_docs.py --write) -->
    ...
    <!-- END GENERATED: <name> -->

`--write` replaces those regions wholesale and never touches the hand-written
prose around them; `--check` renders the same text and exits non-zero when a
committed region differs (the CI gate). Both run offline.

The rendering lives in the sibling `gen_docs_*` modules (model, prose,
sections, graph, blocks); this module is the CLI entry point plus the
backward-compatible surface. `tools/gen_docs.py` stays the command
(`python tools/gen_docs.py --check/--write`) and `tools.gen_docs` stays the
import tests and tools use: the names the old monolith exposed resolve here,
statically for what the CLI needs and dynamically (PEP 562) for the rest.

Usage:
    python tools/gen_docs.py --check   # exit 1 when a generated block is stale
    python tools/gen_docs.py --write   # update the generated blocks
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools.gen_docs_blocks import BEGIN  # noqa: E402
from tools.gen_docs_blocks import END  # noqa: E402
from tools.gen_docs_blocks import GeneratedBlock  # noqa: E402
from tools.gen_docs_blocks import check  # noqa: E402
from tools.gen_docs_blocks import generated_blocks  # noqa: E402
from tools.gen_docs_blocks import support_doc_text  # noqa: E402
from tools.gen_docs_blocks import write  # noqa: E402
from tools.gen_docs_graph import render_mermaid  # noqa: E402
from tools.gen_docs_model import ALL_TYPES  # noqa: E402
from tools.gen_docs_model import BOOL_PROSE  # noqa: E402
from tools.gen_docs_model import FEATURES_DOC  # noqa: E402
from tools.gen_docs_model import GATE_PREFIX  # noqa: E402
from tools.gen_docs_model import INCLUDE_PREFIX  # noqa: E402
from tools.gen_docs_model import PROMPT_STOPS  # noqa: E402
from tools.gen_docs_model import QUESTIONNAIRE_DOC  # noqa: E402
from tools.gen_docs_model import RUNNER_URLS  # noqa: E402
from tools.gen_docs_model import SUPPORT_DOC  # noqa: E402
from tools.gen_docs_model import SUPPORT_YML  # noqa: E402
from tools.gen_docs_model import TIERS_JSON  # noqa: E402
from tools.gen_docs_model import VERIFICATION_DOC  # noqa: E402
from tools.gen_docs_model import GenDocsError  # noqa: E402
from tools.gen_docs_model import Model  # noqa: E402
from tools.gen_docs_prose import asked_for_values  # noqa: E402
from tools.gen_docs_prose import choice_help  # noqa: E402
from tools.gen_docs_prose import condition_prose  # noqa: E402
from tools.gen_docs_prose import declined  # noqa: E402
from tools.gen_docs_prose import default_prose  # noqa: E402
from tools.gen_docs_prose import first_sentence  # noqa: E402
from tools.gen_docs_prose import help_paragraph  # noqa: E402
from tools.gen_docs_prose import prompt_line  # noqa: E402
from tools.gen_docs_prose import recommended  # noqa: E402
from tools.gen_docs_sections import render_areas  # noqa: E402
from tools.gen_docs_sections import render_detailed_questions  # noqa: E402
from tools.gen_docs_sections import render_features_areas  # noqa: E402
from tools.gen_docs_sections import render_features_task_runner  # noqa: E402
from tools.gen_docs_sections import render_project_details  # noqa: E402
from tools.gen_docs_sections import render_project_types  # noqa: E402
from tools.gen_docs_sections import render_support_doc  # noqa: E402
from tools.gen_docs_sections import render_support_table  # noqa: E402
from tools.gen_docs_sections import render_tier_ledger  # noqa: E402
from tools.questionnaire import Question  # noqa: E402

__all__ = [
    "ALL_TYPES",
    "BEGIN",
    "BOOL_PROSE",
    "END",
    "FEATURES_DOC",
    "GATE_PREFIX",
    "INCLUDE_PREFIX",
    "PROMPT_STOPS",
    "QUESTIONNAIRE_DOC",
    "RUNNER_URLS",
    "SUPPORT_DOC",
    "SUPPORT_YML",
    "TIERS_JSON",
    "TOP",
    "VERIFICATION_DOC",
    "GenDocsError",
    "GeneratedBlock",
    "Model",
    "Question",
    "_parse_args",
    "asked_for_values",
    "check",
    "choice_help",
    "condition_prose",
    "declined",
    "default_prose",
    "first_sentence",
    "generated_blocks",
    "help_paragraph",
    "main",
    "prompt_line",
    "recommended",
    "render_areas",
    "render_detailed_questions",
    "render_features_areas",
    "render_features_task_runner",
    "render_mermaid",
    "render_project_details",
    "render_project_types",
    "render_support_doc",
    "render_support_table",
    "render_tier_ledger",
    "support_doc_text",
    "write",
]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit non-zero when a generated block is stale (default)")
    mode.add_argument("--write", action="store_true", help="rewrite the generated blocks")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: check or rewrite the generated blocks."""
    args = _parse_args(argv)
    model = Model.load()
    blocks = generated_blocks()
    if args.write:
        changed = write(model, blocks)
        if not changed:
            print(f"{len(blocks)} generated block(s) already up to date")
            return 0
        print("updated:\n  " + "\n  ".join(changed))
        return 0
    problems = check(model, blocks)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print("generated docs are stale; run: python tools/gen_docs.py --write", file=sys.stderr)
        return 1
    print(f"{len(blocks)} generated block(s) in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
