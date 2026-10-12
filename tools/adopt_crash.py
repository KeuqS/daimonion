"""Crash points and signals: the drill hooks and the rollback handler.

SIGINT/SIGTERM mid-run are turned into the ordinary rollback; SIGKILL and
power loss cannot be caught at all, which is what the journal
(`tools.adopt_journal`) is for. `COPIER_ADOPT_CRASH_AT` kills the process
at a named point so the drills (and a manual crash rehearsal) exercise the
recovery path for real. In-repo callers go through `fire_crash_hook` --
never `_crash_at` directly -- so a test fake installed at
`tools.adopt._crash_at` fires wherever the real hook would.

This is a drivers-layer module by the tests/test_tool_layers.py table: it
watches the real target tree for writes.
"""

from __future__ import annotations

import contextlib
import os
import signal
import sys
import threading
from collections.abc import Generator
from pathlib import Path
from types import FrameType
from typing import Any

TOP = Path(__file__).resolve().parent.parent
if str(TOP) not in sys.path:
    sys.path.insert(0, str(TOP))

from tools.adopt_models import CRASH_POINT_ENV  # noqa: E402


def fire_crash_hook(point: str) -> None:
    """Invoke the installed crash hook, resolved off the facade at call time.

    Tests replace `tools.adopt._crash_at` with a raising fake; every
    in-repo caller goes through here so the fake fires wherever the real
    hook would, including inside the rollback, the recovery, and the
    write-counting audit hook.
    """
    from tools import adopt  # noqa: PLC0415 -- top-level would be circular; at call time the facade is loaded

    adopt._crash_at(point)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


# --- crash points and signals ------------------------------------------------
#
# SIGINT/SIGTERM are turned into the ordinary rollback; SIGKILL and power loss
# cannot be caught at all, which is what the journal above is for.


class _Interrupted(BaseException):
    """A signal arrived inside the transaction: roll back like any other failure.

    A `BaseException` on purpose: the exception handlers of the render and the
    merge step must not swallow it -- and it is not an error the caller can do
    anything about, it is the caller asking for the run to stop.
    """


@contextlib.contextmanager
def _signals_roll_back() -> Generator[None]:
    """Make SIGINT/SIGTERM mid-run a rollback instead of a half-written tree.

    The handler raises once; a second signal while the restore runs is ignored,
    because the point of the first one was to get the project back. Signals can
    only be taken on the main thread, so a threaded caller (the MCP tool) is
    left with the journal path alone.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    interrupted = False

    def handler(signum: int, _frame: FrameType | None) -> None:
        nonlocal interrupted
        if interrupted:
            return
        interrupted = True
        msg = f"interrupted by {signal.Signals(signum).name}"
        raise _Interrupted(msg)

    previous = {number: signal.signal(number, handler) for number in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for number, original in previous.items():
            signal.signal(number, original)


def _crash_at(point: str) -> None:
    """Kill this process at `point` when COPIER_ADOPT_CRASH_AT asks for it.

    Exists for tests/test_adopt.py and for a manual crash drill:
    `COPIER_ADOPT_CRASH_AT=render:3` dies (SIGKILL -- uncatchable, so the run
    really cannot clean up after itself) once the render has written three
    files into the target, `merge:1` after the first merge write, and `verify`
    before the run checks what it did. The undo is drillable too, the way the
    protocol model crashes in every state: `rollback` dies inside a failing
    run's rollback, after its first real write or deletion, and `recover`
    dies inside `--recover`, at the first old bytes written back or created
    file removed -- both leave the journal in place, which is what the next
    `--recover` finishes from. Any other value, and the variable being unset,
    is a no-op: no production path is affected.
    """
    if os.environ.get(CRASH_POINT_ENV) == point:
        os.kill(os.getpid(), signal.SIGKILL)


def _crash_writes(phase: str) -> int | None:
    """How many writes COPIER_ADOPT_CRASH_AT asks `phase` to die after."""
    name, _, count = os.environ.get(CRASH_POINT_ENV, "").partition(":")
    if name != phase or not count.isdigit() or int(count) < 1:
        return None
    return int(count)


def _is_write(mode: object, flags: object) -> bool:
    """Whether an `open` audit event is a write (the drill counts only those)."""
    if isinstance(mode, str):
        return any(character in mode for character in "wax+")
    return isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND))


def _under(root: Path, path: str) -> bool:
    """Whether a write landed inside `root` (resolved: a tmp dir may be a symlink)."""
    try:
        return Path(path).resolve().is_relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False


@contextlib.contextmanager
def _crash_on_write(phase: str, target: Path) -> Generator[None]:
    """Count the writes into `target` and kill the process at the requested one.

    The count comes from the `open` audit event, so it is what really landed on
    disk rather than a prediction -- and it kills on the write *after* the
    requested one, because that event is raised before the file is opened: by
    the time the next file is opened, the counted one is closed and complete.
    `render:1` is therefore the instant after the first file was written, which
    is exactly the crash point a journal has to cover.
    """
    wanted = _crash_writes(phase)
    if wanted is None:
        yield
        return
    root = Path(target).resolve()
    point = f"{phase}:{wanted}"
    written: set[str] = set()
    active = [True]

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if not active[0] or event != "open":
            return
        path, mode, flags = args
        if not isinstance(path, str) or not _is_write(mode, flags) or not _under(root, path):
            return
        written.add(path)
        if len(written) > wanted:
            fire_crash_hook(point)

    sys.addaudithook(hook)
    try:
        yield
    finally:
        active[0] = False
