"""The command line every step script shares, so twelve copies of it cannot drift apart.

Each step is a standalone program the engine runs by path — `<slug>.py probe|apply|verify <root>`
— and its exit code is not a status but a vocabulary the engine reads: 0 and 1 and 2 and 3 each
mean something different to `/adopt`, and only 3 means the run failed. That makes the argument
handling the one part of a step that must be identical everywhere. Written out per step it was
identical everywhere by luck: twelve hand-written copies of the same sixteen lines, already
carrying three different comments and one with none, each an opportunity for the next author to
return 1 on a usage error and have a repo silently recorded "does not apply".

The exception is caught here rather than by a foot-of-file guard. A hook ends with
`except BaseException: raise SystemExit(0)` because a hook's job is never to disrupt Claude Code;
a step that did the same would be telling the engine it had found the repo in the target shape.
Here an unexpected failure prints its traceback and returns 3, which is the only code that means
the question was not answered.

`--dry-run` is stripped before the positional arguments are counted and passed separately, so a
step cannot accidentally read it as a repo path. Every `apply` takes it, including the steps that
write nothing either way — those ignore the flag and say so in their own docstring, which keeps
all twelve signatures the same shape.
"""

import os
import sys
import traceback
from collections.abc import Callable

COMMANDS = ("probe", "apply", "verify")


def run(script: str, probe: Callable[[str], int], apply: Callable[[str, bool], int],
        verify: Callable[[str], int]) -> int:
    """Dispatch one step invocation and return the code the engine reads."""
    dry_run = "--dry-run" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg != "--dry-run"]
    if len(args) != 2 or args[0] not in COMMANDS:
        print(f"usage: {os.path.basename(script)} {{probe|apply|verify}} <repo-root> [--dry-run]")
        return 3
    root = os.path.abspath(args[1])
    try:
        if args[0] == "probe":
            return probe(root)
        if args[0] == "apply":
            return apply(root, dry_run)
        return verify(root)
    except BaseException:
        traceback.print_exc()
        return 3
