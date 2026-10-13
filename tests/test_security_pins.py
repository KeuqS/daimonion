"""The security-tool pins the weekly upstream check must not lose.

`tools/check_upstream.py` already tracked the gitleaks binary and the
actionlint digest; the zizmor cli/action pair and the three uvx tools in the
hygiene workflow are the pins with the same blast radius (a stale secrets
scanner, workflow linter or SAST gate fails open). These checks run the
checker in `--offline` mode only, so they stay in the fast tier: they assert
extraction from the single source of truth, never the network verdict.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools import check_upstream as cu  # noqa: E402

HYGIENE = TOP / ".github" / "workflows" / "_hygiene.yml"
SECURITY = TOP / ".github" / "workflows" / "security.yml"


def _pins() -> dict[str, cu.Pin]:
    pins = cu.extract_pins()
    cu.resolve_upstream(pins, offline=True)
    return {pin.name: pin for pin in pins}


def test_security_tool_pins_are_extracted_offline():
    """Every security-sensitive pin resolves to its workflow value, not '?'."""
    hygiene = HYGIENE.read_text(encoding="utf-8")
    security = SECURITY.read_text(encoding="utf-8")
    expected = {
        "gitleaks version (_hygiene.yml)": re.search(r"GITLEAKS_VERSION: (\d+\.\d+\.\d+)", hygiene),
        "uvx conventional-pre-commit version (_hygiene.yml)": re.search(
            r"uvx conventional-pre-commit==([0-9][\w.+-]*)", hygiene
        ),
        "uvx nbstripout version (_hygiene.yml)": re.search(r"uvx nbstripout==([0-9][\w.+-]*)", hygiene),
        "uvx cffconvert version (_hygiene.yml)": re.search(r"uvx cffconvert==([0-9][\w.+-]*)", hygiene),
        "zizmor cli version (security.yml)": re.search(r'version: "(\d+\.\d+\.\d+)"', security),
        "zizmor action version (security.yml)": re.search(
            r"zizmorcore/zizmor-action@[0-9a-f]{40} # (v\d+\.\d+\.\d+)", security
        ),
    }
    pins = _pins()
    for name, match in expected.items():
        assert match, f"the workflow no longer pins {name}"
        assert name in pins, f"extract_pins() lost {name}"
        assert pins[name].current == match.group(1), f"{name} reads a stale value"


def test_actionlint_digest_pin_is_extracted_offline():
    """The digest pin reports the short digest behind the latest tag."""
    hygiene = HYGIENE.read_text(encoding="utf-8")
    digest = re.search(r"rhysd/actionlint@sha256:([0-9a-f]{64})", hygiene)
    assert digest, "the hygiene workflow no longer digest-pins actionlint"
    pins = _pins()
    assert pins["actionlint image digest (_hygiene.yml)"].current == digest.group(1)[:12]


def test_uvx_drift_rule_distinguishes_behind_from_removed():
    """A floor/latest gap is [DRIFT]; a REMOVED floor stays [DRIFT] too, never [ok]."""
    behind = cu.Pin(
        name="uvx nbstripout version (_hygiene.yml)",
        current="0.8.1",
        upstream="floor 0.8.1 / latest 0.9.1",
        checkable=True,
    )
    is_drift, message = cu._is_drift(behind)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    assert is_drift and message.startswith("[DRIFT]"), f"a behind uvx pin must read as drift: {message}"
    current = cu.Pin(
        name="uvx cffconvert version (_hygiene.yml)",
        current="2.0.0",
        upstream="floor 2.0.0 / latest 2.0.0",
        checkable=True,
    )
    ok, ok_message = cu._is_drift(current)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    assert not ok and ok_message.startswith("[ok]"), f"a current uvx pin must read as ok: {ok_message}"


def test_zizmor_drift_rule_tracks_both_halves_of_the_pair():
    """The cli and action halves each drift independently (the allowlist test covers pairing)."""
    cli = cu.Pin(name="zizmor cli version (security.yml)", current="1.30.1", upstream="v1.31.0", checkable=True)
    cli_drift, cli_message = cu._is_drift(cli)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    assert cli_drift and "[DRIFT]" in cli_message
    action = cu.Pin(name="zizmor action version (security.yml)", current="v0.6.4", upstream="v0.6.4", checkable=True)
    action_ok, action_message = cu._is_drift(action)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    assert not action_ok and action_message.startswith("[ok]")
