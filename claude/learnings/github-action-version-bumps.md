# Bumping GitHub Action majors safely

Runner deprecation notices ("The following actions target Node.js 20 but are being forced to run on
Node.js 24") are the usual prompt. The actions are pinned by major (`actions/checkout@v4`), so the
fix is a major bump — which is exactly the change that can break a workflow silently. Four checks
make it a decision instead of a gamble, and all four are one command each.

## 1. What is the current major?

Do not guess from memory; these move fast, and several actions are further along than you expect.

```bash
for a in actions/checkout actions/setup-dotnet actions/upload-artifact actions/download-artifact; do
  printf '%-32s %s\n' "$a" "$(gh api "repos/$a/releases/latest" --jq .tag_name)"
done
```

Measured 2026-08-31: checkout `v7.0.1`, setup-dotnet `v6.0.0`, upload-artifact `v7.0.1`,
download-artifact `v8.0.1` — while a typical workflow still says `@v4` for all four. The artifact
pair being on *different* majors is normal and not a mismatch.

## 2. Read only the `vN.0.0` notes

Every intermediate release is noise; breaking changes are announced in major releases.

```bash
gh api "repos/$a/releases?per_page=60" --jq '.[].tag_name' | grep -E '^v[0-9]+\.0\.0$'
gh api "repos/$a/releases/tags/v7.0.0" --jq .body
```

Judge each against **how you actually use the action**, not in the abstract. Real examples:

- `download-artifact@v5` — "🚨 Breaking Change … if you're downloading single artifacts **by ID**".
  A workflow using `name:` is untouched. The scary heading does not apply.
- `upload-artifact@v7` — adds `archive: false` for unzipped single-file uploads. Opt-in, so the
  default glob-to-one-zip behaviour is unchanged.
- Several majors are "BREAKING CHANGE: this update supports Node v24.x … we're treating it as such"
  — a runtime bump labelled breaking out of caution, not an API change.

## 3. Verify the runtime and every input at the target ref

This is the check that actually proves the bump: fetch `action.yml` at the tag and confirm the
runtime moved *and* that each input you pass still exists. An input silently dropped across a major
is not a build failure — Actions ignores unknown inputs, so the step runs with a default.

```bash
check() { y=$(curl -sfL "https://raw.githubusercontent.com/$1/$2/action.yml")
  printf '%-34s runs=%s  ' "$1@$2" "$(echo "$y" | grep -oE 'node[0-9]+' | head -1)"
  for i in $3; do echo "$y" | grep -qE "^  $i:" && printf '%s=ok ' "$i" || printf '%s=MISSING ' "$i"; done; echo; }

check actions/upload-artifact v7.0.1 "name path"
# actions/upload-artifact@v7.0.1   runs=node24  inputs: name=ok path=ok
```

`runs=node24` is the confirmation that the deprecation is actually cleared — the whole point of the
bump. Pin the workflow to the major (`@v7`), not the patch, matching the convention already there.

## 4. Know which steps your test run will not execute

The trap. A release workflow gates its packaging steps on the ref:

```yaml
      - name: Upload artifacts
        if: startsWith(github.ref, 'refs/tags/v')
        uses: actions/upload-artifact@v7
```

So pushing the bump to `main` runs `checkout` and `setup-dotnet` and **skips** the artifact actions
entirely — a green tick that proves nothing about the two riskiest lines in the diff. The
`upload-artifact` → `download-artifact` handoff then executes for the first time during an actual
release, which is the worst possible moment to discover a mismatch.

Check what was skipped rather than trusting the tick:

```bash
gh api "repos/OWNER/REPO/actions/runs/$rid/jobs" \
  --jq '.jobs[] | .name + ": " + ((.steps | map(select(.conclusion=="skipped")) | length) | tostring) + " skipped"'
```

Say so explicitly when reporting the bump as done. If it matters, add a `workflow_dispatch` trigger,
or push a throwaway prerelease tag (`v0.0.1-ci`, deleted after) to exercise the full path — but note
that publishes a real release unless the workflow marks hyphenated tags `--prerelease`.
