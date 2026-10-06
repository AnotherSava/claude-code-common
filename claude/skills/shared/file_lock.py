"""Serialise a read-modify-write of one file across processes.

Two writers that each read a registry, change their own entry and write the whole file back lose one
of the two edits — and the loser is silent, because both writes succeed. The ports registry and the
tailnet publish registry are both written that way, from scripts the user can run concurrently in
two sessions.

`locked(path)` holds an exclusive lock on `path` for the body of a `with` block. The lock file is its
own path, never the file being protected: a lock taken on the data file would collide with the atomic
replace that writes it.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Iterator


@contextlib.contextmanager
def locked(lock_path: Path) -> Iterator[None]:
    """Hold an exclusive cross-process lock for the body of the block.

    Blocks until it is granted. `msvcrt.locking` raises on contention rather than waiting, so the
    Windows branch retries; `flock` waits by itself.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if sys.platform == "win32":
            import msvcrt  # inline: Windows-only module

            handle.seek(0)
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl  # inline: POSIX-only module

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
