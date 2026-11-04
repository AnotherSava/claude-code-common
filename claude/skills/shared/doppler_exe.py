"""The doppler executable the skills' Python scripts spawn.

Resolved through PATHEXT with shutil.which: a bare "doppler" handed to subprocess on Windows finds only a
.exe, so a .cmd shim earlier on PATH would be passed over for whichever doppler.exe comes later.
"""

import shutil
import sys


def doppler(failure: str, code: int = 1) -> str:
    """The doppler path, or exit with `code` after printing `failure`, which names what could not be done without it."""
    path = shutil.which("doppler")
    if not path:
        sys.stderr.write(f"{failure}: doppler is not on PATH\n")
        sys.exit(code)
    return path
