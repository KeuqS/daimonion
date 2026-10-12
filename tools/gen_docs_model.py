"""The questionnaire model behind the generated docs: paths, vocabulary, groupings.

`tools/gen_docs.py` renders the questionnaire-derived documentation; this
module is the reading half: where the generated blocks live, the curated
vocabulary (gate prefixes, boolean prose, runner links), and the `Model`
groupings (gates, layers, details, follow-ups) every renderer builds from.

This is a machinery-layer module by the tests/test_tool_layers.py table: the
questionnaire as data in, groupings out -- no template tree, no subprocess.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import questionnaire  # noqa: E402
from tools import support_ledger  # noqa: E402
from tools import when_model  # noqa: E402
from tools.questionnaire import Question  # noqa: E402

QUESTIONNAIRE_DOC = TOP / "docs" / "reference" / "questionnaire.md"
FEATURES_DOC = TOP / "docs" / "reference" / "features.md"
SUPPORT_DOC = support_ledger.SUPPORT_DOC
SUPPORT_YML = support_ledger.SUPPORT_YML

TIERS_JSON = TOP / "tests" / "matrix" / "tiers.json"
"""The cost ledger (tests/test_marker_drift.py owns enforcing it)."""

VERIFICATION_DOC = TOP / "docs" / "explanations" / "verification.md"
"""The page whose tier table carries the ledger's numbers."""

GATE_PREFIX = "use_recommended_"
INCLUDE_PREFIX = "include_"

# Boolean identifiers a condition may name, with the explanation the prose
# table gives them. Keyed by the identifier itself (the meaning), never by the
# whole `when` string (the spelling): a semantically identical rewrite of a
# condition renders the same sentence, and every other identifier renders
# mechanically -- see `tools.gen_docs_prose._condition_prose`. A genuinely new
# shape is a loud generator failure, not a stale sentence in the docs.
BOOL_PROSE: dict[str, str] = {
    "include_scraping": "a `cli` base answers Yes to `include_scraping`",
    "include_bot": "a `cli` / `web_api` base answers Yes to `include_bot`",
    "include_web_api": "library + the web_api layer",
    "kaggle": "kaggle",
}
ALL_TYPES = "all"

# Lines that start a paragraph of a question's help after the prompt itself
# (`Recommended: ...`, `Answer No to ...`): the prompt stops before them.
PROMPT_STOPS = ("Recommended: ", "Answer No to ", "Answer Yes ", "Deselect ", "If yes", "If true")

# Link targets for the task runners the questionnaire offers. The runner
# *names* come from the model (`labels`); only the URLs are curated here.
RUNNER_URLS: dict[str, str] = {
    "just": "https://just.systems",
    "task": "https://taskfile.dev",
    "poe": "https://github.com/nat-n/poethepoet",
    "make": "https://www.gnu.org/software/make/",
    "invoke": "https://www.pyinvoke.org",
    "duty": "https://pawamoy.github.io/duty",
    "pixi": "https://pixi.sh",
}


class GenDocsError(Exception):
    """The docs cannot be generated from the questionnaire."""


def _mentions(question: Question, names: list[str]) -> bool:
    """True when the raw `when` expression references any of `names`.

    The identifiers come from when_model's Jinja scanner -- the one scanner --
    so a prefix-collision (`use_recommended_docs` inside
    `use_recommended_docs_type`) cannot fake a reference the way a raw
    substring match would.
    """
    return bool(when_model.jinja_identifiers(str(question.when)) & set(names))


def _mentions_project_type(question: Question, choice: str) -> bool:
    """True when a question is asked for one `project_type` choice.

    Either the `when` compares `project_type` to the literal (the quoted form
    is exact, so `cli` cannot match `'client'`), or it tests a derived boolean
    named after the choice (`online_judge`, ...), identified through the same
    scanner as `_mentions`.
    """
    when = str(question.when)
    identifiers = when_model.jinja_identifiers(when)
    if "project_type" in identifiers and f"'{choice}'" in when:
        return True
    return choice in identifiers


@dataclass(frozen=True)
class Model:
    """The questionnaire, plus the groupings the generated docs are built from."""

    questions: tuple[Question, ...]

    @classmethod
    def load(cls, config: Path | None = None) -> Model:
        """Load the questionnaire from `copier.yml` (or another config)."""
        questions, _settings = questionnaire.load_questions(config)
        return cls(tuple(questions))

    @property
    def external(self) -> list[Question]:
        """The questions a user is actually asked (not `when: false` internals)."""
        return [q for q in self.questions if not q.internal]

    @property
    def gates(self) -> list[Question]:
        """The `use_recommended_*` area gates, in ask order."""
        return [q for q in self.external if q.name.startswith(GATE_PREFIX)]

    @property
    def includes(self) -> list[Question]:
        """The `include_*` opt-in layers, in ask order.

        Integration switches (`include_sentry`, `include_mcp`) share the
        prefix but are gate details, not layers.
        """
        return [
            q
            for q in self.external
            if q.name.startswith(INCLUDE_PREFIX) and not _mentions(q, [g.name for g in self.gates])
        ]

    @property
    def area_gates(self) -> list[Question]:
        """The top-level areas: gates no `include_*` opt-in owns."""
        includes = [q.name for q in self.includes]
        return [q for q in self.gates if not _mentions(q, includes)]

    @property
    def option_gates(self) -> list[Question]:
        """Gates an opt-in layer owns (`include_scraping` -> `use_recommended_scraping`)."""
        area = {q.name for q in self.area_gates}
        return [q for q in self.gates if q.name not in area]

    @property
    def project_details(self) -> list[Question]:
        """The trailing questions asked after the last gate (package, author, ...)."""
        gated = [q.name for q in self.gates] + [q.name for g in self.gates for q in self.details(g)]
        gated += [q.name for q in self.includes]
        last = max(index for index, q in enumerate(self.external) if q.name in gated)
        return self.external[last + 1 :]

    def question(self, name: str) -> Question:
        """The question with this name."""
        for candidate in self.questions:
            if candidate.name == name:
                return candidate
        msg = f"no question named {name!r} in the questionnaire"
        raise GenDocsError(msg)

    def details(self, gate: Question) -> list[Question]:
        """The detailed questions a gate reveals when answered No."""
        return [
            q
            for q in self.external
            if q.name != gate.name and not q.name.startswith(GATE_PREFIX) and _mentions(q, [gate.name])
        ]

    def is_detail(self, question: Question) -> bool:
        """True for a question revealed by answering No to a gate."""
        return any(_mentions(question, [gate.name]) for gate in self.gates)

    def follow_ups(self, choice: str) -> list[Question]:
        """The genre questions asked for one `project_type` choice.

        Gates, opt-in layers and the details they reveal are excluded: those
        are documented by the areas table, not as project-type follow-ups.
        """
        owned = {q.name for q in self.gates} | {q.name for q in self.includes}
        return [
            q
            for q in self.external
            if q.name not in owned
            and q.when is not None
            and not self.is_detail(q)
            and _mentions_project_type(q, choice)
        ]
