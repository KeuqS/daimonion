"""The composition contract: the manifest renders, and `verify` judges it.

The manifest (`.daimonion-manifest.yml`) is the public record of a
generation -- the template ref, the answers file it describes, and the
ethics sections the render distributed -- never answer values. These tests
render through tests/support.py's `render_answers` (the one render entry
point, TODO §28.6-D5) and pin the three claims `daimonion verify` checks:

- the manifest ships in a real render with its required keys;
- `verify` succeeds on it, and fails when the manifest no longer matches
  the answers file;
- `--against` reports what changed between two compositions.
"""

import sys
from pathlib import Path

import pytest
import yaml

from support import render_answers

TOP = Path(__file__).absolute().parent.parent
if str(TOP) not in sys.path:  # tests/test_batch.py does the same to reach tools/
    sys.path.insert(0, str(TOP))

from tools import cli  # noqa: E402
from tools import verify  # noqa: E402
from tools.answers import BASE  # noqa: E402

LIBRARY: dict[str, object] = {**BASE, "project_type": "library"}
CLI: dict[str, object] = {**BASE, "project_type": "cli"}
REQUIRED_KEYS = ("manifest_schema_version", "template_ref", "answers_file", "ethics_sections")


def _render(target: Path, answers: dict[str, object]) -> None:
    render_answers(target, answers, run_tasks=False)


def _manifest(target: Path) -> dict[str, object]:
    return yaml.safe_load((target / verify.MANIFEST_NAME).read_text(encoding="utf-8"))


def test_manifest_ships_with_the_required_keys(tmp_path: Path):
    """A real render carries the manifest, with every key the contract needs."""
    _render(tmp_path, LIBRARY)
    payload = _manifest(tmp_path)
    for key in REQUIRED_KEYS:
        assert key in payload, f"the manifest must carry {key!r}"
    assert payload["manifest_schema_version"] == 1
    assert payload["answers_file"] == ".copier-answers.yml"
    assert isinstance(payload["ethics_sections"], list) and payload["ethics_sections"], (
        "the library render distributes sections (license-drift at least)"
    )
    for entry in payload["ethics_sections"]:
        assert set(entry) == {"id", "version"}, f"a section entry is id + version, got {entry!r}"


def test_manifest_records_no_answer_values(tmp_path: Path):
    """The manifest is the public record: no answer value may land in it."""
    _render(tmp_path, LIBRARY)
    text = (tmp_path / verify.MANIFEST_NAME).read_text(encoding="utf-8")
    assert "kasi-x" not in text, "an identity answer leaked into the public record"
    assert "smoke_example" not in text, "a project answer leaked into the public record"


def test_manifest_ref_matches_the_answers_stamp(tmp_path: Path):
    """The manifest's ref is the answers file's `_commit`, not a second spelling."""
    _render(tmp_path, LIBRARY)
    answers = yaml.safe_load((tmp_path / ".copier-answers.yml").read_text(encoding="utf-8"))
    assert _manifest(tmp_path)["template_ref"] == answers["_commit"]


def _tamper(target: Path, old: str, new: str) -> None:
    """Rewrite one manifest line in a fresh render (the ref/schema failure probe)."""
    manifest = target / verify.MANIFEST_NAME
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def _rendered_pair(
    tmp_path: Path, before_answers: dict[str, object], after_answers: dict[str, object]
) -> tuple[str, str]:
    """Render two compositions, returning the (after, before) dirs for a `--against` run."""
    before = tmp_path / "before"
    after = tmp_path / "after"
    _render(before, before_answers)
    _render(after, after_answers)
    return str(after), str(before)


def test_verify_succeeds_on_a_fresh_render(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """`daimonion verify` accepts what the template just rendered."""
    _render(tmp_path, LIBRARY)
    assert cli.main(["verify", str(tmp_path)]) == cli.OK
    assert "verify: ok" in capsys.readouterr().out


def test_verify_fails_on_a_tampered_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Editing the manifest's ref breaks check (b): the answers disagree."""
    _render(tmp_path, LIBRARY)
    _tamper(tmp_path, "template_ref:", "template_ref: tampered-")
    assert cli.main(["verify", str(tmp_path)]) == cli.FAILED
    assert "mismatch" in capsys.readouterr().out


def test_verify_fails_on_an_unknown_schema(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """A manifest from a newer template is refused, not half-read."""
    _render(tmp_path, LIBRARY)
    _tamper(tmp_path, "manifest_schema_version: 1", "manifest_schema_version: 99")
    assert cli.main(["verify", str(tmp_path)]) == cli.FAILED
    assert "not supported" in capsys.readouterr().out


def test_verify_compares_two_compositions(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """`--against` names what changed: the answers and the distributed sections."""
    after, before = _rendered_pair(tmp_path, LIBRARY, CLI)
    assert cli.main(["verify", after, "--against", before]) == cli.OK
    out = capsys.readouterr().out
    assert "project_type" in out, "the changed answer must be named"
    assert "ethics section" in out, "the redistributed sections must be named"


def test_verify_reports_an_identical_composition(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Two renders of the same answers drift nothing: the report says so."""
    after, before = _rendered_pair(tmp_path, LIBRARY, LIBRARY)
    assert cli.main(["verify", after, "--against", before]) == cli.OK
    assert "no composition drift" in capsys.readouterr().out
