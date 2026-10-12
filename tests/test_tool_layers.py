"""The tools/ dependency layers are declared, and no import points up.

tools/ grew past nineteen modules with an IMPLICIT layering: every cross-module
import is spelled `from tools import x`, but nothing recorded which modules sit
where, so "may adopt.py use invariants?" was answerable only by reading all of
them. The layering is now a declared contract, in the repo's registry idiom
(tests/test_answer_fixtures.py's DEFAULT_REPEATS_ALLOWED, tests/matrix/
invariants.yml's `excluded`): declared, not discovered, and enforced here
structurally -- an `ast` scan of the import statements, no runtime import, so
the check costs milliseconds and cannot go red because a tool grew an expensive
import.

The layers, bottom up (the table also lives in docs/explanations/template-dev.md,
next to the other structural rules):

    standalone   maintenance/CI scripts that run on their own: they import
                 nothing from tools/ (check_upstream, check_upstream_fork,
                 check_questionnaire_diff, generate_license_template)
    foundations  the questionnaire model and shared primitives: the
                 questionnaire as data (questionnaire), its when-expressions
                 (when_model), the shared answer fixture (answers), the
                 render-input fingerprint (render_inputs), the declared
                 support contract (support_ledger)
    machinery    pure transformations over template/adoption artifacts: the
                 text and pyproject merges (file_merge, pyproject_merge), the
                 leaf invariants (invariants) and the Z3 leaf enumerator
                 (z3_witnesses)
    drivers      the tools that act on real trees with copier/subprocess:
                 detect, batch, adopt, the shared git runner (git), the
                 condition classifier built on the machinery (predicates),
                 the inverse selector that turns wanted features into
                 witness answers (answers_for), the questionnaire
                 dependency graph built on the foundations (question_graph),
                 and the constrained proposal gate over copier's own pass
                 (suggest)
    frontends    the entry points an agent or a human calls: cli, explain,
                 gen_docs, mcp_server

The rule: a module may import modules of its own layer or any layer BELOW it.
An import that points up fails here, unless the pair is declared in
ALLOWED_UPWARD_IMPORTS with a one-line reason -- a genuine tangle that is not
worth refactoring away is stated, not hidden. Both halves are stale-proofed
the way DEFAULT_REPEATS_ALLOWED is: an undeclared upward import fails, and so
does a declared exception whose edge has vanished or stopped pointing up.

A new module under tools/ fails
`test_every_tool_module_is_declared_in_exactly_one_layer` until it is placed:
pick the layer it belongs in, and the import-direction test tells you whether
the guess was right.
"""

from __future__ import annotations

import ast
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
TOOLS = TOP / "tools"

# Layer -> (what it is, its modules). Order IS the ranking: earlier = lower =
# importable by everything above it. A module appears in exactly one layer.
LAYERS: dict[str, tuple[str, frozenset[str]]] = {
    "standalone": (
        (
            "maintenance/CI scripts that import nothing from tools/"
            " (a pristine checkout or a released tarball is their world)"
        ),
        frozenset(
            {
                "check_ethics_contract",
                "check_ethics_drift",
                "check_questionnaire_diff",
                "check_upstream",
                "check_upstream_fork",
                "generate_license_template",
            }
        ),
    ),
    "foundations": (
        "the questionnaire model and shared primitives: data and meaning, no behavior on real trees",
        frozenset({"answers", "ethics", "questionnaire", "render_inputs", "support_ledger", "when_model"}),
    ),
    "machinery": (
        "pure transformations and verifiers over template/adoption artifacts",
        frozenset({"file_merge", "invariants", "pyproject_merge", "z3_witnesses"}),
    ),
    "drivers": (
        "act on real trees with copier/subprocess; consume the machinery",
        frozenset(
            {
                "adopt",
                "answers_for",
                "batch",
                "detect",
                "git",
                "predicates",
                "question_graph",
                "render_delta",
                "suggest",
                "update_rehearsal",
                "verify",
            }
        ),
    ),
    "frontends": (
        "the entry points a human or an agent calls; consume the drivers",
        frozenset({"cli", "explain", "gen_docs", "gen_ethics_appendix", "mcp_server"}),
    ),
}

# Upward imports accepted on purpose: (importer, imported) -> why the tangle
# stays. Declared, not discovered: an upward import missing here fails, and an
# entry whose edge no longer exists (or no longer points up) fails too.
ALLOWED_UPWARD_IMPORTS: dict[tuple[str, str], str] = {}


def _placement() -> dict[str, str]:
    """Module -> the single layer that declares it."""
    placement: dict[str, str] = {}
    for layer, (_what, modules) in LAYERS.items():
        for module in modules:
            placement[module] = layer
    return placement


def _tools_modules() -> dict[str, Path]:
    """Every tools/ module on disk, by its dotted name relative to tools/ (the
    discovery tests/test_qa.py uses for the same directory)."""
    return {
        str(p.relative_to(TOOLS)).removesuffix(".py").replace("/", "."): p
        for p in sorted(TOOLS.rglob("*.py"))
        if p.name != "__init__.py"
    }


def _tools_relative(dotted: str | None) -> str:
    """`tools.x[.y...]` -> `x...`; anything else -> "" (not a tools/ import)."""
    if dotted is None:
        return ""
    if dotted == "tools":
        return ""
    if dotted.startswith("tools."):
        return dotted[len("tools.") :]
    return ""


def _tool_imports(path: Path, declared: set[str]) -> set[str]:
    """The declared tools/ modules one module's source imports (AST, no runtime).

    Absolute (`from tools import batch`, `import tools.questionnaire`) and
    relative (`from . import batch` -- tools/ is a namespace package) forms
    both resolve; the longest declared prefix of the dotted name wins, so
    `from tools.questionnaire import Question` lands on `questionnaire`.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dotted: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dotted.update(_tools_relative(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                dotted.add(_tools_relative(node.module))
                if node.module == "tools":  # `from tools import a, b` imports each name
                    dotted.update(alias.name for alias in node.names)
            else:  # relative: resolves inside tools/ itself
                dotted.add(node.module.split(".")[0] if node.module else "")
                if not node.module:
                    dotted.update(alias.name for alias in node.names)
    edges: set[str] = set()
    for name in dotted:
        parts = name.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in declared:
                edges.add(candidate)
                break
    return edges


def _rank() -> dict[str, int]:
    return {layer: index for index, layer in enumerate(LAYERS)}


def test_every_tool_module_is_declared_in_exactly_one_layer() -> None:
    """Every tools/ module sits in exactly one declared layer, and every
    declared module exists.

    A module on disk without a layer is an unplanned dependency surface; a
    layer naming a module that is gone is a stale row of the table; a module
    in two layers is an ambiguous contract; an empty layer is a ranking nobody
    can observe. All four are the registry lying in one direction or the other.
    """
    on_disk = _tools_modules()
    placement = _placement()
    duplicated = {
        module: [layer for layer, (_what, modules) in LAYERS.items() if module in modules]
        for module in placement
        if sum(module in modules for _what, modules in LAYERS.values()) > 1
    }
    unknown = sorted(set(on_disk) - set(placement))
    stale = sorted(set(placement) - set(on_disk))
    empty = [layer for layer, (_what, modules) in LAYERS.items() if not modules]
    assert not duplicated and not unknown and not stale and not empty, (
        "the tools/ layer registry and the tools/ directory disagree:\n"
        + "".join(f"\n  declared twice: {module} -> {layers}" for module, layers in duplicated.items())
        + "".join(
            f"\n  undeclared module: tools/{module}.py -- pick a layer in tests/test_tool_layers.py LAYERS"
            for module in unknown
        )
        + "".join(f"\n  stale entry: {module} is declared in {placement[module]} but not on disk" for module in stale)
        + "".join(f"\n  empty layer: {layer}" for layer in empty)
    )


def test_no_tool_module_imports_from_a_higher_layer() -> None:
    """Every tools -> tools import points down or sideways, never up.

    The scan is structural: it reads the import statements' AST and resolves
    each to its declared layer. An upward import must either be fixed (move
    code down a layer) or declared in ALLOWED_UPWARD_IMPORTS with the reason
    the tangle stays.
    """
    placement = _placement()
    rank = _rank()
    edges = {module: _tool_imports(path, set(placement)) for module, path in _tools_modules().items()}
    undeclared = [
        (module, target) for module, targets in edges.items() for target in sorted(targets) if target not in placement
    ]
    upward = [
        f"tools/{module}.py ({placement[module]}) imports tools/{target}.py ({placement[target]}, above it)"
        for module, targets in edges.items()
        for target in sorted(targets)
        if target in placement
        and rank[placement[target]] > rank[placement[module]]
        and (module, target) not in ALLOWED_UPWARD_IMPORTS
    ]
    assert not undeclared and not upward, (
        "an import points up the tools/ layers:"
        + "".join(f"\n  {module} imports undeclared {target}" for module, target in undeclared)
        + "".join(
            f"\n  {line} -- move the code down a layer, or declare the edge in ALLOWED_UPWARD_IMPORTS"
            " (tests/test_tool_layers.py) with the one-line reason it stays"
            for line in upward
        )
    )


def test_every_declared_exception_is_a_live_upward_import_with_a_reason() -> None:
    """ALLOWED_UPWARD_IMPORTS neither lies nor outlives its edge.

    The other direction of the registry (the DEFAULT_REPEATS_ALLOWED idiom):
    an entry whose import has disappeared, whose modules are gone, or that no
    longer points UP (the refactor happened, or the modules were re-layered)
    is stale and must be dropped -- otherwise the exception list grows into an
    uncheckable folklore of tangles that used to exist.
    """
    placement = _placement()
    rank = _rank()
    edges = {module: _tool_imports(path, set(placement)) for module, path in _tools_modules().items()}
    stale = []
    for (module, target), reason in ALLOWED_UPWARD_IMPORTS.items():
        live_and_upward = (
            target in edges.get(module, set())
            and module in placement
            and target in placement
            and rank[placement[target]] > rank[placement[module]]
        )
        if not live_and_upward:
            stale.append(f"({module}, {target}): the import is gone or no longer points up")
        if not reason.strip():
            stale.append(f"({module}, {target}): declared without the one-line reason the tangle stays")
    assert not stale, (
        "ALLOWED_UPWARD_IMPORTS declares an exception that no longer holds, so the registry is stale"
        " and must drop or fix the entry:\n  " + "\n  ".join(sorted(stale))
    )
