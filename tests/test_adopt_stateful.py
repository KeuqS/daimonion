"""Model-based test of an adoption: the driver, checked against a reference model.

TODO.md §25.3 judges Hypothesis the cheapest way to an executable specification
of adoption, and §26.4 V4 puts it to work. The machine builds a random project
tree, runs a random sequence of real adoptions against it (tools/adopt.py,
copier through tools/batch.py, the real merges), and after *every* step asserts
the tree against a model that knows the contract rather than the code:

- adoption adds and never rewrites: a file the model owns comes back byte for
  byte, unless it is a merge kind, and a merge may only append;
- a merge kind whose entries are missing ends up carrying them, and one that
  already carries them keeps them;
- a failed, cancelled or dry run leaves the tree exactly as the model says;
- a run killed mid-flight leaves a journal, an unseen but bounded selection of
  new files, and no damage to the model's files -- and `--recover` puts the
  tree back byte for byte, directories included; the undo is a crash region
  like the run it undoes: a rollback killed while it undoes an uncovered
  collision, and a recovery killed before it drops the journal, are sampled
  too, and the next `--recover` still lands byte for byte;
- the journal exists while a run is unfinished and is gone once it commits or
  rolls back, and a run started over a stale journal is refused untouched.

The model is written from the outside. `TEMPLATE_FILES`/`PROTECTED_FILES` below
are what the fixture ships; every expectation is derived from those plus the
rules above, and `declared_values`/`gitignore_entries` read the adopter's files
with the standard library rather than through the driver's own helpers. When
the model and the driver disagree, the shrunk sequence is a finding about the
driver -- not a reason to adjust the model.

The template rendered here is a miniature one, built by the test, not
`template/`: the subject is the protocol in tools/adopt.py, and a miniature
template turns a 1.6s adoption into ~50ms, which is what makes 100 sequences
affordable in the edit loop (measured on 16 cores: ~13-19s of one worker's time
for the 100, i.e. a second or so of the tier's wall, which is work-bound). No
venv, no network, and the trees stay small.
"""

from __future__ import annotations

import re
import sys
import tempfile
import tomllib
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import invariant
from hypothesis.stateful import precondition
from hypothesis.stateful import rule
from hypothesis.stateful import run_state_machine_as_test

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import adopt  # noqa: E402
from tools import detect  # noqa: E402
from tools import file_merge  # noqa: E402

# --- the miniature template -------------------------------------------------

# What the fixture renders. The plain ones are copied verbatim; the protected
# ones are gated on the same `adopt_protect` token template/ uses, so an
# adopter who has the file keeps it and never sees the template's copy.
TEMPLATE_FILES: dict[str, str] = {
    "CHANGELOG.md": "# Changelog\n",
    ".github/workflows/ci.yml": (
        "name: CI\non: [push]\njobs:\n"
        "  checks:\n    uses: ./.github/workflows/_test.yml\n"
        "  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo publish\n"
    ),
    "Taskfile.yml": 'version: "3"\ntasks:\n  hello:\n    cmds:\n      - echo hi\n',
    "notes/one.txt": "one\n",
}
PROTECTED_FILES: dict[str, str] = {
    "README.md": "readme",
    "pyproject.toml": "pyproject",
    ".gitignore": "gitignore",
}
PROJECT_TOML = """\
[project]
name = "mini"
version = "0"
dependencies = ["httpx>=0.27"]

[tool.ruff]
line-length = 120
"""
GITIGNORE_CONTENT = "__pycache__/\n*.py[cod]\n.venv/\n"
PROTECTED_CONTENT = {
    "README.md": "# README\n",
    "pyproject.toml": PROJECT_TOML,
    ".gitignore": GITIGNORE_CONTENT,
}

GITIGNORE_ENTRIES = frozenset({"__pycache__/", "*.py[cod]", ".venv/"})
PYPROJECT_REQUIREMENT = "httpx"

# The paths the fixture can put into the target, and the two copier adds itself.
RENDER_PATHS = frozenset({*TEMPLATE_FILES, *PROTECTED_FILES})
ANSWERS = ".copier-answers.yml"
CI = ".github/workflows/ci.yml"
CI_CALLER = f".github/workflows/{file_merge.CI_CALLER_NAME}"
PYPROJECT = "pyproject.toml"
GITIGNORE = ".gitignore"
TASKFILE = "Taskfile.yml"

# The files the merge step edits when both sides have them (tools/adopt.py's
# MERGE_KINDS). The fixture ships these three, so an existing copy of one is the
# only file of the adopter's a run may touch at all -- `toml` is the pyproject
# merge (value-preserving), `prefix` the ones that may only grow. The Taskfile
# merge is report-only unless the caller approves it, so `prefix` is the widest
# the model has to allow for it (no rule here approves an append).
MERGE_KINDS = {PYPROJECT: "toml", GITIGNORE: "prefix", TASKFILE: "prefix"}

# The names the machine may give the adopter's own files. A README.rst without a
# README.md is the interesting one: `readme` is already protected by a file the
# render never writes.
POOL = (
    ".gitignore",
    ".github/workflows/ci.yml",
    ".python-version",
    "README.rst",
    "Taskfile.yml",
    "docs/index.md",
    "notes/scratch.txt",
    "src/legacy/__init__.py",
)
DIRS = ("docs/nested", "notes", "src")


def pyproject_text(*, dependencies: list[str], line_length: int | None) -> str:
    """A pyproject.toml of the shape an adopter has: PEP 621, well-formed TOML."""
    declared = ", ".join(f'"{entry}"' for entry in dependencies)
    tool = f"\n[tool.ruff]\nline-length = {line_length}\n" if line_length is not None else ""
    return f'[project]\nname = "legacy"\nversion = "0"\ndependencies = [{declared}]\n{tool}'


# pyproject.toml is the one file the merge *reads*, so the machine only writes a
# well-formed one into it. The merge's input contract is a pyproject it can
# parse; hand it something else and the whole run refuses and rolls back (the
# two ways that goes wrong are reported with this test rather than modelled
# here: tools/pyproject_merge.merge_problem calls an unparsable file "the merged
# file does not parse", and a `[project].dependencies` that is not a list raises
# AttributeError inside the merge).
PYPROJECT_TEXT = st.builds(
    pyproject_text,
    dependencies=st.lists(
        st.sampled_from(("httpx>=0.20", "httpx<1", "structlog>=24", "click>=8")), unique=True, max_size=3
    ),
    line_length=st.one_of(st.none(), st.sampled_from((88, 120))),
)

CRASH_POINTS = ("render:1", "verify", "merge:1")
# The undo paths are crash regions too -- the Quint model (adopt_crash.qnt)
# enables `crash` in every state, its three undo steps included: `rollback`
# dies inside a failing run's undo and `recover` inside `--recover`, before it
# drops the journal. Neither can fire in adopt_and_die -- a run that succeeds
# never rolls back, and the recovery is a separate call -- so each is pinned
# to the rule below that actually reaches it. The real SIGKILL drills for both
# live in tests/test_adopt.py.

# Every rule here runs a real render, and the fast tier's budget decides how
# many of 100 sequences can afford: the measured wall time is reported with the
# test, not asserted here (a loaded machine must not turn it red). Everything
# else -- the example database, `print_blob`, `derandomize` -- is the loaded
# Hypothesis profile's business (hypothesis's built-in `ci` profile is what CI
# and this checkout use), so this only pins what the loops need.
SETTINGS = settings(
    max_examples=100,
    stateful_step_count=3,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def protected_name(name: str, token: str) -> str:
    """The file name template/ uses to render `name` only when `token` is free."""
    return f"{{% if not existing_project or '{token}' not in adopt_protect %}}{name}{{% endif %}}.jinja"


def build_template(root: Path) -> Path:
    """Write the miniature template and return its `template/` directory."""
    directory = root / "template"
    for name, content in TEMPLATE_FILES.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for name, token in PROTECTED_FILES.items():
        (directory / protected_name(name, token)).write_text(PROTECTED_CONTENT[name])
    # copier writes the answers file from this one, the way template/ does.
    (directory / "{{ _copier_conf.answers_file }}.jinja").write_text("{{ _copier_answers | to_nice_yaml -}}\n")
    (root / "copier.yml").write_text(
        "---\n"
        "existing_project:\n"
        "    type: bool\n"
        "    default: false\n"
        "adopt_protect:\n"
        "    type: str\n"
        "    multiselect: true\n"
        "    default: [readme, license, pyproject, gitignore, python_version, scaffold]\n"
        "    choices: [readme, license, pyproject, gitignore, python_version, scaffold, docs]\n"
        "    when: '{{ existing_project }}'\n"
        "---\n"
        "_subdirectory: 'template'\n"
        "_skip_if_exists:\n"
        "    - CHANGELOG.md\n"
    )
    return directory


# --- the model's own reading of a tree and of the adopter's files -----------


def files_under(root: Path) -> dict[str, bytes]:
    """Every file in the tree by relative path, minus the driver's own journal."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != adopt.JOURNAL_NAME
    }


def dirs_under(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_dir()}


def parents_of(relative: str) -> set[str]:
    """Every directory a relative file path lives under."""
    parts = Path(relative).parts[:-1]
    return {str(Path(*parts[: index + 1])) for index in range(len(parts))}


def canonical(requirement: str) -> str:
    """The distribution name a PEP 508 requirement starts with (PEP 503 style)."""
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
    return re.sub(r"[-_.]+", "-", match.group(0) if match else requirement).lower()


def gitignore_entries(text: str) -> set[str]:
    """The patterns a `.gitignore` declares: non-empty, non-comment lines."""
    return {line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")}


def declared_values(text: str) -> dict[str, str] | None:
    """Every requirement and `[tool.*]` leaf value a pyproject declares, or None when it is not TOML.

    Leaf values are kept as their `repr`, so `true` is not the same declaration
    as `1` and a round trip through the merge has to be exact.
    """
    try:
        document = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError):
        return None
    found: dict[str, str] = {}
    project = document.get("project")
    if isinstance(project, dict):
        for entry in project.get("dependencies", []):
            if isinstance(entry, str):
                found[f"project.dependencies.{canonical(entry)}"] = entry
    tool = document.get("tool")
    if isinstance(tool, dict):
        collect_leaves(tool, "tool", found)
    return found


def collect_leaves(table: dict[str, Any], path: str, found: dict[str, str]) -> None:
    for key, value in table.items():
        key_path = f"{path}.{key}"
        if isinstance(value, dict):
            collect_leaves(value, key_path, found)
        else:
            found.setdefault(key_path, repr(value))


def pep621_requirements(text: str) -> set[str] | None:
    """The names a PEP 621 `[project]` table declares, or None when the merge would not see one."""
    try:
        document = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError):
        return None
    project = document.get("project")
    if not isinstance(project, dict):
        return None
    return {canonical(entry) for entry in project.get("dependencies", []) if isinstance(entry, str)}


def check_pyproject_only_added(before: bytes, after: bytes) -> None:
    """The pyproject merge may only add: everything declared before is still declared, unchanged."""
    declared = declared_values(before.decode())
    if declared is None:
        assert after == before, "a pyproject the merge cannot parse must be left alone"
        return
    now = declared_values(after.decode())
    assert now is not None, "the merge rewrote a pyproject into something that no longer parses"
    for key, value in declared.items():
        assert key in now, f"the merge dropped {key}"
        assert now[key] == value, f"the merge changed {key} from {value!r} to {now[key]!r}"


# --- the machine ------------------------------------------------------------


class AdoptionMachine(RuleBasedStateMachine):
    """A random project tree, a random sequence of runs, and the contract after each."""

    def __init__(self, trees: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        super().__init__()
        self.target = Path(tempfile.mkdtemp(prefix="tree-", dir=trees))
        self.monkeypatch = monkeypatch
        # The model's picture of the tree the adopter owns, plus what a run was
        # allowed to do to it: `merge_wrote` is the sticky set of merge kinds a
        # merge has already extended (the model no longer claims their exact
        # bytes), `merge_ran` says the run that just finished merged, which is
        # when the positive "the missing entries arrived" checks apply.
        self.files: dict[str, bytes] = {}
        self.dirs: set[str] = set()
        self.merge_wrote: set[str] = set()
        self.merge_ran = False
        self.pending_journal = False
        self.allowed_new: set[str] = set()
        # The paths the model knew before the last run: what is on disk but not
        # in here is what that run created.
        self.known_before: set[str] = set()

    # -- the invariant: after every rule, the tree is what the model says -----

    @invariant()
    def the_tree_is_what_the_model_says(self) -> None:
        observed = files_under(self.target)
        journal_present = (self.target / adopt.JOURNAL_NAME).is_file()
        assert journal_present == self.pending_journal, (
            f"the journal is {'there' if journal_present else 'gone'}, "
            f"but the model says a run {'is' if self.pending_journal else 'is not'} unfinished"
        )
        for path, content in self.files.items():
            assert path in observed, f"{path} was deleted by a run that only adds"
            after = observed[path]
            if path in self.merge_wrote:
                self._check_merged(path, content, after)
            else:
                assert after == content, f"{path} was rewritten by a run that must not touch it"
        fresh = set(observed) - self.known_before
        unknown = sorted(fresh - self.allowed_new)
        assert not unknown, f"the run created {unknown}, which the model does not know"
        if not self.pending_journal:
            missing = sorted(self.allowed_new - fresh)
            assert not missing, f"the run did not create {missing}"
            assert dirs_under(self.target) == self.dirs, "the tree's directories are not the model's"

    def _check_merged(self, path: str, before: bytes, after: bytes) -> None:
        """A merge may only add: the old bytes stay, and what was missing arrives."""
        if MERGE_KINDS[path] == "toml":
            check_pyproject_only_added(before, after)
            if self.merge_ran and pep621_requirements(before.decode()) is not None:
                now = pep621_requirements(after.decode()) or set()
                assert PYPROJECT_REQUIREMENT in now, "the merge did not add the template's dependency"
            return
        assert after.startswith(before), f"{path} lost the adopter's own content in a merge"
        if path == GITIGNORE and self.merge_ran:
            declared = gitignore_entries(after.decode())
            assert declared >= GITIGNORE_ENTRIES, "the merge did not add the template's ignore patterns"

    # -- the adopter's own edits ---------------------------------------------

    @precondition(lambda self: not self.files and not self.dirs and not self.pending_journal)
    @rule(with_pyproject=st.booleans(), content=PYPROJECT_TEXT)
    def start_a_project(self, with_pyproject: bool, content: str) -> None:
        """The project an adopter starts from: one that has a pyproject.toml, or an empty one.

        An adopter who already has one exercises the merge from the first run;
        one who has nothing at all is the fresh path. Both are real, and a
        machine that only ever started empty would reach the merge planning
        (and the confirmation prompt) far too rarely. The `pending_journal`
        guard is the sibling rules': this rule's bookkeeping calls
        `expect_settled`, and a tree a run died in the middle of is not
        settled -- the journal it left decides when the model may again claim
        the tree settled, and only a recovery (or a refusal) does.
        """
        if with_pyproject:
            self.write_file(PYPROJECT, content)

    @precondition(lambda self: not self.pending_journal)
    @rule(name=st.sampled_from(POOL), content=st.text(max_size=80))
    def put_file(self, name: str, content: str) -> None:
        """The machine's own file: adoption must leave these bytes alone.

        The content is arbitrary text on purpose -- the only files a run reads
        are `.gitignore` (line-oriented) and `Taskfile.yml` (report-only without
        approval), and both survive anything.
        """
        self.write_file(name, content)

    @precondition(lambda self: not self.pending_journal)
    @rule(content=PYPROJECT_TEXT)
    def put_pyproject(self, content: str) -> None:
        """The machine's own pyproject.toml, which the merge *reads* (see PYPROJECT_TEXT)."""
        self.write_file(PYPROJECT, content)

    def write_file(self, name: str, content: str) -> None:
        path = self.target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.files[name] = content.encode()
        self.dirs |= parents_of(name)
        self.expect_settled(new=set())

    @precondition(lambda self: not self.pending_journal)
    @rule(name=st.sampled_from(DIRS))
    def make_dir(self, name: str) -> None:
        """An empty directory of the adopter's own: a rollback must not remove it."""
        (self.target / name).mkdir(parents=True, exist_ok=True)
        self.dirs |= parents_of(f"{name}/x") | {name}
        self.expect_settled(new=set())

    # -- the runs ------------------------------------------------------------

    @precondition(lambda self: self.can_adopt())
    @rule()
    def adopt_and_merge(self) -> None:
        """The everyday run: render, then merge what the adopter already has."""
        result = adopt.adopt(self.target, ref="HEAD")
        assert result.ok and result.applied, f"a clean adoption failed: {result.error}"
        self.expect_settled(new=self.expected_new(merge=True), merged=True)

    @precondition(lambda self: self.can_adopt())
    @rule()
    def adopt_without_merging(self) -> None:
        """`--no-merge`: the render happens, nothing the adopter owns is edited."""
        result = adopt.adopt(self.target, ref="HEAD", merge_generated=False)
        assert result.ok and result.applied, f"a render-only adoption failed: {result.error}"
        self.expect_settled(new=self.expected_new(merge=False))

    @precondition(lambda self: self.can_adopt())
    @rule()
    def adopt_as_a_dry_run(self) -> None:
        """`--dry-run` writes nothing, however much it would have added."""
        result = adopt.adopt(self.target, ref="HEAD", dry_run=True)
        assert result.ok and not result.applied, "a dry run applied something"
        self.expect_settled(new=set())

    @precondition(lambda self: self.can_adopt())
    @rule(answer=st.sampled_from(("cancel", "no")))
    def adopt_and_answer_the_plan(self, answer: str) -> None:
        """The confirmation prompt: cancel rolls the render back, no keeps it.

        The precondition is the driver's own: there is a plan to confirm only
        when the adopter already has a file the merge step would edit. When
        there is none the driver does not ask at all, and the run is an everyday
        one -- which the model reads off the callback, not off a guess.
        """
        asked: list[str] = []

        def ask(question: str) -> str:
            asked.append(question)
            return answer

        result = adopt.adopt(self.target, ref="HEAD", ask=ask)
        if not asked:
            assert result.ok and result.applied, f"an unconfirmed adoption failed: {result.error}"
            self.expect_settled(new=self.expected_new(merge=True), merged=True)
        elif answer == "cancel":
            assert result.cancelled and not result.applied, "cancel must roll the run back"
            self.expect_settled(new=set())
        else:
            assert result.ok and result.applied, f"answering 'no' must keep the render: {result.error}"
            self.expect_settled(new=self.expected_new(merge=False))

    @precondition(lambda self: self.can_adopt())
    @rule(point=st.sampled_from(CRASH_POINTS))
    def adopt_and_die(self, point: str) -> None:
        """Kill the run at `point` the way SIGKILL does: nothing gets rolled back.

        The run got past the crash point without being killed when nothing was
        left to write there, which is an ordinary run.
        """
        with self.monkeypatch.context() as patch:
            patch.setattr(adopt, "_crash_at", self._die_at(point))
            patch.setenv(adopt.CRASH_POINT_ENV, point)
            try:
                result = adopt.adopt(self.target, ref="HEAD")
            except KeyboardInterrupt:
                self.expect_interrupted(merged=point.startswith("merge"))
            else:
                assert result.ok and result.applied, f"a run past {point} failed: {result.error}"
                self.expect_settled(new=self.expected_new(merge=True), merged=True)

    def _die_at(self, point: str) -> Callable[[str], None]:
        """A `_crash_at` that dies at `point` the way SIGKILL would: no cleanup.

        `KeyboardInterrupt` stands in for the signal -- like SIGKILL it is not
        an `except Exception`, so the driver's rollback never runs and the
        journal is what is left behind. The real SIGKILL drills are in
        tests/test_adopt.py; this one stays in-process because 100 sequences
        cannot afford a process.
        """
        real_crash_at = adopt._crash_at  # noqa: SLF001

        def crash_at(hit: str) -> None:
            if hit == point:
                raise KeyboardInterrupt(hit)
            real_crash_at(hit)

        return crash_at

    @precondition(lambda self: self.can_adopt())
    @rule()
    def adopt_a_collision_and_die_rolling_it_back(self) -> None:
        """Kill the rollback while it is undoing an uncovered collision.

        `skip=[]` is the run that fails: copier stops on the first file it may
        not write, the run refuses, and the rollback starts -- the crash point
        fires at its first real write, so the tree keeps some of what the run
        created and the journal stays. A draw where nothing collides is an
        ordinary successful run past a point that never fired, and one where
        the render stopped before its first write is a rollback with nothing
        in it to kill.
        """
        with self.monkeypatch.context() as patch:
            patch.setattr(adopt, "_crash_at", self._die_at("rollback"))
            try:
                result = adopt.adopt(self.target, ref="HEAD", skip=[])
            except KeyboardInterrupt:
                self.expect_interrupted(merged=False)
            else:
                if result.ok:
                    assert result.applied, "a clean adoption must be applied"
                    self.expect_settled(new=self.expected_new(merge=True), merged=True)
                else:
                    assert not result.applied, "a failed run must not stay applied"
                    self.expect_settled(new=set())

    @precondition(lambda self: self.pending_journal)
    @rule()
    def recover_and_die(self) -> None:
        """Kill `--recover` itself, before it can drop the journal.

        The journal is dropped last precisely for this kill: whatever the
        half-finished recovery left -- some old bytes back, some of the run's
        files deleted -- is still journal country, and the model only loosens
        to "any prefix of the render" until the next recovery lands. A draw
        whose recovery had nothing on disk to change finishes without reaching
        the crash point, which is the no-op recovery -- also success.
        """
        with self.monkeypatch.context() as patch:
            patch.setattr(adopt, "_crash_at", self._die_at("recover"))
            try:
                adopt.recover(self.target)
            except KeyboardInterrupt:
                self.expect_interrupted(merged=True)
            else:
                self.expect_settled(new=set())

    # -- recovery and refusal ------------------------------------------------

    @rule()
    def recover(self) -> None:
        """Whatever a killed run left, recovery puts the tree back -- twice is a no-op."""
        recovery = adopt.recover(self.target)
        assert recovery.found == self.pending_journal, "recovery disagrees with the model about the journal"
        self.expect_settled(new=set())

    @precondition(lambda self: self.pending_journal)
    @rule()
    def adopt_over_a_stale_journal(self) -> None:
        """A tree nobody chose is not a tree to plan from: refuse, write nothing."""
        with pytest.raises(adopt.StaleJournalError):
            adopt.adopt(self.target, ref="HEAD")
        self.expect_interrupted(merged=False)

    @precondition(lambda self: self.adopted and not self.pending_journal)
    @rule()
    def adopt_an_adopted_project(self) -> None:
        """A project the template already owns is not adopted a second time."""
        with pytest.raises(adopt.AdoptError):
            adopt.adopt(self.target, ref="HEAD")
        self.expect_settled(new=set())

    # -- the model ------------------------------------------------------------

    def can_adopt(self) -> bool:
        return not self.pending_journal and not self.adopted

    @property
    def adopted(self) -> bool:
        return ANSWERS in self.files

    def protection(self, token: str) -> bool:
        """Whether the adopter's tree already answers `token` (detection's own question)."""
        if token == "readme":
            return any("/" not in name and name.startswith("README") for name in self.files)
        if token == "pyproject":
            return PYPROJECT in self.files
        if token == "gitignore":
            return GITIGNORE in self.files
        message = f"the fixture protects {token!r}, which the model does not know"
        raise AssertionError(message)

    def expected_new(self, *, merge: bool) -> set[str]:
        """The paths a committed run must have created, and no others."""
        rendered = {
            path for path in RENDER_PATHS if not (PROTECTED_FILES.get(path) and self.protection(PROTECTED_FILES[path]))
        }
        new = (rendered | {ANSWERS}) - set(self.files)
        # The CI caller goes beside the adopter's workflow -- including the one
        # this very render just added.
        if merge and (CI in self.files or CI in rendered) and CI_CALLER not in self.files:
            new.add(CI_CALLER)
        return new

    def expect_settled(self, *, new: set[str], merged: bool = False) -> None:
        """Record what a finished run was allowed to do; the invariant checks it."""
        self.pending_journal = False
        self.merge_ran = merged
        self.allowed_new = set(new)
        if merged:
            self.merge_wrote |= {path for path in MERGE_KINDS if path in self.files} | (new & set(MERGE_KINDS))
        self.absorb(new)
        # What the model knew *before* the run: everything it knows now, less
        # what the run created.
        self.known_before = set(self.files) - set(new)

    def expect_interrupted(self, *, merged: bool) -> None:
        """A killed run may leave any prefix of the render, and nothing else new.

        A merge that was interrupted may have written any of its files and
        stopped anywhere, so the model stops claiming their exact bytes but
        asserts nothing about what did or did not arrive.
        """
        self.pending_journal = True
        self.merge_ran = False
        self.allowed_new = set(RENDER_PATHS) | {ANSWERS, CI_CALLER}
        self.known_before = set(self.files)
        if merged:
            self.merge_wrote |= set(MERGE_KINDS) & set(self.files)

    def absorb(self, paths: Iterable[str]) -> None:
        """A file this run created is not the adopter's: the model takes it as it landed.

        A path that is not there is left out rather than raised on, so the
        invariant reports it as "the run did not create ..." instead of an
        `OSError` from the model's own bookkeeping.
        """
        for path in paths:
            created = self.target / path
            if created.is_file():
                self.files[path] = created.read_bytes()
                self.dirs |= parents_of(path)


def test_adoption_matches_the_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """100 sequences of random trees and random runs, each checked after every step."""
    mini = tmp_path / "mini"
    template = build_template(mini)
    trees = tmp_path / "trees"
    trees.mkdir()
    monkeypatch.setattr(adopt, "TOP", mini)
    monkeypatch.setattr(detect, "TEMPLATE_DIR", template)

    def machine() -> AdoptionMachine:
        return AdoptionMachine(trees, monkeypatch)

    run_state_machine_as_test(machine, settings=SETTINGS)
