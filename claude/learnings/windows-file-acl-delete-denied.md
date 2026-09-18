# A Windows file you can write but cannot delete

`git mv` answering `fatal: renaming 'x' failed: Permission denied` on a file you own the directory of, with `touch`, append and whole-file rewrite all succeeding in that same directory, is an ACL missing one entry rather than a lock, a sandbox or a git bug. Windows splits `DELETE` from `FILE_WRITE_DATA`, so a principal can hold write and not hold delete — and rename is delete plus create.

The shape, measured on a repo where five files under one directory refused to move while every other tracked file moved fine:

| operation | result |
|---|---|
| `cat file` | works |
| `echo x >> file` | works |
| `cat backup > file` | works |
| `mv file other` | `Permission denied` |
| `rm file` | `Permission denied` |
| `git checkout -- file` | `error: unable to unlink old 'file': Invalid argument` |
| `touch new && mv new new2 && rm new2` | all work, in the same directory |

That last row is what rules out a lock: a file you create yourself is fully yours while the ones already there are not.

## Read the ACL, and read one you created beside it

```
cd <the directory>
MSYS_NO_PATHCONV=1 icacls <filename>
echo probe > _cmp.md && MSYS_NO_PATHCONV=1 icacls _cmp.md && rm -f _cmp.md
```

The offending file:

```
file  BUILTIN\Administrators:(I)(F)
      NT AUTHORITY\SYSTEM:(I)(F)
      BUILTIN\Users:(I)(RX,W)
```

The probe you just made:

```
_cmp.md  MACHINE\User:(I)(F)
         NT AUTHORITY\SYSTEM:(I)(F)
         BUILTIN\Administrators:(I)(F)
         BUILTIN\Users:(I)(RX,W)
```

`BUILTIN\Users:(RX,W)` is read, execute and write — **not** modify, so it carries no `DELETE`. The only entry that would grant it is the one the directory's inherit-only `CREATOR OWNER:(OI)(CI)(IO)(F)` ACE stamps onto each new file, resolved to whoever created it. On the probe that resolved to the user; on the offending file it resolved to `BUILTIN\Administrators`, which is what an **elevated** process gets as its token owner. So the diagnosis is: those files were written by a session running elevated, and the unelevated user was left with write but not delete.

Nothing about this is visible from `ls -l`, which reports `-rw-r--r--` throughout, or from `attrib`, which reports `A`.

## Two instruments that answer the wrong thing

- **`icacls` through `cmd //c` with a quoted absolute path.** Git Bash rewrites the path and `cmd` gets a mangled argument: `The filename, directory name, or volume label syntax is incorrect`, on a file that plainly exists. Run `icacls` directly with `MSYS_NO_PATHCONV=1` and a relative filename from inside the directory.
- **`Get-Acl`.** On a constrained-language or restricted-module PowerShell it fails with *the module could not be loaded*, which reads as a missing cmdlet rather than a policy refusal. `icacls` needs no module.

Disabling the agent's command sandbox changes nothing here, which is worth trying once to rule it out: the refusal comes from the filesystem, not from the harness.

## The repair needs an elevated token

The owner is `BUILTIN\Administrators`, so `WRITE_DAC` is not held by the unelevated user and `icacls /grant` answers `Access is denied` on the directory itself. Where the user is a member of Administrators — the normal case on a personal machine — elevation alone suffices and no password is involved.

```powershell
icacls "<dir>" /setowner "<MACHINE>\<User>" /T /C
icacls "<dir>" /grant "<MACHINE>\<User>:(OI)(CI)F" /T /C
```

Drive it from a script file rather than a `-Command` string, so PowerShell's own `$` and quoting survive the shell that launches it:

```bash
dir="$(mktemp -d)"; cat > "$dir/fix.ps1" <<'PS1'
$p = '<dir>'
icacls $p /setowner "<MACHINE>\<User>" /T /C
icacls $p /grant "<MACHINE>\<User>:(OI)(CI)F" /T /C
PS1
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -WindowStyle Hidden -Wait -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','$(cygpath -w "$dir/fix.ps1")'"
```

`-Verb RunAs` raises the UAC consent dialog on the secure desktop, so it takes the foreground for a few seconds and the user has to click — ask immediately before running it. `-WindowStyle Hidden` keeps a console from flashing, and `-Wait` is what lets the caller verify afterwards rather than racing the elevation.

`(OI)(CI)` is object-inherit plus container-inherit, so files and directories created under that tree afterwards carry the grant. Verify by creating one and reading its ACL back — the user's `(I)(F)` entry appearing is the proof, and a `/grant` that silently reached nothing looks identical without it.

**The repair covers one subtree, and the condition is not confined to one.** Everything above the repaired directory still resolves `CREATOR OWNER` per created object, so an elevated session creating a *new* directory anywhere — `.claude/` is the one that has done it — hands that directory and everything under it to `BUILTIN\Administrators` again. Nothing reports it until some later rename or delete fails, and by then the error names git rather than the token that wrote the files.

## Finding the whole blast radius

The condition is per-file, so check every tracked path rather than the one that failed:

```bash
git ls-files > /tmp/tracked.txt
while IFS= read -r f; do
  MSYS_NO_PATHCONV=1 icacls "$f" </dev/null 2>/dev/null | grep -qF '<MACHINE>\<User>' || echo "$f"
done < /tmp/tracked.txt
```

The `</dev/null` matters: `icacls` reads standard input, and without it the first call swallows the rest of the loop's input and the sweep reports every remaining file as affected.
