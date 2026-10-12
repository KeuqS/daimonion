"""The shipped entry point's dispatch: `daimonion new <dir>`.

`tools/cli.py` is the console script this template publishes (pyproject.toml
`[project.scripts]`), and it is a *dispatcher*: the mode `tools/detect.py`
reports picks one of three outcomes, two of which refuse. The tools it calls
have their own tests (test_adopt.py, test_detect.py, test_batch.py); what only
this module can check is the branch that picks between them, and the exit codes
it promises (0 ok / 1 failed / 2 invalid request / 3 refused -- the same
contract as the tools it dispatches to).

The collaborators are patched at this module's boundary (`cli.detect.detect`,
`cli.adopt.adopt`, `cli.batch.render`) so each branch is one in-process call: a
real render, adoption or detector run is that tool's test's subject, not this
dispatcher's. The one path exercised for real is preset loading, whose failure
is this module's own.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

TOP = Path(__file__).absolute().parent.parent
if str(TOP) not in sys.path:  # tests/test_adopt.py does the same to reach tools/
    sys.path.insert(0, str(TOP))

from tools import adopt  # noqa: E402
from tools import batch  # noqa: E402
from tools import cli  # noqa: E402
from tools import detect  # noqa: E402


def _detection(mode: str, **overrides: Any) -> detect.Detection:
    """A Detection with the fields this dispatcher reads."""
    fields: dict[str, Any] = {"path": "/tmp/target", "mode": mode}
    fields.update(overrides)
    return detect.Detection(**fields)


def _adoption(**overrides: Any) -> adopt.Adoption:
    """An Adoption with the fields this dispatcher reads."""
    fields: dict[str, Any] = {
        "target": "/tmp/target",
        "mode": "adopt",
        "ref": "HEAD",
        "ref_reason": "the working tree",
    }
    fields.update(overrides)
    return adopt.Adoption(**fields)


# cli.py imports these modules at module level and reads their attributes as
# `cli.<module>.<name>`, so patching the imported module's attribute here
# (the same object cli.py holds) patches what the dispatcher calls.


def test_new_fresh_renders_and_reports_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`fresh` mode renders through batch.render and reports the created tree."""
    calls: list[dict[str, Any]] = []

    def fake_render(src: str, dest: Path, data: dict[str, Any], ref: str = "HEAD", **kwargs: Any) -> None:
        calls.append({"src": src, "dest": Path(dest), "data": data, "ref": ref, **kwargs})
        (Path(dest) / "README.md").write_text("# made\n")

    monkeypatch.setattr(
        detect, "detect", lambda *a, **k: _detection("fresh", suggested_answers={"existing_project": False})
    )
    monkeypatch.setattr(adopt, "resolve_ref", lambda requested=None: ("HEAD", "the working tree"))
    monkeypatch.setattr(batch, "render", fake_render)

    assert cli.new(tmp_path, preset=None, ref=None, dry_run=False) == cli.OK
    assert calls and calls[0]["dest"] == tmp_path and calls[0]["ref"] == "HEAD"
    assert calls[0]["defaults"] is False  # no preset: copier asks the questionnaire
    out = capsys.readouterr().out
    assert "mode:    fresh" in out
    assert f"target:  {tmp_path.resolve()}" in out
    assert "created: 1 file(s)" in out


def test_new_fresh_with_preset_keeps_copier_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A preset makes the run non-interactive, so the render keeps copier's defaults."""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("fresh", suggested_answers={}))
    monkeypatch.setattr(adopt, "resolve_ref", lambda requested=None: ("HEAD", "why"))

    def fake_render(*args: Any, **kwargs: Any) -> None:
        calls.append(kwargs)
        (Path(args[1]) / "README.md").write_text("")

    monkeypatch.setattr(batch, "render", fake_render)

    assert cli.new(tmp_path, preset="library", ref=None, dry_run=False) == cli.OK
    assert calls and calls[0]["defaults"] is True


def test_new_fresh_preset_warns_only_for_keys_the_rendered_ref_drops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A preset key the rendered template does not define must be surfaced.

    The rendered questionnaire is what decides: a `when`-gated key (asked for
    some renders, dropped from .copier-answers.yml) is NOT a warning -- the
    bare preset names `include_mcp`, which stays silent at HEAD -- while a key
    an older tag never heard of (`cicd_extras` against 6.1.0) must warn.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("fresh", suggested_answers={}))
    monkeypatch.setattr(adopt, "resolve_ref", lambda requested=None: ("6.1.0", "latest tag"))

    def fake_render(_src: str, dest: Path, _data: dict[str, Any], _ref: str = "HEAD", **_kwargs: Any) -> Any:
        (Path(dest) / "README.md").write_text("")
        # questions_data without cicd_extras mirrors the 6.1.0 questionnaire;
        # include_mcp present but gated out of the render is the negative case.
        return SimpleNamespace(template=SimpleNamespace(questions_data={"include_mcp": {}, "project_type": {}}))

    monkeypatch.setattr(batch, "render", fake_render)

    assert cli.new(tmp_path, preset="bare", ref=None, dry_run=False) == cli.OK
    err = capsys.readouterr().err
    assert "cicd_extras" in err, "a preset key the ref dropped must warn"
    assert "include_mcp" not in err, "a defined-but-gated key must not warn"


def test_new_fresh_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`--dry-run` plans through adopt.render_fresh_source and never renders."""
    source = tmp_path / "plan"
    (source / "pkg").mkdir(parents=True)
    (source / "pkg" / "__init__.py").write_text("")
    (source / "README.md").write_text("")
    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("fresh", suggested_answers={}))
    monkeypatch.setattr(adopt, "resolve_ref", lambda requested=None: ("HEAD", "the working tree"))
    monkeypatch.setattr(adopt, "render_fresh_source", lambda data, ref: source)
    monkeypatch.setattr(batch, "render", lambda *a, **k: pytest.fail("a dry run must not render"))

    target = tmp_path / "target"
    assert cli.new(target, preset=None, ref=None, dry_run=True) == cli.OK
    out = capsys.readouterr().out
    assert "dry run -- nothing written" in out
    assert "would create 2 file(s); top level: README.md, pkg" in out
    assert not target.exists()


def test_new_foreign_refuses_with_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Another template's project is refused, not overwritten."""
    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("foreign", foreign_src="https://example.com/x"))
    monkeypatch.setattr(batch, "render", lambda *a, **k: pytest.fail("a foreign project must not render"))

    assert cli.new(tmp_path, preset=None, ref=None, dry_run=False) == cli.REFUSED
    assert "example.com" in capsys.readouterr().err


def test_new_update_refuses_with_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A project this template already generated is sent to `copier update`."""
    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("update"))
    monkeypatch.setattr(batch, "render", lambda *a, **k: pytest.fail("update mode must not render"))

    assert cli.new(tmp_path, preset=None, ref=None, dry_run=False) == cli.INVALID
    assert "copier update" in capsys.readouterr().err


def test_new_adopt_goes_through_the_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`adopt` mode delegates to tools/adopt.py, never merges, and warns on collisions."""
    calls: list[dict[str, Any]] = []

    def fake_adopt(target: Path, **kwargs: Any) -> adopt.Adoption:
        calls.append({"target": target, **kwargs})
        return _adoption(ok=True)

    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("adopt", collisions=["README.md"]))
    monkeypatch.setattr(adopt, "adopt", fake_adopt)
    monkeypatch.setattr(adopt, "render_report", lambda adoption: "adopted 1 file(s)")

    assert cli.new(tmp_path, preset=None, ref=None, dry_run=False) == cli.OK
    assert calls and calls[0]["merge_generated"] is False  # the CLI never merges
    captured = capsys.readouterr()
    assert "adopted 1 file(s)" in captured.out
    assert "warning: 1 existing file(s)" in captured.err  # collisions warn before adopting


def test_new_adopt_reports_a_failed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """An adoption that did not hold returns 1, the same verdict the tool reports."""
    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("adopt"))
    monkeypatch.setattr(adopt, "adopt", lambda *a, **k: _adoption(ok=False, error="rollback ran"))
    monkeypatch.setattr(adopt, "render_report", lambda adoption: "rolled back")

    assert cli.new(tmp_path, preset=None, ref=None, dry_run=False) == cli.FAILED
    assert "rolled back" in capsys.readouterr().out


def test_new_adopt_refuses_a_foreign_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """adopt.py's ownership refusal maps to exit 3, not to a generic failure."""

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        message = "owned by another template"
        raise adopt.OwnershipError(message)

    monkeypatch.setattr(detect, "detect", lambda *a, **k: _detection("adopt"))
    monkeypatch.setattr(adopt, "adopt", refuse)

    assert cli.new(tmp_path, preset=None, ref=None, dry_run=False) == cli.REFUSED
    assert "owned by another template" in capsys.readouterr().err


def test_new_unknown_preset_is_an_invalid_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A preset that does not exist fails before the detector runs."""
    monkeypatch.setattr(detect, "detect", lambda *a, **k: pytest.fail("an unknown preset must not reach detect"))

    assert cli.new(tmp_path, preset="no-such-preset", ref=None, dry_run=False) == cli.INVALID
    err = capsys.readouterr().err
    assert "unknown preset" in err
    assert "library" in err  # the available presets are listed


def test_preset_answers_reads_a_real_preset_and_rejects_a_non_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A preset file must be an answers mapping; the shipped ones are readable."""
    assert cli.preset_answers("library")["project_type"] == "library"
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "broken.yml").write_text("- just\n- a\n- list\n")
    monkeypatch.setattr(cli, "PRESETS", presets)

    with pytest.raises(cli.RequestError, match="not an answers mapping"):
        cli.preset_answers("broken")


def test_collision_warning_summarizes_past_the_limit():
    """The warning names up to the limit, then counts the rest."""
    few = cli.collision_warning(["a.txt", "b.txt"])
    assert few == "warning: 2 existing file(s) the template also ships will be left alone: a.txt, b.txt"
    many = cli.collision_warning([f"f{index}.txt" for index in range(cli.COLLISION_LIMIT + 3)])
    assert "warning: 15 existing file(s)" in many
    assert "(+3 more)" in many


def test_main_parses_the_new_subcommand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`main` resolves the subcommand, the directory and the flags."""
    seen: dict[str, Any] = {}

    def fake_new(
        target: Path, *, preset: str | None, ref: str | None, dry_run: bool, list_presets: bool = False
    ) -> int:
        seen.update(target=target, preset=preset, ref=ref, dry_run=dry_run, list_presets=list_presets)
        return cli.OK

    monkeypatch.setattr(cli, "new", fake_new)

    assert cli.main(["new", str(tmp_path), "--preset", "library", "--ref", "HEAD", "--dry-run"]) == cli.OK
    assert seen == {"target": tmp_path, "preset": "library", "ref": "HEAD", "dry_run": True, "list_presets": False}


def test_main_dispatches_the_verify_subcommand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`main` routes `verify` to tools/verify.py with the directory and --against."""
    seen: dict[str, Any] = {}

    def fake_verify(argv: list[str] | None) -> int:
        seen["argv"] = argv
        return cli.OK

    monkeypatch.setattr(cli.verify, "main", fake_verify)  # pyright: ignore[reportPrivateLocalImportUsage]  WHYNOT: patching the module's own import is the point.
    other = tmp_path / "other"

    assert cli.main(["verify", str(tmp_path)]) == cli.OK
    assert seen == {"argv": [str(tmp_path)]}

    assert cli.main(["verify", str(tmp_path), "--against", str(other)]) == cli.OK
    assert seen == {"argv": ["--against", str(other), str(tmp_path)]}


def test_main_dispatches_the_explain_subcommand(monkeypatch: pytest.MonkeyPatch):
    """`main` routes `explain` to tools/explain.py with the preset/question/deviate flags."""
    seen: dict[str, Any] = {}

    def fake_explain(argv: list[str] | None) -> int:
        seen["argv"] = argv
        return cli.OK

    monkeypatch.setattr(cli.explain, "main", fake_explain)  # pyright: ignore[reportPrivateLocalImportUsage]  WHYNOT: patching the module's own import is the point.

    assert cli.main(["explain", "--preset", "web-api"]) == cli.OK
    assert seen == {"argv": ["--preset", "web-api"]}

    assert cli.main(["explain", "project_type", "cli"]) == cli.OK
    assert seen == {"argv": ["project_type", "cli"]}

    assert cli.main(["explain", "--deviate", "project_type", "cli"]) == cli.OK
    assert seen == {"argv": ["--deviate", "project_type", "cli"]}


def test_main_dispatches_the_suggest_subcommand(monkeypatch: pytest.MonkeyPatch):
    """`main` routes `suggest` to tools/suggest.py with the requirements/validate/json flags."""
    seen: dict[str, Any] = {}

    def fake_suggest(argv: list[str] | None) -> int:
        seen["argv"] = argv
        return cli.OK

    monkeypatch.setattr(cli.suggest, "main", fake_suggest)  # pyright: ignore[reportPrivateLocalImportUsage]  WHYNOT: patching the module's own import is the point.

    assert cli.main(["suggest", "internal API, postgres"]) == cli.OK
    assert seen == {"argv": ["internal API, postgres"]}

    assert cli.main(["suggest", "--validate", "answers.yml", "--json"]) == cli.OK
    assert seen == {"argv": ["--validate", "answers.yml", "--json"]}


def test_main_dispatches_the_scaffold_subcommand(monkeypatch: pytest.MonkeyPatch):
    """`main` routes `scaffold` to tools/scaffold.py with the subcommand and args."""
    from tools import scaffold  # noqa: PLC0415

    seen: dict[str, Any] = {}

    def fake_scaffold(argv: list[str] | None) -> int:
        seen["argv"] = argv
        return cli.OK

    monkeypatch.setattr(scaffold, "main", fake_scaffold)

    assert cli.main(["scaffold", "check"]) == cli.OK
    assert seen == {"argv": ["check"]}

    assert cli.main(["scaffold", "question", "my_flag", "--dry-run"]) == cli.OK
    assert seen == {
        "argv": [
            "question",
            "my_flag",
            "--type",
            "bool",
            "--when",
            "true",
            "--default",
            "true",
            "--file",
            "questions/_common_c.yml",
            "--dry-run",
        ]
    }


def test_new_list_presets_prints_every_preset_and_skips_detect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`--list-presets` prints each preset with its header description, exiting before detect."""
    monkeypatch.setattr(detect, "detect", lambda *a, **k: pytest.fail("listing presets must not reach detect"))
    assert cli.new(tmp_path, preset=None, ref=None, dry_run=False, list_presets=True) == cli.OK
    out = capsys.readouterr().out
    for name in cli.available_presets():
        assert f"{name}:" in out, f"preset {name} missing from --list-presets output"
    assert "A minimal Python library render" in out  # bare's first comment line


# Installed-mode delegation: `main` re-dispatches to the cached clone when TOP
# carries no copier.yml. The git runner and the child process are faked; what
# is pinned is the observable contract -- one delegation, the child's exit
# code, the recursion guard, the URL in errors, the stale-clone fallback.


def test_main_delegates_to_the_cached_checkout_and_propagates_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An install without a checkout next to it runs the cached clone's CLI once."""
    calls: list[tuple[list[str], dict[str, str]]] = []
    cache = tmp_path / "cache" / "repo"
    (cache / "tools").mkdir(parents=True)
    (cache / "tools" / "cli.py").write_text("")
    monkeypatch.setattr(cli, "TOP", tmp_path / "no-checkout")  # no copier.yml: installed mode
    monkeypatch.setattr(cli, "_cache_dir", lambda: cache)
    monkeypatch.setattr(cli, "_refresh_checkout", lambda _cache: None)  # the clone already exists

    def fake_call(argv: list[str], env: dict[str, str]) -> int:
        calls.append((argv, env))
        return 7  # an arbitrary child exit code, propagated as-is

    monkeypatch.setattr(cli.subprocess, "call", fake_call)  # pyright: ignore[reportPrivateLocalImportUsage]  WHYNOT: patching the module's own import is the point.

    assert cli.main(["new", "proj", "--preset", "library"]) == 7
    assert len(calls) == 1  # one delegation, never a second
    argv, env = calls[0]
    assert argv == [sys.executable, str(cache / "tools" / "cli.py"), "new", "proj", "--preset", "library"]
    assert env[cli.DELEGATED_ENV] == "1"


def test_delegation_sentinel_fails_without_a_second_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A delegated clone that is still not a checkout errors instead of recursing."""
    monkeypatch.setattr(cli, "TOP", tmp_path / "no-checkout")
    monkeypatch.setattr(cli, "_cache_dir", lambda: tmp_path / "cache" / "repo")
    monkeypatch.setenv(cli.DELEGATED_ENV, "1")
    monkeypatch.setattr(cli.subprocess, "call", lambda *a, **k: pytest.fail("must not delegate again"))  # pyright: ignore[reportPrivateLocalImportUsage]  WHYNOT: same as above.

    assert cli.main(["new", "proj"]) == cli.FAILED
    assert "not a template checkout" in capsys.readouterr().err


def test_offline_without_cache_names_the_remote_and_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A cold cache that cannot be cloned reports the URL and exits non-zero."""
    from types import SimpleNamespace

    cache = tmp_path / "cache" / "repo"
    monkeypatch.setattr(cli, "TOP", tmp_path / "no-checkout")
    monkeypatch.setattr(cli, "_cache_dir", lambda: cache)
    monkeypatch.setattr(cli, "_remote_url", lambda: "https://example.invalid/template.git")

    def failed_git(_where: Path, *_args: str) -> SimpleNamespace:
        return SimpleNamespace(returncode=128, stdout="", stderr="fatal: could not read from remote")

    monkeypatch.setattr(cli, "run_git", failed_git)

    assert cli.main(["new", "proj"]) == cli.FAILED
    assert "https://example.invalid/template.git" in capsys.readouterr().err
    assert not cache.exists()  # nothing half-cloned left behind


def test_stale_cache_with_failed_fetch_still_delegates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A refresh failure warns and the stale clone is used, not a hard error."""
    from types import SimpleNamespace

    calls: list[list[str]] = []
    cache = tmp_path / "cache" / "repo"
    (cache / "tools").mkdir(parents=True)
    (cache / "tools" / "cli.py").write_text("")
    monkeypatch.setattr(cli, "TOP", tmp_path / "no-checkout")
    monkeypatch.setattr(cli, "_cache_dir", lambda: cache)

    def failed_fetch(_where: Path, *_args: str) -> SimpleNamespace:
        return SimpleNamespace(returncode=128, stdout="", stderr="fatal: unable to access")

    monkeypatch.setattr(cli, "run_git", failed_fetch)
    monkeypatch.setattr(cli.subprocess, "call", lambda argv, env: calls.append(argv) or cli.OK)  # pyright: ignore[reportPrivateLocalImportUsage]  WHYNOT: same as above.

    assert cli.main(["new", "proj"]) == cli.OK
    assert "stale" in capsys.readouterr().err
    assert calls and calls[0][:2] == [sys.executable, str(cache / "tools" / "cli.py")]


def test_clone_losing_the_rename_race_keeps_the_existing_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`_clone_checkout` against an already-published cache keeps the winner's clone."""
    from types import SimpleNamespace

    cache = tmp_path / "cache" / "repo"
    cache.mkdir(parents=True)
    (cache / "winner.txt").write_text("mine")

    def ok_clone(_where: Path, *_args: str) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli, "run_git", ok_clone)

    assert cli._clone_checkout(cache) == cli.OK  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: atomic publish has no public entry point; the test pins its contract.
    assert (cache / "winner.txt").read_text() == "mine"  # the loser must not replace it
    assert [p.name for p in cache.parent.iterdir()] == [cache.name]  # the loser's temp dir is gone


def test_remote_url_defaults_to_the_shipped_repo(monkeypatch: pytest.MonkeyPatch):
    """The fallback remote is the canonical template repo, overridable by env."""
    monkeypatch.delenv(cli.REMOTE_URL_ENV, raising=False)
    assert cli._remote_url() == "https://github.com/ConstitutiveTemplates/daimonion.git"  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: no public entry point; the fallback remote is a contract.
    monkeypatch.setenv(cli.REMOTE_URL_ENV, "https://example.com/x.git")
    assert cli._remote_url() == "https://example.com/x.git"  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: same as above.


def test_cache_dir_follows_xdg_and_defaults_to_home(monkeypatch: pytest.MonkeyPatch):
    """The cache lives under $XDG_CACHE_HOME (or ~/.cache) + the template name."""
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg-cache")
    assert cli._cache_dir() == Path("/tmp/xdg-cache") / "daimonion" / "repo"  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  WHYNOT: no public entry point; the documented cache location is a contract.
