"""The generated blocks: markers, catalogue, drift check and rewrite.

`tools/gen_docs.py` renders the questionnaire-derived documentation; this
module owns the mechanism: the marker pairs (`BEGIN`/`END`) that delimit
each generated region, the `GeneratedBlock` catalogue (which renderer fills which
region of which file), and the `check`/`write` pair the `--check`/`--write`
CLI modes run on.

This is a machinery-layer module by the tests/test_tool_layers.py table:
files and the `Model` in, problems or changed paths out -- no template
tree, no subprocess.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import support_ledger  # noqa: E402
from tools.gen_docs_graph import render_mermaid  # noqa: E402
from tools.gen_docs_model import FEATURES_DOC  # noqa: E402
from tools.gen_docs_model import QUESTIONNAIRE_DOC  # noqa: E402
from tools.gen_docs_model import SUPPORT_DOC  # noqa: E402
from tools.gen_docs_model import SUPPORT_YML  # noqa: E402
from tools.gen_docs_model import VERIFICATION_DOC  # noqa: E402
from tools.gen_docs_model import GenDocsError  # noqa: E402
from tools.gen_docs_model import Model  # noqa: E402
from tools.gen_docs_sections import render_areas  # noqa: E402
from tools.gen_docs_sections import render_detailed_questions  # noqa: E402
from tools.gen_docs_sections import render_features_areas  # noqa: E402
from tools.gen_docs_sections import render_features_task_runner  # noqa: E402
from tools.gen_docs_sections import render_project_details  # noqa: E402
from tools.gen_docs_sections import render_project_types  # noqa: E402
from tools.gen_docs_sections import render_support_doc  # noqa: E402
from tools.gen_docs_sections import render_support_table  # noqa: E402
from tools.gen_docs_sections import render_tier_ledger  # noqa: E402

BEGIN = "<!-- BEGIN GENERATED: {name} (tools/gen_docs.py --write) -->"
END = "<!-- END GENERATED: {name} -->"


@dataclass(frozen=True)
class GeneratedBlock:
    """One generated block: where it lives, its marker name and its renderer."""

    path: Path
    block: str
    render: Callable[[Model], str]

    def begin(self) -> str:
        """The opening marker line."""
        return BEGIN.format(name=self.block)

    def end(self) -> str:
        """The closing marker line."""
        return END.format(name=self.block)

    def pattern(self) -> re.Pattern[str]:
        """The compiled marker pair, with the body as the `body` group."""
        return re.compile(
            rf"{re.escape(self.begin())}\n(?P<body>.*?)\n{re.escape(self.end())}",
            re.DOTALL,
        )

    def render_text(self, model: Model) -> str:
        """The block body for this questionnaire."""
        text = self.render(model)
        if "<!-- BEGIN GENERATED" in text or "<!-- END GENERATED" in text:
            msg = f"the {self.block!r} block renders marker text"
            raise GenDocsError(msg)
        return text


def generated_blocks(support: Path = SUPPORT_YML) -> list[GeneratedBlock]:
    """Every generated block, in file order.

    The catalogue blocks live in `docs/reference/features.md`, so the README
    keeps no generated region; the support matrix is only generated when
    `support.yml` exists: W4 owns that file, and its blocks (the catalogue's
    summary and the full `docs/reference/support.md` reference) appear with it.
    The tier-ledger block (docs/explanations/verification.md) is generated
    from the cost ledger, not the questionnaire (TODO.md §28.6-D4).
    """
    blocks = [
        GeneratedBlock(QUESTIONNAIRE_DOC, "project-types", render_project_types),
        GeneratedBlock(QUESTIONNAIRE_DOC, "areas", render_areas),
        GeneratedBlock(QUESTIONNAIRE_DOC, "detailed-questions", render_detailed_questions),
        GeneratedBlock(QUESTIONNAIRE_DOC, "project-details", render_project_details),
        GeneratedBlock(FEATURES_DOC, "features-areas", render_features_areas),
        GeneratedBlock(FEATURES_DOC, "features-mermaid", _mermaid_block),
        GeneratedBlock(FEATURES_DOC, "features-task-runner", render_features_task_runner),
        GeneratedBlock(VERIFICATION_DOC, "tier-ledger", render_tier_ledger),
    ]
    if support.is_file():
        blocks.append(GeneratedBlock(FEATURES_DOC, "support-table", _support_block(support)))
        blocks.append(GeneratedBlock(SUPPORT_DOC, "support-matrix", _support_doc_block(support)))
    return blocks


def _mermaid_block(model: Model) -> str:
    """The catalogue mermaid block, fences included."""
    return f"```mermaid\n{render_mermaid(model)}\n```"


def _support_block(support: Path) -> Callable[[Model], str]:
    """A renderer for the catalogue's compact support summary, bound to `support.yml`."""

    def render(_model: Model) -> str:
        return render_support_table(support_ledger.load_support(support))

    return render


def _support_doc_block(support: Path) -> Callable[[Model], str]:
    """A renderer for the full `docs/reference/support.md`, bound to `support.yml`."""

    def render(_model: Model) -> str:
        return render_support_doc(support_ledger.load_support(support))

    return render


def support_doc_text(support: Path = SUPPORT_YML) -> str:
    """The complete `docs/reference/support.md`, markers included."""
    target = GeneratedBlock(SUPPORT_DOC, "support-matrix", _support_doc_block(support))
    return f"{target.begin()}\n{target.render_text(Model.load())}\n{target.end()}\n"


def _relative(path: Path) -> str:
    return str(path.relative_to(TOP)) if path.is_relative_to(TOP) else str(path)


def _drift(target: GeneratedBlock, actual: str, expected: str) -> str:
    """Describe the first line where a committed block differs from the model."""
    committed = actual.splitlines()
    wanted = expected.splitlines()
    for index, (left, right) in enumerate(zip(committed, wanted, strict=False), start=1):
        if left != right:
            return f"{_relative(target.path)}: {target.block} differs at line {index}\n  - {left}\n  + {right}"
    if len(committed) != len(wanted):
        extra = wanted[len(committed)] if len(wanted) > len(committed) else committed[len(wanted)]
        return (
            f"{_relative(target.path)}: {target.block} has {len(committed)} lines, expected {len(wanted)}\n  ± {extra}"
        )
    return f"{_relative(target.path)}: {target.block} differs"


def check(model: Model, blocks: list[GeneratedBlock]) -> list[str]:
    """Return one problem per stale or missing generated block."""
    problems: list[str] = []
    for target in blocks:
        match = target.pattern().search(target.path.read_text(encoding="utf-8"))
        if match is None:
            problems.append(f"{_relative(target.path)}: no generated block {target.block!r} (add its markers)")
            continue
        expected = target.render_text(model)
        if match.group("body") != expected:
            problems.append(_drift(target, match.group("body"), expected))
    return problems


def write(model: Model, blocks: list[GeneratedBlock]) -> list[str]:
    """Replace every generated block; return the blocks that changed."""
    changed: list[str] = []
    for target in blocks:
        text = target.path.read_text(encoding="utf-8")
        match = target.pattern().search(text)
        if match is None:
            msg = f"{_relative(target.path)}: no generated block {target.block!r} (add its markers)"
            raise GenDocsError(msg)
        expected = target.render_text(model)
        if match.group("body") == expected:
            continue
        target.path.write_text(text[: match.start("body")] + expected + text[match.end("body") :], encoding="utf-8")
        changed.append(f"{_relative(target.path)}: {target.block}")
    return changed
