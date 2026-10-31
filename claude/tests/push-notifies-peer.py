#!/usr/bin/env python3
"""Every skill authorized to push asks the other machine to pull.

These repos are cloned on two machines, so a push leaves the other clone behind. Nothing over there
measures that: its session-start hooks do not fetch, and the first sign is work rebuilt that already
exists upstream, or its own push rejected. The counterweight is one message sent after each push,
which the pushing skill has to remember to send.

Which skills may push is not a property of the skills — it is the clear condition on the `Push to
GitHub` rule in `claude/settings.json`'s `autoMode.soft_deny`, and a skill absent from it is refused
on any push the user did not ask for in their own words. So that list is where a new pushing skill
enters, and this check reads the list rather than hunting for `git push` commands: a skill that
pushes without being named there is stopped by the permission gate, while one added to the list with
no notice wired is stopped by nothing at all.

Measured, 2026-10-01: `/release` pushed `chore: bump version to 1.15.0` to `tauri-dashboard`'s main
having never sent the message, which only `/commit` did. The Windows clone sat behind with nothing
reporting it, and the gap surfaced because the user asked.

What is asserted, both ways:

  list -> skill          every skill the clear condition names calls notify_peer_pull.py, unless
                         EXEMPT gives a reason it cannot
  skill -> list          every skill that calls it is named there, since a notice wired into a
                         skill the gate refuses to let push is a contradiction
  exemptions             each one names a real skill and is still needed — an exempt skill that
                         has since gained the call fails, so the list cannot rot into prose
  the script             the path every caller spells actually exists
  the push step          a skill pushing through shared/push.py counts as notifying and reporting the
                         bookmark, and push.py itself must call the notifier and `review_scope.py status`
  bookmark state         every skill the clear condition names, exempt or not, either pushes through
                         shared/push.py or closes its report as
                         shared/review-bookmark-status.md describes, and that file runs
                         `review_scope.py status`, since a push is where the review bookmark is
                         published or fails to be, and a failure line printed mid-report is missed

A clear condition this file cannot parse stops the run rather than reporting a pass. A check that
reads nothing and prints success is the failure it exists to prevent.

Usage:  python claude/tests/push-notifies-peer.py
Exit:   0 every authorized skill notifies, 1 one does not or the rule could not be read
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SETTINGS = os.path.join(REPO, "claude", "settings.json")
SKILLS = os.path.join(REPO, "claude", "skills")
NOTIFIER = os.path.join(SKILLS, "shared", "notify_peer_pull.py")

CALL = "notify_peer_pull.py"
# The command a step runs, not the basename: the `peer` skill names the script in prose while routing
# work, and a skill's own allowed-tools line grants the command without any step calling it. Matching
# either would count a document that mentions the notice as one that sends it.
INVOCATION = "python ~/.claude/skills/shared/notify_peer_pull.py"
STATUS = "python ~/.claude/scripts/review_scope.py status"
# One file holds the closing step so its wording cannot drift between the skills that push; each skill
# points at it, and the file itself is what has to run STATUS.
STATUS_STEP = "~/.claude/skills/shared/review-bookmark-status.md"
STATUS_FILE = os.path.join(SKILLS, "shared", "review-bookmark-status.md")
# The shared push step does both after-push duties itself, so a skill that pushes through it notifies and reports the
# bookmark without spelling either; the script is then what has to carry both calls.
PUSH_STEP = "~/.claude/skills/shared/push.py --caller"
PUSH_SCRIPT = os.path.join(SKILLS, "shared", "push.py")
RULE_MARKER = "Push to GitHub"
CLAUSE_MARKER = "a user turn invoking"
SKILL_RE = re.compile(r"`/([a-z0-9-]+)`")

# A skill the clear condition authorizes that cannot send the notice, with what makes it exempt.
# Keyed by skill name; the value is read out in the failure text, so write it as a reason.
EXEMPT = {
    "pr-create": "it pushes a feature branch rather than the tracked branch, and /pull fast-forwards "
                 "the branch the peer is on — there is nothing there for it to restore",
}

FAILURES: list[str] = []


class Unreadable(Exception):
    """An input this file will not guess at."""


def fail(message: str) -> None:
    FAILURES.append(message)


def authorized_skills() -> list[str]:
    """The skill names the push rule's clear condition accepts, in the order it lists them."""
    with open(SETTINGS, encoding="utf-8") as handle:
        settings = json.load(handle)
    rules = settings.get("autoMode", {}).get("soft_deny", [])
    matching = [rule for rule in rules if isinstance(rule, str) and RULE_MARKER in rule]
    if len(matching) != 1:
        raise Unreadable(f"autoMode.soft_deny holds {len(matching)} rule(s) mentioning {RULE_MARKER!r}, "
                         "so which one gates a push is unclear")
    rule = matching[0]
    start = rule.find(CLAUSE_MARKER)
    if start < 0:
        raise Unreadable(f"the {RULE_MARKER!r} rule has no {CLAUSE_MARKER!r} clause, so the skills it "
                         "clears for cannot be read")
    end = rule.find(")", start)
    if end < 0:
        raise Unreadable(f"the {CLAUSE_MARKER!r} clause is never closed, so where the list of skills ends "
                         "cannot be read")
    names = SKILL_RE.findall(rule[start:end])
    if not names:
        raise Unreadable(f"the {CLAUSE_MARKER!r} clause names no skill, which cannot be right")
    return names


def skill_body(name: str) -> str:
    """A SKILL.md with its frontmatter removed, so an allowed-tools grant is not read as a step."""
    with open(os.path.join(SKILLS, name, "SKILL.md"), encoding="utf-8") as handle:
        text = handle.read()
    if text.startswith("---\n"):
        closing = text.find("\n---", 3)
        if closing < 0:
            raise Unreadable(f"claude/skills/{name}/SKILL.md opens frontmatter it never closes")
        return text[closing:]
    return text


def callers() -> set[str]:
    """Every skill whose SKILL.md runs the notifier in one of its steps."""
    found = set()
    for name in sorted(os.listdir(SKILLS)):
        if not os.path.isfile(os.path.join(SKILLS, name, "SKILL.md")):
            continue
        body = skill_body(name)
        if INVOCATION in body or PUSH_STEP in body:
            found.add(name)
    return found


def main() -> int:
    try:
        authorized = authorized_skills()
        calling = callers()
    except (Unreadable, OSError, UnicodeDecodeError, ValueError) as exc:
        # Not a failure count: nothing was compared, and a run that could not read its inputs must
        # not report the same "every push site notifies" a clean run does.
        print(f"push notifies peer: NOT CHECKED — {exc}")
        return 1

    if not os.path.isfile(NOTIFIER):
        fail(f"every caller spells {CALL}, and claude/skills/shared/{CALL} does not exist")

    try:
        with open(STATUS_FILE, encoding="utf-8") as handle:
            if STATUS not in handle.read():
                fail(f"{STATUS_STEP} never runs `{STATUS}`, so no pushing skill's report says whether the review "
                     "bookmark moved")
    except OSError:
        fail(f"every pushing skill points at {STATUS_STEP}, and it does not exist")

    try:
        with open(PUSH_SCRIPT, encoding="utf-8") as handle:
            script = handle.read()
        if CALL not in script or 'REVIEW_SCOPE, "status"' not in script:
            fail(f"shared/push.py no longer calls {CALL} and `review_scope.py status`, so every skill pushing through it "
                 "skips one of the duties this check exists for")
    except OSError:
        fail("skills push through shared/push.py, and it does not exist")

    for name in authorized:
        try:
            body = skill_body(name)
        except OSError:
            fail(f"the push rule clears for /{name}, and claude/skills/{name}/SKILL.md does not exist")
            continue
        except Unreadable as exc:
            fail(str(exc))
            continue
        notifies = INVOCATION in body or PUSH_STEP in body
        if STATUS_STEP not in body and PUSH_STEP not in body:
            fail(f"the push rule clears /{name} to push, and its SKILL.md never points at {STATUS_STEP}, so its "
                 "report never says whether the review bookmark moved")
        if name in EXEMPT:
            if notifies:
                fail(f"/{name} is exempt because {EXEMPT[name]} — and its SKILL.md now calls {CALL}, "
                     "so remove the exemption")
        elif not notifies:
            fail(f"the push rule clears /{name} to push, and its SKILL.md never calls {CALL}, so a push "
                 "from it leaves the other machine's clone behind with nothing saying so")

    for name in sorted(calling - set(authorized)):
        fail(f"/{name} calls {CALL}, and the push rule does not clear it to push — either add it to the "
             "clear condition or drop the call")

    for name in sorted(set(EXEMPT) - set(authorized)):
        fail(f"/{name} is listed as exempt, and the push rule does not clear it to push, so the "
             "exemption covers nothing")

    if FAILURES:
        print(f"push notifies peer: {len(FAILURES)} push site(s) out of step with {CALL}\n")
        for failure in FAILURES:
            print(f"  {failure}")
        print()
        return 1
    print(f"push notifies peer: {len(authorized)} authorized skill(s), {len(EXEMPT)} exempt — "
          f"every other one calls {CALL}, and all of them report the bookmark")
    return 0


if __name__ == "__main__":
    sys.exit(main())
