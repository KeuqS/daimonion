"""Behavioral guard for the generation commands documented in the repo's docs.

The docs show `uvx copier copy --trust <url> ...` with no `--vcs-ref`, which
makes copier expand the repository's **newest git tag**. Since the 6.0.0 fork
detach that tag is the fork's own release, so the documented command generates
from the fork questionnaire (`questions/*.yml`). Before the detach the newest
tag was an inherited pre-fork one (`5.4.0`, DiamondLightSource template
content): a default copy silently generated the old template (the real
"docs_type rejects zensical" and "asks component_owner" bug reports; see
BUG.md and the private kasi-x/daimonion-internal COPIER_UPSTREAM.md item 9) and demanded `author_name` outright,
which is why the docs used to pin `--vcs-ref=main`.

The render below deliberately passes no `vcs_ref`, so the test fails if the
newest tag ever stops carrying the fork questionnaire.
"""

from pathlib import Path

from copier import run_copy

TOP = Path(__file__).absolute().parent.parent

# The minimal answers file the README documents for `--defaults` runs, plus
# `docs_type`: copier validates a supplied value against the question's choices
# even while `use_recommended_docs` keeps `when` false, so `zensical` being
# accepted is the fork-only signal. `author_name`/`author_email` are
# deliberately absent — the fork gives them defaults, the inherited
# questionnaire raised `Question "author_name" is required`.
MINIMAL_ANSWERS = {
    "project_type": "library",
    "package_name": "default_copy_example",
    "description": "An example project",
    "git_platform": "github.com",
    "github_org": "kasi-x",
    "docs_type": "zensical",
}


def test_default_copy_sees_the_fork_questionnaire(tmp_path: Path):
    """A copy with no `vcs_ref` must resolve the fork's released tag.

    Reaching the assertion already proves the fork-only behaviours: the render
    raised neither "author_name is required" nor an invalid-choice error for
    `docs_type`, and the fork's docs question produced the Zensical layout.
    """
    run_copy(
        src_path=str(TOP),
        dst_path=tmp_path,
        data=MINIMAL_ANSWERS,
        defaults=True,
        unsafe=True,
        overwrite=True,
        skip_tasks=True,  # uv sync / REUSE-copy tasks are not what this guards
    )
    assert (tmp_path / "zensical.toml").exists(), "docs_type=zensical must generate the Zensical config"
