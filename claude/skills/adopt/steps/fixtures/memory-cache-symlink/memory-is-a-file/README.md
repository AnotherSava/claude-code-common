# Fixture repo

A repo where .claude/memory is a file rather than a directory. Pointing the machine cache at
a file would make every memory write fail, so apply refuses and moves nothing.
