#!/usr/bin/env python3
"""Report drift between vendored ethics sections and good-future-codex.

_shared/ethics/ is a vendored snapshot of ConstitutiveTemplates/good-future-codex
(the canonical section texts of the Good-future charter). This script is the
consumer-side half of the sync contract in docs/explanations/ethics-external.md:
it diffs the vendored tree against the codex at the SHA recorded in
.ethics-vendored, and again at codex's current main, so a run answers both
"is the vendored copy clean" and "is upstream ahead of it".

Exits 0 when the vendored tree matches the marker AND the marker is codex's
main; exits 1 on either drift (dirty vendor or upstream ahead). Runs from a
pristine checkout: it clones the codex into a temp dir rather than touching
any named remote.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import UTC
from datetime import datetime
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
CODEX_URL = "https://github.com/ConstitutiveTemplates/good-future-codex.git"
MARKER = TOP / ".ethics-vendored"
VENDORED = TOP / "_shared" / "ethics"


def run(*args: str, cwd: Path | None = None) -> str:
    # args is a fixed literal argv built by this script, never user input.
    return subprocess.run(  # noqa: S603
        args, check=True, capture_output=True, text=True, cwd=cwd
    ).stdout


# Consumer-side wiring that is not vendored: REGISTRY.yml (its gate column
# names template flags) and FLAGS.yml (the abstract->concrete mapping the
# codex's MANIFEST.yml resolves against). MANIFEST.yml IS vendored: it is the
# contract the consistency test reads offline, so it travels with the
# sections even though the codex owns it.
CONSUMER_OWNED = {"REGISTRY.yml", "FLAGS.yml"}


def _tree(root: Path, skip: frozenset[str] = frozenset()) -> dict[str, bytes]:
    """Map every file under root to its bytes, keyed by relative path."""
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name not in CONSUMER_OWNED and p.name not in skip
    }


def _diff(a: dict[str, bytes], b: dict[str, bytes]) -> list[str]:
    """Relative paths that differ or exist on only one side."""
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))


def main() -> int:
    if not MARKER.exists():
        print(
            f"No vendored marker at {MARKER.name}: record the codex SHA the "
            "vendored snapshot was taken from (one line, full sha).",
            file=sys.stderr,
        )
        return 2
    vendored_sha = MARKER.read_text(encoding="utf-8").strip()

    with tempfile.TemporaryDirectory() as tmp:
        codex = Path(tmp) / "codex"
        # The codex is public (it exists for external consumers), so a plain
        # https clone needs no auth -- no secret, no deploy key, no PAT.
        run("git", "clone", "--quiet", CODEX_URL, str(codex))
        upstream_head = run("git", "rev-parse", "HEAD", cwd=codex).strip()
        upstream_ts = int(run("git", "show", "-s", "--format=%ct", "HEAD", cwd=codex).strip())
        age_days = max(
            0,
            (datetime.now(UTC) - datetime.fromtimestamp(upstream_ts, UTC)).days,
        )
        # Additive display only: exit semantics below are unchanged.
        print(f"vendored={vendored_sha[:8]} upstream={upstream_head[:8]} age_days={age_days}")
        upstream_sections = _tree(codex / "sections")

        # The codex's own tree at the vendored SHA, for the dirty-vendor check.
        run("git", "checkout", "--quiet", vendored_sha, cwd=codex)
        vendored_sections = _tree(codex / "sections")
    local = _tree(VENDORED)
    dirty = _diff(local, vendored_sections)
    ahead = _diff(local, upstream_sections) if vendored_sha != upstream_head else []

    if not dirty and not ahead:
        print(f"Vendored ethics sections clean at {vendored_sha[:10]} (codex main).")
        return 0
    if dirty:
        print("Vendored _shared/ethics/ differs from the recorded snapshot:")
        for path in dirty:
            print(f"  {path}")
        excludes = " ".join(f"--exclude {name}" for name in sorted(CONSUMER_OWNED))
        print(
            "\nEither restore the vendored copy or re-vendor: "
            f"rsync -a --delete {excludes} <codex>/sections/ _shared/ethics/ && "
            f"echo <sha> > {MARKER.name}"
        )
    if ahead:
        print(f"good-future-codex is ahead of the vendored {vendored_sha[:10]}:")
        for path in ahead:
            print(f"  {path}")
        print(f"\nReview the diff, then re-vendor and bump {MARKER.name} to {upstream_head}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
