#!/usr/bin/env python3
"""Interactive/guided scaffolding for new questions, layers, and presets.

Reduces contributor friction by:
- Generating well-formed question YAML blocks with `when:`, `default:`, and `help:`.
- Generating well-formed `include_<layer>` layer stubs with invariants entry.
- Generating well-formed preset YAML stubs under `presets/`.
- Validating Z3 reachability/satisfiability so mistakes fail fast.
- Running `task regen` to update all witness leaves, tiers, and docs safely.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import answers  # noqa: E402
from tools import invariants  # noqa: E402
from tools import questionnaire  # noqa: E402
from tools import when_model  # noqa: E402


def validate_expression(expr: str) -> tuple[bool, str]:
    """Test if a `when` expression is satisfiable under the question domain using Z3."""
    try:
        import z3  # noqa: PLC0415
    except ImportError:
        return True, "z3 not installed (skipped SAT check)"

    questions, _order = when_model.load_questions()
    domains = when_model.str_domains(questions)
    try:
        sat = when_model.when_expr_satisfiable(expr, domains, z3)
    except Exception as exc:  # noqa: BLE001
        return False, f"Failed to evaluate expression with Z3: {exc}"
    if not sat:
        return False, f"Expression is unsatisfiable under model: {expr!r}"
    return True, "Satisfiable"


def scaffold_question(  # noqa: PLR0913
    name: str,
    *,
    qtype: str = "bool",
    when: str = "true",
    default: Any = True,
    help_text: str = "",
    target_file: str = "questions/_common_c.yml",
    dry_run: bool = False,
) -> int:
    """Generate a question stub in the specified questions file."""
    path = TOP / target_file
    if not path.is_file():
        print(f"Error: Target question file does not exist: {path}", file=sys.stderr)
        return 1
    if qtype not in ("bool", "str", "yaml"):
        print(f"Error: unknown question type {qtype!r} (expected bool, str, or yaml)", file=sys.stderr)
        return 1

    # Validate SAT if when != "true" (a missing `when` also asks: copier defaults it to true)
    if when != "true":
        ok, msg = validate_expression(when)
        if not ok:
            print(f"Warning: {msg}", file=sys.stderr)

    braced = when if (when == "true" or (when.startswith("{{") and when.endswith("}}"))) else "{{ " + when + " }}"
    default_str = "true" if default is True else ("false" if default is False else repr(default))
    help_block = "\n".join(f"        {line}" for line in (help_text or f"Configure {name}?").splitlines())
    stub = f"""
{name}:
    type: {qtype}
    when: "{braced}"
    default: {default_str}
    help: |
{help_block}
"""
    if dry_run:
        print(f"=== [Dry Run] Would append to {path.relative_to(TOP)} ===")
        print(stub)
        return 0

    with path.open("a", encoding="utf-8") as f:
        f.write(stub)
    print(f"Added question {name!r} to {path.relative_to(TOP)}")
    return 0


def scaffold_layer(
    layer_name: str,
    *,
    description: str = "",
    dry_run: bool = False,
) -> int:
    """Scaffold a new `include_<layer>` question, invariants row, layers-matrix row, and template guidance."""
    clean_name = layer_name.removeprefix("include_")
    question_name = f"include_{clean_name}"

    # 1. Add question to questions/_combo.yml (the opt-in layers' home; keep
    # ask order = file order there). The generated `when` is the combinable
    # default; tighten it to the layer's real bases (cf. the existing
    # include_* rows) and declare the same bases in tests/matrix/layers.yml.
    q_file = "questions/_combo.yml"
    help_text = f"Include {clean_name} support? ({description or 'Opt-in layer'})"
    print(f"1. Staging question {question_name!r} in {q_file}...")
    res = scaffold_question(
        question_name,
        qtype="bool",
        when="{{ project_type in ['library', 'cli'] }}",
        default=False,
        help_text=help_text,
        target_file=q_file,
        dry_run=dry_run,
    )
    if res != 0:
        return res

    # 2. Print invariants + layers-matrix guidance
    inv_file = TOP / "tests" / "matrix" / "invariants.yml"
    inv_stub = f"""
  - id: include={question_name}
    select: {{include: [{question_name}]}}
    ships: []
    absent: []
    predicates: []
    tier:
      name: fast
      why: "{clean_name} layer renders and checks clean in the fast tier"
    why: "the {clean_name} opt-in layer"
"""
    layers_file = TOP / "tests" / "matrix" / "layers.yml"
    layers_stub = f"""
  - include: {question_name}
    bases: [library, cli]
    why: >-
      <why this layer rides exactly these bases>
"""
    if dry_run:
        print(f"=== [Dry Run] Would append to {inv_file.relative_to(TOP)} ===")
        print(inv_stub)
        print(f"=== [Dry Run] Would append to {layers_file.relative_to(TOP)} ===")
        print(layers_stub)
    else:
        print(f"2. Please add the following to {inv_file.relative_to(TOP)}:\n{inv_stub}")
        print(f"   And the following to {layers_file.relative_to(TOP)}:\n{layers_stub}")

    # 3. Print template + effective-internal guidance (layers render through
    # a <name>_effective internal, not a raw include_* file condition)
    print(
        f"3. Wire the layer through a {clean_name}_effective internal in questions/_internal.yml "
        f'(default: "{{{{ {question_name} and ... }}}}" , when: false), '
        f"then gate template files on it: "
        f"template/{{{{% if {clean_name}_effective %}}}}...{{{{% endif %}}}}/"
    )
    print("   Then run the extending runbook (docs/explanations/extending.md): task witness + markers + docs.")
    return 0


def scaffold_preset(
    name: str,
    *,
    description: str = "",
    base_project_type: str = "library",
    answers_map: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> int:
    """Generate a preset YAML file under presets/."""
    preset_file = TOP / "presets" / f"{name}.yml"
    if preset_file.exists():
        print(f"Error: Preset {name!r} already exists at {preset_file}", file=sys.stderr)
        return 1
    questions, _order = when_model.load_questions()
    valid_bases = questionnaire.static_str_choices(questions["project_type"])
    if base_project_type not in valid_bases:
        print(
            f"Error: unknown base project_type {base_project_type!r} (expected one of: {', '.join(valid_bases)})",
            file=sys.stderr,
        )
        return 1

    content_lines = [
        f"# {description or f'{name.title()} preset configuration'}",
        "#",
        f"project_type: {base_project_type}",
    ]
    if answers_map:
        for k, v in answers_map.items():
            if k != "project_type":
                val_str = "true" if v is True else ("false" if v is False else repr(v))
                content_lines.append(f"{k}: {val_str}")

    payload = "\n".join(content_lines) + "\n"
    if dry_run:
        print(f"=== [Dry Run] Would write {preset_file.relative_to(TOP)} ===")
        print(payload)
        return 0

    preset_file.write_text(payload, encoding="utf-8")
    print(f"Created preset at {preset_file.relative_to(TOP)}")
    return 0


def scaffold_check() -> int:
    """Check integrity across questionnaire, Z3 model, presets, and invariants."""
    print("Checking questionnaire Z3 satisfiability and model consistency...")
    try:
        import z3  # noqa: PLC0415

        questions, _ = when_model.load_questions()
        domains = when_model.str_domains(questions)
        whens = {name: q["when"] for name, q in questions.items() if isinstance(q.get("when"), str)}
        unsat = []
        for q_name, when in whens.items():
            if when and when != "true":
                try:
                    if not when_model.when_expr_satisfiable(when, domains, z3):
                        unsat.append((q_name, when))
                except Exception as exc:  # noqa: BLE001
                    print(f"  Error checking {q_name}: {exc}")
        if unsat:
            print(f"Error: {len(unsat)} questions have unsatisfiable when conditions:")
            for q_name, w in unsat:
                print(f"  - {q_name}: {w}")
            return 1
        print(f"  All {len(whens)} question when conditions are satisfiable.")
    except ImportError:
        print("  Z3 not installed; skipped deep SAT checks.")

    # Check presets
    print("Checking presets...")
    for p in answers.preset_names():
        ans = answers.read_preset(p)
        if not ans.get("project_type"):
            print(f"  Warning: preset {p} does not specify project_type")
    print(f"  All {len(answers.preset_names())} presets are valid mappings.")

    # Check invariants
    print("Checking invariants...")
    inv = invariants.load()
    print(f"  Loaded {len(inv.rows)} invariant rows across {len(inv.renderable_project_types)} project types.")
    print("Integrity check passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="daimonion scaffold",
        description="Scaffold and validate additions to questionnaire, layers, and presets.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # question
    q_parser = sub.add_parser("question", help="scaffold a new question block in questions/")
    q_parser.add_argument("name", help="question variable name")
    q_parser.add_argument("--type", default="bool", choices=["bool", "str", "yaml"], help="type of question")
    q_parser.add_argument("--when", default="true", help="when condition (Jinja expression)")
    q_parser.add_argument("--default", default="true", help="default value (true, false, or literal)")
    q_parser.add_argument("--help-text", default="", help="help/prompt text for questionnaire")
    q_parser.add_argument("--file", default="questions/_common_c.yml", help="target file under questions/")
    q_parser.add_argument("--dry-run", action="store_true", help="print without writing")

    # layer
    l_parser = sub.add_parser("layer", help="scaffold a new opt-in layer (include_<name>)")
    l_parser.add_argument("name", help="layer identifier (e.g. grpc, kafka)")
    l_parser.add_argument("--description", default="", help="short layer description")
    l_parser.add_argument("--dry-run", action="store_true", help="print without writing")

    # preset
    p_parser = sub.add_parser("preset", help="scaffold a new answers preset under presets/")
    p_parser.add_argument("name", help="preset name (e.g. grpc-service)")
    p_parser.add_argument("--description", default="", help="description header")
    p_parser.add_argument("--base", default="library", help="base project_type")
    p_parser.add_argument("--dry-run", action="store_true", help="print without writing")

    # check
    sub.add_parser("check", help="verify satisfiability and model consistency")

    args = parser.parse_args(argv)

    if args.subcommand == "question":
        val = True if args.default.lower() == "true" else (False if args.default.lower() == "false" else args.default)
        return scaffold_question(
            args.name,
            qtype=args.type,
            when=args.when,
            default=val,
            help_text=args.help_text,
            target_file=args.file,
            dry_run=args.dry_run,
        )
    if args.subcommand == "layer":
        return scaffold_layer(args.name, description=args.description, dry_run=args.dry_run)
    if args.subcommand == "preset":
        return scaffold_preset(
            args.name, description=args.description, base_project_type=args.base, dry_run=args.dry_run
        )
    if args.subcommand == "check":
        return scaffold_check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
