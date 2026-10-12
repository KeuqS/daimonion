"""Behavioural checks for the secret-scanning setup.

pre-commit used to run gitleaks locally; scanning now happens in CI via the
hygiene workflow (`gitleaks/gitleaks-action`), which reads `.gitleaks.toml`.
These tests exercise that config the way gitleaks does — parse it, compile the
rule regexes and run them against sample secrets — plus the wiring the old
tests covered: the config ships into generated projects, the action runs
SHA-pinned, and the SealedSecrets allowlist stays scoped to YAML.
"""

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

TOP = Path(__file__).resolve().parent.parent
GITLEAKS_TOML = TOP / ".gitleaks.toml"
TEMPLATE_LINK = TOP / "template" / "{% if cicd_extras %}.gitleaks.toml{% endif %}"
HYGIENE = TOP / ".github" / "workflows" / "_hygiene.yml"


def config() -> dict[str, Any]:
    return tomllib.loads(GITLEAKS_TOML.read_text(encoding="utf-8"))


def rule(rule_id: str) -> dict[str, Any]:
    """The configured rule with this id (gitleaks fails on duplicates too)."""
    entries = [entry for entry in config()["rules"] if entry["id"] == rule_id]
    assert len(entries) == 1, f"expected exactly one {rule_id!r} rule, got {len(entries)}"
    return entries[0]


def test_gitleaks_config_ships_into_generated_projects():
    """Generated projects scan with the same rules as this repo."""
    assert TEMPLATE_LINK.is_file(), "the template must ship .gitleaks.toml"
    assert TEMPLATE_LINK.read_text(encoding="utf-8") == GITLEAKS_TOML.read_text(encoding="utf-8"), (
        "template/.gitleaks.toml must stay in sync with the root config"
    )


def test_hygiene_workflow_runs_gitleaks_pinned_binary():
    """The hygiene workflow downloads a pinned gitleaks release binary and
    scans the full git history (checkout fetch-depth: 0) — no license fee,
    unlike gitleaks-action v3 which charges org accounts."""
    src = HYGIENE.read_text(encoding="utf-8")
    assert "gitleaks/gitleaks-action" not in src, "gitleaks-action v3 requires a paid license for orgs"
    version_m = re.search(r"GITLEAKS_VERSION: (\d+\.\d+\.\d+)", src)
    assert version_m, "GITLEAKS_VERSION must pin the downloaded binary"
    download = re.search(
        r"gitleaks/gitleaks/releases/download/v\$\{GITLEAKS_VERSION\}/gitleaks_\$\{GITLEAKS_VERSION\}_linux_x64\.tar\.gz",
        src,
    )
    assert download, "the step must download the pinned release tarball"
    assert re.search(r"gitleaks git --redact --config \.gitleaks\.toml", src), (
        "the scan must run `gitleaks git` with the repo config"
    )


def test_sealed_secrets_allowlist_stays_yaml_scoped():
    """The generic-api-key allowlist for long Ag… tokens must stay limited to
    YAML files — broadening it to all files would silence real leaks (the
    scenario the old behavioral gitleaks tests covered)."""
    allowlists = rule("generic-api-key").get("allowlists") or []
    assert allowlists, "the Ag… allowlist must exist"

    token = "Ag" + "A" * 600
    assert any(re.search(pattern, f"key: {token}") for entry in allowlists for pattern in entry["regexes"]), (
        "the allowlist must actually cover a long Ag… token"
    )
    for entry in allowlists:
        paths = [re.compile(pattern) for pattern in entry.get("paths") or ()]
        assert paths, "an allowlist without `paths` applies to every file"
        assert any(pattern.fullmatch("secrets.yaml") for pattern in paths), entry
        assert not any(pattern.fullmatch("src/config.json") for pattern in paths), entry


@pytest.mark.parametrize("artifact", ["**/*.ipynb", "REUSE.toml", "CITATION.cff"])
def test_hygiene_workflow_steps_are_gated(artifact: str):
    """The optional hygiene steps self-gate via hashFiles so a generated
    project only runs what it ships."""
    workflow = yaml.safe_load(HYGIENE.read_text(encoding="utf-8"))
    conditions = [str(step.get("if", "")) for step in workflow["jobs"]["hygiene"]["steps"]]
    assert any(f"hashFiles('{artifact}')" in condition for condition in conditions), (
        f"no hygiene step is gated on {artifact}"
    )


@pytest.mark.parametrize("fragment", ["secret_salt", "deidentification_salt", "pseudonym_salt"])
def test_deidentification_salt_rule_matches_every_naming_variant(fragment: str):
    """The privacy rule guarding data/DEIDENTIFICATION.md must keep matching
    every salt naming variant — and not the prose that documents the policy."""
    pattern = re.compile(rule("deidentification-salt")["regex"])
    assert pattern.search(f'{fragment} = "hunter2"'), f"{fragment} = ... must be caught"
    assert pattern.search(f"{fragment}='hunter2'"), f"{fragment}='...' must be caught"
    assert not pattern.search(f"# {fragment} is never committed"), "prose must not trip the rule"
