#!/usr/bin/env python3
"""One command to create a project from this template.

`daimonion new <dir>` asks `tools/detect.py` what the target is
and dispatches to the tool that does the right thing for it:

What it does is decided by the mode `tools/detect.py` reports:

- `fresh` (missing or empty directory): one copier render of this checkout,
  `--trust` included.
- `adopt` (an existing project): `tools/adopt.py`'s transaction -- collisions
  are skipped, the files you already have are verified byte-for-byte, and the
  run rolls back if any of them changed.
- `update` (this template already generated it): refuses; `copier update` is
  the right verb.
- `foreign` (another copier template owns it): refuses, exit 3.

`--ref` defaults to this fork's newest release tag; `tools/adopt.py:resolve_ref`
returns the default branch (with the reason) only when that tag carries a
different questionnaire, so the fork's older upstream tags cannot leak in.
`--preset NAME` reads `presets/NAME.yml` as the answers file and makes the run
non-interactive -- every question the preset does not answer keeps its copier
default, which is what keeps each preset a one-family file. Without a preset
the questionnaire is the interface: copier asks it, which needs a terminal.

The CLI never edits a file the target already has: an adoption runs with the
merge step off (use `tools/adopt.py --merge` when you want the template's
dependencies and runner recipes added to your own files).

The command works both from a clone of the template repo and installed
(`uvx --from git+https://github.com/ConstitutiveTemplates/daimonion.git
daimonion`, or a pip wheel): when TOP (this file's parent's
parent) carries no copier.yml, there is no checkout next to the package, and
`main` delegates to a cached clone of the template repo under
`~/.cache/daimonion` (or `$XDG_CACHE_HOME`), so every TOP-
relative path -- tools/, presets/, copier.yml -- resolves in a checkout
version-matched to the template ref it renders.

Usage::

    python -m tools.cli new my-project --preset library
    daimonion new /path/to/existing-project --dry-run
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import copier.errors
from copier._main import Worker

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import adopt  # noqa: E402
from tools import answers  # noqa: E402
from tools import batch  # noqa: E402
from tools import detect  # noqa: E402
from tools import explain  # noqa: E402
from tools import suggest  # noqa: E402
from tools import verify  # noqa: E402
from tools.git import run as run_git  # noqa: E402

PRESETS = answers.PRESETS

# Exit codes, the same contract as the tools this dispatches to: 0 ok,
# 1 failed, 2 invalid request, 3 refused (another template owns the target).
OK = 0
FAILED = 1
INVALID = 2
REFUSED = 3

# Collisions to name before the warning starts summarising them.
COLLISION_LIMIT = 12


class RequestError(Exception):
    """The request cannot be carried out as asked."""


def available_presets() -> list[str]:
    """The names `--preset` accepts: the answer files under `presets/`."""
    return answers.preset_names(PRESETS)


def preset_description(name: str) -> str:
    """The preset file's leading comment (the family's one-line description)."""
    return answers.preset_description(name, PRESETS)


def preset_answers(name: str) -> dict[str, Any]:
    """The answers mapping of `presets/<name>.yml`.

    Only the questions that define the family are in there; the rest of the
    questionnaire keeps the default copier would use for a non-interactive
    run.
    """
    try:
        return answers.read_preset(name, PRESETS)
    except answers.PresetError as error:
        raise RequestError(str(error)) from error


def collision_warning(collisions: list[str]) -> str:
    """The one-line warning for files both the target and the template have."""
    named = ", ".join(collisions[:COLLISION_LIMIT])
    if len(collisions) > COLLISION_LIMIT:
        named += f", ... (+{len(collisions) - COLLISION_LIMIT} more)"
    return f"warning: {len(collisions)} existing file(s) the template also ships will be left alone: {named}"


def _render(target: Path, data: dict[str, Any], ref: str, *, defaults: bool) -> Worker:
    """Render this checkout into `target`, through `tools/batch.py:render`.

    The convention pins `unsafe` (copier's `--trust`) and `quiet`; the one
    knob this CLI turns is `defaults`, which the convention otherwise pins to
    True. A `--preset` run is fully specified, so it keeps copier's defaults
    for every question the preset leaves out; without a preset the
    questionnaire is the interface, and copier asks it (which needs a
    terminal).
    """
    with batch.report_stream_only():
        return batch.render(str(TOP), target, data, ref, defaults=defaults)


def _warn_unknown_preset_keys(worker: Worker | None, answers: dict[str, Any]) -> None:
    """Warn when a preset key is not a question the rendered ref defines.

    Copier ignores answer keys with no matching question -- an older tag
    silently drops a newer preset key (measured: `--preset bare` against the
    6.1.0 tag ignores `cicd_extras`, so the project renders with every
    extra). `worker.template.questions_data` is the questionnaire the ref
    actually served; checking against it (not against the recorded answers
    file, which legitimately omits `when`-gated questions) keeps the warning
    to real drift.
    """
    if worker is None:
        return
    unknown = sorted(key for key in answers if key not in worker.template.questions_data)
    if unknown:
        print(
            "warning: preset answer(s) the rendered template does not ask "
            f"({', '.join(unknown)}) -- they were ignored; "
            "did the preset outrun the ref?",
            file=sys.stderr,
        )


def _fresh_dry_run(target: Path, data: dict[str, Any], resolved: str, reason: str) -> int:
    """Print dry-run output predicting what fresh mode would create."""
    print("dry run -- nothing written")
    print("mode:    fresh")
    print(f"ref:     {resolved}  ({reason})")
    print(f"target:  {target}")
    print("answers: " + ", ".join(f"{key}={value}" for key, value in sorted(data.items())))
    source = adopt.render_fresh_source(data, resolved)
    try:
        planned = sorted(str(path.relative_to(source)) for path in source.rglob("*") if path.is_file())
    finally:
        shutil.rmtree(source, ignore_errors=True)
    top = sorted({path.split("/")[0] for path in planned})
    print(f"would create {len(planned)} file(s); top level: {', '.join(top)}")
    return OK


def _fresh(  # noqa: PLR0913  WHYNOT: a thin shell over copier's flags; preset_answers exists so the rendered ref can be checked for unknown preset keys after the copy.
    target: Path,
    data: dict[str, Any],
    ref: str | None,
    *,
    dry_run: bool,
    defaults: bool,
    preset_answers: dict[str, Any] | None = None,
) -> int:
    """Render this checkout into an empty (or not yet created) directory."""
    resolved, reason = adopt.resolve_ref(ref)
    if dry_run:
        return _fresh_dry_run(target, data, resolved, reason)
    try:
        worker = _render(target, data, resolved, defaults=defaults)
    except copier.errors.InteractiveSessionError as exc:
        msg = f"{exc}; pass --preset <name> for a non-interactive run"
        print(msg, file=sys.stderr)
        return INVALID
    except Exception as exc:  # noqa: BLE001  WHYNOT: copier's failure is reported, not re-raised.
        print(f"render failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return FAILED
    created = sorted(path for path in target.rglob("*") if path.is_file())
    if preset_answers:
        _warn_unknown_preset_keys(worker, preset_answers)
    top = sorted({str(path.relative_to(target)).split("/")[0] for path in created})
    print("mode:    fresh")
    print(f"target:  {target}")
    print(f"ref:     {resolved}  ({reason})")
    print(f"created: {len(created)} file(s); top level: {', '.join(top)}")
    return OK


def _adopt(target: Path, answers: dict[str, Any], ref: str | None, *, dry_run: bool) -> int:
    """Adopt into an existing project through `tools/adopt.py`'s transaction."""
    try:
        adoption = adopt.adopt(target, ref=ref, answers=answers, dry_run=dry_run, merge_generated=False)
    except adopt.OwnershipError as exc:
        print(str(exc), file=sys.stderr)
        return REFUSED
    except (adopt.AdoptError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return INVALID
    print(adopt.render_report(adoption))
    return OK if adoption.ok or adoption.error is None else FAILED


def _inspect_target_or_error(target: Path) -> tuple[detect.Detection | None, int | None]:
    """Inspect target directory; returns (Detection, None) on success or (None, exit_code) on refusal."""
    try:
        detection = detect.detect(target)
    except (detect.DetectError, OSError) as exc:
        print(f"cannot inspect {target}: {exc}", file=sys.stderr)
        return None, INVALID
    if detection.mode == "foreign":
        print(detect.render_report(detection), file=sys.stderr)
        return None, REFUSED
    if detection.mode == "update":
        msg = (
            f"{target} was generated from this template: update it with `copier update`"
            " (or tools/adopt.py), not with a second copy"
        )
        print(msg, file=sys.stderr)
        return None, INVALID
    return detection, None


def new(  # noqa: PLR0911  WHYNOT: one early return per input guard (list-presets, unknown preset, unreadable target, foreign, update) plus the two mode dispatches; a dispatch table would hide the guard order the errors depend on.
    target: Path, *, preset: str | None, ref: str | None, dry_run: bool, list_presets: bool = False
) -> int:
    """Create (`fresh`) or adopt into (`adopt`) `target`, and report the mode."""
    if list_presets:
        for name in available_presets():
            print(f"{name}: {preset_description(name)}")
        return OK

    try:
        answers = preset_answers(preset) if preset else {}
    except RequestError as exc:
        print(str(exc), file=sys.stderr)
        return INVALID
    target = target.resolve()
    detection, error_code = _inspect_target_or_error(target)
    if error_code is not None or detection is None:
        return error_code if error_code is not None else INVALID
    if detection.collisions:
        print(collision_warning(detection.collisions), file=sys.stderr)
    if detection.mode == "adopt":
        return _adopt(target, answers, ref, dry_run=dry_run)
    # Fresh mode derives `existing_project: false` (and nothing else) from the
    # filesystem; the preset, when there is one, overrides what it names.
    return _fresh(
        target,
        {**detection.suggested_answers, **answers},
        ref,
        dry_run=dry_run,
        defaults=preset is not None,
        preset_answers=answers if preset else None,
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="daimonion",
        description="Create a project from this template: detect the mode, then render or adopt.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    new_command = subcommands.add_parser("new", help="create a project, or adopt into an existing one")
    new_command.add_argument("dir", type=Path, help="directory to create or adopt into")
    new_command.add_argument(
        "--preset",
        default=None,
        help=f"answers family under presets/ ({', '.join(available_presets())}); implies a non-interactive run",
    )
    new_command.add_argument(
        "--list-presets",
        action="store_true",
        help="list preset names with their one-line descriptions, then exit",
    )
    new_command.add_argument(
        "--ref", default=None, help="template revision to expand (default: this fork's newest release tag)"
    )
    new_command.add_argument("--dry-run", action="store_true", help="plan only; write nothing")
    _add_verify_command(subcommands)
    _add_explain_command(subcommands)
    _add_suggest_command(subcommands)
    return parser.parse_args(argv)


def _add_verify_command(subcommands: Any) -> None:
    """Register the `verify` subcommand: one directory, optionally diffed against another."""
    verify_command = subcommands.add_parser(
        "verify", help="verify a generated project's composition contract (template ref, answers, ethics sections)"
    )
    verify_command.add_argument("dir", type=Path, help="generated project to verify")
    verify_command.add_argument(
        "--against",
        type=Path,
        default=None,
        help="compare against another generated project (reports what changed)",
    )


def _add_explain_command(subcommands: Any) -> None:
    """Register the `explain` subcommand: the same shape as `tools/explain.py` parses."""
    explain_command = subcommands.add_parser(
        "explain", help="explain a preset or an answer choice (why this value, what changes otherwise)"
    )
    explain_command.add_argument("--preset", default=None, help="explain one preset (e.g. --preset web-api)")
    explain_command.add_argument("question", nargs="?", default=None, help="question to explain")
    explain_command.add_argument("value", nargs="?", default=None, help="value to explain")
    explain_command.add_argument(
        "--deviate",
        nargs=2,
        default=None,
        metavar=("QUESTION", "VALUE"),
        help="explain what changes if QUESTION takes VALUE",
    )


def _add_suggest_command(subcommands: Any) -> None:
    """Register the `suggest` subcommand: the same shape as `tools/suggest.py` parses."""
    suggest_command = subcommands.add_parser(
        "suggest", help="propose preset candidates for requirements, or validate an answers file"
    )
    suggest_command.add_argument("requirements", nargs="*", help="requirement words (e.g. 'internal API, postgres')")
    suggest_command.add_argument(
        "--validate",
        type=Path,
        default=None,
        metavar="ANSWERS_YML",
        help="validate an answers YAML file instead of suggesting (exit 2 when rejected)",
    )
    suggest_command.add_argument("--json", action="store_true", help="print the machine-readable payload")


# --- installed (non-checkout) operation: delegate to the cached clone --------
#
# An installed `daimonion` (uvx --from git+..., pip wheel) has no
# checkout next to it: TOP is the install's site-packages, so every TOP-
# relative path (tools/, presets/, copier.yml) resolves to nothing. The cached
# clone below is the checkout those tools expect, and re-running this CLI from
# it keeps every TOP-relative resolution version-matched to the template ref
# it renders.

DEFAULT_REMOTE = "https://github.com/ConstitutiveTemplates/daimonion.git"
REMOTE_URL_ENV = "DAIMONION_TEMPLATE_URL"  # override for mirrors / local test clones
DELEGATED_ENV = "DAIMONION_DELEGATED"  # recursion guard for the delegated run


def _remote_url() -> str:
    """The template repo to clone when this install is not a checkout."""
    return os.environ.get(REMOTE_URL_ENV, DEFAULT_REMOTE)


def _cache_dir() -> Path:
    """Where the cached checkout of the template repo lives."""
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    # renamed from ~/.cache/foundry on the daimonion rename; the old dir is
    # abandoned, the mirror re-clones.
    return base / "daimonion" / "repo"


def _clone_checkout(cache: Path) -> int:
    """Blobless-clone the remote and atomically publish it as `cache`.

    Two processes racing a cold cache both clone into their own unique temp
    dir; `os.rename` publishes the winner (atomic on POSIX), and the loser --
    whose rename fails against the now-existing directory -- removes its temp
    dir, so a half-cloned cache is never visible. A failed clone (offline)
    names the URL and leaves nothing behind.
    """
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"{cache.name}.", dir=cache.parent))
    try:
        clone = run_git(cache.parent, "clone", "--filter=blob:none", _remote_url(), str(tmp))
        if clone.returncode != 0:
            print(
                f"cannot clone the template repo {_remote_url()}: {clone.stderr.strip()}\n"
                "(the template is fetched on first use; is this machine offline?)",
                file=sys.stderr,
            )
            return FAILED
        try:
            Path(tmp).rename(cache)  # atomic: readers see the whole clone or none
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)  # lost the race: the winner's clone is used
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # a failed clone must not litter
    return OK


def _refresh_checkout(cache: Path) -> None:
    """Re-fetch the cached clone and fast-forward its default branch.

    `tools/adopt.py:resolve_ref` reads `git describe --tags`, so the clone
    must stay current with the release tags -- a stale local branch would not
    see the newest one. A failed fetch is not fatal: the stale clone still
    renders, so we warn and keep going (and a garbled fetch cannot corrupt,
    because checkout only ever moves the branch forward to origin's).
    """
    fetched = run_git(cache, "fetch", "--tags", "origin")
    if fetched.returncode != 0:
        print(
            f"warning: could not refresh the cached template ({fetched.stderr.strip()}); using the stale clone",
            file=sys.stderr,
        )
        return
    head = run_git(cache, "rev-parse", "--abbrev-ref", "origin/HEAD")
    if head.returncode != 0:
        return  # no origin/HEAD: an odd clone, keep whatever is checked out
    branch = head.stdout.strip().removeprefix("origin/")
    if not branch:
        return
    checked = run_git(cache, "checkout", branch)
    if checked.returncode != 0:
        run_git(cache, "checkout", "-B", branch, f"origin/{branch}")  # no local branch yet
    else:
        run_git(cache, "merge", "--ff-only", f"origin/{branch}")


def _delegate(argv: list[str]) -> int:
    """Run the same CLI from the cached checkout of the template repo.

    The cached clone is a real checkout, so every TOP-relative path resolves
    there; running *its* tools/cli.py also makes the tools themselves
    version-matched to the template ref they render. The child inherits stdio
    and carries the recursion guard: if even the clone has no copier.yml (a
    broken cache), it must fail loudly instead of delegating again.
    """
    cache = _cache_dir()
    if os.environ.get(DELEGATED_ENV):
        print(
            f"the delegated clone at {cache} is not a template checkout (no copier.yml); "
            "delete it and rerun so it can be re-cloned",
            file=sys.stderr,
        )
        return FAILED
    try:
        if cache.exists():
            _refresh_checkout(cache)
        else:
            status = _clone_checkout(cache)
            if status != OK:
                return status
    except OSError as exc:
        print(f"cannot prepare the cached template clone at {cache}: {exc}", file=sys.stderr)
        return FAILED
    script = cache / "tools" / "cli.py"
    if not script.is_file():
        print(f"{script} is missing; delete {cache} and rerun", file=sys.stderr)
        return FAILED
    return subprocess.call(  # noqa: S603  WHYNOT: a list argv never touches a shell; the child is this same CLI.
        [sys.executable, str(script), *argv], env={**os.environ, DELEGATED_ENV: "1"}
    )


def _explain_argv(args: argparse.Namespace) -> list[str]:
    """The `tools/explain.py` argv for the parsed `explain` subcommand."""
    explain_argv: list[str] = []
    if args.preset:
        explain_argv += ["--preset", args.preset]
    if args.deviate:
        explain_argv += ["--deviate", args.deviate[0], args.deviate[1]]
    if args.question:
        explain_argv.append(args.question)
    if args.value:
        explain_argv.append(args.value)
    return explain_argv


def _suggest_argv(args: argparse.Namespace) -> list[str]:
    """The `tools/suggest.py` argv for the parsed `suggest` subcommand."""
    suggest_argv: list[str] = []
    if args.validate is not None:
        suggest_argv += ["--validate", str(args.validate)]
    if args.json:
        suggest_argv.append("--json")
    suggest_argv += list(args.requirements)
    return suggest_argv


def _verify_argv(args: argparse.Namespace) -> list[str]:
    """The `tools/verify.py` argv for the parsed `verify` subcommand."""
    if args.against:
        return ["--against", str(args.against), str(args.dir)]
    return [str(args.dir)]


def _dispatch_verify(args: argparse.Namespace) -> int:
    """Run the `verify` subcommand through `tools/verify.py`."""
    return verify.main(_verify_argv(args))


def _dispatch_explain(args: argparse.Namespace) -> int:
    """Run the `explain` subcommand through `tools/explain.py`."""
    return explain.main(_explain_argv(args))


def _dispatch_suggest(args: argparse.Namespace) -> int:
    """Run the `suggest` subcommand through `tools/suggest.py`."""
    return suggest.main(_suggest_argv(args))


_DISPATCH: dict[str, Callable[[argparse.Namespace], int]] = {
    "verify": _dispatch_verify,
    "explain": _dispatch_explain,
    "suggest": _dispatch_suggest,
}
"""One thin shell per forwarded subcommand, each owning its argv translation."""


def main(argv: list[str] | None = None) -> int:
    """Entry point: dispatch on the mode `tools/detect.py` reports.

    From a clone of the template repo TOP carries copier.yml and everything
    runs in place. Installed (uvx --from git+..., pip wheel) there is no
    checkout next to the package: `_delegate` runs the same CLI from the
    cached clone of the template repo instead.
    """
    if not (TOP / "copier.yml").is_file():
        return _delegate(argv if argv is not None else sys.argv[1:])
    args = _parse_args(argv)
    forward = _DISPATCH.get(args.command)
    if forward is not None:
        return forward(args)
    return new(args.dir, preset=args.preset, ref=args.ref, dry_run=args.dry_run, list_presets=args.list_presets)


if __name__ == "__main__":
    raise SystemExit(main())
