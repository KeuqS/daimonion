"""The update rehearsal's verdicts, on crafted fixtures (the real run is nightly).

tools/update_rehearsal.py replays a user's lifecycle per witness leaf --
render at the released tag, commit, `copier update` to HEAD -- and checks
tests/test_update_path.py's contract: no conflict residue, a whitespace-clean
diff, and a recorded `_commit` that advanced. These tests pin the check
logic on crafted fixtures; the whole-pipeline rehearsal runs nightly in
.github/workflows/update-rehearsal.yml and on demand via `task
update-rehearsal`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import copier
import pytest

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import update_rehearsal as ur  # noqa: E402
from tools.check_questionnaire_diff import release_tag  # noqa: E402


def test_conflict_residue_names_markers_and_rej_files(tmp_path: Path):
    """The (a) check: copier's unresolved hunks are found wherever they hide."""
    files = [
        ("README.md", "fine\n"),
        ("conflicted.py", "keep\n<<<<<<< HEAD\nmine\n=======\nyours\n>>>>>>> branch\n"),
        ("notes.txt.rej", "a rejected hunk\n"),
    ]
    for rel, content in files:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    residue = sorted(ur._conflict_residue(tmp_path))  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: the scan under test is the checker's own helper.
    assert residue == ["conflicted.py", "notes.txt.rej"], (
        "both the inline markers and the .rej file are unresolved merge state"
    )


def test_a_clean_project_has_no_residue(tmp_path: Path):
    """The (a) check must not condemn a clean tree."""
    path = tmp_path / "src" / "x.py"
    path.parent.mkdir(parents=True)
    path.write_text("pass\n", encoding="utf-8")
    assert ur._conflict_residue(tmp_path) == []  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


def test_the_rehearsal_of_head_replays_cleanly(tmp_path: Path):
    """A real one-leaf rehearsal: render at the release, update to HEAD, all checks pass.

    This is tests/test_update_path.py's own flow, driven through the tool's
    rehearse_leaf, on one witness leaf's answers.
    """
    base_ref = release_tag(TOP)
    assert base_ref is not None, "the rehearsal needs a release tag to start from"
    base_rev = ur._git_out(TOP, "rev-parse", f"{base_ref}^{{commit}}").strip()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    target_rev = ur._git_out(TOP, "rev-parse", "HEAD").strip()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    leaves = ur._read_leaves()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    leaf_id, answers = min(leaves.items())

    renders = ur.ReleasedRenders(base_ref, base_rev, copier.__version__)
    verdict = ur.rehearse_leaf(
        leaf_id,
        answers,
        base_rev=base_rev,
        target_rev=target_rev,
        target_dirty=bool(ur._git_out(TOP, "status", "--porcelain").strip()),  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        renders=renders,
        fresh_render_available=False,
        work=tmp_path,
    )
    assert verdict.ok, f"rehearsing {leaf_id} from {base_ref} must pass: {verdict.failed}"


@pytest.mark.slow
def test_the_full_rehearsal_passes_on_every_leaf():
    """The nightly run, whole: every witness leaf updates cleanly."""
    code, payload = ur.run(base_ref=release_tag(TOP) or "HEAD", target_ref="HEAD", only=None, jobs=8, audit_fresh=False)
    assert code == 0 and not payload["failures"], (
        f"the rehearsal failed for {sorted(payload['failures'])} -- the update path broke for those configurations"
    )
    # No --only: the rehearsal must cover every declared leaf, and the floor is
    # the committed ledger's own count rather than a literal -- a leaf space
    # that shrank (or a ledger that stopped matching it) fails here, while a
    # deliberate regeneration moves both numbers together. Leaves whose
    # answers are invalid at the released ref (a choice added after the tag)
    # are skipped, not rehearsed -- they count toward coverage because no user
    # could hold a project rendered from them at the base.
    ledger = json.loads((TOP / "tests" / "matrix" / "witnesses.json").read_text(encoding="utf-8"))
    covered = payload["rehearsed"] + len(payload["skipped"])
    assert covered >= ledger["coverage"]["total"] >= 225, (
        f"the rehearsal covered {covered} leaves ({payload['rehearsed']} rehearsed, "
        f"{len(payload['skipped'])} skipped as unrenderable at the base); the ledger records "
        f"{ledger['coverage']['total']}, and the floor this guard landed with is 225"
    )


def _job() -> ur._Job:  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: the job is plain data; the retry contract under test is the pool entry's, not the dataclass's.
    """The smallest rehearsal unit the pool can carry."""
    return ur._Job("lib", {}, "7.0.0", "base", "target", False, False)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


def test_the_rehearse_job_retries_a_transient_workspace_crash(monkeypatch: pytest.MonkeyPatch):
    """An OSError that clears on a fresh workspace does not reach the verdict."""
    attempts: list[int] = []

    def flaky(*_args: object, **_kwargs: object) -> ur.LeafVerdict:
        attempts.append(len(attempts))
        if len(attempts) < 3:
            raise OSError(39, "Directory not empty")
        return ur.LeafVerdict("lib", ok=True, failed=[], convergence=[])

    monkeypatch.setattr(ur, "rehearse_leaf", flaky)

    verdict = ur._rehearse_job(_job())  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: retry behavior is the pool entry's contract.
    assert verdict.ok and not verdict.runner_error and len(attempts) == 3


def test_the_rehearse_job_reports_a_crash_as_a_runner_error(monkeypatch: pytest.MonkeyPatch):
    """A crash that outlives every attempt is a verdict, never a pool crash.

    2026-10-11's scheduled run lost the whole report to an unhandled
    Errno 39 in TemporaryDirectory cleanup: pool.map raised, no JSON was
    written, and CI could only say "failed". The verdict must reach the
    report as runner_error -- red, but named.
    """

    def always_crash(*_args: object, **_kwargs: object) -> ur.LeafVerdict:
        raise OSError(39, "Directory not empty")

    monkeypatch.setattr(ur, "rehearse_leaf", always_crash)

    verdict = ur._rehearse_job(_job())  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: retry behavior is the pool entry's contract.
    assert not verdict.ok and verdict.runner_error
    assert "runner error" in verdict.failed[0]
