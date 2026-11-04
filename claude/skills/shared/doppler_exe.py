"""The doppler executable the skills' Python scripts spawn.

Resolved through PATHEXT with shutil.which: a bare "doppler" handed to subprocess on Windows finds only a
.exe, so a .cmd shim earlier on PATH would be passed over for whichever doppler.exe comes later.
"""

import shutil
import sys


def doppler(failure: str) -> str:
    """The doppler path, or exit with `failure` naming what could not be done without it."""
    path = shutil.which("doppler")
    if not path:
        sys.exit(f"{failure}: doppler is not on PATH")
    return path
