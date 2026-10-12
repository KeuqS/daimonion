"""Command line: plan, apply, recover, and report the exit code.

`main` parses one invocation -- an adoption (planned first, then applied
unless `--dry-run`), or a `--recover` that undoes an interrupted run --
and maps the outcome onto the exit codes the module docstring promises.
`_prompter` builds the confirmation callback only when somebody is there
to answer it; anywhere else the automatic plan applies and says so.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
is the `python tools/adopt.py` entry point over the transaction.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

import yaml  # noqa: E402
from tools.adopt_models import AdoptError  # noqa: E402
from tools.adopt_models import OwnershipError  # noqa: E402
from tools.adopt_models import StaleJournalError  # noqa: E402


def _parse_data(pairs: list[str] | None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for pair in pairs or []:
        if "=" not in pair:
            msg = f"--data expects key=value, got {pair!r}"
            raise AdoptError(msg)
        key, value = pair.split("=", 1)
        data[key.strip()] = yaml.safe_load(value)
    return data


def _load_answers(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.is_file():
        msg = f"answers file not found: {path}"
        raise AdoptError(msg)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is not None and not isinstance(loaded, dict):
        msg = f"{path}: expected a mapping of answers"
        raise AdoptError(msg)
    return dict(loaded or {})


def _prompter(args: argparse.Namespace) -> Callable[[str], str] | None:
    """The confirmation prompt, or None when nobody is there to answer it.

    `--yes` (and any non-interactive run) applies the automatic plan: a tool
    that blocks on stdin in CI or inside an MCP session is worse than one that
    does the safe thing and says so. `--ask` forces the prompt.
    """
    if args.yes or args.dry_run:
        return None
    if not args.ask and not sys.stdin.isatty():
        return None

    def confirm(question: str) -> str:
        print(question)
        while True:
            try:
                answer = input().strip().lower()
            except EOFError:
                print("(no input; taking that as cancel)")
                return "cancel"
            if answer in ("", "y", "yes"):
                return "yes"
            if answer in ("n", "no"):
                return "no"
            if answer in ("c", "cancel"):
                return "cancel"
            if answer in ("a", "all"):
                return "all"

    return confirm


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Adopt this template into an existing project, with rollback and crash recovery."
    )
    parser.add_argument("path", type=Path, help="project to adopt into (a directory)")
    parser.add_argument("--ref", default=None, help="template revision to expand (default: judged from the tags)")
    parser.add_argument(
        "--answers", type=Path, default=None, help="copier answers file (see tools/detect.py --answers)"
    )
    parser.add_argument("--data", action="append", default=None, help="extra answer, key=value (repeatable)")
    parser.add_argument(
        "--skip", action="append", default=None, help="path to never write over (default: the detected collisions)"
    )
    parser.add_argument("--takeover", action="store_true", help="replace a foreign template's answers file")
    parser.add_argument("--dry-run", action="store_true", help="plan only; write nothing")
    parser.add_argument("--yes", action="store_true", help="apply without the confirmation prompt")
    parser.add_argument("--ask", action="store_true", help="confirm even when stdin is not a terminal")
    parser.add_argument("--no-merge", action="store_true", help="do not merge anything into the files you already have")
    parser.add_argument("--recover", action="store_true", help="undo an interrupted adoption from its journal")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser.parse_args(argv)


def _recover_from_cli(args: argparse.Namespace) -> int:
    """`--recover`: undo an interrupted run and report what was put back.

    Exit codes: 0 whether or not there was a journal (running it twice is a
    no-op), 2 when the journal is there but cannot be used.
    """
    from tools.adopt_journal import recover  # noqa: E402  # deferred: facade-level cycle
    from tools.adopt_report import render_recovery  # noqa: E402  # deferred: facade-level cycle

    if args.dry_run:
        print(
            "--recover undoes the interrupted run, --dry-run promises not to write: pass one of them",
            file=sys.stderr,
        )
        return 2
    try:
        recovery = recover(args.path.resolve())
    except (AdoptError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(recovery.as_dict(), indent=2) if args.json else render_recovery(recovery))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point: plan, apply, and -- on any failed expectation -- roll back.

    `--recover` instead undoes a run that was killed, and succeeds whether or
    not there was anything left to undo.
    """
    from tools.adopt_report import render_report  # noqa: E402
    from tools.adopt_transaction import adopt  # deferred: breaks adopt_cli->transaction->confirm/journal cycle

    args = _parse_args(argv)
    if not args.path.is_dir():
        print(f"not a directory: {args.path}", file=sys.stderr)
        return 2
    if args.recover:
        return _recover_from_cli(args)
    try:
        adoption = adopt(
            args.path.resolve(),
            ref=args.ref,
            answers={**_load_answers(args.answers), **_parse_data(args.data)},
            skip=args.skip,
            takeover=args.takeover,
            dry_run=args.dry_run,
            merge_generated=not args.no_merge,
            ask=_prompter(args),
        )
    except StaleJournalError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except OwnershipError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (AdoptError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(adoption.as_dict(), indent=2))
    else:
        print(render_report(adoption))
    return 0 if adoption.ok or adoption.error is None else 1
