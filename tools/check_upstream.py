#!/usr/bin/env python3
"""Check the template's hardcoded pins against official upstream.

The template hardcodes versions renovate cannot track: release tags, CUDA
indexes, distro codenames, image tags. Renovate handles PyPI ranges, GitHub
Action digests and lockfiles — everything here is what it cannot see.

Each check below names its single source of truth in the template and the
upstream feed it is compared against:

- MicroPython tag (`micropython_version` internal) — tracks the latest
  stable release of micropython/micropython on GitHub.
- MicroPython stubs — the pinned community stubs must exist on PyPI.
- CUDA (Dockerfile.gpu base + cu124/cu126-style uv index) — the uv index
  must still receive torch releases; the Docker base should track the
  newest long-lived CUDA minor.
- ROS 2 distros (questions/ros2.yml choices) — no offered distro may be
  past EOL per REP-2000; warn when a newer LTS exists.
- Python floor (requires-python / CI matrix / classifiers) — the oldest
  supported version must not be past EOL per endoflife.date.
- Postgres image (compose + CI service) — the major must still receive
  updates; warn when a newer major is the stable default.
- Ubuntu base (resolute) — the LTS codename must still be supported.

Exits 0 when everything is current, 1 on any drift. Intended to run in CI
(see .github/workflows/check-upstream.yml) where a nonzero exit + the drift
report opens an issue.

Usage:
    python tools/check_upstream.py             # check against upstream
    python tools/check_upstream.py --offline   # report pins only
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime as datetime_
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = TOP / "questions"
TEMPLATE_DIR = TOP / "template"
PYPROJECT_JINJA = TEMPLATE_DIR / (
    "{% if (not existing_project or 'pyproject' not in adopt_protect) "
    "and not ros2_cpp %}pyproject.toml{% endif %}.jinja"
)
GPU_DOCKERFILE = TEMPLATE_DIR / ("{% if use_gpu_effective %}Dockerfile.gpu{% endif %}.jinja")
COMPOSE_JINJA = TEMPLATE_DIR / ("{% if web_api and docker %}compose.local.yml{% endif %}.jinja")
CI_JINJA = TEMPLATE_DIR / (
    "{% if is_github %}.github{% endif %}/{% if ci_provider == 'github_actions' %}workflows{% endif %}/ci.yml.jinja"
)
ROS2_QUESTIONS = QUESTIONS_DIR / "ros2.yml"
MACROS_JINJA = TEMPLATE_DIR.parent / "_shared" / "macros.jinja"


@dataclass
class Pin:
    name: str
    current: str
    upstream: str | None = None
    checkable: bool = False


def https_get(host: str, path: str, headers: dict[str, str] | None = None, attempts: int = 3) -> tuple[int, str, str]:
    """GET a resource over https. Returns (status, body, content-type).

    The weekly check walks ~20 endpoints from one IP, and a throttled or
    reset response is a transient condition of that burst -- retrying 429/5xx
    and connection errors with a short backoff keeps one unlucky request from
    turning into a phantom upstream-drift report.
    """
    for attempt in range(attempts):
        try:
            conn = http.client.HTTPSConnection(host, timeout=20)
            try:
                conn.request("GET", path, headers={"User-Agent": "daimonion-upstream-check", **(headers or {})})
                resp = conn.getresponse()
                body = resp.read().decode("utf-8", "replace")
                status, ctype = resp.status, resp.getheader("Content-Type", "")
            finally:
                conn.close()
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(2 * (attempt + 1))
            continue
        if status in (429, 500, 502, 503, 504) and attempt < attempts - 1:
            time.sleep(2 * (attempt + 1))
            continue
        return status, body, ctype
    raise AssertionError("unreachable")


def https_get_json(host: str, path: str) -> dict[str, object] | list[object]:
    """GET a JSON resource over https."""
    status, body, _ = https_get(host, path)
    if status != 200:
        msg = f"GET https://{host}{path} -> HTTP {status}"
        raise RuntimeError(msg)
    data: dict[str, object] | list[object] = json.loads(body)
    return data


def github_latest_release(repo: str) -> str | None:
    """Return the latest release tag (e.g. v1.25.0) for a GitHub repo."""
    try:
        data = https_get_json("api.github.com", f"/repos/{repo}/releases/latest")
    except RuntimeError:
        return None
    if isinstance(data, dict):
        tag = data.get("tag_name")
        return str(tag) if tag else None
    return None


def pypi_has_version(package: str, version: str) -> bool:
    """Return True if a package version exists on PyPI."""
    try:
        data = https_get_json("pypi.org", f"/pypi/{package}/json")
    except RuntimeError:
        return False
    if not isinstance(data, dict):
        return False
    releases = data.get("releases")
    if not isinstance(releases, dict):
        return False
    return any(rel.startswith(version) for rel in releases)


def pypi_latest(package: str) -> str | None:
    """Return the latest version of a PyPI package.

    None means PyPI itself says the package does not exist (HTTP 404) -- the
    only state that may be reported as a REMOVED floor. A persistent lookup
    failure (throttling, outage) raises instead, so the caller reports an
    unresolved check rather than phantom drift.
    """
    status, body, _ = https_get("pypi.org", f"/pypi/{package}/json")
    if status == 404:
        return None
    if status != 200:
        msg = f"GET https://pypi.org/pypi/{package}/json -> HTTP {status} (persistent after retries)"
        raise RuntimeError(msg)
    data = json.loads(body)
    if isinstance(data, dict):
        info = data.get("info")
        if isinstance(info, dict):
            version = info.get("version")
            return str(version) if version else None
    return None


def pytorch_index_torch_versions(cu_tag: str) -> list[str]:
    """Return torch versions published on a pytorch cu-index (e.g. cu126)."""
    try:
        status, body, _ = https_get("download.pytorch.org", f"/whl/{cu_tag}/torch/")
    except RuntimeError:
        return []
    if status != 200:
        return []
    return sorted(set(re.findall(r"torch-(2\.\d+\.\d+)", body)), key=lambda v: tuple(int(x) for x in v.split(".")))


def eol_date(product: str, cycle: str) -> str | None:
    """Return the EOL date (YYYY-MM-DD) for a product cycle, or None."""
    try:
        data = https_get_json("endoflife.date", f"/api/{product}.json")
    except RuntimeError:
        return None
    if not isinstance(data, list):
        return None
    for entry in data:
        if isinstance(entry, dict) and str(entry.get("cycle")) == cycle:
            eol = entry.get("eol")
            return str(eol) if eol and eol is not False else None
    return None


def _extract_micropython_pins() -> list[Pin]:
    """Extract MicroPython version and stubs pin from copier config."""
    version = "?"
    sources = [TOP / "copier.yml", *QUESTIONS_DIR.glob("*.yml")]
    for src in sources:
        ver_m = re.search(
            r"^micropython_version:\n    type: str\n    default: \"([^\"]+)\"",
            src.read_text(),
            re.MULTILINE,
        )
        if ver_m:
            version = ver_m.group(1)
            break
    return [
        Pin(name="MicroPython tag (micropython_version)", current=version, checkable=True),
        Pin(
            name="micropython-<port>-stubs pin",
            current=f"~={version.removeprefix('v')} (community stubs)",
            checkable=True,
        ),
    ]


def _extract_platform_pins() -> list[Pin]:
    """Extract base images, runtime versions, and distro choices."""
    gpu_src = GPU_DOCKERFILE.read_text()
    cuda_m = re.search(r"FROM nvidia/cuda:([^\s]+) AS", gpu_src)
    cuda_base = cuda_m.group(1) if cuda_m else "?"

    ros_src = ROS2_QUESTIONS.read_text()
    distros = re.findall(r": (humble|jazzy|kilted|rolling)\n", ros_src)

    macros_src = MACROS_JINJA.read_text()
    floor_m = re.search(r"else '(\d+\.\d+)'\)\s*\}\}", macros_src)
    floor = floor_m.group(1) if floor_m else "?"

    compose_src = COMPOSE_JINJA.read_text()
    ci_src = CI_JINJA.read_text()
    pg_tags = set(re.findall(r"image: (postgres:[^\s]+)", compose_src)) | set(
        re.findall(r"image: (postgres:[^\s]+)", ci_src)
    )

    docker_src = (TEMPLATE_DIR / "{% if docker or cicd_extras %}Dockerfile{% endif %}.jinja").read_text()
    ubuntu_tags = set(re.findall(r"(?:ubuntu:|ubuntu-devcontainer:)(\w+)", docker_src))
    base_m = re.search(r"FROM (ghcr\.io/\S+) AS developer", docker_src)

    return [
        Pin(name="CUDA Docker base (Dockerfile.gpu)", current=cuda_base, checkable=True),
        Pin(name="ROS 2 distros offered", current=",".join(sorted(set(distros))) or "?", checkable=True),
        Pin(name="Python floor (requires-python)", current=floor, checkable=True),
        Pin(name="Postgres image (compose + CI)", current=",".join(sorted(pg_tags)) or "?", checkable=True),
        Pin(name="Ubuntu base (Dockerfile)", current=",".join(sorted(ubuntu_tags)) or "?", checkable=False),
        Pin(name="Devcontainer base (Dockerfile)", current=base_m.group(1) if base_m else "?", checkable=True),
    ]


def _load_combined_pyproject_sources() -> str:
    """Load pyproject template along with all _shared partials."""
    src = PYPROJECT_JINJA.read_text()
    for partial in sorted((TOP / "_shared").glob("pyproject-*.toml.jinja")):
        src += "\n" + partial.read_text()
    return src


def _extract_pypi_floor_pins(pyproject_src: str) -> list[Pin]:
    """Extract PyPI dependency floor pins by category."""
    pins: list[Pin] = []
    categories = {
        "core (all projects)": r'"(structlog|ruff|pytest)"',
        "web_api": r'"(fastapi|uvicorn|sqlalchemy|alembic|asyncpg|pydantic-settings|slowapi|prometheus-client)[^"]*"',
        "kaggle/DS": r'"(torch|torchvision|lightgbm|xgboost|optuna|hydra-core|polars|duckdb|pyarrow)[^"]*"',
        "ctf": r'"(pwntools|z3-solver)[^"]*"',
        "mcp": r'"(mcp\[[^\]]*\]|mcp)[^"]*"',
        "bot": r'"(discord\.py|discord-py|slack-bolt|slack_bolt|line-bot-sdk|line_bot_sdk)[^"]*"',
    }
    for category, pattern in categories.items():
        for dep in sorted(set(re.findall(pattern, pyproject_src))):
            floor_m = re.search(rf'"{re.escape(dep)}([^"]*)"', pyproject_src)
            floor = floor_m.group(1) if floor_m else "?"
            pins.append(Pin(name=f"PyPI floor [{category}] {dep}", current=floor or "unpinned", checkable=True))
    return pins


def _extract_copier_pin() -> list[Pin]:
    """Extract the repo's own copier dev-dependency ceiling."""
    root_pyproject_src = (TOP / "pyproject.toml").read_text()
    copier_m = re.search(r'"copier>=(\d+),<(\d+)"', root_pyproject_src)
    if copier_m:
        floor, ceiling = copier_m.group(1), copier_m.group(2)
        return [Pin(name="copier ceiling (root pyproject.toml)", current=f">={floor},<{ceiling}", checkable=True)]
    return []


def _extract_runner_pins() -> list[Pin]:
    """Extract the versions of the task runners the workflows pin."""
    composite_src = (TOP / ".github" / "actions" / "setup-runner" / "action.yml").read_text()
    pins = [
        Pin(
            name="just version (setup-just)",
            current=",".join(sorted(set(re.findall(r'just-version: "(\d+\.\d+\.\d+)"', composite_src)))) or "?",
            checkable=True,
        )
    ]
    audit_src = (TOP / ".github" / "workflows" / "dependency-audit.yml").read_text()
    task_m = re.search(r"task-version: v(\d+\.\d+\.\d+)", audit_src)
    pins.append(
        Pin(name="task version (dependency-audit.yml)", current=task_m.group(1) if task_m else "?", checkable=True)
    )
    task_m = re.search(r"task-version: v(\d+\.\d+\.\d+)", composite_src)
    pins.append(Pin(name="task version (setup-runner)", current=task_m.group(1) if task_m else "?", checkable=True))
    return pins


def _extract_hygiene_pins() -> list[Pin]:
    """Extract pinned versions and digests in hygiene workflow."""
    hygiene_src = (TOP / ".github" / "workflows" / "_hygiene.yml").read_text()
    gitleaks_m = re.search(r"GITLEAKS_VERSION: (\d+\.\d+\.\d+)", hygiene_src)
    digest_m = re.search(r"rhysd/actionlint@sha256:([0-9a-f]{64})", hygiene_src)
    return [
        Pin(
            name="gitleaks version (_hygiene.yml)",
            current=gitleaks_m.group(1) if gitleaks_m else "?",
            checkable=True,
        ),
        Pin(
            name="actionlint image digest (_hygiene.yml)",
            current=digest_m.group(1)[:12] if digest_m else "?",
            checkable=True,
        ),
    ]


def extract_pins() -> list[Pin]:
    """Extract the pins from the template files (no network)."""
    pyproject_src = _load_combined_pyproject_sources()
    pins: list[Pin] = []
    pins.extend(_extract_micropython_pins())
    pins.extend(_extract_platform_pins())
    pins.extend(_extract_pypi_floor_pins(pyproject_src))
    pins.extend(_extract_copier_pin())
    pins.extend(_extract_runner_pins())
    pins.extend(_extract_hygiene_pins())
    return pins


def _parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", text)[:3])


def _today() -> str:
    return datetime_.now(tz=UTC).date().isoformat()


def _resolve_cuda_base() -> str | None:
    # Report the newest CUDA minor seen on the torch index family: the
    # Docker base should track what torch ships for.
    cu_versions = {cu: pytorch_index_torch_versions(cu) for cu in ("cu124", "cu126", "cu128")}
    newest = max(
        (cu for cu, vers in cu_versions.items() if vers),
        default=None,
        key=lambda cu: _parse_version(cu_versions[cu][-1]),
    )
    return f"newest torch-bearing index {newest}" if newest else None


def _resolve_torch_index(cu: str) -> str:
    versions = pytorch_index_torch_versions(cu)
    latest = pypi_latest("torch")
    if not versions:
        return f"index {cu} unreachable or empty"
    if latest and _parse_version(versions[-1]) < _parse_version(latest):
        return f"index tops out at {versions[-1]}, PyPI latest {latest} (index frozen?)"
    return f"index current (tops out at {versions[-1]})"


ROS_EOL = {"humble": "2027-05", "jazzy": "2029-05", "kilted": "2026-11"}


def _resolve_ros(current: str, today: str) -> str:
    # REP-2000 dates, hardcoded rather than scraped: the source is a
    # versioned spec document, and scraping RST is brittle.
    offered = current.split(",") if current != "?" else []
    past = [d for d in offered if d in ROS_EOL and ROS_EOL[d] < today[:7]]
    if past:
        return f"EOL passed: {','.join(past)}"
    return f"all supported (today {today})"


def _resolve_python_floor(cycle: str, today: str) -> str:
    eol = eol_date("python", cycle)
    if eol is None:
        return "EOL lookup failed"
    if eol > today:
        return f"supported until {eol}"
    return f"EOL {eol} PASSED"


def _resolve_postgres(current: str) -> str:
    tags = current.split(",") if current != "?" else []
    majors = sorted({tag.split(":")[1].split("-")[0].split(".")[0] for tag in tags if ":" in tag})
    latest_pg = None
    try:
        status, body, _ = https_get(
            "hub.docker.com", "/v2/repositories/library/postgres/tags?name=18-alpine&page_size=1"
        )
        count = json.loads(body).get("count", 0) if status == 200 else 0
        latest_pg = "18" if count else None
    except RuntimeError:
        latest_pg = None
    state = "available" if latest_pg else "status unknown"
    return f"major {','.join(majors)}; postgres 18 {state}"


def resolve_upstream(pins: list[Pin], *, offline: bool) -> None:
    """Fill in upstream values for the checkable pins."""
    today = _today()
    for pin in pins:
        if not pin.checkable:
            continue
        if offline:
            pin.upstream = "?"
        else:
            pin.upstream = _resolve_one(pin, today)


def _resolve_pypi_floor(name: str, current: str) -> str | None:
    """Check a PyPI floor exists and report how far behind latest it is.

    `current` is the raw spec suffix from the template (e.g. `>=4.13,<5` or
    empty when unpinned). Returns a status string the drift detector keys
    on: `REMOVED` when the floor matches no release, else
    `floor <f> / latest <v>`.
    """
    # drop PEP 508 extras from the tracked name: mcp[cli] checks the mcp dist
    pkg = name.rsplit(" ", 1)[-1].split("[", maxsplit=1)[0]
    floor_m = re.search(r"(\d+(?:\.\d+)*)", current)
    if not floor_m:
        return "unpinned (no floor to check)"
    floor = floor_m.group(1)
    try:
        latest = pypi_latest(pkg)
    except (RuntimeError, OSError) as exc:
        return f"lookup failed ({exc}; re-run before treating this as drift)"
    # The floor is a >= constraint: it is satisfiable whenever any release
    # >= the floor exists, which for a live package means latest >= floor.
    # (An exact-version check false-positives when the floor version only
    # shipped as fuller artifacts, e.g. mcp has 2.0.1 but no literal 2.0.)
    if latest is None:
        return f"REMOVED floor {floor} matches no PyPI release"
    if _parse_version(latest) < _parse_version(floor):
        return f"REMOVED floor {floor} above latest {latest}"
    return f"floor {floor} / latest {latest}"


def _resolve_devcontainer_base(image: str) -> str:
    """Anonymous registry manifest check for the ghcr devcontainer base."""
    path, tag = image.removeprefix("ghcr.io/").rsplit(":", 1)
    headers = {"Accept": "application/vnd.oci.image.index.v1+json"}
    try:
        data = https_get_json("ghcr.io", f"/token?scope=repository:{path}:pull")
        if isinstance(data, dict) and data.get("token"):
            headers["Authorization"] = f"Bearer {data['token']}"
        status, _, _ = https_get("ghcr.io", f"/v2/{path}/manifests/{tag}", headers)
    except RuntimeError:
        return "registry unreachable"
    return "present" if status == 200 else f"MISSING (HTTP {status})"


def _resolve_one(pin: Pin, today: str) -> str | None:  # noqa: PLR0911, PLR0912, C901
    """Resolve a single pin. Dispatches on the pin name prefix."""
    name, current = pin.name, pin.current
    if name.startswith("micropython-<port>-stubs"):
        stub_version = current.split("~=")[1].split(" ")[0]
        exists = pypi_has_version("micropython-esp32-stubs", stub_version)
        return "stub release exists" if exists else "NO STUB RELEASE"
    if name.startswith("MicroPython tag"):
        return github_latest_release("micropython/micropython")
    if name.startswith("torch uv index"):
        return _resolve_torch_index(current)
    if name.startswith("ROS 2 distros"):
        return _resolve_ros(current, today)
    if name.startswith("Python floor"):
        return _resolve_python_floor(current, today)
    if name.startswith("Postgres image"):
        return _resolve_postgres(current)
    if name.startswith("CUDA Docker base"):
        return _resolve_cuda_base()
    if name.startswith("PyPI floor"):
        return _resolve_pypi_floor(name, current)
    if name.startswith("copier ceiling"):
        return pypi_latest("copier")
    if name.startswith("Devcontainer base"):
        return _resolve_devcontainer_base(current)
    if name.startswith("just version"):
        return github_latest_release("casey/just")
    if name.startswith("task version"):
        return github_latest_release("go-task/task")
    if name.startswith("gitleaks version"):
        return github_latest_release("gitleaks/gitleaks")
    if name.startswith("actionlint image digest"):
        data = https_get_json("hub.docker.com", "/v2/repositories/rhysd/actionlint/tags/latest")
        digest = data.get("digest") if isinstance(data, dict) else None
        return str(digest).removeprefix("sha256:")[:12] if digest else None
    return None


def _check_copier_ceiling_drift(pin: Pin) -> tuple[bool, str]:
    """Check whether a newer major release than the ceiling has shipped."""
    ceiling = int(pin.current.split("<")[1])
    latest_major = _parse_version(pin.upstream)[0] if pin.upstream else None
    drift = latest_major is not None and latest_major >= ceiling
    msg = (
        f"[DRIFT]  {pin.name}: ceiling <{ceiling} but latest is {pin.upstream}"
        if drift
        else f"[ok]     {pin.name}: {pin.current} (latest {pin.upstream})"
    )
    return drift, msg


def _check_exact_match_drift(pin: Pin) -> tuple[bool, str] | None:
    """Check exact equality drift against upstream."""
    by_exact_match = {
        "gitleaks version": (
            f"v{pin.current}" == pin.upstream,
            f"[ok]     {pin.name}: v{pin.current}",
            f"[DRIFT]  {pin.name}: v{pin.current} -> official latest {pin.upstream}",
        ),
        "actionlint image digest": (
            pin.current == pin.upstream,
            f"[ok]     {pin.name}: sha256:{pin.current}…",
            f"[DRIFT]  {pin.name}: image digest changed (latest tag now {pin.upstream})",
        ),
        "just version": (
            pin.current == pin.upstream,
            f"[ok]     {pin.name}: {pin.current}",
            f"[DRIFT]  {pin.name}: {pin.current} -> official latest {pin.upstream}",
        ),
        "task version": (
            f"v{pin.current}" == pin.upstream,
            f"[ok]     {pin.name}: v{pin.current}",
            f"[DRIFT]  {pin.name}: v{pin.current} -> official latest {pin.upstream}",
        ),
        "MicroPython tag": (
            pin.current == pin.upstream,
            f"[ok]     {pin.name}: {pin.current}",
            f"[DRIFT]  {pin.name}: {pin.current} -> official latest {pin.upstream}",
        ),
        "micropython-<port>-stubs": (
            pin.upstream == "stub release exists",
            f"[ok]     {pin.name}: {pin.current}",
            f"[DRIFT]  {pin.name}: {pin.current} ({pin.upstream})",
        ),
    }
    for prefix, (ok, ok_msg, drift_msg) in by_exact_match.items():
        if pin.name.startswith(prefix):
            return (False, ok_msg) if ok else (True, drift_msg)
    return None


def _check_trigger_markers_drift(pin: Pin) -> tuple[bool, str] | None:
    """Check substring markers in upstream response indicating drift."""
    triggers = {
        "torch uv index": ("frozen", "unreachable", "empty"),
        "ROS 2 distros": ("EOL passed",),
        "Python floor": ("PASSED",),
        "PyPI floor": ("REMOVED",),
        "Devcontainer base": ("MISSING",),
    }
    if pin.upstream is None:
        return None
    upstream = pin.upstream
    for prefix, markers in triggers.items():
        if pin.name.startswith(prefix):
            if any(m in upstream for m in markers):
                return True, f"[DRIFT]  {pin.name}: {pin.current} ({upstream})"
            if "lookup failed" in upstream:
                return True, f"[warn]   {pin.name}: {pin.current} ({upstream})"
            return False, f"[ok]     {pin.name}: {pin.current} ({upstream})"
    return None


def _is_drift(pin: Pin) -> tuple[bool, str]:
    """Return (drift, message) for a resolved pin."""
    if pin.upstream in (None, "?"):
        return False, f"[info]   {pin.name}: {pin.current} (upstream unknown)"
    if pin.name.startswith("copier ceiling"):
        return _check_copier_ceiling_drift(pin)
    match_result = _check_exact_match_drift(pin)
    if match_result is not None:
        return match_result
    trigger_result = _check_trigger_markers_drift(pin)
    if trigger_result is not None:
        return trigger_result
    return False, f"[info]   {pin.name}: {pin.current} ({pin.upstream})"


def report(pins: list[Pin]) -> int:
    drift = False
    warn = False
    for pin in pins:
        if not pin.checkable:
            print(f"[info]   {pin.name}: {pin.current}")
            continue
        is_drift, message = _is_drift(pin)
        print(message)
        if message.startswith("[warn]"):
            warn = True
        else:
            drift = drift or is_drift
    print()
    if drift:
        print("Template pins are behind upstream. See the [DRIFT] lines above for what to bump.")
        return 1
    if warn:
        print("Some upstream lookups failed (a throttling or outage burst). Re-run before drawing conclusions.")
        return 1
    print("Template pins are up to date.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Report pins without hitting the network",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated name prefixes to check (default: all)",
    )
    args = parser.parse_args()

    for required in (PYPROJECT_JINJA, MACROS_JINJA, GPU_DOCKERFILE, ROS2_QUESTIONS):
        if not required.exists():
            msg = f"Template file not found: {required}; run from the repo root."
            sys.exit(msg)

    pins = extract_pins()
    if args.only:
        prefixes = tuple(p.strip() for p in args.only.split(","))
        pins = [p for p in pins if p.name.startswith(prefixes)]
        if not pins:
            msg = f"No pins match --only={args.only!r}."
            sys.exit(msg)
    resolve_upstream(pins, offline=args.offline)
    sys.exit(report(pins))


if __name__ == "__main__":
    main()
